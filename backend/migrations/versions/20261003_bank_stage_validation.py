"""Retain Bank-stage validation batches before apply.

Revision ID: 20261003bankstageval
Revises: 20261002taskviewed
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20261003bankstageval"
down_revision = "20261002taskviewed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("csv_import_batches", sa.Column("file_name", sa.String(255)))
    op.add_column("csv_import_batches", sa.Column("validation_status", sa.String(30)))
    op.add_column("csv_import_row_results", sa.Column("case_id", UUID(as_uuid=True)))
    op.add_column("csv_import_row_results", sa.Column("internal_case_id", sa.String(80)))
    op.add_column("csv_import_row_results", sa.Column("bank_case_number", sa.String(120)))
    op.add_column("csv_import_row_results", sa.Column("product_label", sa.String(150)))
    op.add_column("csv_import_row_results", sa.Column("current_stage", sa.String(150)))
    op.add_column("csv_import_row_results", sa.Column("requested_stage", sa.String(150)))
    op.add_column("csv_import_row_results", sa.Column("remark", sa.Text()))
    op.create_foreign_key(
        "fk_csv_import_row_case",
        "csv_import_row_results",
        "cases",
        ["case_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        "DROP TRIGGER IF EXISTS protect_csv_import_row_results_update ON csv_import_row_results"
    )
    op.execute(
        """
        CREATE FUNCTION amafh_bank_stage_row_apply_update() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.status = 'Valid'
             AND NEW.status IN ('Applied', 'Rejected', 'Unchanged')
             AND OLD.batch_id IS NOT DISTINCT FROM NEW.batch_id
             AND OLD.row_number IS NOT DISTINCT FROM NEW.row_number
             AND OLD.case_id IS NOT DISTINCT FROM NEW.case_id
             AND OLD.internal_case_id IS NOT DISTINCT FROM NEW.internal_case_id
             AND OLD.bank_case_number IS NOT DISTINCT FROM NEW.bank_case_number
             AND OLD.product_label IS NOT DISTINCT FROM NEW.product_label
             AND OLD.current_stage IS NOT DISTINCT FROM NEW.current_stage
             AND OLD.requested_stage IS NOT DISTINCT FROM NEW.requested_stage
             AND OLD.remark IS NOT DISTINCT FROM NEW.remark
             AND OLD.column_name IS NOT DISTINCT FROM NEW.column_name
             AND EXISTS (
               SELECT 1 FROM csv_import_batches
               WHERE id = NEW.batch_id AND kind = 'bank_stage'
             )
          THEN
            RETURN NEW;
          END IF;
          RAISE EXCEPTION 'Immutable record';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER protect_csv_import_row_results_update "
        "BEFORE UPDATE ON csv_import_row_results "
        "FOR EACH ROW EXECUTE FUNCTION amafh_bank_stage_row_apply_update()"
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only Bank-stage validation migration")
