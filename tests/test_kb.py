import pytest
from sqlalchemy import select

from app.ai.pipeline import retrieval
from app.models import KBArticle, User
from tests.test_retrieval import one_hot
from tests.test_tickets import headers_for


class FakeEmbeddings:
    """Shipping text points one way, everything else another; queries point at shipping."""

    async def aembed_documents(self, texts):
        return [one_hot(0 if "shipping" in text.lower() else 1) for text in texts]

    async def aembed_query(self, text):
        return one_hot(0)


@pytest.fixture
async def users(client, session_maker, monkeypatch):
    monkeypatch.setattr(retrieval, "get_embeddings", lambda: FakeEmbeddings())
    headers = {role: await headers_for(client, f"{role}@example.com") for role in ("admin", "agent", "customer")}
    async with session_maker() as session:
        for role in ("admin", "agent"):
            (await session.scalar(select(User).where(User.email == f"{role}@example.com"))).role = role
        await session.commit()
    return headers


async def create(client, headers, title, content="..."):
    return await client.post("/kb/articles", json={"title": title, "content": content}, headers=headers)


async def test_admin_creates_and_agent_lists(client, users):
    assert (await create(client, users["admin"], "Refunds")).status_code == 201
    response = await client.get("/kb/articles", headers=users["agent"])
    assert [a["title"] for a in response.json()] == ["Refunds"]


async def test_only_admin_can_change_articles(client, users):
    assert (await create(client, users["agent"], "Refunds")).status_code == 403
    assert (await client.get("/kb/articles", headers=users["customer"])).status_code == 403


async def test_update_keeps_id_and_re_embeds(client, users, session_maker):
    article_id = (await create(client, users["admin"], "Refunds")).json()["id"]
    response = await client.put(f"/kb/articles/{article_id}", json={"title": "Shipping times", "content": "..."},
                                headers=users["admin"])
    assert response.json()["id"] == article_id
    async with session_maker() as session:
        assert list((await session.get(KBArticle, article_id)).embedding) == one_hot(0)


async def test_delete(client, users):
    article_id = (await create(client, users["admin"], "Refunds")).json()["id"]
    assert (await client.delete(f"/kb/articles/{article_id}", headers=users["admin"])).status_code == 204
    assert (await client.get(f"/kb/articles/{article_id}", headers=users["agent"])).status_code == 404


async def test_search_ranks_closest_first(client, users):
    await create(client, users["admin"], "Refunds")
    await create(client, users["admin"], "Shipping times")
    response = await client.post("/kb/search", json={"query": "where is my order"}, headers=users["agent"])
    assert [r["title"] for r in response.json()][:2] == ["Shipping times", "Refunds"]
