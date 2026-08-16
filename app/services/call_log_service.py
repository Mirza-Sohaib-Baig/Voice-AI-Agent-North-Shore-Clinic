"""Call-log helpers used by the Vapi webhook."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.call_log import CallLog, CallOutcome

log = structlog.get_logger(__name__)


def upsert_call_log(
    db: Session,
    *,
    vapi_call_id: str,
    from_number: str | None = None,
    transcript: str | None = None,
    summary: str | None = None,
    recording_url: str | None = None,
    ended_reason: str | None = None,
    outcome: CallOutcome | None = None,
    patient_id: Any = None,
) -> CallLog:
    row = db.scalar(select(CallLog).where(CallLog.vapi_call_id == vapi_call_id))
    if row is None:
        row = CallLog(
            vapi_call_id=vapi_call_id,
            from_number=from_number,
            transcript=transcript,
            summary=summary,
            recording_url=recording_url,
            ended_reason=ended_reason,
            outcome=outcome or CallOutcome.UNKNOWN,
            patient_id=patient_id,
        )
        db.add(row)
    else:
        if from_number:
            row.from_number = from_number
        if transcript:
            row.transcript = transcript
        if summary:
            row.summary = summary
        if recording_url:
            row.recording_url = recording_url
        if ended_reason:
            row.ended_reason = ended_reason
        if outcome:
            row.outcome = outcome
        if patient_id:
            row.patient_id = patient_id
    db.flush()
    log.info(
        "call_log_upserted",
        vapi_call_id=vapi_call_id,
        outcome=row.outcome.value if row.outcome else None,
        patient_id=str(row.patient_id) if row.patient_id else None,
    )
    return row
