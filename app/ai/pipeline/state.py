from typing import TypedDict


class TicketState(TypedDict, total=False):
    ticket_id: int
    subject: str
    body: str

    category: str
    priority: str
    sentiment: str
    language: str
    summary: str
    classification_confidence: float

    kb_articles: list[dict]
    best_kb_score: float

    draft_reply: str
    draft_confidence: float
    cited_article_ids: list[int]
    quality_issues: list[str]
    attempts: int

    route: str
    route_reasons: list[str]

    review_action: str
    final_reply: str
