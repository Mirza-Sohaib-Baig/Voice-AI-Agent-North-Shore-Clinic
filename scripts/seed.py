#!/usr/bin/env python3
"""Insert 1–2 fictional patients so the API and dashboard aren't empty at review."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.models.patient import Patient, Sex  # noqa: E402
from datetime import date

SEEDS = [
    Patient(
        first_name="Jane",
        last_name="Doe",
        date_of_birth=date(1988, 4, 12),
        sex=Sex.FEMALE,
        phone_number="6502530000",
        email="jane.doe@example.com",
        address_line_1="1600 Amphitheatre Parkway",
        address_line_2=None,
        city="Mountain View",
        state="CA",
        zip_code="94043",
        insurance_provider="Blue Shield of California",
        insurance_member_id="BSC1234567",
        preferred_language="English",
        emergency_contact_name="John Doe",
        emergency_contact_phone="6502530001",
    ),
    Patient(
        first_name="Carlos",
        last_name="Rivera",
        date_of_birth=date(1975, 11, 3),
        sex=Sex.MALE,
        phone_number="2127365000",
        email=None,
        address_line_1="350 Fifth Avenue",
        address_line_2="Suite 1",
        city="New York",
        state="NY",
        zip_code="10118",
        preferred_language="Spanish",
    ),
]


def main() -> None:
    db = SessionLocal()
    try:
        for patient in SEEDS:
            exists = (
                db.query(Patient)
                .filter(Patient.phone_number == patient.phone_number, Patient.deleted_at.is_(None))
                .first()
            )
            if exists:
                print(f"skip existing {patient.first_name} {patient.last_name} ({patient.phone_number})")
                continue
            db.add(patient)
            print(f"seed {patient.first_name} {patient.last_name}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
