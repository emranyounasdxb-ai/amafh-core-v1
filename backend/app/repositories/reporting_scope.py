"""Current, bounded CC/PF supervision shared by employee and Case access."""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, exists, false, or_, select

from app.db.cases import product_types
from app.db.organization import (
    departments,
    designations,
    employees,
    team_memberships,
    teams,
    user_accounts,
)
from app.policies import Actor
from app.services.department_products import TARGET_PRODUCT_CODES


def sales_reporting_scope(report, manager_id, branch_id, department_id):
    """A direct report, or a member of an explicitly supervised leader's active Team.

    Relationships and product classifications are read in SQL on every request;
    a reporting link never opens an entire second department or another Branch.
    """
    report_department = departments.alias()
    manager_department = departments.alias()
    report_product = product_types.alias()
    manager_product = product_types.alias()
    classified = exists(
        select(report_department.c.id)
        .select_from(
            report_department.join(
                report_product, report_product.c.id == report_department.c.product_type_id
            )
            .join(manager_department, manager_department.c.id == department_id)
            .join(manager_product, manager_product.c.id == manager_department.c.product_type_id)
        )
        .where(
            report_department.c.id == report.c.department_id,
            report_department.c.branch_id == branch_id,
            manager_department.c.branch_id == branch_id,
            report_department.c.active.is_(True),
            manager_department.c.active.is_(True),
            report_product.c.active.is_(True),
            manager_product.c.active.is_(True),
            report_product.c.code.in_(TARGET_PRODUCT_CODES),
            manager_product.c.code.in_(TARGET_PRODUCT_CODES),
        )
        .correlate_except(report_department, manager_department, report_product, manager_product)
    )
    leader = employees.alias()
    leader_role = designations.alias()
    member_role = designations.alias()
    membership = team_memberships.alias()
    team = teams.alias()
    supervised_team = exists(
        select(membership.c.id)
        .select_from(
            membership.join(team, team.c.id == membership.c.team_id)
            .join(leader, leader.c.id == team.c.leader_employee_id)
            .join(leader_role, leader_role.c.id == leader.c.designation_id)
            .join(member_role, member_role.c.id == report.c.designation_id)
        )
        .where(
            membership.c.employee_id == report.c.id,
            membership.c.end_date.is_(None),
            membership.c.start_date <= datetime.now(ZoneInfo("Asia/Dubai")).date(),
            team.c.active.is_(True),
            team.c.branch_id == branch_id,
            team.c.department_id == report.c.department_id,
            leader.c.reporting_manager_id == manager_id,
            leader.c.status == "Active",
            leader.c.branch_id == branch_id,
            leader.c.department_id == report.c.department_id,
            leader_role.c.name == "Team Leader",
            member_role.c.name == "Sales Executive",
            report.c.status == "Active",
        )
        .correlate_except(membership, team, leader, leader_role, member_role)
    )
    return and_(
        report.c.id != manager_id,
        report.c.branch_id == branch_id,
        report.c.status != "Offboarded",
        classified,
        or_(report.c.reporting_manager_id == manager_id, supervised_team),
    )


def assigned_sales_reports(actor: Actor, report=employees):
    if (
        actor.designation != "Sales Manager"
        or actor.branch_id is None
        or actor.department_id is None
    ):
        return false()
    return sales_reporting_scope(report, actor.employee_id, actor.branch_id, actor.department_id)


def active_sales_managers(branch_id, department_id, owner_id=None):
    """Normal department approvers plus this owner's explicitly assigned manager."""
    scope = employees.c.department_id == department_id
    if owner_id is not None:
        report = employees.alias()
        assigned = exists(
            select(report.c.id)
            .where(
                report.c.id == owner_id,
                report.c.branch_id == branch_id,
                report.c.department_id == department_id,
                sales_reporting_scope(report, employees.c.id, branch_id, employees.c.department_id),
            )
            .correlate_except(report)
        )
        scope = or_(scope, assigned)
    return (
        select(employees.c.id)
        .join(designations, designations.c.id == employees.c.designation_id)
        .join(user_accounts, user_accounts.c.employee_id == employees.c.id)
        .where(
            designations.c.name == "Sales Manager",
            employees.c.status == "Active",
            employees.c.branch_id == branch_id,
            user_accounts.c.access_status == "Active",
            scope,
        )
    )
