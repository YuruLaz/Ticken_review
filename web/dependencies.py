"""Who is logged in: the token cookie, the current-user dependency and role helpers."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from web import api

TOKEN_COOKIE = "token"


class LoginRequired(Exception):
    """Raised anywhere; the handler in main.py turns it into a redirect to the login page."""


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


def agent_only(user: dict):
    # For the htmx partials; the full /inbox page redirects customers to their portal instead.
    if user["role"] == "customer":
        raise HTTPException(status_code=403, detail="Agents only")
