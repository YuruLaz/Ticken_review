# Alembic finds tables through Base.metadata, which only knows about models
# that have been imported. Importing them all here keeps that in one place.
from app.models.ticket import Ticket, TicketMessage
from app.models.user import User

__all__ = ["Ticket", "TicketMessage", "User"]
