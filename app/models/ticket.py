from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="new", index=True)

    # Empty until the AI classifies the ticket, hence nullable.
    category: Mapped[str | None] = mapped_column(String(30))
    priority: Mapped[str | None] = mapped_column(String(20))
    sentiment: Mapped[str | None] = mapped_column(String(20))
    language: Mapped[str | None] = mapped_column(String(10))

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket", order_by="TicketMessage.created_at"
    )


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    # customer | ai | agent. Stored separately from author_id because AI messages have no user.
    sender_type: Mapped[str] = mapped_column(String(20))
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    ticket: Mapped[Ticket] = relationship(back_populates="messages")
