"""Patient REST API as specified in the take-home: /patients."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.envelope import ok
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.patient_service import PatientService

router = APIRouter(tags=["patients"])


def _svc(db: Session = Depends(get_db)) -> PatientService:
    return PatientService(db)


@router.get("/patients")
def list_patients(
    last_name: str | None = Query(default=None),
    date_of_birth: str | None = Query(default=None),
    phone_number: str | None = Query(default=None),
    svc: PatientService = Depends(_svc),
) -> dict:
    rows = svc.list(
        last_name=last_name,
        date_of_birth=date_of_birth,
        phone_number=phone_number,
    )
    return ok([svc.to_read(p) for p in rows])


@router.get("/patients/{patient_id}")
def get_patient(patient_id: uuid.UUID, svc: PatientService = Depends(_svc)) -> dict:
    return ok(svc.to_read(svc.get(patient_id)))


@router.post("/patients", status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, svc: PatientService = Depends(_svc)) -> dict:
    return ok(svc.to_read(svc.create(payload)))


@router.put("/patients/{patient_id}")
def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    svc: PatientService = Depends(_svc),
) -> dict:
    return ok(svc.to_read(svc.update(patient_id, payload)))


@router.delete("/patients/{patient_id}")
def delete_patient(
    patient_id: uuid.UUID,
    response: Response,
    svc: PatientService = Depends(_svc),
) -> dict:
    patient = svc.soft_delete(patient_id)
    response.status_code = status.HTTP_200_OK
    return ok(svc.to_read(patient))
