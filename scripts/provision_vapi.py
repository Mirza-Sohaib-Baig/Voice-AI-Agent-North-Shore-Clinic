#!/usr/bin/env python3
"""Create/update the Vapi assistant, custom tools, and webhook credential.

Prereqs (see docs/setup/05-vapi-setup.md):
  VAPI_API_KEY, VAPI_WEBHOOK_SECRET, PUBLIC_BASE_URL
Optional:
  VAPI_ASSISTANT_ID — PATCH an existing assistant instead of creating a new one.

This does not import the Twilio number (that stays a dashboard click so we never
handle Twilio auth tokens in this repo). After it prints the assistant id, assign
the imported number to the assistant in the Vapi dashboard.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402

PROMPT = (ROOT / "app" / "voice" / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
ASSISTANT_TEMPLATE = json.loads((ROOT / "vapi" / "assistant.json").read_text(encoding="utf-8"))

API = "https://api.vapi.ai"

# Public Vapi/ElevenLabs Rachel. The nickname "rachel" 400s if the org has an ElevenLabs credential.
RACHEL_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"


def _end_call_key(phrase: str) -> str:
    """Vapi uniqueness ignores case, accents, and punctuation (Talk fails otherwise)."""
    folded = unicodedata.normalize("NFKD", phrase).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


def _unique_end_call_phrases(phrases: list[str] | None) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for phrase in phrases or []:
        key = _end_call_key(phrase)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(phrase)
    return unique


def _voice() -> dict:
    """Working ElevenLabs id + multilingual TTS. Nickname 'rachel' 400s with BYO credentials."""
    voice = dict(ASSISTANT_TEMPLATE.get("voice") or {})
    if voice.get("voiceId") in {None, "", "rachel"}:
        voice["voiceId"] = RACHEL_VOICE_ID
    voice["provider"] = "11labs"
    voice.setdefault("model", "eleven_multilingual_v2")
    return {k: v for k, v in voice.items() if v is not None}


def _transcriber_fallback(primary: dict) -> dict | None:
    if (primary or {}).get("model") == "nova-3":
        return {**primary, "model": "nova-2"}
    return None


def _raise(res: httpx.Response) -> None:
    if res.is_error:
        print(f"Vapi {res.status_code} {res.request.method} {res.request.url}: {res.text[:1000]}")
        res.raise_for_status()


def _client(settings) -> httpx.Client:
    if not settings.vapi_api_key:
        sys.exit("VAPI_API_KEY is required")
    return httpx.Client(
        base_url=API,
        headers={"Authorization": f"Bearer {settings.vapi_api_key}", "Content-Type": "application/json"},
        timeout=30.0,
    )


def _server_url(settings) -> str:
    base = (settings.public_base_url or settings.app_base_url).rstrip("/")
    if not base.startswith("https://"):
        print("WARNING: PUBLIC_BASE_URL should be HTTPS (Render or ngrok). Vapi will reject http://localhost.")
    return f"{base}/api/v1/vapi/webhook"


def tool_payloads(server_url: str) -> list[dict]:
    common_server = {"url": server_url, "timeoutSeconds": 20}
    fields = ASSISTANT_TEMPLATE["tools"]
    out = []
    for tool in fields:
        if tool.get("type") == "endCall":
            continue
        body = {
            "type": "function",
            "function": tool["function"],
            "server": common_server,
            "async": False,
            "messages": tool.get("messages", []),
        }
        out.append(body)
    return out


def ensure_end_call_tool(client: httpx.Client) -> str | None:
    """Vapi default tool that actually disconnects PSTN. Phrases alone are unreliable."""
    existing = client.get("/tool").json()
    if isinstance(existing, list):
        for t in existing:
            fn = (t.get("function") or {}).get("name") or t.get("name")
            if t.get("type") == "endCall" or fn == "endCall":
                print(f"using existing endCall tool ({t.get('id')})")
                return t["id"]

    payload = {
        "type": "endCall",
        "function": {
            "name": "endCall",
            "description": (
                "Hang up immediately after a farewell. Call this as soon as the "
                "conversation is finished; do not wait for the caller to hang up."
            ),
        },
    }
    res = client.post("/tool", json=payload)
    if res.is_error:
        print(
            f"WARNING: could not create endCall tool ({res.status_code}): {res.text[:300]}\n"
            "The assistant PATCH will attach an inline endCall tool instead."
        )
        return None
    tid = res.json()["id"]
    print(f"created tool endCall ({tid})")
    return tid


def create_or_replace_tools(client: httpx.Client, payloads: list[dict]) -> list[str]:
    """Create each tool. Listing+matching by name keeps reruns from stacking duplicates
    as well as Vapi's API allows without a delete-by-name endpoint."""
    existing = client.get("/tool").json()
    by_name = {}
    if isinstance(existing, list):
        for t in existing:
            fn = (t.get("function") or {}).get("name") or t.get("name")
            if fn:
                by_name[fn] = t.get("id")

    ids = []
    for payload in payloads:
        name = payload["function"]["name"]
        existing_id = by_name.get(name)
        if existing_id:
            res = client.patch(f"/tool/{existing_id}", json=payload)
            _raise(res)
            ids.append(existing_id)
            print(f"updated tool {name} ({existing_id})")
        else:
            res = client.post("/tool", json=payload)
            _raise(res)
            tid = res.json()["id"]
            ids.append(tid)
            print(f"created tool {name} ({tid})")
    return ids


def upsert_assistant(
    client: httpx.Client,
    settings,
    tool_ids: list[str],
    server_url: str,
    *,
    inline_end_call: bool = False,
) -> str:
    model = ASSISTANT_TEMPLATE["model"]
    model_body: dict = {
        "provider": model["provider"],
        "model": model["model"],
        "temperature": model.get("temperature", 0.4),
        "messages": [{"role": "system", "content": PROMPT}],
        "toolIds": tool_ids,
    }
    if inline_end_call:
        model_body["tools"] = [{"type": "endCall"}]
    body = {
        "name": ASSISTANT_TEMPLATE.get("name", "Northshore Intake"),
        "firstMessage": ASSISTANT_TEMPLATE["firstMessage"],
        "model": model_body,
        "transcriber": ASSISTANT_TEMPLATE["transcriber"],
        "server": {"url": server_url, "timeoutSeconds": 20},
        "serverMessages": ASSISTANT_TEMPLATE["serverMessages"],
        "endCallPhrases": _unique_end_call_phrases(ASSISTANT_TEMPLATE.get("endCallPhrases") or []),
        "silenceTimeoutSeconds": ASSISTANT_TEMPLATE.get("silenceTimeoutSeconds", 30),
        "maxDurationSeconds": ASSISTANT_TEMPLATE.get("maxDurationSeconds", 900),
        "backgroundSound": ASSISTANT_TEMPLATE.get("backgroundSound", "off"),
        "startSpeakingPlan": ASSISTANT_TEMPLATE.get("startSpeakingPlan"),
        "stopSpeakingPlan": ASSISTANT_TEMPLATE.get("stopSpeakingPlan"),
    }
    # Drop Nones so Vapi doesn't 400.
    body = {k: v for k, v in body.items() if v is not None}

    assistant_id = settings.vapi_assistant_id
    body["voice"] = _voice()

    def _send(payload: dict, *, create: bool) -> httpx.Response:
        if create:
            return client.post("/assistant", json=payload)
        return client.patch(f"/assistant/{assistant_id}", json=payload)

    create = not bool(assistant_id)
    res = _send(body, create=create)
    if res.status_code == 400:
        fallback = _transcriber_fallback(body.get("transcriber") or {})
        if fallback:
            print(f"WARNING: transcriber nova-3 rejected ({res.text[:300]}). Retrying Deepgram nova-2 language=multi.")
            body["transcriber"] = fallback
            res = _send(body, create=create)
    _raise(res)
    if create:
        assistant_id = res.json()["id"]
        print(f"created assistant {assistant_id}")
        print("Set VAPI_ASSISTANT_ID to this value so reruns PATCH instead of creating another assistant.")
        return assistant_id
    print(f"updated assistant {assistant_id}")
    return assistant_id


def main() -> None:
    settings = get_settings()
    server_url = _server_url(settings)
    print(f"webhook: {server_url}")
    print("Remember: in the Vapi dashboard, attach a Custom Credential to this server URL")
    print(f"with header X-Vapi-Secret (no Bearer prefix). Secret is VAPI_WEBHOOK_SECRET.")

    with _client(settings) as client:
        tool_ids = create_or_replace_tools(client, tool_payloads(server_url))
        end_call_id = ensure_end_call_tool(client)
        if end_call_id:
            tool_ids.append(end_call_id)
        assistant_id = upsert_assistant(
            client,
            settings,
            tool_ids,
            server_url,
            inline_end_call=end_call_id is None,
        )
    print("SUCCESS")


if __name__ == "__main__":
    main()
