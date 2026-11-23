from dataclasses import dataclass

MIN_KB_SCORE = 0.65

MIN_CLASSIFICATION_CONFIDENCE = 0.75
MIN_DRAFT_CONFIDENCE = 0.80

ALWAYS_REVIEW_CATEGORIES = {"billing"}

HUMAN_PRIORITIES = {"high", "urgent"}


@dataclass
class RouteDecision:
    action: str
    reasons: list[str]


def route(
    priority: str,
    sentiment: str,
    category: str,
    classification_confidence: float,
    draft_confidence: float,
    best_kb_score: float,
    quality_issues: list[str],
) -> RouteDecision:
    reasons = []

    if priority in HUMAN_PRIORITIES:
        reasons.append(f"{priority} priority")
    if sentiment == "angry":
        reasons.append("angry customer")
    if category in ALWAYS_REVIEW_CATEGORIES:
        reasons.append(f"{category} tickets are always reviewed")

    if best_kb_score < MIN_KB_SCORE:
        reasons.append("no matching KB article")
    reasons.extend(f"quality issue: {issue}" for issue in quality_issues)

    if classification_confidence < MIN_CLASSIFICATION_CONFIDENCE:
        reasons.append("low classification confidence")
    if draft_confidence < MIN_DRAFT_CONFIDENCE:
        reasons.append("low draft confidence")

    if reasons:
        return RouteDecision("human_review", reasons)
    return RouteDecision("auto_send", [])
