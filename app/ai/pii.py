import re

CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
PHONE = re.compile(r"\+?\d(?:[ ()-]*\d){8,14}")


def mask_card(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group())
    return f"{digits[:4]} **** **** {digits[-4:]}"


def mask_pii(text: str) -> str:
    """Hides card and phone numbers. Cards first: a card number would also match the phone pattern."""
    text = CARD.sub(mask_card, text)
    return PHONE.sub("[phone number]", text)
