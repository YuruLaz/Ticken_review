import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.ticket import AgentTicketDetail


class TriageRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    classification_confidence: float | None
    draft_reply: str | None
    draft_confidence: float | None
    best_kb_score: float | None
    attempts: int
    route: str
    route_reasons: list[str]
    human_decision: str | None
    review_note: str | None
    langsmith_run_id: uuid.UUID | None
    created_at: datetime


class KBArticleBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


class ReviewDetail(BaseModel):
    ticket: AgentTicketDetail
    run: TriageRunRead
    kb_articles: list[KBArticleBrief]


class Decision(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edited_reply: str | None = None  # required when action is "edit"
    note: str | None = None
