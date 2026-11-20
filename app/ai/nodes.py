from app.ai.llm import get_llm
from app.ai.prompts import classify_prompt, draft_prompt
from app.ai.routing import route
from app.ai.schemas import DraftReply, TicketClassification
from app.ai.state import TicketState

# Each node returns only the fields it changed; LangGraph merges them into the state.


def classify(state: TicketState) -> dict:
    result = get_llm().with_structured_output(TicketClassification).invoke(classify_prompt(state))
    return {
        "category": result.category,
        "priority": result.priority,
        "sentiment": result.sentiment,
        "classification_confidence": result.confidence,
    }


def mark_spam(state: TicketState) -> dict:
    return {"route": "spam"}


def retrieve(state: TicketState) -> dict:
    # Stub until RAG (step 12): "nothing found" makes route() send every ticket to a human.
    return {"kb_articles": [], "best_kb_score": 0.0}


def draft(state: TicketState) -> dict:
    result = get_llm().with_structured_output(DraftReply).invoke(draft_prompt(state))
    return {
        "draft_reply": result.reply,
        "draft_confidence": result.confidence,
        "cited_article_ids": result.cited_article_ids,
        "attempts": state.get("attempts", 0) + 1,
    }


def quality_check(state: TicketState) -> dict:
    issues = []
    if not state["draft_reply"].strip():
        issues.append("empty reply")

    retrieved_ids = [a["id"] for a in state["kb_articles"]]
    if any(i not in retrieved_ids for i in state["cited_article_ids"]):
        issues.append("cites an article that was not retrieved")

    return {"quality_issues": issues}


def decide_route(state: TicketState) -> dict:
    decision = route(
        priority=state["priority"],
        sentiment=state["sentiment"],
        category=state["category"],
        classification_confidence=state["classification_confidence"],
        draft_confidence=state["draft_confidence"],
        best_kb_score=state["best_kb_score"],
        quality_issues=state["quality_issues"],
    )
    return {"route": decision.action, "route_reasons": decision.reasons}
