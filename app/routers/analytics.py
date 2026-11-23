from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.dependencies import SessionDep, require_role
from app.models import Ticket, TriageRun, User

router = APIRouter(prefix="/analytics", tags=["analytics"])

Admin = Annotated[User, Depends(require_role("admin"))]


async def count_by(session, column) -> dict[str, int]:
    """{value: number of rows} for one column, e.g. {"billing": 4, "shipping": 2}."""
    query = select(column, func.count()).where(column.is_not(None)).group_by(column)
    return dict((await session.execute(query)).all())


def rate(part: int, total: int) -> float | None:
    return round(part / total, 3) if total else None


@router.get("/overview")
async def overview(user: Admin, session: SessionDep):
    return {
        "by_category": await count_by(session, Ticket.category),
        "by_priority": await count_by(session, Ticket.priority),
        "by_status": await count_by(session, Ticket.status),
    }


@router.get("/automation-rate")
async def automation_rate(user: Admin, session: SessionDep):
    routes = await count_by(session, TriageRun.route)
    auto, human = routes.get("auto_send", 0), routes.get("human_review", 0)
    return {"routes": routes, "automation_rate": rate(auto, auto + human)}


@router.get("/ai-accuracy")
async def ai_accuracy(user: Admin, session: SessionDep):
    """What agents did with the drafts sent to review."""
    query = (
        select(
            TriageRun.human_decision,
            func.count(),
            func.avg(TriageRun.draft_confidence),
        )
        .where(TriageRun.human_decision.is_not(None))
        .group_by(TriageRun.human_decision)
    )
    rows = (await session.execute(query)).all()
    decisions = {
        decision: {"count": count, "avg_draft_confidence": round(avg, 3) if avg is not None else None}
        for decision, count, avg in rows
    }
    reviewed = sum(d["count"] for d in decisions.values())
    approved = decisions.get("approve", {}).get("count", 0)
    return {"reviewed": reviewed, "decisions": decisions, "approval_rate": rate(approved, reviewed)}
