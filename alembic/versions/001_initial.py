"""initial patients + call_logs

Revision ID: 001_initial
Revises:
Create Date: 2026-08-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATES = (
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
    "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
    "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
    "WI","WY","DC",
)
STATE_IN = ", ".join(f"'{s}'" for s in STATES)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "patients",
        sa.Column("patient_id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("first_name", sa.String(50), nullable=False),
        sa.Column("last_name", sa.String(50), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("sex", sa.String(32), nullable=False),
        sa.Column("phone_number", sa.String(10), nullable=False),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("address_line_1", sa.String(200), nullable=False),
        sa.Column("address_line_2", sa.String(200), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("zip_code", sa.String(10), nullable=False),
        sa.Column("insurance_provider", sa.String(200), nullable=True),
        sa.Column("insurance_member_id", sa.String(64), nullable=True),
        sa.Column("preferred_language", sa.String(50), nullable=False, server_default="English"),
        sa.Column("emergency_contact_name", sa.String(100), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_call_id", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("length(first_name) BETWEEN 1 AND 50", name="ck_patients_first_name_len"),
        sa.CheckConstraint("length(last_name) BETWEEN 1 AND 50", name="ck_patients_last_name_len"),
        sa.CheckConstraint("length(city) BETWEEN 1 AND 100", name="ck_patients_city_len"),
        sa.CheckConstraint("date_of_birth <= CURRENT_DATE", name="ck_patients_dob_not_future"),
        sa.CheckConstraint("phone_number ~ '^\\d{10}$'", name="ck_patients_phone_digits"),
        sa.CheckConstraint("zip_code ~ '^\\d{5}(-\\d{4})?$'", name="ck_patients_zip_format"),
        sa.CheckConstraint(
            "sex IN ('Male', 'Female', 'Other', 'Decline to Answer')",
            name="ck_patients_sex",
        ),
        sa.CheckConstraint(f"state IN ({STATE_IN})", name="ck_patients_state"),
        sa.UniqueConstraint("source_call_id", name="ux_patients_source_call_id"),
    )
    op.create_index("ix_patients_last_name", "patients", ["last_name"])
    op.create_index("ix_patients_date_of_birth", "patients", ["date_of_birth"])
    op.create_index("ix_patients_phone_number", "patients", ["phone_number"])
    op.execute(
        "CREATE UNIQUE INDEX ux_patients_phone_active "
        "ON patients (phone_number) WHERE deleted_at IS NULL"
    )

    op.create_table(
        "call_logs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("vapi_call_id", sa.String(64), nullable=False),
        sa.Column("from_number", sa.String(20), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("recording_url", sa.String(500), nullable=True),
        sa.Column("ended_reason", sa.String(100), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.patient_id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("vapi_call_id", name="ux_call_logs_vapi_call_id"),
    )


def downgrade() -> None:
    op.drop_table("call_logs")
    op.drop_index("ux_patients_phone_active", table_name="patients")
    op.drop_index("ix_patients_phone_number", table_name="patients")
    op.drop_index("ix_patients_date_of_birth", table_name="patients")
    op.drop_index("ix_patients_last_name", table_name="patients")
    op.drop_table("patients")
