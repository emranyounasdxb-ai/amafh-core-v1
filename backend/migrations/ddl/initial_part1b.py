"""Reviewed V1 PostgreSQL DDL, part 1b."""

import sqlalchemy as sa
from alembic import op


def create_part1b() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("asset_code", sa.String(length=80), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("brand", sa.String(length=150), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("serial_number", sa.String(length=150), nullable=False),
        sa.Column("mobile_number", sa.String(length=40), nullable=True),
        sa.Column("operator_provider", sa.String(length=150), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category <> 'SIM Card' OR "
            "(mobile_number IS NOT NULL AND operator_provider IS NOT NULL)"
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_code"),
        sa.UniqueConstraint("serial_number"),
    )
    op.create_table(
        "departments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "name"),
    )
    op.create_table(
        "financial_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("bank_id", sa.UUID(), nullable=False),
        sa.Column("product_type_id", sa.UUID(), nullable=False),
        sa.Column("product_variant_id", sa.UUID(), nullable=True),
        sa.Column("pf_amount_min", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("pf_amount_max", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("cc_points", sa.Integer(), nullable=True),
        sa.Column("commission_aed", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bank_id"], ["banks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_type_id"], ["product_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["product_variant_id"], ["product_variants.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_financial_rule_context",
        "financial_rules",
        ["bank_id", "product_type_id", "effective_date"],
        unique=False,
    )
    op.create_table(
        "office_timings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "effective_date"),
    )
    op.create_table(
        "pipeline_stages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pipeline_configuration_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("expected_business_days", sa.Integer(), nullable=False),
        sa.Column("is_final", sa.Boolean(), server_default="false", nullable=False),
        sa.CheckConstraint("stage_order > 0 AND expected_business_days >= 0"),
        sa.ForeignKeyConstraint(
            ["pipeline_configuration_id"], ["pipeline_configurations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pipeline_configuration_id", "name"),
        sa.UniqueConstraint("pipeline_configuration_id", "stage_order"),
    )
    op.create_table(
        "asset_maintenance_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("resulting_status", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "employees",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("system_employee_code", sa.String(length=80), nullable=False),
        sa.Column("company_employee_code", sa.String(length=80), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("mobile", sa.String(length=40), nullable=False),
        sa.Column("personal_email", sa.String(length=254), nullable=False),
        sa.Column("nationality", sa.String(length=2), nullable=False),
        sa.Column("gender", sa.String(length=10), nullable=False),
        sa.Column("marital_status", sa.String(length=10), nullable=False),
        sa.Column("date_of_joining", sa.Date(), nullable=False),
        sa.Column("passport_number", sa.String(length=100), nullable=False),
        sa.Column("emirates_id_number", sa.String(length=100), nullable=True),
        sa.Column("designation_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column("department_id", sa.UUID(), nullable=True),
        sa.Column("reporting_manager_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="Pending Setup", nullable=False),
        sa.Column("avatar_file_id", sa.UUID(), nullable=True),
        sa.Column("cover_file_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("gender IN ('Male','Female')"),
        sa.CheckConstraint("marital_status IN ('Single','Married')"),
        sa.CheckConstraint("status IN ('Pending Setup','Active','Offboarded')"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["designation_id"], ["designation_user_types.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["reporting_manager_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_employee_code"),
        sa.UniqueConstraint("emirates_id_number"),
        sa.UniqueConstraint("passport_number"),
        sa.UniqueConstraint("system_employee_code"),
    )
    op.create_index(
        "ix_employees_branch_department", "employees", ["branch_id", "department_id"], unique=False
    )
    op.create_table(
        "targets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("designation_id", sa.UUID(), nullable=False),
        sa.Column("target_value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["designation_id"], ["designation_user_types.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("branch_id", "department_id", "designation_id", "effective_date"),
    )
    op.create_index(
        "uq_active_target",
        "targets",
        ["branch_id", "department_id", "designation_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "asset_assignments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=True),
        sa.Column("return_reason", sa.Text(), nullable=True),
        sa.Column("condition_on_return", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_issued_asset",
        "asset_assignments",
        ["asset_id"],
        unique=True,
        postgresql_where=sa.text("return_date IS NULL"),
    )
