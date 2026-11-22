import re

# 13-19 digits: payment card lengths.
CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
# Min 9 digits keeps order numbers readable.
PHONE = re.compile(r"\+?\d(?:[ ()-]*\d){8,14}")


def mask_card(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group())
    return f"{digits[:4]} **** **** {digits[-4:]}"


def mask_pii(text: str) -> str:
    """Hides card and phone numbers. Cards first: a card number would also match the phone pattern."""
    # shortcut: regex only; try Presidio if misses.
    text = CARD.sub(mask_card, text)
    return PHONE.sub("[phone number]", text)
