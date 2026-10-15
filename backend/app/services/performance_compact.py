"""Aggregate retained facts only for populations with proven stable scope."""

import json
from datetime import date
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession


def stable_period(assignments, memberships, leaderships, changes, start, end) -> bool:
    if changes or len(assignments) != 1:
        return False
    assignment = assignments[0]
    if assignment["assignment_start_date"] > start or assignment["assignment_end_date"] is not None:
        return False
    for rows in (memberships, leaderships):
        if rows and (
            len(rows) != 1 or rows[0]["start_date"] > start or rows[0]["end_date"] is not None
        ):
            return False
    return start <= end


# Case ownership remains an instant boundary, even when employee scope is stable.
# UUID ordering is equivalent to the canonical UUID-string tie break in Python.
# Every relation is read in the same statement snapshot; no response is cached.
_FACTS = text("""
WITH supplied AS MATERIALIZED (
 SELECT value AS p, CAST(value->>'id' AS uuid) AS proof_id
 FROM jsonb_array_elements(CAST(:proofs AS jsonb))
),
eligible AS MATERIALIZED (
 SELECT proof_id AS employee_id FROM supplied
 WHERE p->'assignments'=COALESCE((
  SELECT jsonb_agg(jsonb_build_object('id',h.id,'branch_id',h.branch_id,
   'department_id',h.department_id,'designation_id',h.designation_id,
   'assignment_start_date',h.assignment_start_date,'assignment_end_date',h.assignment_end_date))
  FROM employee_assignment_history h WHERE h.employee_id=proof_id), '[]'::jsonb)
 AND p->'memberships'=COALESCE((
  SELECT jsonb_agg(jsonb_build_object('id',h.id,'team_id',h.team_id,
   'start_date',h.start_date,'end_date',h.end_date))
  FROM team_memberships h WHERE h.employee_id=proof_id), '[]'::jsonb)
 AND p->'leaderships'=COALESCE((
  SELECT jsonb_agg(jsonb_build_object('id',h.id,'team_id',h.team_id,
   'start_date',h.start_date,'end_date',h.end_date))
  FROM team_leader_history h WHERE h.leader_employee_id=proof_id), '[]'::jsonb)
 AND p->'person'=(SELECT jsonb_build_object('id',e.id,'branch_id',e.branch_id,
  'department_id',e.department_id,'designation_id',e.designation_id,
  'date_of_joining',e.date_of_joining) FROM employees e WHERE e.id=proof_id)
 AND NOT EXISTS (SELECT 1 FROM audit_events a WHERE a.action='employee.assignment_changed'
  AND a.entity_type='employee' AND a.entity_id=p->>'id')
), selected AS MATERIALIZED (
 SELECT c.id,c.created_by_employee_id,c.owner_employee_id,c.created_at,c.bank_id,
 c.pipeline_configuration_id,c.current_status,c.administratively_voided_at,p.code AS product_code
 FROM cases c JOIN product_types p ON p.id=c.product_type_id
 WHERE c.id IN (
  SELECT id FROM cases WHERE created_by_employee_id=ANY(:ids)
  UNION SELECT id FROM cases WHERE owner_employee_id=ANY(:ids)
  UNION SELECT case_id FROM case_ownership_history WHERE owner_employee_id=ANY(:ids)
  UNION SELECT case_id FROM case_financial_results WHERE credited_owner_employee_id=ANY(:ids)
 )
), ownership_presence AS MATERIALIZED (
 SELECT DISTINCT h.case_id FROM case_ownership_history h JOIN selected c ON c.id=h.case_id
), owner_as_of AS MATERIALIZED (
 SELECT DISTINCT ON (h.case_id) h.case_id,h.owner_employee_id
 FROM case_ownership_history h JOIN selected c ON c.id=h.case_id
 WHERE h.started_at<=:as_of AND (h.ended_at IS NULL OR :as_of<h.ended_at)
 ORDER BY h.case_id,h.started_at DESC,h.id DESC
), status_as_of AS MATERIALIZED (
 SELECT DISTINCT ON (h.case_id) h.case_id,h.status
 FROM case_lifecycle_history h JOIN selected c ON c.id=h.case_id
 WHERE h.occurred_at<=:as_of ORDER BY h.case_id,h.occurred_at DESC,h.id DESC
), stage_as_of AS MATERIALIZED (
 SELECT DISTINCT ON (h.case_id) h.case_id,h.stage,h.occurred_at
 FROM case_stage_history h JOIN selected c ON c.id=h.case_id
 WHERE h.occurred_at<=:as_of ORDER BY h.case_id,h.occurred_at DESC,h.id DESC
), current_facts AS MATERIALIZED (
 SELECT c.*, CASE WHEN op.case_id IS NULL THEN c.owner_employee_id
                 ELSE o.owner_employee_id END AS retained_owner,
 COALESCE(l.status,c.current_status) AS retained_status,
 s.stage,(s.occurred_at AT TIME ZONE 'Asia/Dubai')::date AS since,
 p.expected_business_days AS expected
 FROM selected c LEFT JOIN ownership_presence op ON op.case_id=c.id
 LEFT JOIN owner_as_of o ON o.case_id=c.id
 LEFT JOIN status_as_of l ON l.case_id=c.id
 LEFT JOIN stage_as_of s ON s.case_id=c.id
 LEFT JOIN pipeline_stages p ON p.pipeline_configuration_id=c.pipeline_configuration_id
                           AND p.name=s.stage
), lifecycle_events AS MATERIALIZED (
 SELECT DISTINCT ON (h.case_id,h.id) c.id,c.product_code,c.bank_id,h.status,
 CASE WHEN op.case_id IS NULL THEN c.owner_employee_id
      ELSE o.owner_employee_id END AS owner_id
 FROM selected c JOIN case_lifecycle_history h ON h.case_id=c.id
 LEFT JOIN ownership_presence op ON op.case_id=c.id
 LEFT JOIN case_ownership_history o ON o.case_id=c.id AND o.started_at<=h.occurred_at
   AND (o.ended_at IS NULL OR h.occurred_at<o.ended_at)
 WHERE h.status IN ('Booked','Rejected') AND h.occurred_at>=:since AND h.occurred_at<=:as_of
 ORDER BY h.case_id,h.id,o.started_at DESC NULLS LAST,o.id DESC NULLS LAST
), lifecycle AS MATERIALIZED (
 SELECT DISTINCT id,product_code,bank_id,status,owner_id FROM lifecycle_events
), activity AS (
 SELECT created_by_employee_id AS employee_id,product_code,bank_id,'created' AS kind,
 NULL::date AS day,NULL::text AS stage,NULL::date AS since,NULL::integer AS expected,
 count(*) AS fact_count,0::numeric AS amount
 FROM selected WHERE created_at>=:since AND created_at<=:as_of
 GROUP BY created_by_employee_id,product_code,bank_id
 UNION ALL
 SELECT owner_id,product_code,bank_id,CASE status WHEN 'Booked' THEN 'booked' ELSE 'rejected' END,
 NULL::date,NULL::text,NULL::date,NULL::integer,count(*),0::numeric FROM lifecycle
 GROUP BY owner_id,product_code,bank_id,status
 UNION ALL
 SELECT retained_owner,product_code,bank_id,'progress',NULL::date,stage,since,expected,
 count(*),0::numeric
 FROM current_facts WHERE created_at<=:as_of
 AND (administratively_voided_at IS NULL OR administratively_voided_at>:as_of)
 AND retained_status NOT IN ('Completed','Rejected')
 GROUP BY retained_owner,product_code,bank_id,stage,since,expected
 UNION ALL
 SELECT f.credited_owner_employee_id,f.product_code,c.bank_id,'completed',
 (f.completed_at AT TIME ZONE 'Asia/Dubai')::date,NULL::text,NULL::date,NULL::integer,
 count(*),sum(COALESCE(CASE f.product_code WHEN 'CC' THEN f.cc_points ELSE f.pf_amount_aed END,0))
 FROM case_financial_results f JOIN selected c ON c.id=f.case_id
 WHERE f.completed_at>=:since AND f.completed_at<=:as_of
 GROUP BY f.credited_owner_employee_id,f.product_code,c.bank_id,
 (f.completed_at AT TIME ZONE 'Asia/Dubai')::date
 UNION ALL
 SELECT employee_id,NULL::text,NULL::uuid,'proof',NULL::date,NULL::text,
 NULL::date,NULL::integer,1::bigint,0::numeric FROM eligible
)
SELECT employee_id,product_code,bank_id,kind,day,stage,since,expected,
 sum(fact_count)::bigint AS count,sum(amount) AS amount
FROM activity WHERE employee_id IN (SELECT employee_id FROM eligible)
GROUP BY employee_id,product_code,bank_id,kind,day,stage,since,expected
""").bindparams(bindparam("ids", type_=ARRAY(PG_UUID(as_uuid=True))))

# PostgreSQL's generic cost estimate triggers >1s of JIT compilation for this
# bounded read. Its default disk page cost also makes one employee's few Cases
# scan entire history tables instead of the existing (case_id, time) indexes;
# large populations keep the same plan. The materialized row captures previous
# values before the transaction-local overrides apply.
_LOCAL_SETTINGS = text("""
WITH previous AS MATERIALIZED (
 SELECT current_setting('jit') AS jit, current_setting('random_page_cost') AS page_cost
)
SELECT jit, page_cost, set_config('jit', 'off', true), set_config('random_page_cost', '1.1', true)
FROM previous
""")
_RESTORE_SETTINGS = text(
    "SELECT set_config('jit', :jit, true), set_config('random_page_cost', :page_cost, true)"
)


async def read(
    session: AsyncSession,
    ids: list[UUID],
    start: date,
    end: date,
    *,
    proofs: list[dict] | None = None,
) -> dict[UUID, list[dict]]:
    from datetime import datetime, time

    from app.services.performance_math import DUBAI

    if not ids or not proofs:
        return {}
    # Limit these planner settings to this statement, then restore the caller's.
    previous = (await session.execute(_LOCAL_SETTINGS)).one()
    rows = await session.execute(
        _FACTS,
        {
            "ids": ids,
            "since": datetime.combine(start, time.min, DUBAI),
            "as_of": datetime.combine(end, time.max, DUBAI),
            "proofs": json.dumps(proofs, default=str),
        },
    )
    await session.execute(_RESTORE_SETTINGS, {"jit": previous.jit, "page_cost": previous.page_cost})
    grouped: dict[UUID, list[dict]] = {}
    for row in rows.mappings():
        values = grouped.setdefault(row["employee_id"], [])
        if row["kind"] != "proof":
            values.append(dict(row))
    return grouped


def proof(person, assignments, memberships, leaderships) -> dict:
    def fields(row, names):
        return {name: row[name] for name in names}

    return {
        "id": str(person["id"]),
        "person": fields(
            person, ("id", "branch_id", "department_id", "designation_id", "date_of_joining")
        ),
        "assignments": [
            fields(
                row,
                (
                    "id",
                    "branch_id",
                    "department_id",
                    "designation_id",
                    "assignment_start_date",
                    "assignment_end_date",
                ),
            )
            for row in assignments
        ],
        "memberships": [
            fields(row, ("id", "team_id", "start_date", "end_date")) for row in memberships
        ],
        "leaderships": [
            fields(row, ("id", "team_id", "start_date", "end_date")) for row in leaderships
        ],
    }
