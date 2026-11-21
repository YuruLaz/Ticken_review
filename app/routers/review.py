from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from langgraph.types import Command
from sqlalchemy import case, select

from app.ai.triage import graph_config, run_triage
from app.core.dependencies import SessionDep, require_role
from app.models import KBArticle, Ticket, TicketMessage, TriageRun, User
from app.routers.tickets import get_visible_ticket
from app.schemas.review import Decision, ReviewDetail
from app.schemas.ticket import AgentTicketDetail, AgentTicketRead

router = APIRouter(prefix="/review", tags=["review"])

Agent = Annotated[User, Depends(require_role("agent", "admin"))]

# Sorting by the priority text would put "high" before "urgent"; this maps it to a rank.
PRIORITY_RANK = case(
    {"urgent": 0, "high": 1, "medium": 2, "low": 3}, value=Ticket.priority, else_=4
)


async def latest_run(session, ticket_id: int) -> TriageRun:
    return await session.scalar(
        select(TriageRun)
        .where(TriageRun.ticket_id == ticket_id)
        .order_by(TriageRun.id.desc())
        .limit(1)
    )


@router.get("/queue", response_model=list[AgentTicketRead])
async def review_queue(user: Agent, session: SessionDep):
    query = (
        select(Ticket)
        .where(Ticket.status == "awaiting_review")
        .order_by(PRIORITY_RANK, Ticket.created_at)
    )
    return await session.scalars(query)


@router.get("/{ticket_id}", response_model=ReviewDetail)
async def review_detail(ticket_id: int, user: Agent, session: SessionDep):
    ticket = await get_visible_ticket(session, ticket_id, user)
    run = await latest_run(session, ticket_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket has not been triaged yet"
        )
    articles = await session.scalars(
        select(KBArticle).where(KBArticle.id.in_(run.kb_article_ids))
    )
    return {"ticket": ticket, "run": run, "kb_articles": articles.all()}


@router.post("/{ticket_id}/decision", response_model=AgentTicketDetail)
async def decide(
    ticket_id: int, decision: Decision, user: Agent, session: SessionDep, request: Request
):
    # Row lock until commit: if two agents decide at once, the second waits here, then
    # sees the first one's new status below and gets a 409 instead of resuming twice.
    await session.execute(select(Ticket.id).where(Ticket.id == ticket_id).with_for_update())
    ticket = await get_visible_ticket(session, ticket_id, user)
    # Also what stops a second decision: after the first, the status is replied or escalated.
    if ticket.status != "awaiting_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ticket is not awaiting review"
        )
    if decision.action == "edit" and not decision.edited_reply:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="edited_reply is required for edit",
        )

    # Continues the paused graph: human_review runs again and interrupt() returns this dict.
    resume = {"action": decision.action, "reply": decision.edited_reply}
    config = graph_config(ticket_id, "review_decision", ticket.category)
    state = await request.app.state.graph.ainvoke(Command(resume=resume), config)

    run = await latest_run(session, ticket_id)
    run.human_decision = decision.action
    run.review_note = decision.note
    if state["final_reply"]:
        # Appended to the relationship, so the returned ticket already includes it.
        ticket.messages.append(
            TicketMessage(sender_type="agent", author_id=user.id, body=state["final_reply"])
        )
        ticket.status = "replied"
    else:
        # Rejected draft: nothing is sent, a human has to handle the ticket.
        ticket.status = "escalated"
    await session.commit()
    return ticket


@router.post("/{ticket_id}/retriage", response_model=AgentTicketRead, status_code=status.HTTP_202_ACCEPTED)
async def retriage(
    ticket_id: int,
    user: Agent,
    session: SessionDep,
    request: Request,
    background_tasks: BackgroundTasks,
):
    # Same row lock as in decide: two clicks at once can't both see "failed".
    await session.execute(select(Ticket.id).where(Ticket.id == ticket_id).with_for_update())
    ticket = await get_visible_ticket(session, ticket_id, user)
    if ticket.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Only failed tickets can be re-run"
        )
    # Back to "new" right away, so a second click gets a 409 instead of starting a second run.
    ticket.status = "new"
    await session.commit()
    # None: continue the failed run from its last checkpoint instead of starting over.
    background_tasks.add_task(run_triage, request.app.state.graph, ticket_id, None)
    return ticket
