from sqlalchemy import select

from app.ai import triage
from app.models import Ticket, TicketMessage, TriageRun, User

CLASSIFIED = {"category": "shipping", "priority": "low", "sentiment": "neutral", "language": "en",
              "summary": "Customer asks where their order is.", "classification_confidence": 0.9}
DRAFTED = {
    **CLASSIFIED,
    "kb_articles": [{"id": 7, "title": "Shipping", "content": "...", "score": 0.7}],
    "best_kb_score": 0.7,
    "draft_reply": "Your order ships tomorrow.",
    "draft_confidence": 0.9,
    "attempts": 1,
}


class FakeGraph:
    """Returns a prepared final state (or raises a prepared error), so these tests check only what run_triage saves."""

    def __init__(self, state):
        self.state = state

    async def ainvoke(self, input, config):
        if isinstance(self.state, Exception):
            raise self.state
        return self.state


async def run(session_maker, monkeypatch, state):
    monkeypatch.setattr(triage, "SessionLocal", session_maker)
    async with session_maker() as session:
        customer = User(email="c@example.com", full_name="C", hashed_password="x")
        session.add(customer)
        await session.flush()
        ticket = Ticket(customer_id=customer.id, subject="Where is my order?", body="Order 123 is late.")
        session.add(ticket)
        await session.commit()

    await triage.run_triage(FakeGraph(state), ticket.id, {"subject": ticket.subject, "body": ticket.body})

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket.id)
        runs = (await session.scalars(select(TriageRun))).all()
        messages = (await session.scalars(select(TicketMessage))).all()
    return ticket, runs, messages


async def test_auto_send_saves_reply_as_ai_message(session_maker, monkeypatch):
    state = {**DRAFTED, "route": "auto_send", "route_reasons": [], "final_reply": "Your order ships tomorrow."}

    ticket, runs, messages = await run(session_maker, monkeypatch, state)

    assert ticket.status == "replied"
    assert ticket.category == "shipping"
    assert ticket.language == "en"
    assert ticket.ai_summary == "Customer asks where their order is."
    assert len(runs) == 1
    assert runs[0].route == "auto_send"
    assert runs[0].kb_article_ids == [7]
    assert runs[0].langsmith_run_id is not None
    assert [(m.sender_type, m.body) for m in messages] == [("ai", "Your order ships tomorrow.")]


async def test_human_review_waits_without_a_message(session_maker, monkeypatch):
    state = {**DRAFTED, "route": "human_review", "route_reasons": ["low draft confidence"]}

    ticket, runs, messages = await run(session_maker, monkeypatch, state)

    assert ticket.status == "awaiting_review"
    assert runs[0].route_reasons == ["low draft confidence"]
    assert runs[0].human_decision is None
    assert messages == []


async def test_spam_saves_run_without_draft_fields(session_maker, monkeypatch):
    state = {**CLASSIFIED, "category": "spam", "route": "spam"}

    ticket, runs, messages = await run(session_maker, monkeypatch, state)

    assert ticket.status == "spam"
    assert runs[0].draft_reply is None
    assert runs[0].kb_article_ids == []
    assert runs[0].attempts == 0
    assert messages == []


async def test_graph_error_marks_ticket_failed(session_maker, monkeypatch):
    ticket, runs, messages = await run(session_maker, monkeypatch, RuntimeError("Gemini is down"))

    assert ticket.status == "failed"
    assert runs == []
    assert messages == []


async def test_startup_fails_tickets_left_in_new(session_maker, monkeypatch):
    monkeypatch.setattr(triage, "SessionLocal", session_maker)
    async with session_maker() as session:
        customer = User(email="c@example.com", full_name="C", hashed_password="x")
        session.add(customer)
        await session.flush()
        session.add_all([Ticket(customer_id=customer.id, subject="a", body="b", status="new"),
                         Ticket(customer_id=customer.id, subject="a", body="b", status="replied")])
        await session.commit()

    assert await triage.fail_interrupted_runs() == 1
    async with session_maker() as session:
        assert sorted((await session.scalars(select(Ticket.status))).all()) == ["failed", "replied"]
