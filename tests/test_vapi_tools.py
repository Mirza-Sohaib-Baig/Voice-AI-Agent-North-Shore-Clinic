"""Vapi webhook + tool handlers."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

SECRET = "test-vapi-secret"
HEADERS = {"X-Vapi-Secret": SECRET}


def _patient_args(**over) -> dict:
    body = {
        "first_name": "Sam",
        "last_name": "Davis",
        "date_of_birth": "01/20/1992",
        "sex": "Male",
        "phone_number": "5032281234",
        "address_line_1": "100 SW Main",
        "city": "Portland",
        "state": "OR",
        "zip_code": "97204",
    }
    body.update(over)
    return body


def _tool_body(name: str, arguments: dict, call_id: str = "call-1") -> dict:
    return {
        "message": {
            "type": "tool-calls",
            "call": {"id": call_id, "customer": {"number": "+15032281234"}},
            "toolCallList": [
                {"id": "tc_1", "name": name, "arguments": arguments},
            ],
        }
    }


def test_webhook_rejects_bad_secret(client: TestClient):
    res = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body("lookup_patient_by_phone", {"phone_number": "5032281234"}),
        headers={"X-Vapi-Secret": "nope"},
    )
    assert res.status_code == 401


def test_save_then_lookup_duplicate_flow(client: TestClient):
    save = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body("save_patient_registration", _patient_args()),
        headers=HEADERS,
    )
    assert save.status_code == 200, save.text
    result = json.loads(save.json()["results"][0]["result"])
    assert result["status"] == "ok"
    patient_id = result["patient_id"]

    lookup = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body("lookup_patient_by_phone", {"phone_number": "503-228-1234"}),
        headers=HEADERS,
    )
    found = json.loads(lookup.json()["results"][0]["result"])
    assert found["status"] == "found"
    assert found["patient"]["last_name"] == "Davis"
    assert found["patient"]["patient_id"] == patient_id
    assert "city" not in found["patient"]
    assert "already have a record" in found["prompt"]

    # Same call_id is idempotent.
    replay = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body("save_patient_registration", _patient_args(), call_id="call-1"),
        headers=HEADERS,
    )
    replayed = json.loads(replay.json()["results"][0]["result"])
    assert replayed["status"] == "ok"
    assert replayed["patient_id"] == patient_id


def test_invalid_dob_returns_field_error(client: TestClient):
    res = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body(
            "save_patient_registration",
            _patient_args(date_of_birth="01/01/3099"),
        ),
        headers=HEADERS,
    )
    result = json.loads(res.json()["results"][0]["result"])
    assert result["status"] == "invalid"
    fields = {e["field"] for e in result["errors"]}
    assert "date_of_birth" in fields


def test_update_patient_tool(client: TestClient):
    save = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body("save_patient_registration", _patient_args()),
        headers=HEADERS,
    )
    patient_id = json.loads(save.json()["results"][0]["result"])["patient_id"]
    upd = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body(
            "update_patient_record",
            {"patient_id": patient_id, "last_name": "Davies"},
            call_id="call-2",
        ),
        headers=HEADERS,
    )
    result = json.loads(upd.json()["results"][0]["result"])
    assert result["status"] == "ok"
    listed = client.get("/patients?last_name=Davies")
    assert listed.json()["data"][0]["patient_id"] == patient_id


def test_end_of_call_report_persists_transcript(client: TestClient, db):
    body = {
        "message": {
            "type": "end-of-call-report",
            "endedReason": "customer-ended-call",
            "call": {"id": "call-drop-1", "customer": {"number": "+14155552671"}},
            "artifact": {"transcript": "AI: Hi? User: Hello."},
        }
    }
    res = client.post("/api/v1/vapi/webhook", json=body, headers=HEADERS)
    assert res.status_code == 200
    from app.models.call_log import CallLog
    from sqlalchemy import select

    row = db.scalar(select(CallLog).where(CallLog.vapi_call_id == "call-drop-1"))
    assert row is not None
    assert "Hello" in (row.transcript or "")


def test_schedule_appointment_mock(client: TestClient):
    res = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body(
            "schedule_appointment",
            {"patient_id": str(uuid.uuid4()), "preferred_window": "morning"},
        ),
        headers=HEADERS,
    )
    result = json.loads(res.json()["results"][0]["result"])
    assert result["status"] == "ok"
    assert result["available_slots"]


def test_lookup_by_last_name_and_dob(client: TestClient):
    save = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body("save_patient_registration", _patient_args()),
        headers=HEADERS,
    )
    patient_id = json.loads(save.json()["results"][0]["result"])["patient_id"]

    lookup = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body(
            "lookup_patient_by_phone",
            {"last_name": "Davis", "date_of_birth": "01/20/1992"},
            call_id="call-lookup-name",
        ),
        headers=HEADERS,
    )
    found = json.loads(lookup.json()["results"][0]["result"])
    assert found["status"] == "found"
    assert found["patient"]["patient_id"] == patient_id
    assert found["patient"]["first_name"] == "Sam"
    assert set(found["patient"].keys()) == {
        "patient_id",
        "first_name",
        "last_name",
        "date_of_birth",
    }


def test_lookup_requires_phone_or_name_dob(client: TestClient):
    res = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body("lookup_patient_by_phone", {"last_name": "Davis"}, call_id="call-bad"),
        headers=HEADERS,
    )
    result = json.loads(res.json()["results"][0]["result"])
    assert result["status"] == "invalid"


def test_end_call_tool_is_acknowledged(client: TestClient):
    res = client.post(
        "/api/v1/vapi/webhook",
        json=_tool_body("endCall", {}, call_id="call-end"),
        headers=HEADERS,
    )
    assert res.status_code == 200
    result = json.loads(res.json()["results"][0]["result"])
    assert result["status"] == "ok"
