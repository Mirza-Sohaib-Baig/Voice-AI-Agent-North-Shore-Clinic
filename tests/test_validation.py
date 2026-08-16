"""Pydantic / phone / date validators without touching the database."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.patient import PatientCreate
from app.services.phone import normalize_us_phone
from app.services.validation import parse_date_of_birth


def _valid(**overrides):
    base = dict(
        first_name="Maria",
        last_name="O'Brien",
        date_of_birth="03/15/1990",
        sex="Female",
        phone_number="650-253-0000",
        address_line_1="1 Market St",
        city="San Francisco",
        state="CA",
        zip_code="94105",
    )
    base.update(overrides)
    return PatientCreate.model_validate(base)


def test_happy_path_normalizes():
    p = _valid(phone_number="(650) 253-0000", state="california", zip_code="94105-1234")
    assert p.phone_number == "6502530000"
    assert p.state == "CA"
    assert p.zip_code == "94105-1234"
    assert p.date_of_birth == date(1990, 3, 15)
    assert p.preferred_language == "English"


def test_hyphen_apostrophe_names():
    p = _valid(first_name="Mary-Jane", last_name="O'Connor")
    assert p.first_name == "Mary-Jane"
    assert p.last_name == "O'Connor"


def test_reject_digits_in_name():
    with pytest.raises(ValidationError):
        _valid(first_name="Maria2")


def test_future_dob_rejected():
    tomorrow = (date.today() + timedelta(days=1)).strftime("%m/%d/%Y")
    with pytest.raises(ValidationError):
        _valid(date_of_birth=tomorrow)
    with pytest.raises(ValueError):
        parse_date_of_birth(tomorrow)


def test_spoken_month_dob():
    assert parse_date_of_birth("March 15, 1990") == date(1990, 3, 15)


def test_three_digit_phone_rejected():
    with pytest.raises(ValueError):
        normalize_us_phone("555")
    with pytest.raises(ValidationError):
        _valid(phone_number="555")


def test_invalid_zip():
    with pytest.raises(ValidationError):
        _valid(zip_code="ABCDE")


def test_invalid_state():
    with pytest.raises(ValidationError):
        _valid(state="ZZ")


def test_sex_aliases():
    assert _valid(sex="prefer not to say").sex.value == "Decline to Answer"
    assert _valid(sex="male").sex.value == "Male"


def test_blank_optional_email_becomes_none():
    assert _valid(email="").email is None
