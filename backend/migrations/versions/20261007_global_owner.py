"""Keep the Owner global, outside ordinary Branch/Department assignments.

Revision ID: 20261007globalowner
Revises: 20261005p12e2
"""

from alembic import op

revision = "20261007globalowner"
down_revision = "20261005p12e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # An existing assigned Owner needs individual review rather than an automatic
    # rewrite of identity or immutable assignment history.
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM employees e
        JOIN designation_user_types d ON d.id = e.designation_id
        WHERE d.name = 'Owner'
          AND (e.branch_id IS NOT NULL OR e.department_id IS NOT NULL
               OR e.reporting_manager_id IS NOT NULL)
      ) OR EXISTS (
        SELECT 1 FROM employee_assignment_history h
        JOIN employees e ON e.id = h.employee_id
        JOIN designation_user_types d ON d.id = e.designation_id
        WHERE d.name = 'Owner'
      ) THEN
        RAISE EXCEPTION 'Existing Owner assignment requires manual review';
      END IF;
    END $$
    """)
    op.execute("""
    CREATE FUNCTION amafh_guard_global_owner() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM designation_user_types
        WHERE id = NEW.designation_id AND name = 'Owner'
      ) AND (NEW.branch_id IS NOT NULL OR NEW.department_id IS NOT NULL
             OR NEW.reporting_manager_id IS NOT NULL) THEN
        RAISE EXCEPTION 'Global Owner cannot have an employee assignment';
      END IF;
      RETURN NEW;
    END $$
    """)
    op.execute("""
    CREATE TRIGGER guard_global_owner
    BEFORE INSERT OR UPDATE OF designation_id, branch_id, department_id, reporting_manager_id
    ON employees FOR EACH ROW EXECUTE FUNCTION amafh_guard_global_owner()
    """)
    op.execute("""
    CREATE FUNCTION amafh_guard_global_owner_history() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM designation_user_types
        WHERE id = NEW.designation_id AND name = 'Owner'
      ) OR EXISTS (
        SELECT 1 FROM employees e
        JOIN designation_user_types d ON d.id = e.designation_id
        WHERE e.id = NEW.employee_id AND d.name = 'Owner'
      ) THEN
        RAISE EXCEPTION 'Global Owner cannot have assignment history';
      END IF;
      RETURN NEW;
    END $$
    """)
    op.execute("""
    CREATE TRIGGER guard_global_owner_history
    BEFORE INSERT OR UPDATE OF employee_id, designation_id, branch_id, department_id
    ON employee_assignment_history
    FOR EACH ROW EXECUTE FUNCTION amafh_guard_global_owner_history()
    """)


def downgrade() -> None:
    raise RuntimeError("AMAFH migrations are forward-only; restore from a verified backup")
