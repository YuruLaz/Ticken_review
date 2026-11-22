"""The web app's only way to the backend: every call goes to the FastAPI API over HTTP,
so roles and business rules are enforced in one place (the API)."""

import os

import httpx

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


class ApiError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _message(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, str):
        return detail
    # 422 details: one per invalid field.
    if isinstance(detail, list):
        return "; ".join(error["msg"] for error in detail)
    return f"Request failed ({response.status_code})"


async def request(method: str, path: str, token: str | None = None, **kwargs):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        async with httpx.AsyncClient(base_url=API_URL, timeout=30) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
    except httpx.HTTPError:
        raise ApiError(503, "Can't reach the API. Is it running?")
    if response.is_error:
        raise ApiError(response.status_code, _message(response))
    return response.json()


async def login(email: str, password: str) -> str:
    # OAuth2 login: form with username.
    data = {"username": email, "password": password}
    return (await request("POST", "/auth/login", data=data))["access_token"]


async def register(email: str, full_name: str, password: str) -> dict:
    payload = {"email": email, "full_name": full_name, "password": password}
    return await request("POST", "/auth/register", json=payload)


async def me(token: str) -> dict:
    return await request("GET", "/auth/me", token)


async def list_tickets(token: str, **filters) -> list[dict]:
    # Skip unset filters; empty matches nothing.
    params = {key: value for key, value in filters.items() if value}
    return await request("GET", "/tickets", token, params=params)


async def create_ticket(token: str, subject: str, body: str) -> dict:
    return await request("POST", "/tickets", token, json={"subject": subject, "body": body})


async def ticket_counts(token: str) -> dict[str, int]:
    return await request("GET", "/tickets/counts", token)


async def review_queue(token: str) -> list[dict]:
    return await request("GET", "/review/queue", token)


async def get_ticket(token: str, ticket_id: int) -> dict:
    return await request("GET", f"/tickets/{ticket_id}", token)


async def add_message(token: str, ticket_id: int, body: str) -> dict:
    return await request("POST", f"/tickets/{ticket_id}/messages", token, json={"body": body})


async def review_detail(token: str, ticket_id: int) -> dict:
    return await request("GET", f"/review/{ticket_id}", token)


async def decide(token: str, ticket_id: int, action: str, edited_reply: str | None, note: str | None) -> dict:
    payload = {"action": action, "edited_reply": edited_reply, "note": note}
    return await request("POST", f"/review/{ticket_id}/decision", token, json=payload)


async def retriage(token: str, ticket_id: int) -> dict:
    return await request("POST", f"/review/{ticket_id}/retriage", token)
