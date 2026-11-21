from app.database.db import SessionLocal
from app.models import Ticket, TicketMessage, TriageRun

STATUS_BY_ROUTE = {"spam": "spam", "auto_send": "replied", "human_review": "awaiting_review"}


def thread_config(ticket_id: int) -> dict:
    # One ticket = one graph thread, so a paused ticket can be resumed later by its id.
    return {"configurable": {"thread_id": str(ticket_id)}}


async def run_triage(graph, ticket_id: int, subject: str, body: str) -> None:
    """Runs the graph for a new ticket and saves what it produced. Meant to run in the background."""
    # No session is open during the graph run: LLM calls take seconds, and an open
    # session would hold a pooled database connection the whole time.
    state = await graph.ainvoke(
        {"ticket_id": ticket_id, "subject": subject, "body": body}, thread_config(ticket_id)
    )

    async with SessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.category = state["category"]
        ticket.priority = state["priority"]
        ticket.sentiment = state["sentiment"]
        ticket.status = STATUS_BY_ROUTE[state["route"]]

        # .get() for the draft fields: a spam ticket stops after classify and never sets them.
        session.add(TriageRun(
            ticket_id=ticket_id,
            classification_confidence=state["classification_confidence"],
            draft_reply=state.get("draft_reply"),
            draft_confidence=state.get("draft_confidence"),
            best_kb_score=state.get("best_kb_score"),
            kb_article_ids=[article["id"] for article in state.get("kb_articles", [])],
            attempts=state.get("attempts", 0),
            route=state["route"],
            route_reasons=state.get("route_reasons", []),
        ))

        if state["route"] == "auto_send":
            session.add(TicketMessage(ticket_id=ticket_id, sender_type="ai", body=state["final_reply"]))

        await session.commit()
