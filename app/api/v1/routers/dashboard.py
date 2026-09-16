"""Read-only Jinja dashboard of patients + recent calls."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.call_log import CallLog
from app.services.patient_service import PatientService

router = APIRouter(tags=["dashboard"])

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    patients = PatientService(db).list()
    calls = list(
        db.scalars(select(CallLog).order_by(CallLog.created_at.desc()).limit(25)).all()
    )
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"patients": patients, "calls": calls},
    )
