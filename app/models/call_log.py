"""Call transcript / outcome log, keyed by Vapi call id for idempotency."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.patient import Patient


class CallOutcome(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    REGISTERED = "registered"
    UPDATED = "updated"
    ABANDONED = "abandoned"
    ERROR = "error"
    UNKNOWN = "unknown"


class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vapi_call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    from_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ended_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outcome: Mapped[CallOutcome] = mapped_column(
        Enum(
            CallOutcome,
            name="call_outcome_enum",
            native_enum=False,
            length=32,
            values_callable=lambda members: [m.value for m in members],
        ),
        nullable=False,
        default=CallOutcome.UNKNOWN,
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patients.patient_id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    patient: Mapped[Patient | None] = relationship("Patient", back_populates="call_logs")

    __table_args__ = (UniqueConstraint("vapi_call_id", name="ux_call_logs_vapi_call_id"),)
