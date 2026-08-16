"""Patient create/update/read schemas. Voice tools reuse PatientCreate."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.core.constants import US_STATES
from app.models.patient import Sex
from app.services.validation import (
    blank_to_none,
    normalize_name,
    normalize_phone,
    normalize_state,
    normalize_zip,
    parse_date_of_birth,
)


def _sex_from_spoken(value: object) -> Sex:
    if isinstance(value, Sex):
        return value
    if not isinstance(value, str):
        raise ValueError("Sex is required")
    raw = value.strip().lower()
    mapping = {
        "male": Sex.MALE,
        "m": Sex.MALE,
        "man": Sex.MALE,
        "female": Sex.FEMALE,
        "f": Sex.FEMALE,
        "woman": Sex.FEMALE,
        "other": Sex.OTHER,
        "nonbinary": Sex.OTHER,
        "non-binary": Sex.OTHER,
        "decline": Sex.DECLINE_TO_ANSWER,
        "decline to answer": Sex.DECLINE_TO_ANSWER,
        "prefer not to say": Sex.DECLINE_TO_ANSWER,
        "prefer not to answer": Sex.DECLINE_TO_ANSWER,
    }
    if raw not in mapping:
        raise ValueError("Sex must be Male, Female, Other, or Decline to Answer")
    return mapping[raw]


class PatientBase(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    sex: Sex
    phone_number: str
    email: EmailStr | None = None
    address_line_1: str
    address_line_2: str | None = None
    city: str
    state: str
    zip_code: str
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str = "English"
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @field_validator("first_name")
    @classmethod
    def _first(cls, v: str) -> str:
        return normalize_name(v, field="first_name")

    @field_validator("last_name")
    @classmethod
    def _last(cls, v: str) -> str:
        return normalize_name(v, field="last_name")

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def _dob(cls, v: object) -> date:
        return parse_date_of_birth(v)

    @field_validator("sex", mode="before")
    @classmethod
    def _sex(cls, v: object) -> Sex:
        return _sex_from_spoken(v)

    @field_validator("phone_number", mode="before")
    @classmethod
    def _phone(cls, v: object) -> str:
        return normalize_phone(v)

    @field_validator("email", "address_line_2", "insurance_provider", "insurance_member_id",
                     "emergency_contact_name", mode="before")
    @classmethod
    def _empty(cls, v: object) -> object:
        return blank_to_none(v)

    @field_validator("emergency_contact_phone", mode="before")
    @classmethod
    def _emg_phone(cls, v: object) -> str | None:
        v = blank_to_none(v)
        if v is None:
            return None
        return normalize_phone(v)

    @field_validator("address_line_1")
    @classmethod
    def _addr1(cls, v: str) -> str:
        cleaned = " ".join((v or "").strip().split())
        if not cleaned:
            raise ValueError("address_line_1 is required")
        if len(cleaned) > 200:
            raise ValueError("address_line_1 is too long")
        return cleaned

    @field_validator("city")
    @classmethod
    def _city(cls, v: str) -> str:
        cleaned = " ".join((v or "").strip().split())
        if not cleaned or len(cleaned) > 100:
            raise ValueError("city must be 1–100 characters")
        return cleaned

    @field_validator("state", mode="before")
    @classmethod
    def _state(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("state is required")
        return normalize_state(v)

    @field_validator("zip_code")
    @classmethod
    def _zip(cls, v: str) -> str:
        return normalize_zip(v)

    @field_validator("preferred_language", mode="before")
    @classmethod
    def _lang(cls, v: object) -> str:
        v = blank_to_none(v)
        if v is None:
            return "English"
        return str(v).strip()[:50] or "English"

    @field_validator("insurance_member_id")
    @classmethod
    def _member_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        if not cleaned.replace("-", "").isalnum():
            raise ValueError("insurance_member_id must be alphanumeric")
        return cleaned[:64]


class PatientCreate(PatientBase):
    source_call_id: str | None = Field(default=None, max_length=64)


class PatientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    sex: Sex | None = None
    phone_number: str | None = None
    email: EmailStr | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _drop_blanks(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        return {k: blank_to_none(v) for k, v in data.items()}

    @field_validator("first_name")
    @classmethod
    def _first(cls, v: str | None) -> str | None:
        return None if v is None else normalize_name(v, field="first_name")

    @field_validator("last_name")
    @classmethod
    def _last(cls, v: str | None) -> str | None:
        return None if v is None else normalize_name(v, field="last_name")

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def _dob(cls, v: object) -> date | None:
        if v is None or v == "":
            return None
        return parse_date_of_birth(v)

    @field_validator("sex", mode="before")
    @classmethod
    def _sex(cls, v: object) -> Sex | None:
        if v is None or v == "":
            return None
        return _sex_from_spoken(v)

    @field_validator("phone_number", "emergency_contact_phone", mode="before")
    @classmethod
    def _phone(cls, v: object) -> str | None:
        if v is None or v == "":
            return None
        return normalize_phone(v)

    @field_validator("state", mode="before")
    @classmethod
    def _state(cls, v: object) -> str | None:
        if v is None or v == "":
            return None
        if not isinstance(v, str):
            raise ValueError("state is required")
        return normalize_state(v)

    @field_validator("zip_code")
    @classmethod
    def _zip(cls, v: str | None) -> str | None:
        return None if v is None else normalize_zip(v)

    @field_validator("address_line_1")
    @classmethod
    def _addr1(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = " ".join(v.strip().split())
        if not cleaned:
            raise ValueError("address_line_1 is required")
        return cleaned

    @field_validator("city")
    @classmethod
    def _city(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = " ".join(v.strip().split())
        if not cleaned or len(cleaned) > 100:
            raise ValueError("city must be 1–100 characters")
        return cleaned


class PatientRead(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    patient_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    source_call_id: str | None = None

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def _dob(cls, v: object) -> date:  # type: ignore[override]
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        return parse_date_of_birth(v)

    @field_validator("sex", mode="before")
    @classmethod
    def _sex(cls, v: object) -> Sex:  # type: ignore[override]
        if isinstance(v, Sex):
            return v
        return _sex_from_spoken(v)

    @field_validator("phone_number", "emergency_contact_phone", mode="before")
    @classmethod
    def _phone_passthrough(cls, v: object) -> str | None:  # type: ignore[override]
        if v is None or v == "":
            return None
        if isinstance(v, str) and len(v) == 10 and v.isdigit():
            return v
        return normalize_phone(v)

    @field_validator("state", mode="before")
    @classmethod
    def _state(cls, v: object) -> str:  # type: ignore[override]
        if isinstance(v, str) and v in US_STATES:
            return v
        if not isinstance(v, str):
            raise ValueError("state is required")
        return normalize_state(v)

    @field_validator("zip_code")
    @classmethod
    def _zip(cls, v: str) -> str:  # type: ignore[override]
        return v

    @field_validator("first_name")
    @classmethod
    def _first(cls, v: str) -> str:  # type: ignore[override]
        return v

    @field_validator("last_name")
    @classmethod
    def _last(cls, v: str) -> str:  # type: ignore[override]
        return v
