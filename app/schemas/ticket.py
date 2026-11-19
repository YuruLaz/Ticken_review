from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    # Matches String(200) in the model; without it a long subject is a 500 from the DB.
    subject: str = Field(max_length=200)
    body: str


class MessageCreate(BaseModel):
    body: str


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_type: str
    author_id: int | None
    body: str
    created_at: datetime


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    subject: str
    body: str
    status: str
    category: str | None
    priority: str | None
    sentiment: str | None
    language: str | None
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketRead):
    messages: list[MessageRead]
