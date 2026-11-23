"""The shared Jinja2 environment and the filters the templates use."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def age(created_at: str) -> str:
    """'12 min ago' from the API's timestamp (UTC, without a timezone)."""
    minutes = int((datetime.now(UTC).replace(tzinfo=None) - datetime.fromisoformat(created_at)).total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 24 * 60:
        return f"{minutes // 60} h ago"
    return f"{minutes // (24 * 60)} d ago"


def customer_status(status: str) -> str:
    return "Answered" if status == "replied" else "We're on it"


templates.env.filters["age"] = age
templates.env.filters["customer_status"] = customer_status
templates.env.filters["score"] = lambda value: "–" if value is None else f"{value:.2f}"
templates.env.filters["percent"] = lambda value: "–" if value is None else f"{value:.0%}"
