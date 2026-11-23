from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    subject: str = Field(max_length=200)
    body: str = Field(max_length=5000)


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
    language: str | None
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketRead):
    messages: list[MessageRead]


class CustomerBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str
    email: str


class AgentTicketRead(TicketRead):
    customer: CustomerBrief
    priority: str | None
    sentiment: str | None
    ai_summary: str | None


class AgentTicketDetail(AgentTicketRead):
    messages: list[MessageRead]
