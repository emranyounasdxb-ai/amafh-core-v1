"""Retain Cases under an immutable administrative void marker.

Revision ID: 20260926casevoid
Revises: 20260926casefloor
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260926casevoid"
down_revision = "20260926casefloor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("administratively_voided_at", sa.DateTime(timezone=True)))
    op.add_column(
        "cases", sa.Column("administratively_voided_by_employee_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column("cases", sa.Column("administrative_void_reason", sa.Text()))
    op.create_foreign_key(
        "fk_cases_administrative_void_actor",
        "cases",
        "employees",
        ["administratively_voided_by_employee_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_cases_administrative_void_complete",
        "cases",
        "(administratively_voided_at IS NULL AND administratively_voided_by_employee_id IS NULL "
        "AND administrative_void_reason IS NULL) OR "
        "(administratively_voided_at IS NOT NULL AND "
        "administratively_voided_by_employee_id IS NOT NULL AND "
        "administrative_void_reason IS NOT NULL AND "
        "length(btrim(administrative_void_reason)) > 0)",
    )
    op.create_index("ix_cases_voided_at", "cases", ["administratively_voided_at"])
    op.execute("""
    CREATE FUNCTION prevent_voided_case_changes() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF OLD.administratively_voided_at IS NOT NULL THEN
            RAISE EXCEPTION 'Administratively voided Cases are immutable';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER trg_prevent_voided_case_changes
    BEFORE UPDATE ON cases FOR EACH ROW EXECUTE FUNCTION prevent_voided_case_changes();
    CREATE FUNCTION prohibit_case_deletion() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'Permanent Case deletion is prohibited';
    END $$;
    CREATE TRIGGER trg_prohibit_case_deletion
    BEFORE DELETE ON cases FOR EACH ROW EXECUTE FUNCTION prohibit_case_deletion();
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
