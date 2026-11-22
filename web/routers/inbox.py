"""Agent inbox: the views sidebar and the ticket list (left and middle panes)."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from web import api
from web.dependencies import User, agent_only, home_for
from web.templating import templates

router = APIRouter(prefix="/inbox")

# (url name, label, status); first three need action.
VIEWS = [
    ("review", "Needs review", "awaiting_review"),
    ("failed", "Failed", "failed"),
    ("escalated", "Escalated", "escalated"),
    ("new", "Being processed", "new"),
    ("replied", "Answered", "replied"),
    ("spam", "Spam", "spam"),
    ("all", "All tickets", None),
]
VIEW_STATUS = {name: status for name, _, status in VIEWS}


async def load_tickets(user: dict, view: str, q: str) -> list[dict]:
    if view == "review":
        # Queue already sorted: urgent, then oldest.
        tickets = await api.review_queue(user["token"])
        q = q.lower()
        return [t for t in tickets if q in t["subject"].lower() or q in t["body"].lower()]
    return await api.list_tickets(user["token"], status=VIEW_STATUS.get(view), search=q)


async def nav_context(user: dict, view: str) -> dict:
    counts = await api.ticket_counts(user["token"])
    return {"views": VIEWS, "counts": counts, "total": sum(counts.values()), "view": view}


@router.get("")
async def inbox(request: Request, user: User, view: str = "review", q: str = ""):
    if user["role"] == "customer":
        return RedirectResponse(home_for(user), status_code=303)
    context = {"user": user, "q": q, **await nav_context(user, view)}
    context["tickets"] = await load_tickets(user, view, q)
    return templates.TemplateResponse(request, "inbox.html", context)


@router.get("/list")
async def inbox_list(request: Request, user: User, view: str = "review", q: str = ""):
    """Just the ticket list, for htmx: search-as-you-type and the periodic refresh swap only this."""
    agent_only(user)
    context = {"tickets": await load_tickets(user, view, q), "oob": True, **await nav_context(user, view)}
    return templates.TemplateResponse(request, "_inbox_refresh.html", context)
