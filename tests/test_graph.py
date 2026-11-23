import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.ai import nodes
from app.ai.graph import build_graph
from app.ai.schemas import DraftReply, TicketClassification

TICKET = {"ticket_id": 1, "subject": "Where is my order?", "body": "Order 123 is late."}
CONFIG = {"configurable": {"thread_id": "ticket-1"}}


def classification(category="shipping"):
    return TicketClassification(category=category, priority="low", sentiment="neutral", language="en",
                                summary="Customer asks about an order.", confidence=0.9)


def reply(text="Your order ships tomorrow.", cited=()):
    return DraftReply(reply=text, confidence=0.9, cited_article_ids=list(cited))


def new_graph():
    return build_graph(checkpointer=InMemorySaver())


def fake_retrieve(articles):
    async def retrieve(state):
        return {"kb_articles": articles, "best_kb_score": articles[0]["score"] if articles else 0.0}

    return retrieve


@pytest.fixture(autouse=True)
def empty_kb(monkeypatch):
    monkeypatch.setattr(nodes, "retrieve", fake_retrieve([]))


async def test_spam_is_not_replied(fake_llm):
    fake_llm.answers = [classification("spam")]

    result = await new_graph().ainvoke(TICKET, CONFIG)

    assert result["route"] == "spam"
    assert "draft_reply" not in result


async def test_failed_quality_check_retries_once_then_stops(fake_llm):
    fake_llm.answers = [classification(), reply(""), reply("")]

    result = await new_graph().ainvoke(TICKET, CONFIG)

    assert result["attempts"] == 2
    assert "quality issue: empty reply" in result["route_reasons"]


async def test_confident_ticket_is_auto_sent(fake_llm, monkeypatch):
    monkeypatch.setattr(nodes, "retrieve", fake_retrieve([{"id": 1, "score": 0.9}]))
    fake_llm.answers = [classification(), reply(cited=[1])]

    result = await new_graph().ainvoke(TICKET, CONFIG)

    assert result["route"] == "auto_send"
    assert result["final_reply"] == "Your order ships tomorrow."


async def test_human_review_pauses_the_graph(fake_llm):
    fake_llm.answers = [classification(), reply()]

    result = await new_graph().ainvoke(TICKET, CONFIG)

    assert result["route"] == "human_review"
    assert "final_reply" not in result
    assert result["__interrupt__"][0].value["draft_reply"] == "Your order ships tomorrow."


async def test_agent_edit_resumes_the_graph(fake_llm):
    fake_llm.answers = [classification(), reply()]
    graph = new_graph()
    await graph.ainvoke(TICKET, CONFIG)

    result = await graph.ainvoke(Command(resume={"action": "edit", "reply": "Edited by agent."}), CONFIG)

    assert result["review_action"] == "edit"
    assert result["final_reply"] == "Edited by agent."
    assert len(fake_llm.prompts) == 2


async def test_agent_reject_sends_nothing(fake_llm):
    fake_llm.answers = [classification(), reply()]
    graph = new_graph()
    await graph.ainvoke(TICKET, CONFIG)

    result = await graph.ainvoke(Command(resume={"action": "reject"}), CONFIG)

    assert result["review_action"] == "reject"
    assert result["final_reply"] == ""


async def test_failed_run_continues_from_last_checkpoint(fake_llm):
    fake_llm.answers = [classification()]
    graph = new_graph()
    with pytest.raises(IndexError):
        await graph.ainvoke(TICKET, CONFIG)

    fake_llm.answers = [reply()]
    result = await graph.ainvoke(None, CONFIG)

    assert result["route"] == "human_review"
    assert len(fake_llm.prompts) == 3


async def test_llm_never_sees_raw_card_number(fake_llm):
    fake_llm.answers = [classification("spam")]
    ticket = {**TICKET, "body": "Charged twice on card 5167 4401 2233 1234"}

    await new_graph().ainvoke(ticket, CONFIG)

    assert "5167 **** **** 1234" in fake_llm.prompts[0]
    assert "4401" not in fake_llm.prompts[0]
