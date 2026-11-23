import pytest
from sqlalchemy import select

from app.models import Ticket, TriageRun, User
from tests.test_tickets import headers_for


@pytest.fixture
async def admin(client, session_maker):
    headers = await headers_for(client, "admin@example.com")
    async with session_maker() as session:
        user = await session.scalar(select(User).where(User.email == "admin@example.com"))
        user.role = "admin"
        runs = [
            ("billing", "high", "auto_send", None, 0.9),
            ("billing", "low", "auto_send", None, 0.9),
            ("shipping", "high", "human_review", "approve", 0.8),
            ("shipping", "urgent", "human_review", "reject", 0.4),
            ("spam", "low", "spam", None, None),
        ]
        for category, priority, route, decision, confidence in runs:
            ticket = Ticket(customer_id=user.id, subject="s", body="b", status="new",
                            category=category, priority=priority)
            session.add(ticket)
            await session.flush()
            session.add(TriageRun(ticket_id=ticket.id, route=route, human_decision=decision,
                                  draft_confidence=confidence))
        await session.commit()
    return headers


async def test_overview_counts_by_category_and_priority(client, admin):
    data = (await client.get("/analytics/overview", headers=admin)).json()
    assert data["by_category"] == {"billing": 2, "shipping": 2, "spam": 1}
    assert data["by_priority"] == {"high": 2, "low": 2, "urgent": 1}


async def test_automation_rate_leaves_out_spam(client, admin):
    data = (await client.get("/analytics/automation-rate", headers=admin)).json()
    assert data["automation_rate"] == 0.5


async def test_ai_accuracy(client, admin):
    data = (await client.get("/analytics/ai-accuracy", headers=admin)).json()
    assert data["reviewed"] == 2
    assert data["approval_rate"] == 0.5
    assert data["decisions"]["reject"] == {"count": 1, "avg_draft_confidence": 0.4}


async def test_analytics_is_admin_only(client):
    customer = await headers_for(client, "customer@example.com")
    assert (await client.get("/analytics/overview", headers=customer)).status_code == 403
