"""Reviewed V1 PostgreSQL DDL, part 1."""

import sqlalchemy as sa
from alembic import op


def create_part1() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("actor_employee_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("context", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("before_values", sa.JSON(), nullable=True),
        sa.Column("after_values", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_actor_time", "audit_events", ["actor_employee_id", "occurred_at"], unique=False
    )
    op.create_index("ix_audit_entity", "audit_events", ["entity_type", "entity_id"], unique=False)
    op.create_table(
        "banks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("bank_code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("logo_file_id", sa.UUID(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bank_code"),
    )
    op.create_table(
        "business_units",
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "customers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.String(length=80), nullable=False),
        sa.Column("customer_type", sa.String(length=20), nullable=False),
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
        sa.CheckConstraint("customer_type IN ('Individual','Company')"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id"),
    )
    op.create_table(
        "designation_user_types",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("locked", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "name IN ('Owner','Managing Director','Sales Manager','Coordinator',"
            "'Team Leader','Sales Executive','Admin Staff','HR','Finance') AND locked"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_table(
        "product_types",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("image_file_id", sa.UUID(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "bank_product_mappings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("bank_id", sa.UUID(), nullable=False),
        sa.Column("product_type_id", sa.UUID(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["bank_id"], ["banks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_type_id"], ["product_types.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bank_id", "product_type_id"),
    )
    op.create_table(
        "branches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_unit_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["business_unit_id"], ["business_units.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "company_customers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("contact_person", sa.String(length=200), nullable=False),
        sa.Column("trade_license", sa.String(length=100), nullable=False),
        sa.Column("mobile", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id"),
        sa.UniqueConstraint("trade_license"),
    )
    op.create_table(
        "individual_customers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("emirates_id", sa.String(length=100), nullable=False),
        sa.Column("passport_number", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("employer", sa.String(length=200), nullable=False),
        sa.Column("mobile", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id"),
        sa.UniqueConstraint("emirates_id"),
        sa.UniqueConstraint("passport_number"),
    )
    op.create_table(
        "pipeline_configurations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("bank_id", sa.UUID(), nullable=False),
        sa.Column("product_type_id", sa.UUID(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bank_id"], ["banks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_type_id"], ["product_types.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bank_id", "product_type_id", "effective_date"),
        sa.UniqueConstraint("bank_id", "product_type_id", "version"),
    )
    op.create_table(
        "product_variants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("bank_id", sa.UUID(), nullable=False),
        sa.Column("product_type_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("image_file_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["bank_id"], ["banks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_type_id"], ["product_types.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bank_id", "product_type_id", "name"),
    )
    op.create_table(
        "record_scope_config",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("designation_id", sa.UUID(), nullable=False),
        sa.Column("resource", sa.String(length=80), nullable=False),
        sa.Column("scope", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("scope IN ('all','branch','department','team','own','assigned','none')"),
        sa.ForeignKeyConstraint(
            ["designation_id"], ["designation_user_types.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("designation_id", "resource"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("designation_id", sa.UUID(), nullable=False),
        sa.Column("permission_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["designation_id"], ["designation_user_types.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("designation_id", "permission_id"),
    )
