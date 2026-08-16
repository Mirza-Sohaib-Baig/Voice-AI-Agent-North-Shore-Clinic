# Patient Registration Voice Agent

A phone-callable intake coordinator that collects U.S. patient demographics through natural conversation, writes them to Postgres, and exposes them on a small REST API.

**Role assessed:** Voice AI / Conversational AI Engineer  
**Live demo values** (fill these after you complete [docs/setup/06-render-deployment.md](docs/setup/06-render-deployment.md) and [docs/setup/05-vapi-setup.md](docs/setup/05-vapi-setup.md)):

| | |
| --- | --- |
| Phone number | `_TBD after Twilio import_` |
| API base URL | `_TBD after Render deploy_` (health: `/health`, patients: `/patients`, dashboard: `/dashboard`) |
| OpenAPI | `{API}/docs` |

Fictional data only. Not HIPAA-compliant. Do not enter real patient information.

---

## What a reviewer will do

1. Dial the number. Maya asks whether you are a **new patient** or **already on file** (not an IVR tree — you can also just start stating your name and she will take that as registration).
2. New: she collects demographics conversationally, reads everything back, and waits for confirmation before saving.
3. `GET /patients?last_name=...` returns the record. A second call — “I already have a chart” / same phone — finds that row. She confirms identity, then offers an update instead of a duplicate.

## Architecture

```
Caller  →  Twilio US number  →  Vapi (Deepgram STT + GPT-4o + ElevenLabs TTS)
                                    │  HTTPS tool-calls + end-of-call-report
                                    ▼
                         FastAPI on Render  →  Render Postgres
                                    │
                         REST /patients  +  /dashboard
```

Voice tools and REST handlers share one `PatientService` and the same Pydantic models, so the agent cannot persist a date of birth the API would reject.

Details: [docs/architecture.md](docs/architecture.md). Prompt commentary: [docs/prompt-design.md](docs/prompt-design.md). API examples: [docs/api-reference.md](docs/api-reference.md).

## Tech stack (and why)

| Layer | Choice | Why |
| --- | --- | --- |
| Telephony + voice | **Vapi** + imported **Twilio** number | The spec encourages this. Vapi owns barge-in, STT, TTS, and tool calling so time goes to prompt + data, not a media-stream stack. |
| LLM | **OpenAI gpt-4o** (fallback `gpt-4o-mini`) | Reliable function calling, low enough latency for phone. |
| API | **Python FastAPI** | Matches the repo venv; Pydantic v2 validates REST and tool args identically. |
| DB | **Postgres on Render** + SQLAlchemy 2 + Alembic | Survives process restarts (SQLite on Render's disk would not). Real CHECKs and a partial unique index on active phone numbers. |
| Hosting | **Render** web service + managed Postgres | HTTPS out of the box; `render.yaml` is the blueprint. |
| Dashboard | Server-rendered Jinja at `/dashboard` | Bonus only. The spec does not require a frontend framework. |

## Quick start (local)

Full click-through is in `docs/setup/`. Short version on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# start Postgres (see docs/setup/02-database-postgres.md), then:
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```

```powershell
curl http://localhost:8000/health
curl "http://localhost:8000/patients?last_name=Doe"
```

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | yes | Postgres URL. `postgres://` from Render is rewritten to `postgresql+psycopg://`. |
| `VAPI_WEBHOOK_SECRET` | yes | Shared secret. Configure a Vapi Custom Credential with header `X-Vapi-Secret` (Bearer prefix **off**). |
| `ENVIRONMENT` | no | `development` / `production`. Production logs JSON. |
| `LOG_LEVEL` | no | Default `INFO`. |
| `PUBLIC_BASE_URL` | for provisioning | `https://your-service.onrender.com` (no trailing slash). |
| `VAPI_API_KEY` | for `scripts/provision_vapi.py` | Private Vapi key. Never commit it. |
| `VAPI_ASSISTANT_ID` | after first provision | PATCH instead of creating a second assistant. |
| `OPENAI_API_KEY` | optional locally | Vapi bills the model; you do not need this in the API process. |

## Voice tools

Posted to `POST /api/v1/vapi/webhook`:

- `lookup_patient_by_phone` — existing-chart lookup (phone, or last name + DOB) and duplicate detection on new registrations
- `save_patient_registration` — create after confirmation; idempotent on `source_call_id` / Vapi `call.id`
- `update_patient_record` — returning caller or a post-confirm correction
- `schedule_appointment` — mock slots (bonus)

Invalid fields come back as `{status: invalid, errors: [{field, message}]}` so the model re-prompts that field only.

## REST API

| Method | Path | Status |
| --- | --- | --- |
| `GET` | `/patients` | 200 — filters: `last_name`, `date_of_birth`, `phone_number` |
| `GET` | `/patients/{id}` | 200 / 404 |
| `POST` | `/patients` | 201 |
| `PUT` | `/patients/{id}` | 200 — partial updates |
| `DELETE` | `/patients/{id}` | 200 — **soft** delete (`deleted_at`) |

Envelope: `{ "data": ..., "error": null }`. Errors invert that. Same routes are also mounted under `/api/v1`.

## Tests

```powershell
python -m pytest -q
```

SQLite in-memory. No Postgres, Twilio, or Vapi required.

## Setup guides

1. [00 Prerequisites](docs/setup/00-prerequisites.md)
2. [01 Local development](docs/setup/01-local-development.md)
3. [02 Postgres](docs/setup/02-database-postgres.md)
4. [03 OpenAI billing (used by Vapi)](docs/setup/03-openai-setup.md)
5. [04 Twilio number](docs/setup/04-twilio-number.md)
6. [05 Vapi assistant, tools, secret](docs/setup/05-vapi-setup.md)
7. [06 Render deploy](docs/setup/06-render-deployment.md)
8. [07 ngrok for local tool debugging](docs/setup/07-ngrok-local-testing.md)
9. [08 QA call matrix](docs/setup/08-testing-and-qa.md)
10. [09 Logs and troubleshooting](docs/setup/09-observability-troubleshooting.md)

Pre-review checklist: [docs/runbook.md](docs/runbook.md).

## Trade-offs and known limitations

- **Vapi instead of Twilio Media Streams.** Faster path to a natural agent (barge-in, STT, TTS). Cost is vendor lock-in and less raw audio control. Justified by the spec's FAQ and the 3-hour window.
- **Render Postgres `basic-256mb`, not SQLite.** Persistence across deploys is a scored requirement. The smallest paid Render Postgres instance is used in `render.yaml`. Free Postgres has been discontinued.
- **Partial unique index on `phone_number WHERE deleted_at IS NULL`.** Households sometimes share a number; the agent offers an update and can still continue if they insist they are a new patient... except the unique index will reject a second *active* row. Documented to the agent as "household phone — update the existing chart or ask for a different callback number." Soft-deleted numbers can be reused.
- **No HIPAA, no auth on GET /patients.** Assessment rules: fictional data, no compliance theatre.
- **Dashboard is HTML, not React.** Bonus display only.
- **Appointment slots are mock.** There is no EHR calendar.
- **Spanish is prompt-only.** The transcriber is English-primary (`nova-2` + `en`); "Hablo español" will try, but STT quality in Spanish is not guaranteed without flipping the transcriber language.
- **Render cold starts.** Starter plans sleep. Warm the `/health` URL before a review call (see runbook).
- **Webhooks must be fast.** Tool handlers do one SQL transaction and return. Transcripts are stored from `end-of-call-report`, which can arrive after the caller hangs up.

## Next steps (if there had been more time)

- Auth (API key) in front of `/patients` mutation + dashboard.
- Flip the transcriber to multilingual on `language-change-detected`.
- Store structured per-turn messages, not only the concatenated transcript.
- Outbound "your registration is complete" SMS via Twilio.
- Stronger appointment booking against a real calendar.
- CI (GitHub Actions) running `pytest` on every push.
- Pager on `vapi_hang` / 5xx webhook rates.

## License / data

Confidential candidate assessment. All names, phones, and addresses in seed data are fictitious.
