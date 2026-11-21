import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TriageRun(Base):
    """One AI pass over a ticket: the signals the graph produced and what was decided."""

    __tablename__ = "triage_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )

    classification_confidence: Mapped[float | None]
    # Spam tickets stop after classify, so the draft-related fields stay empty for them.
    draft_reply: Mapped[str | None] = mapped_column(Text)
    draft_confidence: Mapped[float | None]
    best_kb_score: Mapped[float | None]
    kb_article_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    attempts: Mapped[int] = mapped_column(default=0)

    route: Mapped[str] = mapped_column(String(20))  # spam | auto_send | human_review
    # Stored so the agent sees why a ticket was flagged, and so the thresholds can be measured later.
    route_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    human_decision: Mapped[str | None] = mapped_column(String(20))  # approve | edit | reject
    review_note: Mapped[str | None] = mapped_column(Text)  # the agent's optional comment on the decision
    # The trace's ID in LangSmith (paste into its search). An ID, not a URL: building the URL
    # would need LangSmith API lookups after every run.
    langsmith_run_id: Mapped[uuid.UUID | None]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
