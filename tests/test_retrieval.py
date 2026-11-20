from app.ai import retrieval
from app.models.kb import EMBEDDING_DIM, KBArticle


def one_hot(i):
    vector = [0.0] * EMBEDDING_DIM
    vector[i] = 1.0
    return vector


class FakeEmbeddings:
    async def aembed_query(self, text):
        return one_hot(0)


async def test_search_kb_returns_closest_article_first(session_maker, monkeypatch):
    monkeypatch.setattr(retrieval, "get_embeddings", lambda: FakeEmbeddings())
    async with session_maker() as session:
        session.add_all([
            KBArticle(title="Refunds", content="...", embedding=one_hot(1)),
            KBArticle(title="Shipping times", content="...", embedding=one_hot(0)),
        ])
        await session.commit()

        results = await retrieval.search_kb(session, "where is my order?")

    assert [r["title"] for r in results] == ["Shipping times", "Refunds"]
    assert results[0]["score"] == 1.0  # same direction as the query
    assert results[1]["score"] == 0.0  # unrelated
