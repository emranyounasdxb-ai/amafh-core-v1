"""Branch operating-city classification for Office Timings.

AMAFH operates the Dubai and Abu Dhabi Branches, whose working hours are
configured independently. Office Timing eligibility used to compare the
editable Branch name with those two city names, so a rename broke the
configuration. Branches now carry an explicit operating city instead. It is
backfilled only from unambiguous evidence: the current name, or an audited
earlier name, equal to a seeded Branch name. Branches without such evidence
stay unclassified and cannot receive Office Timings until an authorized
Settings decision classifies them. A Branch's operating city cannot change once
it has Office Timings.

Revision ID: 20261004p12aot
Revises: 20261004p12a
"""

import sqlalchemy as sa
from alembic import op

revision = "20261004p12aot"
down_revision = "20261004p12a"
branch_labels = None
depends_on = None

CONTEXT = '{"rule": "Office Timing eligibility", "revision": "20261004p12aot"}'


def upgrade() -> None:
    op.add_column("branches", sa.Column("operating_city", sa.String(20)))
    op.create_check_constraint(
        "ck_branches_operating_city", "branches", "operating_city IN ('Dubai', 'Abu Dhabi')"
    )
    op.execute(
        """
        CREATE TEMP TABLE phase12a_branch_evidence AS
        WITH evidence AS (
          SELECT b.id, btrim(b.name) AS label FROM branches b
          UNION
          SELECT b.id, btrim(e.before_values::jsonb ->> 'name')
          FROM branches b JOIN audit_events e
            ON e.entity_type = 'branches' AND e.entity_id = b.id::text
          WHERE e.before_values IS NOT NULL AND e.before_values::jsonb ? 'name'
          UNION
          SELECT b.id, btrim(e.after_values::jsonb ->> 'name')
          FROM branches b JOIN audit_events e
            ON e.entity_type = 'branches' AND e.entity_id = b.id::text
          WHERE e.after_values IS NOT NULL AND e.after_values::jsonb ? 'name'
        )
        SELECT id, min(label) AS city
        FROM evidence WHERE label IN ('Dubai', 'Abu Dhabi')
        GROUP BY id HAVING count(DISTINCT label) = 1
        """
    )
    op.execute(
        f"""
        INSERT INTO audit_events
          (id, actor_employee_id, action, module, entity_type, entity_id,
           context, before_values, after_values, occurred_at)
        SELECT gen_random_uuid(), NULL, 'branches.classified', 'organization',
               'branches', x.id::text, '{CONTEXT}'::json,
               json_build_object('operatingCity', NULL),
               json_build_object('operatingCity', x.city), now()
        FROM phase12a_branch_evidence x
        """
    )
    op.execute(
        """
        UPDATE branches b SET operating_city = x.city
        FROM phase12a_branch_evidence x WHERE b.id = x.id
        """
    )
    op.execute("DROP TABLE phase12a_branch_evidence")
    op.execute(
        """
    CREATE OR REPLACE FUNCTION amafh_guard_office_timing() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE branch_city text;
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Office Timing versions are immutable'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended('office_timing:' || NEW.branch_id::text, 0));
      SELECT operating_city INTO branch_city FROM branches
      WHERE id = NEW.branch_id AND active FOR SHARE;
      IF branch_city IS NULL THEN RAISE EXCEPTION 'Office Timing Branch unavailable'; END IF;
      IF EXISTS (SELECT 1 FROM office_timings WHERE branch_id = NEW.branch_id
                 AND effective_date >= NEW.effective_date)
      THEN RAISE EXCEPTION 'Office Timing effective versions conflict'; END IF;
      RETURN NEW;
    END $$;
    CREATE FUNCTION amafh_guard_branch_operating_city() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.operating_city IS DISTINCT FROM OLD.operating_city
         AND EXISTS (SELECT 1 FROM office_timings t WHERE t.branch_id = OLD.id)
      THEN RAISE EXCEPTION 'Branch operating city is referenced by Office Timings'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_branch_operating_city BEFORE UPDATE ON branches
    FOR EACH ROW EXECUTE FUNCTION amafh_guard_branch_operating_city();
        """
    )


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
