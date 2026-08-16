"""Narrow view of the Vapi webhook payload we actually use."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VapiToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class VapiCustomer(BaseModel):
    number: str | None = None


class VapiCall(BaseModel):
    id: str | None = None
    customer: VapiCustomer | None = None
    phone_number: dict[str, Any] | None = Field(default=None, alias="phoneNumber")

    model_config = {"populate_by_name": True}


class VapiArtifact(BaseModel):
    transcript: str | None = None
    recording: dict[str, Any] | str | None = None
    messages: list[dict[str, Any]] | None = None
    summary: str | None = None
    stereo_recording_url: str | None = Field(default=None, alias="stereoRecordingUrl")
    recording_url: str | None = Field(default=None, alias="recordingUrl")

    model_config = {"populate_by_name": True}


class VapiMessage(BaseModel):
    type: str
    timestamp: int | None = None
    tool_call_list: list[VapiToolCall] = Field(default_factory=list, alias="toolCallList")
    call: VapiCall | None = None
    artifact: VapiArtifact | None = None
    ended_reason: str | None = Field(default=None, alias="endedReason")
    status: str | None = None
    customer: VapiCustomer | None = None
    phone_number: dict[str, Any] | None = Field(default=None, alias="phoneNumber")

    model_config = {"populate_by_name": True}


class VapiWebhook(BaseModel):
    message: VapiMessage
