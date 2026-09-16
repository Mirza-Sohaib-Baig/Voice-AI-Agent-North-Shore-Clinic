"""Webhook authentication helpers."""

from __future__ import annotations

import hmac
import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def verify_vapi_secret(x_vapi_secret: str | None, authorization: str | None = None) -> None:
    """Accept either X-Vapi-Secret (preferred) or Authorization: Bearer <secret>."""
    expected = get_settings().vapi_webhook_secret
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="VAPI_WEBHOOK_SECRET is not configured",
        )

    provided = x_vapi_secret
    if not provided and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            provided = token.strip()
        else:
            provided = authorization.strip()

    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )


async def require_vapi_secret(
    x_vapi_secret: str | None = Header(default=None, alias="X-Vapi-Secret"),
    authorization: str | None = Header(default=None),
) -> None:
    verify_vapi_secret(x_vapi_secret, authorization)


def generate_secret() -> str:
    return secrets.token_urlsafe(48)
