"""Admin pages: the analytics dashboard and the knowledge base manager."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from web import api
from web.dependencies import User, home_for
from web.templating import templates

router = APIRouter(prefix="/admin")


def not_admin(user: dict) -> RedirectResponse | None:
    return None if user["role"] == "admin" else RedirectResponse(home_for(user), status_code=303)


@router.get("")
async def dashboard(request: Request, user: User):
    if redirect := not_admin(user):
        return redirect
    context = {"user": user, **await api.analytics(user["token"])}
    return templates.TemplateResponse(request, "admin.html", context)


@router.get("/kb")
async def kb_list(request: Request, user: User, q: str = "", msg: str = ""):
    if redirect := not_admin(user):
        return redirect
    context = {
        "user": user,
        "articles": await api.kb_articles(user["token"]),
        "q": q,
        "results": await api.kb_search(user["token"], q) if q else None,
        "msg": msg,
    }
    return templates.TemplateResponse(request, "kb_list.html", context)


async def render_form(request: Request, user: dict, article: dict, error: str | None = None):
    context = {"user": user, "article": article, "error": error}
    return templates.TemplateResponse(request, "kb_form.html", context)


@router.get("/kb/new")
async def kb_new(request: Request, user: User):
    if redirect := not_admin(user):
        return redirect
    return await render_form(request, user, {"id": None, "title": "", "content": ""})


@router.get("/kb/{article_id}")
async def kb_edit(request: Request, user: User, article_id: int):
    if redirect := not_admin(user):
        return redirect
    return await render_form(request, user, await api.kb_article(user["token"], article_id))


@router.post("/kb/save")
async def kb_save(
    request: Request,
    user: User,
    title: Annotated[str, Form()],
    content: Annotated[str, Form()],
    article_id: Annotated[int | None, Form()] = None,
):
    try:
        await api.kb_save(user["token"], article_id, title, content)
    except api.ApiError as error:
        article = {"id": article_id, "title": title, "content": content}
        return await render_form(request, user, article, str(error))
    return RedirectResponse(f"/admin/kb?msg=Saved “{title}”", status_code=303)


@router.post("/kb/{article_id}/delete")
async def kb_delete(user: User, article_id: int):
    await api.kb_delete(user["token"], article_id)
    return RedirectResponse("/admin/kb?msg=Article deleted", status_code=303)
