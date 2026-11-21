from typing import Literal

from pydantic import BaseModel, Field

# These models are what the LLM must return. Literal restricts it to the values route() knows,
# and the descriptions are sent to the model as instructions for each field.


class TicketClassification(BaseModel):
    category: Literal["billing", "technical", "account", "shipping", "general", "spam"]
    priority: Literal["low", "medium", "high", "urgent"]
    sentiment: Literal["positive", "neutral", "negative", "angry"]
    language: str = Field(description="ISO 639-1 code of the language the ticket is written in, e.g. en, ka, ru")
    # No max_length here: an over-long summary would fail the whole run; it's cut to 200 when saved instead.
    summary: str = Field(description="One-sentence summary of the ticket for the support agent, under 200 characters")
    confidence: float = Field(ge=0, le=1, description="How sure you are about this classification")


class DraftReply(BaseModel):
    reply: str = Field(description="The reply to send to the customer")
    confidence: float = Field(ge=0, le=1, description="How well the knowledge base articles support this reply")
    # Lets the quality check verify the reply is grounded: every id must be one we actually retrieved.
    cited_article_ids: list[int] = Field(description="IDs of the knowledge base articles this reply is based on")
