from dataclasses import dataclass

# Measured on the seeded KB with gemini-embedding-001: covered questions 0.64-0.73, uncovered 0.58-0.62.
MIN_KB_SCORE = 0.65

# Starting guesses, not measured values: conservative so that doubtful tickets go to a human.
MIN_CLASSIFICATION_CONFIDENCE = 0.75
MIN_DRAFT_CONFIDENCE = 0.80

# Money and account access: a wrong auto-reply here is costly, however confident the model is.
ALWAYS_REVIEW_CATEGORIES = {"billing", "account"}


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
    # Collect every reason instead of stopping at the first one, so the agent sees the full picture.
    reasons = []

    if priority == "urgent":
        reasons.append("urgent priority")
    if sentiment == "angry":
        reasons.append("angry customer")
    if category in ALWAYS_REVIEW_CATEGORIES:
        reasons.append(f"{category} tickets are always reviewed")

    # Measured similarity: a low score means the draft has no KB article to rely on.
    if best_kb_score < MIN_KB_SCORE:
        reasons.append("no matching KB article")
    reasons.extend(f"quality issue: {issue}" for issue in quality_issues)

    # Self-reported by the LLM, so it's the least trusted signal and only a final filter.
    if classification_confidence < MIN_CLASSIFICATION_CONFIDENCE:
        reasons.append("low classification confidence")
    if draft_confidence < MIN_DRAFT_CONFIDENCE:
        reasons.append("low draft confidence")

    if reasons:
        return RouteDecision("human_review", reasons)
    return RouteDecision("auto_send", [])
