from dataclasses import dataclass

# Measured: covered 0.64-0.73, uncovered 0.58-0.62.
MIN_KB_SCORE = 0.65

# Unmeasured guesses, kept deliberately conservative.
MIN_CLASSIFICATION_CONFIDENCE = 0.75
MIN_DRAFT_CONFIDENCE = 0.80

# Money mistakes are costly: always human.
ALWAYS_REVIEW_CATEGORIES = {"billing"}

# Only low/medium may auto-send (spec 4.4).
HUMAN_PRIORITIES = {"high", "urgent"}


@dataclass
class RouteDecision:
    action: str  # "auto_send" or "human_review"
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
    # Collect all reasons for the agent.
    reasons = []

    if priority in HUMAN_PRIORITIES:
        reasons.append(f"{priority} priority")
    if sentiment == "angry":
        reasons.append("angry customer")
    if category in ALWAYS_REVIEW_CATEGORIES:
        reasons.append(f"{category} tickets are always reviewed")

    # Low score: no supporting KB article.
    if best_kb_score < MIN_KB_SCORE:
        reasons.append("no matching KB article")
    reasons.extend(f"quality issue: {issue}" for issue in quality_issues)

    # Self-reported by LLM, least trusted.
    if classification_confidence < MIN_CLASSIFICATION_CONFIDENCE:
        reasons.append("low classification confidence")
    if draft_confidence < MIN_DRAFT_CONFIDENCE:
        reasons.append("low draft confidence")

    if reasons:
        return RouteDecision("human_review", reasons)
    return RouteDecision("auto_send", [])
