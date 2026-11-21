"""Server-rendered UI (Jinja2 + htmx). Run from the project root, next to the API:

    uvicorn web.main:app --port 8001 --reload
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web import api

BASE_DIR = Path(__file__).parent
TOKEN_COOKIE = "token"

app = FastAPI(title="SupportDesk web")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class LoginRequired(Exception):
    pass


@app.exception_handler(LoginRequired)
async def to_login(request: Request, exc: LoginRequired):
    # A plain redirect inside an htmx request would load the login page into the panel
    # being updated; HX-Redirect makes htmx navigate the whole page instead.
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": "/login"})
    return RedirectResponse("/login", status_code=303)


async def get_user(request: Request) -> dict:
    token = request.cookies.get(TOKEN_COOKIE)
    if not token:
        raise LoginRequired
    try:
        user = await api.me(token)
    except api.ApiError:
        raise LoginRequired  # expired or invalid token
    user["token"] = token
    return user


User = Annotated[dict, Depends(get_user)]


def home_for(user: dict) -> str:
    return "/portal" if user["role"] == "customer" else "/inbox"


@app.get("/")
async def home(user: User):
    return RedirectResponse(home_for(user), status_code=303)


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.post("/login")
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


@app.post("/register")
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


@app.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(TOKEN_COOKIE)
    return response


@app.get("/portal")
async def portal(request: Request, user: User):
    if user["role"] != "customer":
        return RedirectResponse(home_for(user), status_code=303)
    return templates.TemplateResponse(request, "portal.html", {"user": user})


# --- agent inbox ---

# (name in the URL, label, ticket status it shows). The first three need an agent's action.
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


def age(created_at: str) -> str:
    """'12 min ago' from the API's timestamp (UTC, without a timezone)."""
    minutes = int((datetime.now(UTC).replace(tzinfo=None) - datetime.fromisoformat(created_at)).total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 24 * 60:
        return f"{minutes // 60} h ago"
    return f"{minutes // (24 * 60)} d ago"


MOOD = {"angry": "😠", "negative": "🙁", "neutral": "😐", "positive": "🙂"}
templates.env.filters["age"] = age
templates.env.filters["mood"] = lambda sentiment: MOOD.get(sentiment, "")


def agent_only(user: dict):
    # For the htmx partials; the full /inbox page redirects customers to their portal instead.
    if user["role"] == "customer":
        raise HTTPException(status_code=403, detail="Agents only")


async def load_tickets(user: dict, view: str, q: str) -> list[dict]:
    try:
        if view == "review":
            # The review queue is already sorted the way agents work: urgent first, then oldest.
            tickets = await api.review_queue(user["token"])
            q = q.lower()
            return [t for t in tickets if q in t["subject"].lower() or q in t["body"].lower()]
        return await api.list_tickets(user["token"], status=VIEW_STATUS.get(view), search=q)
    except api.ApiError as error:
        if error.status_code == 401:
            raise LoginRequired
        raise


@app.get("/inbox")
async def inbox(request: Request, user: User, view: str = "review", q: str = ""):
    if user["role"] == "customer":
        return RedirectResponse(home_for(user), status_code=303)
    counts = await api.ticket_counts(user["token"])
    context = {
        "user": user,
        "views": VIEWS,
        "counts": counts,
        "total": sum(counts.values()),
        "view": view,
        "q": q,
        "tickets": await load_tickets(user, view, q),
    }
    return templates.TemplateResponse(request, "inbox.html", context)


@app.get("/inbox/list")
async def inbox_list(request: Request, user: User, view: str = "review", q: str = ""):
    """Just the ticket list, for htmx: search-as-you-type and the periodic refresh swap only this."""
    agent_only(user)
    context = {"tickets": await load_tickets(user, view, q), "view": view}
    return templates.TemplateResponse(request, "_ticket_list.html", context)
