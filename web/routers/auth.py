from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from web import api
from web.dependencies import TOKEN_COOKIE, User, home_for
from web.templating import templates

router = APIRouter()


@router.get("/")
async def home(user: User):
    return RedirectResponse(home_for(user), status_code=303)


@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
async def login(request: Request, email: Annotated[str, Form()], password: Annotated[str, Form()]):
    try:
        token = await api.login(email, password)
    except api.ApiError as error:
        return templates.TemplateResponse(request, "login.html", {"error": str(error), "email": email})
    response = RedirectResponse("/", status_code=303)
    # httponly: page JavaScript can't read the token, so an injected script can't steal it.
    # samesite=lax: the browser doesn't send it on cross-site form posts (basic CSRF protection).
    # secure=True would be required on HTTPS; it's off because local dev runs on plain HTTP.
    response.set_cookie(TOKEN_COOKIE, token, httponly=True, samesite="lax")
    return response


@router.post("/register")
async def register(
    request: Request,
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    try:
        await api.register(email, full_name, password)
    except api.ApiError as error:
        context = {"register_error": str(error), "tab": "register"}
    else:
        context = {"success": "Account created. You can log in now.", "email": email}
    return templates.TemplateResponse(request, "login.html", context)


@router.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(TOKEN_COOKIE)
    return response
