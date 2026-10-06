"""Department product classification and the whole-number business rule.

Departments gain an explicit Product classification so Targets and Performance
no longer depend on Department display names. The classification is backfilled
only from unambiguous evidence: the current name or an audited earlier name that
equals one of the two originally seeded classification names. Departments
without such evidence stay unclassified for an authorized Settings decision.

Business amounts become NUMERIC(18,0) (DEC-051). Every changed row receives an
audit event with its exact before and after values. The conversion stops instead
of guessing when rounding would violate a positive-amount rule or make active PF
slabs overlap.

Revision ID: 20261004p12a
Revises: 20261003bankstageval
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20261004p12a"
down_revision = "20261003bankstageval"
branch_labels = None
depends_on = None

CONTEXT = '{"rule": "DEC-051", "revision": "20261004p12a"}'

# table -> (audit entity type, audit module, converted columns, positive-only columns)
CONVERSIONS = {
    "cases": ("case", "cases", ("requested_pf_amount",), ("requested_pf_amount",)),
    "financial_rules": (
        "financial_rule",
        "finance",
        ("pf_amount_min", "pf_amount_max", "commission_aed"),
        ("pf_amount_min", "pf_amount_max"),
    ),
    "clawbacks": ("clawback", "finance", ("amount_aed",), ("amount_aed",)),
    "payment_records": ("payment_record", "finance", ("amount_aed",), ("amount_aed",)),
    "targets": ("target", "targets", ("target_amount_aed",), ("target_amount_aed",)),
    "case_financial_results": (
        "case_financial_result",
        "finance",
        ("commission_aed", "pf_amount_aed"),
        (),
    ),
}


def _classify_departments() -> None:
    op.add_column(
        "departments",
        sa.Column(
            "product_type_id",
            UUID(as_uuid=True),
            sa.ForeignKey("product_types.id", ondelete="RESTRICT"),
        ),
    )
    op.create_index("ix_departments_product_type_id", "departments", ["product_type_id"])
    op.execute(
        """
        CREATE TEMP TABLE phase12a_department_evidence AS
        WITH evidence AS (
          SELECT d.id, btrim(d.name) AS label FROM departments d
          UNION
          SELECT d.id, btrim(e.before_values::jsonb ->> 'name')
          FROM departments d JOIN audit_events e
            ON e.entity_type = 'departments' AND e.entity_id = d.id::text
          WHERE e.before_values IS NOT NULL AND e.before_values::jsonb ? 'name'
          UNION
          SELECT d.id, btrim(e.after_values::jsonb ->> 'name')
          FROM departments d JOIN audit_events e
            ON e.entity_type = 'departments' AND e.entity_id = d.id::text
          WHERE e.after_values IS NOT NULL AND e.after_values::jsonb ? 'name'
        ), mapped AS (
          SELECT id,
                 CASE label WHEN 'Credit Card Sales' THEN 'CC'
                            WHEN 'Personal Finance Sales' THEN 'PF' END AS code
          FROM evidence
        )
        SELECT id, min(code) AS code
        FROM mapped WHERE code IS NOT NULL
        GROUP BY id HAVING count(DISTINCT code) = 1
        """
    )
    op.execute(
        f"""
        INSERT INTO audit_events
          (id, actor_employee_id, action, module, entity_type, entity_id,
           context, before_values, after_values, occurred_at)
        SELECT gen_random_uuid(), NULL, 'departments.classified', 'organization',
               'departments', x.id::text, '{CONTEXT}'::json,
               json_build_object('productTypeCode', NULL),
               json_build_object('productTypeCode', x.code), now()
        FROM phase12a_department_evidence x
        JOIN product_types p ON p.code = x.code
        """
    )
    op.execute(
        """
        UPDATE departments d SET product_type_id = p.id
        FROM phase12a_department_evidence x JOIN product_types p ON p.code = x.code
        WHERE d.id = x.id
        """
    )
    op.execute("DROP TABLE phase12a_department_evidence")


def _replace_target_guard() -> None:
    op.execute(
        """
    CREATE OR REPLACE FUNCTION amafh_guard_target_version() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE department_product text;
    DECLARE department_found boolean := FALSE;
    DECLARE today_dubai date := (now() AT TIME ZONE 'Asia/Dubai')::date;
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Target history is immutable'; END IF;
      IF TG_OP = 'UPDATE' THEN
        IF (to_jsonb(NEW) - 'active' - 'inactive_from_date' - 'superseded_by_target_id')
           IS DISTINCT FROM
           (to_jsonb(OLD) - 'active' - 'inactive_from_date' - 'superseded_by_target_id')
           OR OLD.superseded_by_target_id IS NOT NULL
           OR (OLD.active = FALSE AND NEW.active = TRUE)
           OR (OLD.inactive_from_date IS NOT NULL
               AND NEW.inactive_from_date IS DISTINCT FROM OLD.inactive_from_date)
           OR (OLD.active = TRUE AND NEW.active = FALSE
               AND (NEW.inactive_from_date IS NULL
                    OR NEW.inactive_from_date < today_dubai
                    OR NEW.inactive_from_date < OLD.effective_date))
           OR (OLD.active = FALSE AND
               (NEW.active IS DISTINCT FROM OLD.active
                OR NEW.inactive_from_date IS DISTINCT FROM OLD.inactive_from_date
                OR NEW.superseded_by_target_id IS NULL))
        THEN RAISE EXCEPTION 'Target history is immutable'; END IF;
        IF NEW.superseded_by_target_id IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM targets successor WHERE successor.id = NEW.superseded_by_target_id
          AND successor.branch_id = OLD.branch_id
          AND successor.department_id = OLD.department_id
          AND successor.designation_id = OLD.designation_id
          AND successor.effective_date = NEW.inactive_from_date
        ) THEN RAISE EXCEPTION 'Invalid Target successor'; END IF;
        RETURN NEW;
      END IF;
      IF NEW.active IS DISTINCT FROM TRUE OR NEW.inactive_from_date IS NOT NULL
         OR NEW.superseded_by_target_id IS NOT NULL
         OR NEW.effective_date < today_dubai
      THEN RAISE EXCEPTION 'New Target version must start active'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(
        NEW.branch_id::text || NEW.department_id::text || NEW.designation_id::text, 0));
      SELECT TRUE, p.code INTO department_found, department_product
        FROM departments d JOIN branches b ON b.id = d.branch_id
        LEFT JOIN product_types p ON p.id = d.product_type_id
        WHERE d.id = NEW.department_id
        AND d.branch_id = NEW.branch_id AND d.active AND b.active FOR SHARE OF d, b;
      IF department_found IS NOT TRUE OR NOT EXISTS (
          SELECT 1 FROM designation_user_types des
          WHERE des.id = NEW.designation_id AND des.locked
      ) THEN RAISE EXCEPTION 'Inactive Target context'; END IF;
      IF (department_product = 'CC' AND
          (NEW.target_points IS NULL OR NEW.target_amount_aed IS NOT NULL))
         OR (department_product = 'PF' AND
          (NEW.target_amount_aed IS NULL OR NEW.target_points IS NOT NULL))
         OR department_product IS NULL OR department_product NOT IN ('CC', 'PF')
      THEN RAISE EXCEPTION 'Target type does not match Department'; END IF;
      IF EXISTS (
          SELECT 1 FROM targets t WHERE t.branch_id = NEW.branch_id
          AND t.department_id = NEW.department_id
          AND t.designation_id = NEW.designation_id
          AND t.effective_date < 'infinity'::date
          AND (t.inactive_from_date IS NULL OR t.inactive_from_date > NEW.effective_date)
      ) THEN RAISE EXCEPTION 'Target effective periods overlap'; END IF;
      RETURN NEW;
    END $$;
        """
    )
    # Targets keep their Department classification for their whole history.
    op.execute(
        """
    CREATE FUNCTION amafh_guard_department_classification() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.product_type_id IS DISTINCT FROM OLD.product_type_id
         AND EXISTS (SELECT 1 FROM targets t WHERE t.department_id = OLD.id)
      THEN RAISE EXCEPTION 'Department classification is referenced by Targets'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_department_classification BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION amafh_guard_department_classification();
        """
    )


def _guard_conversion() -> None:
    for table, (_, _, _, positive) in CONVERSIONS.items():
        for column in positive:
            op.execute(
                f"""
                DO $$ BEGIN
                  IF EXISTS (SELECT 1 FROM {table}
                             WHERE {column} IS NOT NULL AND {column} > 0 AND round({column}) <= 0)
                  THEN RAISE EXCEPTION
                    'Whole-number conversion would make {table}.{column} non-positive';
                  END IF;
                END $$
                """
            )
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM financial_rules r
            WHERE r.product_variant_id IS NULL AND round(r.pf_amount_min) > round(r.pf_amount_max)
          ) OR EXISTS (
            SELECT 1 FROM financial_rules a JOIN financial_rules b
              ON a.id < b.id AND a.active AND b.active
             AND a.product_variant_id IS NULL AND b.product_variant_id IS NULL
             AND a.bank_id = b.bank_id AND a.product_type_id = b.product_type_id
             AND round(a.pf_amount_min) <= round(b.pf_amount_max)
             AND round(a.pf_amount_max) >= round(b.pf_amount_min)
          ) THEN RAISE EXCEPTION
            'Whole-number conversion would make active PF amount slabs invalid or overlapping';
          END IF;
        END $$
        """
    )


def _convert_amounts() -> None:
    for table, (entity, module, columns, _) in CONVERSIONS.items():
        changed = " OR ".join(f"{c} IS DISTINCT FROM round({c})" for c in columns)
        before = ", ".join(
            f"'{c}', CASE WHEN {c} IS DISTINCT FROM round({c}) THEN {c}::text END" for c in columns
        )
        after = ", ".join(
            f"'{c}', CASE WHEN {c} IS DISTINCT FROM round({c}) THEN round({c})::text END"
            for c in columns
        )
        op.execute(
            f"""
            INSERT INTO audit_events
              (id, actor_employee_id, action, module, entity_type, entity_id,
               context, before_values, after_values, occurred_at)
            SELECT gen_random_uuid(), NULL, 'record.whole_number_converted', '{module}',
                   '{entity}', id::text, '{CONTEXT}'::json,
                   json_strip_nulls(json_build_object({before})),
                   json_strip_nulls(json_build_object({after})), now()
            FROM {table} WHERE {changed}
            """
        )
        for column in columns:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {column} TYPE numeric(18,0) "
                f"USING round({column})"
            )


def upgrade() -> None:
    _classify_departments()
    _replace_target_guard()
    _guard_conversion()
    _convert_amounts()


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
