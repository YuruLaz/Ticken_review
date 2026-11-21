from app.ai.routing import route

# A ticket that passes every rule. Each test changes only what it's about.
GOOD = dict(
    priority="low",
    sentiment="neutral",
    category="shipping",
    classification_confidence=0.95,
    draft_confidence=0.95,
    best_kb_score=0.90,
    quality_issues=[],
)


def test_good_ticket_is_auto_sent():
    assert route(**GOOD).action == "auto_send"


def test_urgent_goes_to_human():
    assert route(**{**GOOD, "priority": "urgent"}).action == "human_review"


def test_high_goes_to_human():
    assert route(**{**GOOD, "priority": "high"}).action == "human_review"


def test_medium_can_be_auto_sent():
    assert route(**{**GOOD, "priority": "medium"}).action == "auto_send"


def test_angry_goes_to_human():
    assert route(**{**GOOD, "sentiment": "angry"}).action == "human_review"


def test_billing_goes_to_human():
    assert route(**{**GOOD, "category": "billing"}).action == "human_review"


def test_account_follows_normal_rules():
    # Spec demo: "how do I reset my password?" (account/low) is auto-replied.
    assert route(**{**GOOD, "category": "account"}).action == "auto_send"


def test_low_kb_score_goes_to_human():
    assert route(**{**GOOD, "best_kb_score": 0.5}).action == "human_review"


def test_all_reasons_are_reported():
    decision = route(**{**GOOD, "priority": "urgent", "sentiment": "angry"})
    assert decision.reasons == ["urgent priority", "angry customer"]
