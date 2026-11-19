from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentUser, SessionDep, require_role
from app.models import Ticket, TicketMessage, User
from app.schemas.ticket import MessageCreate, MessageRead, TicketCreate, TicketDetail, TicketRead

router = APIRouter(prefix="/tickets", tags=["tickets"])

Customer = Annotated[User, Depends(require_role("customer"))]


async def get_visible_ticket(session: SessionDep, ticket_id: int, user: User) -> Ticket:
    # Messages are loaded up front: in async code a lazy load on ticket.messages fails.
    ticket = await session.scalar(
        select(Ticket).options(selectinload(Ticket.messages)).where(Ticket.id == ticket_id)
    )
    # 404 rather than 403 for someone else's ticket, so customers can't probe which ids exist.
    if ticket is None or (user.role == "customer" and ticket.customer_id != user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(data: TicketCreate, user: Customer, session: SessionDep):
    ticket = Ticket(customer_id=user.id, subject=data.subject, body=data.body)
    session.add(ticket)
    await session.commit()
    return ticket


@router.get("", response_model=list[TicketRead])
async def list_tickets(user: CurrentUser, session: SessionDep):
    query = select(Ticket).order_by(Ticket.created_at.desc())
    if user.role == "customer":
        query = query.where(Ticket.customer_id == user.id)
    return await session.scalars(query)


@router.get("/{ticket_id}", response_model=TicketDetail)
async def get_ticket(ticket_id: int, user: CurrentUser, session: SessionDep):
    return await get_visible_ticket(session, ticket_id, user)


@router.post("/{ticket_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def add_message(ticket_id: int, data: MessageCreate, user: Customer, session: SessionDep):
    ticket = await get_visible_ticket(session, ticket_id, user)
    message = TicketMessage(ticket_id=ticket.id, sender_type="customer", author_id=user.id, body=data.body)
    session.add(message)
    await session.commit()
    return message
