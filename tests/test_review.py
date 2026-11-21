import pytest
from sqlalchemy import select

from app.main import app
from app.models import Ticket, TriageRun, User

PASSWORD = "secret123"


class FakeGraph:
    """Stands in for the paused graph: remembers the resume value and answers like human_review would."""

    def __init__(self):
        self.resumed_with = None

    async def ainvoke(self, command, config):
        self.resumed_with = command.resume
        final_reply = {"approve": "Draft reply.", "edit": command.resume["reply"], "reject": ""}
        return {"final_reply": final_reply[command.resume["action"]]}


async def headers_for(client, email):
    await client.post("/auth/register", json={"email": email, "full_name": "X", "password": PASSWORD})
    response = await client.post("/auth/login", data={"username": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def setup(client, session_maker, monkeypatch):
    graph = FakeGraph()
    # The test client skips the lifespan, so the graph has to be put in place by hand.
    monkeypatch.setattr(app.state, "graph", graph, raising=False)

    customer = await headers_for(client, "customer@example.com")
    agent = await headers_for(client, "agent@example.com")

    async with session_maker() as session:
        (await session.scalar(select(User).where(User.email == "agent@example.com"))).role = "agent"
        owner = await session.scalar(select(User).where(User.email == "customer@example.com"))
        ticket = Ticket(customer_id=owner.id, subject="Refund", body="Charged twice.", status="awaiting_review")
        session.add(ticket)
        await session.flush()  # assigns ticket.id
        session.add(TriageRun(ticket_id=ticket.id, draft_reply="Draft reply.", route="human_review",
                              route_reasons=["billing tickets are always reviewed"]))
        await session.commit()

    return {"customer": customer, "agent": agent, "ticket_id": ticket.id, "graph": graph}


async def test_customer_cannot_open_the_queue(client, setup):
    response = await client.get("/review/queue", headers=setup["customer"])

    assert response.status_code == 403


async def test_queue_lists_tickets_awaiting_review(client, setup):
    response = await client.get("/review/queue", headers=setup["agent"])

    assert [t["id"] for t in response.json()] == [setup["ticket_id"]]


async def test_detail_shows_draft_and_reasons(client, setup):
    response = await client.get(f"/review/{setup['ticket_id']}", headers=setup["agent"])

    run = response.json()["run"]
    assert run["draft_reply"] == "Draft reply."
    assert run["route_reasons"] == ["billing tickets are always reviewed"]


async def test_edit_resumes_graph_and_sends_agent_reply(client, setup, session_maker):
    response = await client.post(
        f"/review/{setup['ticket_id']}/decision",
        json={"action": "edit", "edited_reply": "Refund issued."},
        headers=setup["agent"],
    )

    assert response.status_code == 200
    assert response.json()["status"] == "replied"
    assert response.json()["messages"][-1]["sender_type"] == "agent"
    assert response.json()["messages"][-1]["body"] == "Refund issued."
    assert setup["graph"].resumed_with == {"action": "edit", "reply": "Refund issued."}
    async with session_maker() as session:
        assert (await session.scalar(select(TriageRun))).human_decision == "edit"


async def test_reject_escalates_without_a_message(client, setup):
    response = await client.post(
        f"/review/{setup['ticket_id']}/decision", json={"action": "reject"}, headers=setup["agent"]
    )

    assert response.json()["status"] == "escalated"
    assert response.json()["messages"] == []


async def test_second_decision_returns_409(client, setup):
    url = f"/review/{setup['ticket_id']}/decision"
    await client.post(url, json={"action": "approve"}, headers=setup["agent"])

    response = await client.post(url, json={"action": "approve"}, headers=setup["agent"])

    assert response.status_code == 409
