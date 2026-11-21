import re

# 13-19 digits, optionally grouped with spaces or dashes: the length range of payment card numbers.
CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
# 9-15 digits with optional +, spaces, dashes or brackets. 9 is the minimum on purpose: it keeps
# order numbers (8 digits, e.g. SN-20481937) and dates readable.
PHONE = re.compile(r"\+?\d(?:[ ()-]*\d){8,14}")


def mask_card(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group())
    return f"{digits[:4]} **** **** {digits[-4:]}"


def mask_pii(text: str) -> str:
    """Hides card and phone numbers. Cards first: a card number would also match the phone pattern."""
    # shortcut: regex only, so unusual formats slip through; switch to a PII library
    # (e.g. Microsoft Presidio) if real tickets show misses.
    text = CARD.sub(mask_card, text)
    return PHONE.sub("[phone number]", text)
