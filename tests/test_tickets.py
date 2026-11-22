import pytest
from sqlalchemy import select

from app.models import Ticket, User

PASSWORD = "secret123"


async def headers_for(client, email):
    await client.post("/auth/register", json={"email": email, "full_name": "X", "password": PASSWORD})
    response = await client.post("/auth/login", data={"username": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def setup(client, session_maker):
    customer = await headers_for(client, "customer@example.com")
    other = await headers_for(client, "other@example.com")
    agent = await headers_for(client, "agent@example.com")

    # Direct insert avoids running the graph.
    async with session_maker() as session:
        (await session.scalar(select(User).where(User.email == "agent@example.com"))).role = "agent"
        owner = await session.scalar(select(User).where(User.email == "customer@example.com"))
        stranger = await session.scalar(select(User).where(User.email == "other@example.com"))
        session.add_all([
            Ticket(customer_id=owner.id, subject="Charged twice", body="Refund please",
                   status="awaiting_review", sentiment="angry"),
            Ticket(customer_id=owner.id, subject="Where is my order", body="SN-20481937",
                   status="replied", sentiment="neutral"),
            Ticket(customer_id=stranger.id, subject="Login broken", body="Can't sign in",
                   status="awaiting_review", sentiment="neutral"),
        ])
        await session.commit()

    return {"customer": customer, "other": other, "agent": agent}


async def subjects(client, headers, **params):
    response = await client.get("/tickets", params=params, headers=headers)
    return sorted(t["subject"] for t in response.json())


async def test_status_filter(client, setup):
    assert await subjects(client, setup["agent"], status="awaiting_review") == ["Charged twice", "Login broken"]


async def test_search_matches_subject_and_body(client, setup):
    assert await subjects(client, setup["agent"], search="sn-2048") == ["Where is my order"]


async def test_filters_never_show_other_customers_tickets(client, setup):
    assert await subjects(client, setup["customer"], status="awaiting_review") == ["Charged twice"]


async def test_customer_cannot_filter_on_hidden_fields(client, setup):
    # Hidden field filter ignored for customers.
    assert await subjects(client, setup["customer"], sentiment="angry") == ["Charged twice", "Where is my order"]


async def test_pagination(client, setup):
    first = await subjects(client, setup["agent"], size=2, page=1)
    second = await subjects(client, setup["agent"], size=2, page=2)
    assert len(first) == 2 and len(second) == 1


async def test_counts_per_status(client, setup):
    agent = (await client.get("/tickets/counts", headers=setup["agent"])).json()
    customer = (await client.get("/tickets/counts", headers=setup["customer"])).json()

    assert agent == {"awaiting_review": 2, "replied": 1}
    assert customer == {"awaiting_review": 1, "replied": 1}


async def test_customer_follow_up_reopens_answered_ticket(client, setup):
    ticket = (await client.get("/tickets", params={"status": "replied"}, headers=setup["customer"])).json()[0]
    await client.post(f"/tickets/{ticket['id']}/messages", json={"body": "Still waiting"}, headers=setup["customer"])
    assert await subjects(client, setup["agent"], status="escalated") == ["Where is my order"]


async def test_eleventh_ticket_in_an_hour_is_refused(client, session_maker):
    headers = await headers_for(client, "busy@example.com")
    async with session_maker() as session:
        user = await session.scalar(select(User).where(User.email == "busy@example.com"))
        session.add_all(Ticket(customer_id=user.id, subject="s", body="b") for _ in range(10))
        await session.commit()
    response = await client.post("/tickets", json={"subject": "s", "body": "b"}, headers=headers)
    assert response.status_code == 429
