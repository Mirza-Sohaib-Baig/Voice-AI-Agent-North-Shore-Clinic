"""POST /api/v1/vapi/webhook — Vapi server URL for tool-calls and call lifecycle."""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.security import require_vapi_secret
from app.db.session import get_db
from app.models.call_log import CallOutcome
from app.schemas.vapi import VapiWebhook
from app.services.call_log_service import upsert_call_log
from app.voice.tools import dispatch

log = structlog.get_logger(__name__)

router = APIRouter(tags=["vapi"])

_TOOL_TYPES = {"tool-calls", "function-call", "tool.completed"}
_END_TYPES = {"end-of-call-report", "end-of-call-report-event"}
_STATUS_TYPES = {"status-update"}
_HANG_TYPES = {"hang"}


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _extract_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    calls = message.get("toolCallList") or []
    if calls:
        out = []
        for item in calls:
            out.append(
                {
                    "id": item.get("id") or (item.get("toolCall") or {}).get("id"),
                    "name": item.get("name")
                    or (item.get("function") or {}).get("name")
                    or (item.get("toolCall") or {}).get("name"),
                    "arguments": _parse_arguments(
                        item.get("arguments")
                        or item.get("parameters")
                        or (item.get("function") or {}).get("arguments")
                        or (item.get("toolCall") or {}).get("parameters")
                    ),
                }
            )
        return [c for c in out if c["id"] and c["name"]]

    # Older function-call payload.
    fc = message.get("functionCall") or {}
    if fc:
        return [
            {
                "id": fc.get("id") or "legacy",
                "name": fc.get("name"),
                "arguments": _parse_arguments(fc.get("parameters") or fc.get("arguments")),
            }
        ]
    return []


def _recording_url(artifact: dict[str, Any] | None) -> str | None:
    if not artifact:
        return None
    rec = artifact.get("recording")
    if isinstance(rec, str):
        return rec
    if isinstance(rec, dict):
        return rec.get("stereoUrl") or rec.get("monoUrl") or rec.get("url")
    return artifact.get("stereoRecordingUrl") or artifact.get("recordingUrl")


def _caller_number(message: dict[str, Any]) -> str | None:
    customer = message.get("customer") or {}
    if isinstance(customer, dict) and customer.get("number"):
        return customer["number"]
    call = message.get("call") or {}
    nested = (call.get("customer") or {}) if isinstance(call, dict) else {}
    return nested.get("number")


@router.post("/api/v1/vapi/webhook")
async def vapi_webhook(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_vapi_secret),
) -> dict:
    body = await request.json()
    message = body.get("message") or {}
    msg_type = message.get("type") or ""
    call = message.get("call") or {}
    call_id = call.get("id")

    log.info("vapi_event", type=msg_type, call_id=call_id)

    if msg_type in _TOOL_TYPES or message.get("toolCallList"):
        results = []
        for tool in _extract_tool_calls(message):
            result = dispatch(db, tool["name"], tool["arguments"], call_id)
            results.append({"toolCallId": tool["id"], "result": result})
            log.info("vapi_tool_result", tool=tool["name"], call_id=call_id, result=result)
        return {"results": results}

    if msg_type in _END_TYPES:
        artifact = message.get("artifact") or {}
        if call_id:
            upsert_call_log(
                db,
                vapi_call_id=call_id,
                from_number=_caller_number(message),
                transcript=artifact.get("transcript"),
                summary=artifact.get("summary") or message.get("summary"),
                recording_url=_recording_url(artifact),
                ended_reason=message.get("endedReason"),
                outcome=CallOutcome.ABANDONED
                if not message.get("endedReason") in {"assistant-said-end-call", "customer-ended-call"}
                else None,
            )
        log.info(
            "end_of_call",
            call_id=call_id,
            ended_reason=message.get("endedReason"),
            transcript=(artifact.get("transcript") or "")[:500],
        )
        return {"ok": True}

    if msg_type in _STATUS_TYPES and call_id:
        status = message.get("status")
        outcome = CallOutcome.IN_PROGRESS if status == "in-progress" else None
        upsert_call_log(
            db,
            vapi_call_id=call_id,
            from_number=_caller_number(message),
            outcome=outcome,
        )
        return {"ok": True}

    if msg_type in _HANG_TYPES:
        log.warning("vapi_hang", call_id=call_id)
        return {"ok": True}

    # Acknowledge anything else so Vapi doesn't retry.
    return {"ok": True}


# Imported so we fail loudly if the schema drifts; not required at runtime.
_ = VapiWebhook
