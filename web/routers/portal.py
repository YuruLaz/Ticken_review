"""Customer pages: new request form, My requests, and one request's conversation."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from web import api
from web.dependencies import User, home_for
from web.templating import templates

router = APIRouter(prefix="/portal")

# Shown as the subject choices. Only a hint: the AI still classifies every ticket itself.
TOPICS = ["Billing or payment", "Order and shipping", "Account and login", "Technical problem", "General question"]


async def render_portal(request: Request, user: dict, **context):
    tickets = await api.list_tickets(user["token"])
    # Spam is hidden rather than labelled: telling a sender "marked as spam" helps nobody.
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
