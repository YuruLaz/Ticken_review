# Alembic finds tables through Base.metadata, which only knows about models
# that have been imported. Importing them all here keeps that in one place.
from app.models.kb import KBArticle
from app.models.ticket import Ticket, TicketMessage
from app.models.triage_run import TriageRun
from app.models.user import User

__all__ = ["KBArticle", "Ticket", "TicketMessage", "TriageRun", "User"]
