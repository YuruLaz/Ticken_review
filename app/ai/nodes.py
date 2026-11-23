import re

from langchain_core.exceptions import OutputParserException
from langgraph.types import interrupt
from pydantic import ValidationError

from app.ai.llm import get_llm
from app.ai.pii import mask_pii
from app.ai.prompts import classify_prompt, draft_prompt
from app.ai.retrieval import search_kb
from app.ai.routing import route
from app.ai.schemas import DraftReply, TicketClassification
from app.ai.state import TicketState
from app.database.db import SessionLocal


RETRY_BAD_OUTPUT = {"retry_if_exception_type": (OutputParserException, ValidationError), "stop_after_attempt": 2}


def sanitize_input(state: TicketState) -> dict:
    return {"subject": clean(state["subject"]), "body": clean(state["body"])}


def clean(text: str) -> str:
    text = re.sub(r"</?ticket>", "", text, flags=re.IGNORECASE)
    return mask_pii(text)


def classify(state: TicketState) -> dict:
    result = get_llm().with_structured_output(TicketClassification).with_retry(**RETRY_BAD_OUTPUT).invoke(classify_prompt(state))
    return {
        "category": result.category,
        "priority": result.priority,
        "sentiment": result.sentiment,
        "language": result.language,
        "summary": result.summary,
        "classification_confidence": result.confidence,
    }


def mark_spam(state: TicketState) -> dict:
    return {"route": "spam"}


async def retrieve(state: TicketState) -> dict:
    async with SessionLocal() as session:
        articles = await search_kb(session, f"{state['subject']}\n{state['body']}")
    best_score = articles[0]["score"] if articles else 0.0
    return {"kb_articles": articles, "best_kb_score": best_score}


def draft(state: TicketState) -> dict:
    result = get_llm().with_structured_output(DraftReply).with_retry(**RETRY_BAD_OUTPUT).invoke(draft_prompt(state))
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


def send_reply(state: TicketState) -> dict:
    return {"final_reply": state["draft_reply"]}


def human_review(state: TicketState) -> dict:
    decision = interrupt({"draft_reply": state["draft_reply"], "reasons": state["route_reasons"]})

    if decision["action"] == "approve":
        final_reply = state["draft_reply"]
    elif decision["action"] == "edit":
        final_reply = decision["reply"]
    else:
        final_reply = ""
    return {"review_action": decision["action"], "final_reply": final_reply}
