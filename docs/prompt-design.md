# Prompt design

The live system prompt is [`app/voice/prompts/system_prompt.md`](../app/voice/prompts/system_prompt.md). Every block there starts with `# WHY:` so this file is a map, not a second copy.

## Voice vs. text

Phone STT is lossy. The prompt therefore:

- Asks **one question per turn** (long questions get truncated by barge-in).
- Spells back names and reads phone numbers **digit-by-digit** in 3-3-4 groups.
- Reads dates as **month-name + day + four-digit year**, never `03/15/1990` which sounds like “three fifteen”.
- Forbids reading `patient_id` UUIDs.
- Treats “actually, it’s D-A-V-I-S” as a **field patch**, not a restart.

## Confirmation gate

The spec requires a full read-back **before** persist. The prompt says the `save_patient_registration` tool is illegal until the caller explicitly confirms. The API also happens to be happy if a buggy model skips that — still a product failure, which is why the instruction is repeated and why tool start-speech is “Saving your registration now” (audible cue).

## Tool errors as conversational fuel

Pydantic `ValidationError` is serialized as:

```json
{"status":"invalid","errors":[{"field":"date_of_birth","message":"Date of birth cannot be in the future"}]}
```

The prompt tells the model to re-ask **that field** with the reason. This is how a 3-digit phone or a 2090 DOB is handled without a brittle IVR state machine.

`status=error` (DB/infrastructure) has a **scripted apology** plus a callback promise. Silence after a failed write is an edge-case deduction on the rubric.

## Duplicate detection

On the new-patient path, as soon as a 10-digit number exists (ANI or spoken), `lookup_patient_by_phone`. On the existing-chart path the same tool runs from caller ID, a spoken chart number, or last name + DOB. The result is identity fields only (`patient_id`, names, DOB) — not address or city. The canned prompt for a hit is the spec's line:

> It looks like we already have a record for {first_name} {last_name}. Would you like to update your information instead?

## Optional block

Required fields first. Then one offer for insurance / emergency contact / language — not a second interrogation by default.

## Start over / interruptions / language

- Start over: drop **unconfirmed** in-memory slots and re-ask new vs existing; never DELETE a saved row unless asked.
- Interruptions: `stopSpeakingPlan.numWords = 2` in `vapi/assistant.json` plus the prompt's “stop and listen”.
- Language: default English; **follow the caller** (spec bonus: “Hablo español”). STT is Deepgram **nova-3** `language=multi` (ten codeswitch languages). That vendor set includes Hindi and Spanish, not Urdu; the prompt still replies in Urdu. TTS is ElevenLabs multilingual v2. U.S. 10-digit chart phones stay as the spec.

## First message

Pinned in [`vapi/assistant.json`](../vapi/assistant.json), not left to the LLM, so the first 1.5 seconds are deterministic:

> Are you a new patient, or do you already have a chart with us?

That is intent routing, not a first-name grab. If they ignore it and start dictating demographics, the prompt treats them as **new** so a reviewer can still “speak naturally to register.” Existing / calling back goes through lookup and a name+DOB check before any chart discussion. Other requests get a polite “I only handle registration.”

## Identity

Maya does not dump a full chart to whoever dialed. Lookup returns identity keys; she confirms last name or DOB before offering an update. `patient_id` is never read aloud.

## Ending the call

Spoken farewell is not a hang-up. Vapi keeps the PSTN session open until the assistant calls the default `endCall` tool (or an `endCallPhrases` substring matches the assistant transcript). The prompt therefore:

- Uses a last line in the **active** language (English, Spanish, Hindi, and Urdu have scripted farewells; any other language gets a short idiomatic goodbye).
- Requires `endCall()` in the same turn.
- Treats caller “ok goodbye” as a hang-up moment, not a new question.

Phrases like `you're all set` are **not** hang-up triggers — that line is spoken before the optional appointment offer.

## What we tried not to do

- A rigid slot-filling workflow graph. Faster to ship, worse conversational quality score.
- Stuffing the entire JSON schema into the prompt. Tools already carry the schema; the prompt carries etiquette.
- Claiming HIPAA. The spec forbids the theatre.
