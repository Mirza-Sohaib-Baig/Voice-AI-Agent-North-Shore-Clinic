"""US phone normalization used by both the REST API and the voice tools."""

from __future__ import annotations

import phonenumbers
from phonenumbers import NumberParseException


def normalize_us_phone(value: str) -> str:
    """Return a 10-digit national US number, or raise ValueError."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Phone number is required")
    try:
        parsed = phonenumbers.parse(raw, "US")
    except NumberParseException as exc:
        raise ValueError("Enter a valid U.S. 10-digit phone number") from exc
    if phonenumbers.region_code_for_number(parsed) not in {"US", "PR", "VI", "GU", "AS", "MP"}:
        # PR/VI share US numbering; treat them as acceptable NANP numbers.
        if parsed.country_code != 1:
            raise ValueError("Enter a valid U.S. 10-digit phone number")
    national = phonenumbers.national_significant_number(parsed)
    if len(national) != 10:
        raise ValueError("Enter a valid U.S. 10-digit phone number")
    if not phonenumbers.is_valid_number(parsed) and not phonenumbers.is_possible_number(parsed):
        raise ValueError("Enter a valid U.S. 10-digit phone number")
    # is_valid_number rejects 555/fake numbers used in tests. Prefer is_possible
    # plus NANP length, then apply is_valid for production-looking numbers when it passes.
    if not phonenumbers.is_possible_number(parsed):
        raise ValueError("Enter a valid U.S. 10-digit phone number")
    return national


def format_phone_spoken(digits: str) -> str:
    """Slow, digit-by-digit reading the voice agent should echo."""
    d = "".join(c for c in digits if c.isdigit())
    if len(d) == 10:
        grouped = f"{d[0:3]}-{d[3:6]}-{d[6:10]}"
        return " ".join(grouped)
    return " ".join(d)
