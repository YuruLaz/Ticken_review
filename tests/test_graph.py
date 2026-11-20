from app.ai.graph import build_graph
from app.ai.schemas import DraftReply, TicketClassification

TICKET = {"ticket_id": 1, "subject": "Where is my order?", "body": "Order 123 is late."}


def classification(category="shipping"):
    return TicketClassification(category=category, priority="low", sentiment="neutral", confidence=0.9)


def reply(text="Your order ships tomorrow."):
    return DraftReply(reply=text, confidence=0.9, cited_article_ids=[])


def test_spam_is_not_replied(fake_llm):
    fake_llm.answers = [classification("spam")]

    result = build_graph().invoke(TICKET)

    assert result["route"] == "spam"
    assert "draft_reply" not in result


def test_normal_ticket_gets_a_draft_and_a_route(fake_llm):
    fake_llm.answers = [classification(), reply()]

    result = build_graph().invoke(TICKET)

    assert result["draft_reply"] == "Your order ships tomorrow."
    assert result["attempts"] == 1
    # The retrieve stub finds no articles yet, so every ticket goes to a human for now.
    assert result["route"] == "human_review"


def test_failed_quality_check_retries_once_then_stops(fake_llm):
    fake_llm.answers = [classification(), reply(""), reply("")]

    result = build_graph().invoke(TICKET)

    assert result["attempts"] == 2
    assert result["route"] == "human_review"
    assert "quality issue: empty reply" in result["route_reasons"]
