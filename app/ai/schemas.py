from typing import Literal

from pydantic import BaseModel, Field

# These models are what the LLM must return. Literal restricts it to the values route() knows,
# and the descriptions are sent to the model as instructions for each field.


class TicketClassification(BaseModel):
    category: Literal["billing", "technical", "account", "shipping", "general", "spam"]
    priority: Literal["low", "medium", "high", "urgent"]
    sentiment: Literal["positive", "neutral", "negative", "angry"]
    confidence: float = Field(ge=0, le=1, description="How sure you are about this classification")


class DraftReply(BaseModel):
    reply: str = Field(description="The reply to send to the customer")
    confidence: float = Field(ge=0, le=1, description="How well the knowledge base articles support this reply")
    # Lets the quality check verify the reply is grounded: every id must be one we actually retrieved.
    cited_article_ids: list[int] = Field(description="IDs of the knowledge base articles this reply is based on")
