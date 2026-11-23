"""Load data/kb/*.md into kb_articles. Run from the project root: python -m scripts.seed_kb"""

import asyncio
from pathlib import Path

from sqlalchemy import delete

from app.ai.llm.client import get_embeddings
from app.database.db import SessionLocal
from app.models.kb import KBArticle

KB_DIR = Path(__file__).parent.parent / "data" / "kb"


async def main():
    articles = []
    for path in sorted(KB_DIR.glob("*.md")):
        title, content = path.read_text().split("\n", 1)
        articles.append((title.removeprefix("# "), content.strip()))

    vectors = await get_embeddings().aembed_documents([f"{t}\n{c}" for t, c in articles])

    async with SessionLocal() as session:
        await session.execute(delete(KBArticle))
        session.add_all(
            KBArticle(title=title, content=content, embedding=vector)
            for (title, content), vector in zip(articles, vectors)
        )
        await session.commit()

    print(f"Seeded {len(articles)} articles")


if __name__ == "__main__":
    asyncio.run(main())
