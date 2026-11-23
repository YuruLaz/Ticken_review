import logging
import uuid

from sqlalchemy import update

from app.core.config import settings
from app.database.db import SessionLocal
from app.models import Ticket, TicketMessage, TriageRun

logger = logging.getLogger(__name__)

STATUS_BY_ROUTE = {"spam": "spam", "auto_send": "replied", "human_review": "awaiting_review"}


def graph_config(
    ticket_id: int, run_name: str, category: str | None = None, run_id: uuid.UUID | None = None
) -> dict:
    metadata = {"ticket_id": ticket_id, "environment": settings.environment}
    if category:
        metadata["category"] = category
    config = {
        "configurable": {"thread_id": str(ticket_id)},
        "run_name": run_name,
        "tags": [run_name, settings.environment],
        "metadata": metadata,
    }
    if run_id:
        config["run_id"] = run_id
    return config


def ticket_input(ticket: Ticket) -> dict:
    """The graph's starting state for a ticket."""
    return {"ticket_id": ticket.id, "subject": ticket.subject, "body": ticket.body}


async def fail_interrupted_runs() -> int:
    """At startup nothing is running, so any "new" ticket lost its run; make it re-runnable."""
    async with SessionLocal() as session:
        result = await session.execute(update(Ticket).where(Ticket.status == "new").values(status="failed"))
        await session.commit()
    return result.rowcount


async def run_triage(graph, ticket_id: int, graph_input: dict | None) -> None:
    """Runs the graph for a ticket and saves what it produced. Meant to run in the background.

    graph_input is the new ticket's subject/body, or None to continue a failed run from its
    last checkpoint, so steps that already succeeded (and their LLM calls) aren't repeated.
    """
    try:
        run_id = uuid.uuid4()
        state = await graph.ainvoke(graph_input, graph_config(ticket_id, "triage", run_id=run_id))
    except Exception:
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
        ticket.ai_summary = state["summary"][:200]
        ticket.status = STATUS_BY_ROUTE[state["route"]]

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
            langsmith_run_id=run_id,
        ))

        if state["route"] == "auto_send":
            session.add(TicketMessage(ticket_id=ticket_id, sender_type="ai", body=state["final_reply"]))

        await session.commit()
