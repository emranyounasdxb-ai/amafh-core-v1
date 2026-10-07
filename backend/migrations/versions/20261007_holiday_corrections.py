"""Permit audited holiday corrections while retaining holiday identities and deletion protection.

No existing holiday or certification data is changed. The application retains
the existing certification gate for new dates and audits every correction.
"""

from alembic import op

revision = "20261007holidays"
down_revision = "20261007globalowner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DROP TRIGGER protect_uae_public_holidays ON uae_public_holidays;
    CREATE TRIGGER protect_uae_public_holidays BEFORE DELETE ON uae_public_holidays
    FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change();
    CREATE FUNCTION amafh_guard_holiday_correction() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.id IS DISTINCT FROM OLD.id
         OR NEW.created_by_employee_id IS DISTINCT FROM OLD.created_by_employee_id
         OR NEW.created_at IS DISTINCT FROM OLD.created_at
      THEN RAISE EXCEPTION 'Holiday retained identity is immutable'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(
        'uae_holidays:' || LEAST(OLD.applicable_year, NEW.applicable_year)::text, 0));
      IF OLD.applicable_year <> NEW.applicable_year THEN
        PERFORM pg_advisory_xact_lock(hashtextextended(
          'uae_holidays:' || GREATEST(OLD.applicable_year, NEW.applicable_year)::text, 0));
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_holiday_correction BEFORE UPDATE ON uae_public_holidays
    FOR EACH ROW EXECUTE FUNCTION amafh_guard_holiday_correction();
    """)


def downgrade() -> None:
    op.execute("""
    DROP TRIGGER guard_holiday_correction ON uae_public_holidays;
    DROP FUNCTION amafh_guard_holiday_correction();
    DROP TRIGGER protect_uae_public_holidays ON uae_public_holidays;
    CREATE TRIGGER protect_uae_public_holidays BEFORE UPDATE OR DELETE ON uae_public_holidays
    FOR EACH ROW EXECUTE FUNCTION amafh_reject_immutable_change();
    """)
