from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import get_embeddings
from app.models.kb import KBArticle


async def search_kb(session: AsyncSession, text: str, limit: int = 3) -> list[dict]:
    query_vector = await get_embeddings().aembed_query(text)
    distance = KBArticle.embedding.cosine_distance(query_vector)

    rows = await session.execute(select(KBArticle, distance).order_by(distance).limit(limit))
    return [
        {"id": article.id, "title": article.title, "content": article.content, "score": 1 - dist}
        for article, dist in rows
    ]


async def embed_article(title: str, content: str) -> list[float]:
    return (await get_embeddings().aembed_documents([f"{title}\n{content}"]))[0]
