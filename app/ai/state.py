from typing import TypedDict


# total=False: each node fills in only its own fields, so most keys are missing early on.
class TicketState(TypedDict, total=False):
    # input
    ticket_id: int
    subject: str
    body: str

    # classify
    category: str
    priority: str
    sentiment: str
    language: str
    summary: str
    classification_confidence: float

    # retrieve (stub until RAG in step 12)
    kb_articles: list[dict]
    best_kb_score: float

    # draft + quality check
    draft_reply: str
    draft_confidence: float
    cited_article_ids: list[int]
    quality_issues: list[str]
    attempts: int

    # route
    route: str  # spam | auto_send | human_review
    route_reasons: list[str]

    # outcome
    review_action: str  # approve | edit | reject (only when a human reviewed it)
    final_reply: str  # what the customer gets; empty when rejected
