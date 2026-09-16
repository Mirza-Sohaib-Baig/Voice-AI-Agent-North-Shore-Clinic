# Architecture

## Runtime flow

```
┌──────────────┐     PSTN      ┌──────────────────┐             ┌─────────────────┐
│ Reviewer     │──────────────▶│ Vapi inbound US  │────────────▶│ Vapi Assistant  │
│ cell (US)    │               │ DID              │             │ Deepgram nova-3 │
└──────────────┘               └──────────────────┘             │ multi STT      │
                                                                │ GPT-4o          │
                                                                │ ElevenLabs TTS  │
                                                                └────────┬────────┘
                                                                         │ POST JSON
                                                                         │ X-Vapi-Secret
                                                                         ▼
┌──────────────┐  GET/POST /patients   ┌─────────────────────────────────────────┐
│ curl / docs  │◀─────────────────────▶│ FastAPI  (Render web service)           │
│ /dashboard   │                       │  routers → PatientService → SQLAlchemy  │
└──────────────┘                       └──────────────────┬──────────────────────┘
                                                           │
                                                           ▼
                                                   Neon Postgres
                                                   patients, call_logs
```

Three HTTP surfaces, one service layer:

| Surface | Path | Auth |
| --- | --- | --- |
| REST | `/patients`, also `/api/v1/patients` | none (assessment) |
| Voice webhook | `/api/v1/vapi/webhook` | `X-Vapi-Secret` |
| Dashboard | `/dashboard` | none, HTML |

Validation is **not** duplicated. `PatientCreate` / `PatientUpdate` run for REST **and** for tool arguments. Tool failures return `{status: "invalid", errors: [{field, message}]}` as the Vapi `result` string so the LLM re-prompts one field.

## Persistence

- `patients.patient_id` UUID PK
- Soft delete via `deleted_at`; all reads filter `IS NULL`
- Partial unique index on `phone_number` for active rows → duplicate detection is meaningful
- `source_call_id` unique → Vapi retried `save_patient_registration` for the same call returns the original row (HTTP 201 with the same UUID)
- `call_logs.vapi_call_id` unique; `end-of-call-report` upserts transcript + recording URL even when the caller hung up before save

## Error contract

Global handlers in `app/main.py` always return:

```json
{ "data": null, "error": { "code": "validation_error", "message": "...", "details": [...] } }
```

| Code | HTTP |
| --- | --- |
| `validation_error` | 422 |
| `not_found` | 404 |
| `conflict` | 400 |
| `http_error` | whatever Starlette said (401 webhook secrets) |
| `internal_error` | 500 |

## Why not a separate worker?

Tool calls must answer in a few seconds (Vapi tool timeout). A queue would add a moving part and a “please wait” UX we don't need. Writes are a single INSERT/UPDATE.

## Why not SQLite in production?

Render’s filesystem is ephemeral. A second call after a deploy would lose Jane Doe — that is an explicit scoring item. Neon is the persistent store; this API process is stateless.

The Vapi inbound DID is **US national inbound**. The agent does not place outbound calls. Non-U.S. caller ID is not used as the chart phone.

## Trust boundary

Vapi is the only caller of `/api/v1/vapi/webhook`. The secret is a Bearer-Token custom credential with the legacy `X-Vapi-Secret` header so we don't have to parse `Authorization` if we don't want to. REST is open because the spec does not ask for API keys; noted as a limitation.
