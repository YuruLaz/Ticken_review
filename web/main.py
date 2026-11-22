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


# --- customer portal ---

# Customers see two states only; the internal ones (awaiting_review, failed, escalated...)
# all mean "a person or the AI is still working on it" from their side.
def customer_status(status: str) -> str:
    return "Answered" if status == "replied" else "We're on it"


templates.env.filters["customer_status"] = customer_status


# Shown as the subject choices. Only a hint: the AI still classifies every ticket itself.
TOPICS = ["Billing or payment", "Order and shipping", "Account and login", "Technical problem", "General question"]


async def render_portal(request: Request, user: dict, **context):
    tickets = await api.list_tickets(user["token"])
    # Spam is hidden rather than labelled: telling a sender "marked as spam" helps nobody.
    tickets = [t for t in tickets if t["status"] != "spam"]
    context |= {"user": user, "tickets": tickets, "topics": TOPICS}
    return templates.TemplateResponse(request, "portal.html", context)


@app.get("/portal")
async def portal(request: Request, user: User, sent: int | None = None):
    if user["role"] != "customer":
        return RedirectResponse(home_for(user), status_code=303)
    return await render_portal(request, user, sent=sent)


@app.post("/portal/tickets")
async def create_ticket(
    request: Request,
    user: User,
    topic: Annotated[str, Form()],
    body: Annotated[str, Form()],
    subject: Annotated[str | None, Form()] = None,  # only sent when the topic is "other"
):
    if topic != "other":
        subject = topic
    try:
        ticket = await api.create_ticket(user["token"], subject, body)
    except api.ApiError as error:
        # Re-render with what they typed, so a failed send doesn't lose a long message.
        return await render_portal(request, user, error=str(error), topic=topic, subject=subject, body=body)
    # Redirect after POST: a browser refresh then reloads the page instead of resending the form.
    return RedirectResponse(f"/portal?sent={ticket['id']}", status_code=303)


async def render_ticket(request: Request, user: dict, ticket_id: int, **context):
    ticket = await api.get_ticket(user["token"], ticket_id)
    context |= {"user": user, "ticket": ticket}
    return templates.TemplateResponse(request, "portal_ticket.html", context)


@app.get("/portal/tickets/{ticket_id}")
async def portal_ticket(request: Request, user: User, ticket_id: int):
    return await render_ticket(request, user, ticket_id)


@app.post("/portal/tickets/{ticket_id}/messages")
async def portal_reply(request: Request, user: User, ticket_id: int, body: Annotated[str, Form()]):
    try:
        await api.add_message(user["token"], ticket_id, body)
    except api.ApiError as error:
        return await render_ticket(request, user, ticket_id, error=str(error), body=body)
    return RedirectResponse(f"/portal/tickets/{ticket_id}", status_code=303)


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


# --- agent workspace (right pane) ---

templates.env.filters["score"] = lambda value: "–" if value is None else f"{value:.2f}"


async def render_workspace(request: Request, user: dict, ticket_id: int, **context):
    agent_only(user)
    try:
        context |= await api.review_detail(user["token"], ticket_id)
    except api.ApiError as error:
        if error.status_code != 404:
            raise
        # No triage run saved yet (still new, or failed before the end): no AI panel.
        context |= {"ticket": await api.get_ticket(user["token"], ticket_id), "run": None}
    return templates.TemplateResponse(request, "_workspace.html", context)


async def after_action(request: Request, user: dict, ticket_id: int, call):
    """Run one API action, then re-render the pane: with the error, or with the new state."""
    try:
        await call
    except api.ApiError as error:
        return await render_workspace(request, user, ticket_id, error=str(error))
    response = await render_workspace(request, user, ticket_id)
    # The ticket probably moved to another view; this event makes the list refresh now.
    response.headers["HX-Trigger"] = "ticketsChanged"
    return response


@app.get("/inbox/tickets/{ticket_id}")
async def workspace(request: Request, user: User, ticket_id: int):
    return await render_workspace(request, user, ticket_id)


def same_text(a: str, b: str) -> bool:
    # Browsers send textarea line breaks as \r\n, so compare without that difference.
    return a.replace("\r\n", "\n").strip() == b.replace("\r\n", "\n").strip()


@app.post("/inbox/tickets/{ticket_id}/decision")
async def decision(
    request: Request,
    user: User,
    ticket_id: int,
    action: Annotated[str, Form()],
    reply: Annotated[str, Form()] = "",
    draft: Annotated[str, Form()] = "",
    note: Annotated[str, Form()] = "",
):
    # One "Send reply" button for the agent; the API wants to know whether the draft was changed.
    if action == "approve" and not same_text(reply, draft):
        action = "edit"
    edited_reply = reply if action == "edit" else None
    call = api.decide(user["token"], ticket_id, action, edited_reply, note or None)
    return await after_action(request, user, ticket_id, call)


@app.post("/inbox/tickets/{ticket_id}/retriage")
async def retriage(request: Request, user: User, ticket_id: int):
    return await after_action(request, user, ticket_id, api.retriage(user["token"], ticket_id))


@app.post("/inbox/tickets/{ticket_id}/reply")
async def agent_reply(request: Request, user: User, ticket_id: int, body: Annotated[str, Form()]):
    return await after_action(request, user, ticket_id, api.add_message(user["token"], ticket_id, body))
