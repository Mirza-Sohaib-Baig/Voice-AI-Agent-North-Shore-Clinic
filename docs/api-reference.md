# API reference

Base URL: the origin in the README **Live demo** table (local: `http://127.0.0.1:8000`).
All JSON bodies and responses use the envelope `{ "data": ..., "error": null }`.
OpenAPI UI: `/docs`.

The spec’s paths are `/patients`. They are also aliased under `/api/v1`.

## `GET /health`

```bash
curl -s $BASE/health
```

```json
{"data":{"status":"ok","database":"up"},"error":null}
```

HTTP 200 even if the database is down (`status: "degraded"`) so Render's health check does not flap during a brief blip. Watch `database` for real readiness.

## `GET /patients`

Query params (all optional, AND together):

- `last_name` — exact, case-insensitive
- `date_of_birth` — `MM/DD/YYYY` or ISO
- `phone_number` — any US formatting; matched as 10 digits

```bash
curl -s "$BASE/patients?last_name=Doe"
curl -s "$BASE/patients?phone_number=650-253-0000"
curl -s "$BASE/patients?date_of_birth=04/12/1988"
```

```json
{
  "data": [
    {
      "patient_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "first_name": "Jane",
      "last_name": "Doe",
      "date_of_birth": "1988-04-12",
      "sex": "Female",
      "phone_number": "6502530000",
      "email": "jane.doe@example.com",
      "address_line_1": "1600 Amphitheatre Parkway",
      "address_line_2": null,
      "city": "Mountain View",
      "state": "CA",
      "zip_code": "94043",
      "insurance_provider": "Blue Shield of California",
      "insurance_member_id": "BSC1234567",
      "preferred_language": "English",
      "emergency_contact_name": "John Doe",
      "emergency_contact_phone": "6502530001",
      "created_at": "2026-08-16T12:00:00Z",
      "updated_at": "2026-08-16T12:00:00Z",
      "deleted_at": null,
      "source_call_id": null
    }
  ],
  "error": null
}
```

## `GET /patients/{patient_id}`

200 with one object, or 404:

```json
{"data":null,"error":{"code":"not_found","message":"Patient … not found","details":null}}
```

## `POST /patients`

201. Required fields: `first_name`, `last_name`, `date_of_birth`, `sex`, `phone_number`, `address_line_1`, `city`, `state`, `zip_code`.

```bash
curl -s -X POST $BASE/patients -H "Content-Type: application/json" -d '{
  "first_name": "Riley",
  "last_name": "Chen",
  "date_of_birth": "11/02/1994",
  "sex": "Other",
  "phone_number": "2066246827",
  "address_line_1": "400 Broad St",
  "city": "Seattle",
  "state": "WA",
  "zip_code": "98109"
}'
```

422 on validation errors (future DOB, 3-digit phone, invalid ZIP/state, digits in a name).  
400 `conflict` if that phone already has an **active** patient.

## `PUT /patients/{patient_id}`

Partial update. Omitted fields stay. Empty strings become `null` where the column is optional.

```bash
curl -s -X PUT $BASE/patients/$ID -H "Content-Type: application/json" -d '{"city":"Oakland","zip_code":"94612"}'
```

## `DELETE /patients/{patient_id}`

Soft delete: sets `deleted_at`, does not drop the row. Subsequent GET by id is 404. The phone number may be reused.

## `GET /dashboard`

HTML table of active patients and the latest 25 call logs. No framework bundle.

## `POST /api/v1/vapi/webhook`

Vapi server URL. Header `X-Vapi-Secret: <VAPI_WEBHOOK_SECRET>`.

Tool-call response shape Vapi expects:

```json
{"results":[{"toolCallId":"tc_1","result":"{\"status\":\"ok\",\"patient_id\":\"…\"}"}]}
```

`result` is a **string** (JSON-encoded) so both string and object parsers on Vapi's side succeed.

Unauthenticated → 401 envelope.
