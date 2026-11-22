from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.ai.retrieval import embed_article, search_kb
from app.core.dependencies import SessionDep, require_role
from app.models import KBArticle, User
from app.schemas.kb import KBArticleRead, KBArticleWrite, KBSearch, KBSearchResult

router = APIRouter(prefix="/kb", tags=["kb"])

Admin = Annotated[User, Depends(require_role("admin"))]
Staff = Annotated[User, Depends(require_role("agent", "admin"))]


async def get_article(session, article_id: int) -> KBArticle:
    article = await session.get(KBArticle, article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return article


@router.get("/articles", response_model=list[KBArticleRead])
async def list_articles(user: Staff, session: SessionDep):
    return await session.scalars(select(KBArticle).order_by(KBArticle.title))


@router.get("/articles/{article_id}", response_model=KBArticleRead)
async def read_article(article_id: int, user: Staff, session: SessionDep):
    return await get_article(session, article_id)


@router.post("/articles", response_model=KBArticleRead, status_code=status.HTTP_201_CREATED)
async def create_article(data: KBArticleWrite, user: Admin, session: SessionDep):
    article = KBArticle(
        title=data.title, content=data.content, embedding=await embed_article(data.title, data.content)
    )
    session.add(article)
    await session.commit()
    return article


@router.put("/articles/{article_id}", response_model=KBArticleRead)
async def update_article(article_id: int, data: KBArticleWrite, user: Admin, session: SessionDep):
    # Updated in place: same id, so past triage runs still point to it.
    article = await get_article(session, article_id)
    article.title, article.content = data.title, data.content
    article.embedding = await embed_article(data.title, data.content)
    await session.commit()
    return article


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(article_id: int, user: Admin, session: SessionDep):
    await session.delete(await get_article(session, article_id))
    await session.commit()


@router.post("/search", response_model=list[KBSearchResult])
async def search(data: KBSearch, user: Staff, session: SessionDep):
    # Same search the graph uses, for checking what a ticket would retrieve.
    return await search_kb(session, data.query)
