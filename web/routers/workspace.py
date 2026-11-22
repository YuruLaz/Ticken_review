"""Agent workspace (right pane): one ticket, its AI analysis, and the agent's actions.
Every route returns the _workspace.html partial, which htmx swaps into #workspace."""

from typing import Annotated

from fastapi import APIRouter, Form, Request

from web import api
from web.dependencies import User, agent_only
from web.routers.inbox import load_tickets
from web.templating import templates

router = APIRouter(prefix="/inbox/tickets")


async def render_workspace(request: Request, user: dict, ticket_id: int, **context):
    agent_only(user)
    try:
        context |= await api.review_detail(user["token"], ticket_id)
    except api.ApiError as error:
        if error.status_code != 404:
            raise
        # Not triaged yet: no AI panel.
        context |= {"ticket": await api.get_ticket(user["token"], ticket_id), "run": None}
    return templates.TemplateResponse(request, "_workspace.html", context)


async def after_action(request: Request, user: dict, ticket_id: int, call, done: str):
    """Run one API action. On error stay on the ticket; on success open the view's next one."""
    try:
        await call
    except api.ApiError as error:
        return await render_workspace(request, user, ticket_id, error=str(error))
    # The forms send the inbox's view and search (hx-include="#filters").
    form = await request.form()
    tickets = await load_tickets(user, form.get("view", "review"), form.get("q", ""))
    following = next((t for t in tickets if t["id"] != ticket_id), None)
    notice = f"Ticket #{ticket_id}: {done}."
    if following:
        response = await render_workspace(request, user, following["id"], notice=notice)
    else:
        response = templates.TemplateResponse(request, "_workspace_empty.html", {"notice": notice})
    # Tell the list to refresh.
    response.headers["HX-Trigger"] = "ticketsChanged"
    return response


@router.get("/{ticket_id}")
async def workspace(request: Request, user: User, ticket_id: int):
    return await render_workspace(request, user, ticket_id)


def same_text(a: str, b: str) -> bool:
    # Ignore \r\n vs \n differences.
    return a.replace("\r\n", "\n").strip() == b.replace("\r\n", "\n").strip()


@router.post("/{ticket_id}/decision")
async def decision(
    request: Request,
    user: User,
    ticket_id: int,
    action: Annotated[str, Form()],
    reply: Annotated[str, Form()] = "",
    draft: Annotated[str, Form()] = "",
    note: Annotated[str, Form()] = "",
):
    # Unchanged draft is approve, else edit.
    if action == "approve" and not same_text(reply, draft):
        action = "edit"
    edited_reply = reply if action == "edit" else None
    call = api.decide(user["token"], ticket_id, action, edited_reply, note or None)
    done = {"approve": "reply sent", "edit": "edited reply sent", "reject": "draft rejected, moved to Escalated"}
    return await after_action(request, user, ticket_id, call, done[action])


@router.post("/{ticket_id}/retriage")
async def retriage(request: Request, user: User, ticket_id: int):
    return await after_action(request, user, ticket_id, api.retriage(user["token"], ticket_id), "AI re-run started")


@router.post("/{ticket_id}/reply")
async def agent_reply(request: Request, user: User, ticket_id: int, body: Annotated[str, Form()]):
    return await after_action(request, user, ticket_id, api.add_message(user["token"], ticket_id, body), "reply sent")
