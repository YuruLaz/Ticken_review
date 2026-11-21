import logging

from app.database.db import SessionLocal
from app.models import Ticket, TicketMessage, TriageRun

logger = logging.getLogger(__name__)

STATUS_BY_ROUTE = {"spam": "spam", "auto_send": "replied", "human_review": "awaiting_review"}


def thread_config(ticket_id: int) -> dict:
    # One ticket = one graph thread, so a paused ticket can be resumed later by its id.
    return {"configurable": {"thread_id": str(ticket_id)}}


async def run_triage(graph, ticket_id: int, graph_input: dict | None) -> None:
    """Runs the graph for a ticket and saves what it produced. Meant to run in the background.

    graph_input is the new ticket's subject/body, or None to continue a failed run from its
    last checkpoint, so steps that already succeeded (and their LLM calls) aren't repeated.
    """
    # No session is open during the graph run: LLM calls take seconds, and an open
    # session would hold a pooled database connection the whole time.
    try:
        state = await graph.ainvoke(graph_input, thread_config(ticket_id))
    except Exception:
        # Any failure (Gemini error, rate limit, timeout): nobody sees a background task's
        # exception, so log it and mark the ticket so an agent can find and re-run it.
        logger.exception("Triage failed for ticket %s", ticket_id)
        async with SessionLocal() as session:
            ticket = await session.get(Ticket, ticket_id)
            ticket.status = "failed"
            await session.commit()
        return

    async with SessionLocal() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.category = state["category"]
        ticket.priority = state["priority"]
        ticket.sentiment = state["sentiment"]
        ticket.language = state["language"]
        ticket.ai_summary = state["summary"][:200]  # the column's limit; the LLM may overshoot
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
