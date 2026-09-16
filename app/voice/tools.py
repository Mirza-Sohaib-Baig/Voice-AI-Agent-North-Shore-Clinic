"""Vapi custom-tool implementations.

Each handler returns a dict that is JSON-serialized into `result`.
On validation failure we return field-level errors so the LLM re-prompts
only the bad field instead of restarting the whole intake.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.exceptions import AppError, ValidationFailed
from app.models.call_log import CallOutcome
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.call_log_service import upsert_call_log
from app.services.patient_service import PatientService, pydantic_errors
from app.services.phone import normalize_us_phone

log = structlog.get_logger(__name__)

MOCK_SLOTS = (
    "Tuesday 9:00 AM",
    "Tuesday 2:30 PM",
    "Wednesday 11:15 AM",
)


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _identity(patient) -> dict[str, Any]:
    """Fields the model may use to confirm who they are — not the full chart."""
    return {
        "patient_id": str(patient.patient_id),
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "date_of_birth": _iso(patient.date_of_birth),
    }


def lookup_patient_by_phone(db: Session, arguments: dict[str, Any], call_id: str | None) -> dict:
    phone_raw = arguments.get("phone_number") or arguments.get("phoneNumber") or ""
    last_name = (arguments.get("last_name") or arguments.get("lastName") or "").strip()
    dob_raw = arguments.get("date_of_birth") or arguments.get("dateOfBirth") or ""
    svc = PatientService(db)

    if phone_raw:
        try:
            normalized = normalize_us_phone(str(phone_raw))
        except ValueError as exc:
            return {
                "status": "invalid",
                "errors": [{"field": "phone_number", "message": str(exc)}],
            }
        patient = svc.find_by_phone(normalized)
        if patient is None:
            return {"status": "not_found", "phone_number": normalized}
        return {
            "status": "found",
            "patient": _identity(patient),
            "prompt": (
                f"It looks like we already have a record for {patient.first_name} {patient.last_name}. "
                "Would you like to update your information instead?"
            ),
        }

    if last_name and dob_raw:
        try:
            matches = svc.list(last_name=last_name, date_of_birth=str(dob_raw))
        except ValidationFailed as exc:
            return {"status": "invalid", "errors": [{"field": "date_of_birth", "message": exc.message}]}
        if not matches:
            return {"status": "not_found", "last_name": last_name}
        if len(matches) > 1:
            return {
                "status": "ambiguous",
                "count": len(matches),
                "message": "More than one chart matched. Ask for the callback phone number.",
            }
        patient = matches[0]
        return {
            "status": "found",
            "patient": _identity(patient),
            "prompt": (
                f"It looks like we already have a record for {patient.first_name} {patient.last_name}. "
                "Would you like to update your information instead?"
            ),
        }

    return {
        "status": "invalid",
        "errors": [
            {
                "field": "phone_number",
                "message": "Pass phone_number, or last_name and date_of_birth together.",
            }
        ],
    }


def save_patient_registration(db: Session, arguments: dict[str, Any], call_id: str | None) -> dict:
    payload = dict(arguments)
    if call_id and not payload.get("source_call_id"):
        payload["source_call_id"] = call_id
    try:
        parsed = PatientCreate.model_validate(payload)
    except ValidationError as exc:
        return {"status": "invalid", "errors": pydantic_errors(exc)}

    svc = PatientService(db)
    try:
        patient = svc.create(parsed)
    except AppError as exc:
        if exc.code == "conflict":
            return {
                "status": "duplicate",
                "message": exc.message,
                "errors": exc.details,
            }
        log.exception("save_patient_failed", payload=payload)
        return {
            "status": "error",
            "message": "The record could not be saved. Apologize and offer a callback.",
        }

    if call_id:
        upsert_call_log(
            db,
            vapi_call_id=call_id,
            outcome=CallOutcome.REGISTERED,
            patient_id=patient.patient_id,
        )

    log.info(
        "voice_registration_saved",
        patient_id=str(patient.patient_id),
        call_id=call_id,
        payload=parsed.model_dump(mode="json"),
    )
    return {
        "status": "ok",
        "patient_id": str(patient.patient_id),
        "first_name": patient.first_name,
        "confirmation": f"You're all set, {patient.first_name}.",
    }


def update_patient_record(db: Session, arguments: dict[str, Any], call_id: str | None) -> dict:
    raw_id = arguments.get("patient_id") or arguments.get("patientId")
    if not raw_id:
        return {
            "status": "invalid",
            "errors": [{"field": "patient_id", "message": "patient_id is required"}],
        }
    try:
        patient_id = uuid.UUID(str(raw_id))
    except ValueError:
        return {
            "status": "invalid",
            "errors": [{"field": "patient_id", "message": "patient_id must be a UUID"}],
        }

    fields = {k: v for k, v in arguments.items() if k not in {"patient_id", "patientId", "call_id"}}
    try:
        parsed = PatientUpdate.model_validate(fields)
    except ValidationError as exc:
        return {"status": "invalid", "errors": pydantic_errors(exc)}

    svc = PatientService(db)
    try:
        patient = svc.update(patient_id, parsed)
    except AppError as exc:
        return {"status": exc.code, "message": exc.message, "errors": exc.details}

    if call_id:
        upsert_call_log(
            db,
            vapi_call_id=call_id,
            outcome=CallOutcome.UPDATED,
            patient_id=patient.patient_id,
        )
    return {
        "status": "ok",
        "patient_id": str(patient.patient_id),
        "first_name": patient.first_name,
        "updated_fields": list(parsed.model_dump(exclude_unset=True).keys()),
    }


def schedule_appointment(db: Session, arguments: dict[str, Any], call_id: str | None) -> dict:
    """Mock slots — bonus. No calendar backend."""
    preferred = (arguments.get("preferred_window") or arguments.get("preferredWindow") or "").strip()
    raw_id = arguments.get("patient_id") or arguments.get("patientId")
    patient_id = None
    if raw_id:
        try:
            patient_id = uuid.UUID(str(raw_id))
            PatientService(db).get(patient_id)
        except Exception:
            patient_id = None

    return {
        "status": "ok",
        "patient_id": str(patient_id) if patient_id else None,
        "preferred_window": preferred or None,
        "available_slots": MOCK_SLOTS,
        "note": "These are mock clinic slots for the assessment; nothing is booked in a real EHR.",
    }


HANDLERS = {
    "lookup_patient_by_phone": lookup_patient_by_phone,
    "save_patient_registration": save_patient_registration,
    "update_patient_record": update_patient_record,
    "schedule_appointment": schedule_appointment,
}

# Vapi default tools are executed on their side. Acknowledge if they are posted here
# so a mis-routed endCall cannot block hang-up.
_VAPI_NATIVE = {"endCall", "end_call"}


def dispatch(db: Session, name: str, arguments: dict[str, Any], call_id: str | None) -> str:
    if name in _VAPI_NATIVE:
        return json.dumps({"status": "ok"})
    handler = HANDLERS.get(name)
    if handler is None:
        result = {"status": "error", "message": f"Unknown tool '{name}'"}
    else:
        try:
            result = handler(db, arguments, call_id)
        except Exception:
            log.exception("tool_handler_crash", tool=name, arguments=arguments)
            result = {
                "status": "error",
                "message": "The record could not be saved. Apologize and offer a callback.",
            }
    return json.dumps(result)
