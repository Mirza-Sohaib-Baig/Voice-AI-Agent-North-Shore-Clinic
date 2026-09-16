# Patient Registration Voice Agent

A phone-callable intake coordinator that collects U.S. patient demographics through natural conversation, writes them to Postgres, and exposes them on a REST API.

**Role assessed:** Voice AI / Conversational AI Engineer

Fictional data only. Not HIPAA-compliant. Do not enter real patient information.

## Live demo

| | |
| --- | --- |
| Phone number | `+1 (551) 233 0188` |
| API base URL | `https://voice-ai-agent-north-shore-clinic.onrender.com` |
| Health | `https://voice-ai-agent-north-shore-clinic.onrender.com/health` |
| Patients | `https://voice-ai-agent-north-shore-clinic.onrender.com/patients` |
| Dashboard | `https://voice-ai-agent-north-shore-clinic.onrender.com/dashboard` |
| OpenAPI | `https://voice-ai-agent-north-shore-clinic.onrender.com/docs` |

## Reviewer Notes:

1. Dial the number. Maya asks whether you are a **new patient** or **already have a chart** (not an IVR tree). You can skip the menu and start stating your name; that is treated as registration.
2. New: she collects required demographics conversationally, reads everything back, and waits for confirmation before saving. After save she says you are all set and offers a mock first appointment; decline if you do not want one. The call should then end.
3. `GET {API}/patients?last_name=...` (or `?phone_number=`) returns the row. A second call — “I already have a chart” / the same US callback number — finds that row. She confirms identity, then offers an **update** instead of a duplicate.

Use a **U.S. 10-digit** number when she asks for a callback. See [Constraints](#constraints-and-known-gaps).

## Architecture

```
Caller  →  Vapi inbound US number  →  Vapi (Deepgram STT + GPT-4o + ElevenLabs TTS)
                                          │  HTTPS tool-calls + end-of-call-report
                                          ▼
                               FastAPI on Render  →  Neon Postgres
                                          │
                               REST /patients  +  /dashboard
```

Voice tools and REST share one `PatientService` and the same Pydantic models, so the agent cannot persist a date of birth the API would reject.

- Runtime diagram and schema: [docs/architecture.md](docs/architecture.md)
- Prompt commentary: [docs/prompt-design.md](docs/prompt-design.md)
- Live system prompt (commented): [app/voice/prompts/system_prompt.md](app/voice/prompts/system_prompt.md)
- HTTP examples: [docs/api-reference.md](docs/api-reference.md)

## Tech stack (and why)

| Layer | Choice | Why |
| --- | --- | --- |
| Telephony + voice | **Vapi inbound US number** (Deepgram + GPT-4o + ElevenLabs) | The spec encourages a voice platform so time goes to prompt, tools, and data — not a custom media-stream stack. |
| LLM | **OpenAI gpt-4o** (fallback `gpt-4o-mini`) | Reliable function calling, acceptable latency on a phone. Billed through Vapi; this API process does not call OpenAI. |
| API | **Python FastAPI** | Pydantic v2 validates REST and tool args identically. |
| DB | **Neon Postgres** + SQLAlchemy 2 + Alembic | Survives process restarts. CHECKs plus a partial unique index on active phone numbers. |
| Hosting | **Render** web service | Stable HTTPS for Vapi tool-calls. |
| Dashboard | Server-rendered Jinja at `/dashboard` | Spec bonus. Not a frontend framework. |

## Data model

Required on create (and on the call, before save): `first_name`, `last_name`, `date_of_birth`, `sex`, `phone_number`, `address_line_1`, `city`, `state`, `zip_code`.

Optional (offered as one opt-in block, not a second interrogation): `email`, `address_line_2`, `insurance_provider`, `insurance_member_id`, `preferred_language` (default English), `emergency_contact_name`, `emergency_contact_phone`.

Auto: `patient_id` (UUID), `created_at`, `updated_at`. Soft delete sets `deleted_at`.

Names: 1–50 characters, letters / spaces / hyphens / apostrophes. Sex: Male, Female, Other, Decline to Answer. Phone: U.S. 10 digits. State: 2-letter USPS. ZIP: 5 or ZIP+4. DOB: not future, not older than 120.

## Voice tools

Posted to `POST /api/v1/vapi/webhook` (header `X-Vapi-Secret`):

- `lookup_patient_by_phone` — existing-chart lookup (phone, or last name + DOB) and duplicate detection
- `save_patient_registration` — create only after confirmation; idempotent on `source_call_id` / Vapi `call.id`
- `update_patient_record` — returning caller or a post-confirm correction
- `schedule_appointment` — mock slots (bonus)
- `endCall` — Vapi default tool; disconnects after the farewell

Invalid fields come back as `{status: invalid, errors: [{field, message}]}` so the model re-prompts that field only. A failed write returns `status=error`; Maya apologizes and promises a callback — she does not claim it saved.

## REST API

| Method | Path | Status |
| --- | --- | --- |
| `GET` | `/health` | 200 |
| `GET` | `/patients` | 200 — filters: `last_name`, `date_of_birth`, `phone_number` |
| `GET` | `/patients/{id}` | 200 / 404 |
| `POST` | `/patients` | 201 |
| `PUT` | `/patients/{id}` | 200 — partial updates |
| `DELETE` | `/patients/{id}` | 200 — **soft** delete (`deleted_at`) |

Envelope: `{ "data": ..., "error": null }`. Errors invert that. Same patient routes are also mounted under `/api/v1`.

```bash
curl -s "{API}/health"
curl -s "{API}/patients?last_name=Doe"
```

## Environment variables

Never commit `.env`. Copy [`.env.example`](.env.example).

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | yes | Postgres URL. `postgres://` is rewritten to `postgresql+psycopg://`. |
| `VAPI_WEBHOOK_SECRET` | yes | Shared secret. Vapi Custom Credential header `X-Vapi-Secret` (Bearer prefix **off**). |
| `ENVIRONMENT` | no | `development` / `production`. Production logs JSON. |
| `LOG_LEVEL` | no | Default `INFO`. |
| `PUBLIC_BASE_URL` | for provisioning | Public HTTPS origin, no trailing slash. |
| `VAPI_API_KEY` | for `scripts/provision_vapi.py` | Private Vapi key. Not needed in the API process. |
| `VAPI_ASSISTANT_ID` | after first provision | PATCH the same assistant instead of duplicating. |
| `OPENAI_API_KEY` | optional locally | Unused by the hosted API. |

Conversations: tool results (the collected payload) go to stdout; transcripts land on `end-of-call-report` in `call_logs`.

## Constraints and known gaps

- **Inbound U.S. number only.** A U.S. reviewer can dial the Vapi number. This free DID cannot place an outbound call to a non-U.S. cell, and inbound from outside the U.S. (for example Pakistan) often never rings. The agent will not “call you back” on a `+92` line.
- **Stored phones are U.S. 10-digit.** Speak a U.S. callback when Maya asks. `+92` / `03xx` fails validation. Caller ID that is not NANP is ignored; she asks for the chart number.
- **Not HIPAA.** Fictional identities only. No real dates of birth or member IDs that belong to anyone.
- **Cold start.** Render and Neon may sleep. If `{API}/health` is slow, wait 30–60s and retry until `"database":"up"`.
- **Hang up before confirm.** No new patient row. `call_logs` can still store a transcript fragment from `end-of-call-report`.
- **Database write failure.** Spoken apology + callback promise — never silence, never “you're all set.”
- **Multilingual follow-the-caller.** Greeting stays English. If they speak another language (including “Hablo español”), Maya continues in it and saves `preferred_language`. **Deepgram nova-3 `language=multi`** codeswitches ten languages (English, Spanish, Hindi, French, German, Portuguese, Japanese, Italian, Dutch, Russian) — that list is Deepgram’s product, not a feature we declined. **Urdu** is not in that codeswitch set (vendor: monolingual `ur` would break English intake). Spoken Urdu may transcribe as Hindi; Maya still replies in Urdu. **ElevenLabs `eleven_multilingual_v2`** lists Spanish and Hindi; Urdu is not on that TTS list (vendor). Chart phones stay U.S. 10-digit per the spec.
- **Appointments are mock.** No EHR calendar.
- **No auth on `/patients` or `/dashboard`.** Assessment scope.
- **Two active charts cannot share a phone.** Partial unique index; the agent offers an update or a different callback.

## Local run

Python 3.11 or 3.12, a local Postgres, then from the repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# set DATABASE_URL, then:
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```

```powershell
python -m pytest -q
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/patients?last_name=Doe"
```

Tests use in-memory SQLite. No live telephony required.

## Next steps (if there had been more time)

- Auth (API key) in front of `/patients` mutation + dashboard.
- Store structured per-turn messages, not only the concatenated transcript.
- Outbound SMS when registration completes.
- Real calendar for appointments.
- CI running `pytest` on every push.

## License / data

Confidential candidate assessment. Seed names, phones, and addresses are fictitious.
