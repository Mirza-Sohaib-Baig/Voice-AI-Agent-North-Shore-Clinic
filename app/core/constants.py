"""Shared constants for the patient demographic model."""

from __future__ import annotations

# 50 states + District of Columbia. Territories omitted on purpose — the spec
# asks for a 2-letter U.S. state abbreviation.
US_STATES: frozenset[str] = frozenset(
    {
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
    }
)

NAME_PATTERN = r"^[A-Za-z][A-Za-z' \-]{0,49}$"
ZIP_PATTERN = r"^\d{5}(-\d{4})?$"
MAX_AGE_YEARS = 120
