"""Shared validators: names, dates, ZIP, state. Imported by Pydantic schemas."""

from __future__ import annotations

import re
from datetime import date, datetime

from app.core.constants import MAX_AGE_YEARS, NAME_PATTERN, US_STATES, ZIP_PATTERN
from app.services.phone import normalize_us_phone

_NAME_RE = re.compile(NAME_PATTERN)
_ZIP_RE = re.compile(ZIP_PATTERN)

_DATE_FORMATS = (
    "%m/%d/%Y",
    "%Y-%m-%d",
    "%m-%d-%Y",
    "%B %d %Y",
    "%B %d, %Y",
    "%b %d %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%Y/%m/%d",
)


def blank_to_none(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def normalize_name(value: str, *, field: str = "name") -> str:
    cleaned = " ".join((value or "").strip().split())
    if not cleaned:
        raise ValueError(f"{field} is required")
    if len(cleaned) > 50:
        raise ValueError(f"{field} must be 1–50 characters")
    if not _NAME_RE.match(cleaned):
        raise ValueError(
            f"{field} may only contain letters, spaces, hyphens, and apostrophes"
        )
    return cleaned


def parse_date_of_birth(value: object) -> date:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        dob = value
    elif isinstance(value, str):
        raw = value.strip()
        # Spoken "March fifteenth nineteen ninety" sometimes arrives as digits with ordinals.
        raw = (
            raw.replace("st,", ",")
            .replace("nd,", ",")
            .replace("rd,", ",")
            .replace("th,", ",")
            .replace("st ", " ")
            .replace("nd ", " ")
            .replace("rd ", " ")
            .replace("th ", " ")
        )
        dob = None
        for fmt in _DATE_FORMATS:
            try:
                dob = datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                continue
        if dob is None:
            raise ValueError("Date of birth must be a valid date (MM/DD/YYYY)")
    else:
        raise ValueError("Date of birth must be a valid date (MM/DD/YYYY)")

    today = date.today()
    if dob > today:
        raise ValueError("Date of birth cannot be in the future")
    if dob < date(today.year - MAX_AGE_YEARS, today.month, today.day):
        raise ValueError(f"Date of birth cannot be more than {MAX_AGE_YEARS} years ago")
    return dob


def normalize_state(value: str) -> str:
    cleaned = (value or "").strip().upper()
    aliases = {
        "CALIFORNIA": "CA",
        "NEW YORK": "NY",
        "TEXAS": "TX",
        "FLORIDA": "FL",
        "WASHINGTON D.C.": "DC",
        "WASHINGTON DC": "DC",
        "DISTRICT OF COLUMBIA": "DC",
    }
    cleaned = aliases.get(cleaned, cleaned)
    if cleaned not in US_STATES:
        raise ValueError("State must be a valid 2-letter U.S. state abbreviation")
    return cleaned


def normalize_zip(value: str) -> str:
    cleaned = (value or "").strip()
    if not _ZIP_RE.match(cleaned):
        raise ValueError("ZIP code must be 5 digits or ZIP+4 (12345 or 12345-6789)")
    return cleaned


def normalize_phone(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Enter a valid U.S. 10-digit phone number")
    return normalize_us_phone(value)
