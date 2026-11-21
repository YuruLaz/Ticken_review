from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.triage import run_triage
from app.core.dependencies import CurrentUser, SessionDep, require_role
from app.models import Ticket, TicketMessage, User
from app.schemas.ticket import (
    AgentTicketDetail,
    AgentTicketRead,
    MessageCreate,
    MessageRead,
    TicketCreate,
    TicketDetail,
    TicketRead,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])

Customer = Annotated[User, Depends(require_role("customer"))]


async def get_visible_ticket(session: SessionDep, ticket_id: int, user: User) -> Ticket:
    # Messages are loaded up front: in async code a lazy load on ticket.messages fails.
    ticket = await session.scalar(
        select(Ticket)
        .options(selectinload(Ticket.messages))
        .where(Ticket.id == ticket_id)
    )
    # 404 rather than 403 for someone else's ticket, so customers can't probe which ids exist.
    if ticket is None or (user.role == "customer" and ticket.customer_id != user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found"
        )
    return ticket


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    data: TicketCreate,
    user: Customer,
    session: SessionDep,
    request: Request,
    background_tasks: BackgroundTasks,
):
    ticket = Ticket(customer_id=user.id, subject=data.subject, body=data.body)
    session.add(ticket)
    await session.commit()
    # Runs after the response is sent: the customer gets their ticket id now, not after the LLM calls.
    graph_input = {"ticket_id": ticket.id, "subject": ticket.subject, "body": ticket.body}
    background_tasks.add_task(run_triage, request.app.state.graph, ticket.id, graph_input)
    return ticket


# Both roles share these routes, so the schema is picked per request; the union in
# response_model lets FastAPI serialize whichever one was returned.
@router.get("", response_model=list[AgentTicketRead] | list[TicketRead])
async def list_tickets(user: CurrentUser, session: SessionDep):
    query = select(Ticket).order_by(Ticket.created_at.desc())
    if user.role == "customer":
        query = query.where(Ticket.customer_id == user.id)
    schema = TicketRead if user.role == "customer" else AgentTicketRead
    return [schema.model_validate(ticket) for ticket in await session.scalars(query)]


@router.get("/{ticket_id}", response_model=AgentTicketDetail | TicketDetail)
async def get_ticket(ticket_id: int, user: CurrentUser, session: SessionDep):
    ticket = await get_visible_ticket(session, ticket_id, user)
    schema = TicketDetail if user.role == "customer" else AgentTicketDetail
    return schema.model_validate(ticket)


@router.post(
    "/{ticket_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(
    ticket_id: int, data: MessageCreate, user: CurrentUser, session: SessionDep
):
    ticket = await get_visible_ticket(session, ticket_id, user)
    if user.role == "customer":
        sender_type = "customer"
    else:
        # The graph is paused on this ticket; replying here would leave it paused forever.
        if ticket.status == "awaiting_review":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ticket is awaiting review: use POST /review/{id}/decision",
            )
        sender_type = "agent"
        ticket.status = "replied"
    message = TicketMessage(
        ticket_id=ticket.id, sender_type=sender_type, author_id=user.id, body=data.body
    )
    session.add(message)
    await session.commit()
    return message
