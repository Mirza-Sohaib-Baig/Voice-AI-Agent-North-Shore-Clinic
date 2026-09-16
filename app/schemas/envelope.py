"""Consistent JSON envelope: {\"data\": ..., \"error\": null}."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class Envelope(BaseModel, Generic[T]):
    data: T | None
    error: ErrorBody | None = None


def ok(data: T) -> dict[str, Any]:
    return {"data": data, "error": None}


def err(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "data": None,
        "error": {"code": code, "message": message, "details": details},
    }


class FieldError(BaseModel):
    field: str
    message: str
