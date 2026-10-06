"""Generate immutable Bank Codes and retain repeat Case approvals after owner transfer.

Revision ID: 20260926bankroute
Revises: 20260926casevoid
"""

import sqlalchemy as sa
from alembic import op

revision = "20260926bankroute"
down_revision = "20260926casevoid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE amafh_bank_code_seq AS bigint START WITH 1 NO CYCLE")
    op.execute("""
    SELECT setval('amafh_bank_code_seq', GREATEST(1, COALESCE((
      SELECT max(substring(btrim(bank_code) from 6)::bigint) + 1
      FROM banks WHERE btrim(bank_code) ~* '^BANK-[0-9]{6,18}$'
    ), 1)), false)
    """)
    op.execute("""
    CREATE FUNCTION prohibit_bank_code_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.bank_code IS DISTINCT FROM OLD.bank_code THEN
            RAISE EXCEPTION 'Bank Code is immutable';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER trg_prohibit_bank_code_change
    BEFORE UPDATE OF bank_code ON banks
    FOR EACH ROW EXECUTE FUNCTION prohibit_bank_code_change();
    """)
    op.add_column("cases", sa.Column("owner_transfer_previous_status", sa.String(80)))
    op.drop_constraint("uq_case_approval_once", "case_approvals", type_="unique")
    op.create_index("ix_case_approvals_case_time", "case_approvals", ["case_id", "approved_at"])


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
