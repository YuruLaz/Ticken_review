from app.ai.llm import get_llm
from app.ai.routing import route
from app.ai.schemas import DraftReply, TicketClassification
from app.ai.state import TicketState

# Each node receives the full state and returns only the fields it changed;
# LangGraph merges those into the state.


def classify(state: TicketState) -> dict:
    llm = get_llm().with_structured_output(TicketClassification)
    result = llm.invoke(
        "Classify this customer support ticket.\n\n"
        f"Subject: {state['subject']}\n\n{state['body']}"
    )
    return {
        "category": result.category,
        "priority": result.priority,
        "sentiment": result.sentiment,
        "classification_confidence": result.confidence,
    }


def mark_spam(state: TicketState) -> dict:
    return {"route": "spam", "route_reasons": ["classified as spam"]}


def retrieve(state: TicketState) -> dict:
    # Stub until RAG (step 12). A score of 0 means "nothing found", so route() sends every ticket
    # to a human for now, which is the safe default.
    return {"kb_articles": [], "best_kb_score": 0.0}


def draft(state: TicketState) -> dict:
    articles = "\n\n".join(
        f"[{a['id']}] {a['title']}\n{a['content']}" for a in state["kb_articles"]
    )
    prompt = (
        "Write a reply to this customer support ticket using only the knowledge base articles below. "
        "Cite the ids of the articles you used.\n\n"
        f"Subject: {state['subject']}\n\n{state['body']}\n\n"
        f"Knowledge base articles:\n{articles or '(none found)'}"
    )
    # On a retry, tell the model what was wrong with its previous attempt.
    if state.get("quality_issues"):
        prompt += "\n\nYour previous reply had these problems, fix them:\n- " + "\n- ".join(
            state["quality_issues"]
        )

    result = get_llm().with_structured_output(DraftReply).invoke(prompt)
    return {
        "draft_reply": result.reply,
        "draft_confidence": result.confidence,
        "cited_article_ids": result.cited_article_ids,
        "attempts": state.get("attempts", 0) + 1,
    }


def quality_check(state: TicketState) -> dict:
    issues = []
    if not state["draft_reply"].strip():
        issues.append("reply is empty")

    retrieved_ids = {a["id"] for a in state["kb_articles"]}
    unknown = [i for i in state["cited_article_ids"] if i not in retrieved_ids]
    if unknown:
        issues.append(f"cites articles that were not retrieved: {unknown}")

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
