"""Customer pages: new request form, My requests, and one request's conversation."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from web import api
from web.dependencies import User, home_for
from web.templating import templates

router = APIRouter(prefix="/portal")

# Subject choices; AI still classifies.
TOPICS = ["Billing or payment", "Order and shipping", "Account and login", "Technical problem", "General question"]


async def render_portal(request: Request, user: dict, **context):
    tickets = await api.list_tickets(user["token"])
    # Hide spam from customers.
    tickets = [t for t in tickets if t["status"] != "spam"]
    context |= {"user": user, "tickets": tickets, "topics": TOPICS}
    return templates.TemplateResponse(request, "portal.html", context)


@router.get("")
async def portal(request: Request, user: User, sent: int | None = None):
    if user["role"] != "customer":
        return RedirectResponse(home_for(user), status_code=303)
    return await render_portal(request, user, sent=sent)


@router.post("/tickets")
async def create_ticket(
    request: Request,
    user: User,
    topic: Annotated[str, Form()],
    body: Annotated[str, Form()],
    subject: Annotated[str | None, Form()] = None,  # only for topic "other"
):
    if topic != "other":
        subject = topic
    try:
        ticket = await api.create_ticket(user["token"], subject, body)
    except api.ApiError as error:
        # Keep typed text on failure.
        return await render_portal(request, user, error=str(error), topic=topic, subject=subject, body=body)
    # Post/Redirect/Get: refresh won't resend.
    return RedirectResponse(f"/portal?sent={ticket['id']}", status_code=303)


async def render_ticket(request: Request, user: dict, ticket_id: int, **context):
    ticket = await api.get_ticket(user["token"], ticket_id)
    context |= {"user": user, "ticket": ticket}
    return templates.TemplateResponse(request, "portal_ticket.html", context)


@router.get("/tickets/{ticket_id}")
async def portal_ticket(request: Request, user: User, ticket_id: int):
    return await render_ticket(request, user, ticket_id)


@router.post("/tickets/{ticket_id}/messages")
async def portal_reply(request: Request, user: User, ticket_id: int, body: Annotated[str, Form()]):
    try:
        await api.add_message(user["token"], ticket_id, body)
    except api.ApiError as error:
        return await render_ticket(request, user, ticket_id, error=str(error), body=body)
    return RedirectResponse(f"/portal/tickets/{ticket_id}", status_code=303)
