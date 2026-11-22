from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.ai.triage import run_triage, ticket_input
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

# Limits LLM cost per customer.
MAX_TICKETS_PER_HOUR = 10


async def get_visible_ticket(session: SessionDep, ticket_id: int, user: User) -> Ticket:
    # Eager-load messages; async lazy loads fail.
    ticket = await session.scalar(
        select(Ticket)
        .options(selectinload(Ticket.messages))
        .where(Ticket.id == ticket_id)
    )
    # 404 not 403: hides which IDs exist.
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
    # DB count: survives restarts, uses DB clock.
    recent = await session.scalar(
        select(func.count())
        .where(Ticket.customer_id == user.id)
        .where(Ticket.created_at > func.now() - timedelta(hours=1))
    )
    if recent >= MAX_TICKETS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests in the last hour. Please try again later.",
        )
    ticket = Ticket(customer_id=user.id, subject=data.subject, body=data.body)
    session.add(ticket)
    await session.commit()
    # Runs after response; customer doesn't wait.
    background_tasks.add_task(run_triage, request.app.state.graph, ticket.id, ticket_input(ticket))
    return ticket


def visible_tickets(user: User):
    """Base query for the tickets this user may see: customers only their own."""
    query = select(Ticket)
    if user.role == "customer":
        query = query.where(Ticket.customer_id == user.id)
    return query


# Schema chosen per role; union serializes either.
@router.get("", response_model=list[AgentTicketRead] | list[TicketRead])
async def list_tickets(
    user: CurrentUser,
    session: SessionDep,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    sentiment: str | None = None,
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    query = visible_tickets(user)
    if status:
        query = query.where(Ticket.status == status)
    if category:
        query = query.where(Ticket.category == category)
    # Hidden fields aren't filterable for customers.
    if user.role != "customer":
        if priority:
            query = query.where(Ticket.priority == priority)
        if sentiment:
            query = query.where(Ticket.sentiment == sentiment)
    if search:
        query = query.where(or_(Ticket.subject.ilike(f"%{search}%"), Ticket.body.ilike(f"%{search}%")))
    query = query.order_by(Ticket.created_at.desc()).offset((page - 1) * size).limit(size)

    schema = TicketRead if user.role == "customer" else AgentTicketRead
    return [schema.model_validate(ticket) for ticket in await session.scalars(query)]


# Before /{ticket_id}, or "counts" matches it.
@router.get("/counts")
async def ticket_counts(user: CurrentUser, session: SessionDep) -> dict[str, int]:
    """Number of visible tickets per status, for the inbox's views."""
    tickets = visible_tickets(user).subquery()
    rows = await session.execute(
        select(tickets.c.status, func.count()).group_by(tickets.c.status)
    )
    return dict(rows.all())


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
        # Follow-up on answered ticket needs a person.
        if ticket.status == "replied":
            ticket.status = "escalated"
    else:
        # Paused graph: use the decision endpoint.
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
