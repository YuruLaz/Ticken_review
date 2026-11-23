from app.ai.pipeline.pii import mask_pii


def test_card_keeps_first_and_last_four_digits():
    assert mask_pii("My card 5167 4401 2233 1234 was charged") == "My card 5167 **** **** 1234 was charged"


def test_card_without_spaces():
    assert mask_pii("card 5167440122331234") == "card 5167 **** **** 1234"


def test_phone_numbers_are_hidden():
    assert mask_pii("Call me at +995 599 12 34 56") == "Call me at [phone number]"
    assert mask_pii("or 555-123-4567") == "or [phone number]"


def test_order_numbers_and_dates_stay_readable():
    text = "Order SN-20481937 from 2026-11-20 costs $1299"
    assert mask_pii(text) == text
