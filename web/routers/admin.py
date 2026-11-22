"""Admin pages: the analytics dashboard."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from web import api
from web.dependencies import User, home_for
from web.templating import templates

router = APIRouter(prefix="/admin")


@router.get("")
async def dashboard(request: Request, user: User):
    if user["role"] != "admin":
        return RedirectResponse(home_for(user), status_code=303)
    context = {"user": user, **await api.analytics(user["token"])}
    return templates.TemplateResponse(request, "admin.html", context)
