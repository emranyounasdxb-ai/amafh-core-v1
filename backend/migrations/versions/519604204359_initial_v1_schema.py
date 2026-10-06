"""Initial confirmed V1 relational schema, reviewed against docs/05 and docs/10.

Revision ID: 519604204359
Revises:
"""

from alembic import op

from migrations.ddl.initial_part1 import create_part1
from migrations.ddl.initial_part1b import create_part1b
from migrations.ddl.initial_part2 import create_part2

revision = "519604204359"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    create_part1()
    create_part1b()
    create_part2()
    for table, column in (
        ("employees", "avatar_file_id"),
        ("employees", "cover_file_id"),
        ("banks", "logo_file_id"),
        ("product_types", "image_file_id"),
        ("product_variants", "image_file_id"),
    ):
        op.create_foreign_key(None, table, "stored_files", [column], ["id"], ondelete="RESTRICT")
    op.create_foreign_key(
        None,
        "case_stage_history",
        "csv_import_batches",
        ["csv_import_batch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute("""
    CREATE FUNCTION amafh_reject_immutable_change() RETURNS trigger
    LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Immutable record'; END $$
    """)
    for table in (
        "audit_events",
        "case_stage_history",
        "points_wallet_transactions",
        "login_failures",
        "attendance_records",
        "payment_records",
        "clawbacks",
        "case_approvals",
    ):
        op.execute(
            f"CREATE TRIGGER protect_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change()"
        )
    op.execute(
        "CREATE TRIGGER protect_employee_delete BEFORE DELETE ON employees "
        "FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change()"
    )
    op.execute(
        "CREATE TRIGGER protect_designations BEFORE UPDATE OR DELETE ON designation_user_types "
        "FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change()"
    )
    for table in (
        "employee_assignment_history",
        "team_memberships",
        "case_ownership_history",
        "asset_assignments",
        "asset_maintenance_history",
        "csv_import_row_results",
    ):
        op.execute(
            f"CREATE TRIGGER protect_{table}_delete BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change()"
        )


def downgrade() -> None:
    raise RuntimeError(
        "Forward-only initial schema; restore from verified backup when recovery is required"
    )
