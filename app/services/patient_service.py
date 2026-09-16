"""Patient persistence. REST handlers and Vapi tools share this layer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, ValidationFailed
from app.models.call_log import CallLog, CallOutcome
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.services.phone import normalize_us_phone
from app.services.validation import parse_date_of_birth

log = structlog.get_logger(__name__)

_UNSET = object()


class PatientService:
    def __init__(self, db: Session):
        self.db = db

    def _active(self) -> Select[tuple[Patient]]:
        return select(Patient).where(Patient.deleted_at.is_(None))

    def get(self, patient_id: uuid.UUID) -> Patient:
        patient = self.db.scalar(self._active().where(Patient.patient_id == patient_id))
        if patient is None:
            raise NotFoundError(f"Patient {patient_id} not found")
        return patient

    def list(
        self,
        *,
        last_name: str | None = None,
        date_of_birth: str | None = None,
        phone_number: str | None = None,
    ) -> list[Patient]:
        stmt = self._active().order_by(Patient.created_at.desc())
        if last_name:
            stmt = stmt.where(Patient.last_name.ilike(last_name.strip()))
        if date_of_birth:
            try:
                dob = parse_date_of_birth(date_of_birth)
            except ValueError as exc:
                raise ValidationFailed(str(exc)) from exc
            stmt = stmt.where(Patient.date_of_birth == dob)
        if phone_number:
            try:
                phone = normalize_us_phone(phone_number)
            except ValueError as exc:
                raise ValidationFailed(str(exc)) from exc
            stmt = stmt.where(Patient.phone_number == phone)
        return list(self.db.scalars(stmt).all())

    def find_by_phone(self, phone_number: str) -> Patient | None:
        try:
            phone = normalize_us_phone(phone_number)
        except ValueError:
            return None
        return self.db.scalar(self._active().where(Patient.phone_number == phone))

    def find_by_source_call_id(self, source_call_id: str) -> Patient | None:
        if not source_call_id:
            return None
        return self.db.scalar(select(Patient).where(Patient.source_call_id == source_call_id))

    def create(self, payload: PatientCreate) -> Patient:
        if payload.source_call_id:
            existing = self.find_by_source_call_id(payload.source_call_id)
            if existing is not None:
                log.info(
                    "idempotent_create_hit",
                    source_call_id=payload.source_call_id,
                    patient_id=str(existing.patient_id),
                )
                return existing

        dup = self.find_by_phone(payload.phone_number)
        if dup is not None:
            raise ConflictError(
                f"A patient with phone number {payload.phone_number} already exists "
                f"({dup.first_name} {dup.last_name})",
                details=[
                    {
                        "field": "phone_number",
                        "message": "duplicate",
                        "existing_patient_id": str(dup.patient_id),
                        "first_name": dup.first_name,
                        "last_name": dup.last_name,
                    }
                ],
            )

        patient = Patient(**payload.model_dump())
        self.db.add(patient)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Could not create patient (constraint violation)") from exc

        log.info(
            "patient_created",
            patient_id=str(patient.patient_id),
            last_name=patient.last_name,
            phone_number=patient.phone_number,
            source_call_id=patient.source_call_id,
            payload=payload.model_dump(mode="json"),
        )
        return patient

    def update(self, patient_id: uuid.UUID, payload: PatientUpdate) -> Patient:
        patient = self.get(patient_id)
        data = payload.model_dump(exclude_unset=True)
        if "phone_number" in data and data["phone_number"]:
            other = self.find_by_phone(data["phone_number"])
            if other is not None and other.patient_id != patient.patient_id:
                raise ConflictError(
                    "That phone number already belongs to another patient",
                    details=[{"field": "phone_number", "existing_patient_id": str(other.patient_id)}],
                )
        for key, value in data.items():
            setattr(patient, key, value)
        patient.updated_at = datetime.now(timezone.utc)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Could not update patient (constraint violation)") from exc
        log.info(
            "patient_updated",
            patient_id=str(patient.patient_id),
            fields=list(data.keys()),
        )
        return patient

    def soft_delete(self, patient_id: uuid.UUID) -> Patient:
        patient = self.get(patient_id)
        now = datetime.now(timezone.utc)
        patient.deleted_at = now
        patient.updated_at = now
        self.db.flush()
        log.info("patient_soft_deleted", patient_id=str(patient.patient_id))
        return patient

    def to_read(self, patient: Patient) -> dict[str, Any]:
        return PatientRead.model_validate(patient).model_dump(mode="json")


def pydantic_errors(exc: ValidationError) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        out.append({"field": loc or "body", "message": err.get("msg", "invalid")})
    return out
