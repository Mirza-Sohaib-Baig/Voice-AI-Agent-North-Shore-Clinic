# Runbook — before the reviewer dials

Print this. Do it in order. Target: 15 minutes before the email/call window.

## 1. Render is Live

- Dashboard shows `patient-registration-api` **Live** (not sleeping / failed deploy).
- `curl https://YOUR-SERVICE.onrender.com/health` → `"database":"up"`.
- `GET /patients` returns JSON envelope (seed or prior test rows are fine).
- `/dashboard` loads.

If the service slept, wait 30–60s after the health check and repeat.

## 2. Vapi + number

- Phone Numbers: Twilio DID is **assigned** to Northshore Intake Coordinator.
- Assistant first message asks **new patient vs already on file**, not “let’s start with your first name.”
- Tools tab lists all four tools. Server URL host is the **Render** origin, not an expired ngrok host.
- Custom Credential is attached; a trial POST with a wrong secret 401s, the right secret 200s (see [05](setup/05-vapi-setup.md) curl).

## 3. Money

- Twilio balance > $2.
- Vapi billing method present.
- OpenAI (if BYO key) has a hard limit **and** remaining credit.

## 4. Personal smoke call (2 minutes)

Dial the number yourself. Answer **new patient**, give a fake identity. Confirm. Hang up.

```bash
curl -s "$BASE/patients?last_name=YOURFAKELAST"
```

You should see the row. If not, **stop** and read [09](setup/09-observability-troubleshooting.md) before the reviewer retries.

Call a second time from the same phone, say **I already have a chart**, and confirm she finds you and offers to **update**.

## 5. README for submission

Top of `README.md` has:

- The dialable number (`+1…`)
- API base URL
- “fictional data only”
- Repo URL

Email / form also gets any extra note (Twilio trial, “press any key” — should be none).

## 6. Don't

- Don't deploy in the last 10 minutes (cold cache + migrating).
- Don't rotate `VAPI_WEBHOOK_SECRET` without updating the Vapi credential.
- Don't paste real PHI into the seed script.
- Don't leave ngrok as the tool URL overnight; it will die before review.

## Rollback

Render → previous successful deploy. Database is intact. Revert the assistant in Vapi by re-running `python scripts/provision_vapi.py` with the last known `system_prompt.md`.
