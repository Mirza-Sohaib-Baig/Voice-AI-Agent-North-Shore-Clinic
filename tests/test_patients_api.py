"""REST API CRUD against SQLite (same routers the reviewers will hit)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _payload(**overrides) -> dict:
    body = {
        "first_name": "Alice",
        "last_name": "Nguyen",
        "date_of_birth": "07/04/1985",
        "sex": "Female",
        "phone_number": "4157771234",
        "email": "alice@example.com",
        "address_line_1": "24 Divisadero St",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94117",
    }
    body.update(overrides)
    return body


def test_create_list_get_update_delete(client: TestClient):
    created = client.post("/patients", json=_payload())
    assert created.status_code == 201, created.text
    envelope = created.json()
    assert envelope["error"] is None
    patient_id = envelope["data"]["patient_id"]
    assert envelope["data"]["phone_number"] == "4157771234"

    listed = client.get("/patients?last_name=Nguyen")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1

    by_phone = client.get("/patients?phone_number=415-777-1234")
    assert len(by_phone.json()["data"]) == 1

    by_dob = client.get("/patients?date_of_birth=07/04/1985")
    assert len(by_dob.json()["data"]) == 1

    fetched = client.get(f"/patients/{patient_id}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["first_name"] == "Alice"

    patched = client.put(
        f"/patients/{patient_id}", json={"city": "Oakland", "zip_code": "94612"}
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["city"] == "Oakland"

    deleted = client.delete(f"/patients/{patient_id}")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted_at"] is not None

    missing = client.get(f"/patients/{patient_id}")
    assert missing.status_code == 404
    assert missing.json()["data"] is None
    assert missing.json()["error"]["code"] == "not_found"


def test_create_validation_error(client: TestClient):
    bad = client.post("/patients", json=_payload(date_of_birth="01/01/3099", phone_number="12"))
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "validation_error"


def test_duplicate_phone_conflict(client: TestClient):
    assert client.post("/patients", json=_payload()).status_code == 201
    again = client.post("/patients", json=_payload(first_name="Bob"))
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "conflict"


def test_idempotent_create_by_source_call_id(client: TestClient):
    body = _payload(source_call_id="call-abc", last_name="Idem")
    first = client.post("/patients", json=body)
    second = client.post("/patients", json=body)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["patient_id"] == second.json()["data"]["patient_id"]


def test_unknown_patient(client: TestClient):
    res = client.get("/patients/00000000-0000-4000-8000-000000000001")
    assert res.status_code == 404


def test_health(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["data"]["status"] in {"ok", "degraded"}


def test_dashboard_renders(client: TestClient):
    client.post("/patients", json=_payload())
    page = client.get("/dashboard")
    assert page.status_code == 200
    assert "Nguyen" in page.text


def test_api_v1_alias(client: TestClient):
    created = client.post("/api/v1/patients", json=_payload())
    assert created.status_code == 201
