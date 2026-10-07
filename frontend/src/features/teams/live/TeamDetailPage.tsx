import { useState } from "react";
import {
  Avatar,
  Button,
  DataTable,
  EmptyState,
  EmptyValue,
  ErrorState,
  InfoField,
  InfoGrid,
  InlineNotice,
  LoadingState,
  NotFoundState,
  OfflineState,
  OverflowMenu,
  PageContainer,
  PermissionDeniedState,
  RecordActions,
  RecordDetailHeader,
  SectionCard,
  StatusBadge,
  TruncatedText,
  type DataTableColumn,
  type MenuItem,
} from "../../../design-system";
import { canManageTeams, canOpenPage } from "../../../access";
import type { NamedRecord } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import { useConnectedColumnLayout } from "../../../shared/table/useConnectedColumnLayout";
import {
  employeeAvatarSrc,
  employeeCode,
  employeeLookupPath,
  employeeName,
  employeeStatusTone,
  namedLabel,
  readEmployeeLookup,
  type EmployeeLabelRecord,
} from "../../employees/live/employeePresentation";
import { TeamCommandDialog, type TeamCommand } from "./TeamCommandDialog";
import { teamScopeFromDetail, type TeamDetailRecord } from "./teamCommands";
import styles from "./TeamDetailPage.module.css";

type Member = {
  id: string;
  name: string;
  code: string;
  designation: string;
  status: string;
  employee?: EmployeeLabelRecord;
};

const MEMBER_COLUMNS = [
  { key: "avatar", label: "Avatar", width: 72, fixed: true },
  { key: "name", label: "Name", width: 200 },
  { key: "code", label: "Employee code", width: 140 },
  { key: "designation", label: "Designation", width: 160 },
  { key: "status", label: "Status", width: 120 },
  { key: "actions", label: "Actions", width: 80, fixed: true },
];

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

function Text({ value }: { value: string }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

export function TeamDetailPage({
  id,
  back,
  openEmployee,
}: {
  id: string;
  back: () => void;
  openEmployee?: (id: string) => void;
}) {
  const { session } = useSession();
  const [refresh, setRefresh] = useState(0);
  const [command, setCommand] = useState<TeamCommand | null>(null);
  const [notice, setNotice] = useState("");
  const layout = useConnectedColumnLayout<Member>(
    "team-members",
    MEMBER_COLUMNS,
  );
  const resource = useResource<TeamDetailRecord>(`/teams/${id}`, refresh);
  const branches = useResource<NamedRecord[]>("/branches");
  const departments = useResource<NamedRecord[]>("/departments");
  const team = resource.data;
  const people = useResource<Record<string, EmployeeLabelRecord>>(
    employeeLookupPath(
      team ? [team.leaderEmployeeId, ...team.memberEmployeeIds] : [],
    ),
    refresh,
    readEmployeeLookup,
    "employee-lookup",
  );

  if (!session) return null;
  const mayWrite = canManageTeams(session);
  const canOpenEmployee = Boolean(
    openEmployee && canOpenPage(session, "employees"),
  );
  const unavailable = (
    <NotFoundState
      title="Team unavailable"
      description="This record is not available in the current authorized scope."
      action={
        <Button variant="secondary" onClick={back}>
          Back
        </Button>
      }
    />
  );
  if (resource.denied) {
    const missing = /unavailable|not found/i.test(resource.error);
    return (
      <PageContainer>
        {missing ? unavailable : <PermissionDeniedState />}
      </PageContainer>
    );
  }
  if (resource.error && !team)
    return (
      <PageContainer>
        {isOffline(resource.error) ? (
          <OfflineState />
        ) : (
          <ErrorState description={resource.error} retry={resource.reload} />
        )}
      </PageContainer>
    );
  if (resource.loading && !team)
    return (
      <PageContainer>
        <LoadingState title="Loading Team" />
      </PageContainer>
    );
  if (!team) return <PageContainer>{unavailable}</PageContainer>;

  const branch = namedLabel(branches.data, team.branchId);
  const department = namedLabel(departments.data, team.departmentId);
  const leader = people.data?.[team.leaderEmployeeId];
  const leaderName = leader
    ? employeeName(leader)
    : people.loading
      ? ""
      : "Assigned employee";
  const members: Member[] = team.memberEmployeeIds.map((memberId) => {
    const employee = people.data?.[memberId];
    return {
      id: memberId,
      name: employee ? employeeName(employee) : "Team member",
      code: employeeCode(employee),
      designation: employee?.designation || "",
      status: employee?.status || "",
      employee,
    };
  });
  const writable = mayWrite && team.active;

  const overflow: MenuItem[] = writable
    ? [
        {
          id: "rename",
          label: "Rename Team",
          onSelect: () => setCommand({ kind: "rename" }),
        },
        {
          id: "deactivate",
          label: "Deactivate Team",
          danger: true,
          separator: true,
          onSelect: () => setCommand({ kind: "deactivate" }),
        },
      ]
    : [];

  const memberActions = (member: Member): MenuItem[] => {
    const items: MenuItem[] = [];
    if (canOpenEmployee && member.employee)
      items.push({
        id: "open",
        label: "View employee",
        onSelect: () => openEmployee?.(member.id),
      });
    if (writable)
      items.push({
        id: "remove",
        label: "Remove member",
        danger: true,
        separator: items.length > 0,
        onSelect: () =>
          setCommand({
            kind: "remove",
            memberId: member.id,
            memberName: member.name,
          }),
      });
    return items;
  };
  const showActions = writable || canOpenEmployee;
  const columns: DataTableColumn<Member>[] = layout.columns
    .filter((column) => showActions || column.key !== "actions")
    .map((column) => ({
      key: column.key,
      header: column.label,
      width: `${column.width}px`,
      fixed: column.fixed,
      render: (member) => {
        switch (column.key) {
          case "avatar":
            return (
              <Avatar
                name={member.name}
                src={employeeAvatarSrc(member.employee)}
                size="sm"
              />
            );
          case "name":
            return <Text value={member.name} />;
          case "code":
            return <Text value={member.code} />;
          case "designation":
            return <Text value={member.designation} />;
          case "status":
            return member.status ? (
              <StatusBadge tone={employeeStatusTone(member.status)}>
                {member.status}
              </StatusBadge>
            ) : (
              <EmptyValue />
            );
          case "actions": {
            const items = memberActions(member);
            return items.length ? (
              <OverflowMenu
                label={`Actions for ${member.name}`}
                items={items}
              />
            ) : (
              <EmptyValue />
            );
          }
          default:
            return <EmptyValue />;
        }
      },
    }));

  return (
    <PageContainer>
      <div className={styles.page}>
        <RecordDetailHeader
          title={team.name}
          subtitle={[branch, department].filter(Boolean).join(" · ")}
          status={team.active ? "Active" : "Inactive"}
          statusTone={team.active ? "success" : "neutral"}
          onBack={back}
          actions={
            writable ? (
              <RecordActions>
                <Button
                  size="compact"
                  onClick={() => setCommand({ kind: "member" })}
                >
                  Add member
                </Button>
                <Button
                  size="compact"
                  variant="secondary"
                  onClick={() => setCommand({ kind: "leader" })}
                >
                  Change Team Leader
                </Button>
                <OverflowMenu label="More Team actions" items={overflow} />
              </RecordActions>
            ) : undefined
          }
        />
        {resource.updating ? (
          <InlineNotice tone="info" title="Refreshing">
            Updating the Team record.
          </InlineNotice>
        ) : null}
        {notice ? (
          <InlineNotice tone="success" title="Saved">
            {notice}
          </InlineNotice>
        ) : null}

        <SectionCard compact title="Team information">
          <InfoGrid>
            <InfoField label="Branch" value={<Text value={branch} />} />
            <InfoField
              label="Department"
              value={<Text value={department} />}
            />
            <InfoField
              label="Team Leader"
              value={<Text value={leaderName} />}
            />
            <InfoField
              label="Members"
              numeric
              value={team.memberEmployeeIds.length}
            />
            <InfoField
              label="Status"
              value={
                <StatusBadge tone={team.active ? "success" : "neutral"}>
                  {team.active ? "Active" : "Inactive"}
                </StatusBadge>
              }
            />
          </InfoGrid>
        </SectionCard>

        <SectionCard compact title="Team Leader">
          <div className={styles.person}>
            <Avatar
              name={leaderName || "Team Leader"}
              src={employeeAvatarSrc(leader)}
              size="md"
            />
            <div className={styles.personCopy}>
              <div className={styles.personName}>
                <TruncatedText value={leaderName || "Loading…"} />
              </div>
              <span>
                {[leader?.designation, employeeCode(leader)]
                  .filter(Boolean)
                  .join(" · ") ||
                  (people.loading ? "Loading…" : "Details unavailable")}
              </span>
            </div>
            {leader && canOpenEmployee ? (
              <Button
                size="compact"
                variant="secondary"
                onClick={() => openEmployee?.(leader.id)}
              >
                View employee
              </Button>
            ) : null}
          </div>
        </SectionCard>

        <SectionCard
          compact
          title="Members"
          description={`${members.length} active ${members.length === 1 ? "member" : "members"}`}
          className={styles.table}
        >
          {members.length ? (
            <DataTable
              ariaLabel={`${team.name} members`}
              density="compact"
              columns={columns}
              rows={members}
              rowKey={(member) => member.id}
              loading={people.loading && !people.data}
              onRowActivate={
                canOpenEmployee
                  ? (member) => {
                      if (member.employee) openEmployee?.(member.id);
                    }
                  : undefined
              }
              rowActivateLabel={(member) => `Open ${member.name}`}
              onColumnResize={layout.resize}
              onColumnReorder={layout.move}
            />
          ) : (
            <EmptyState
              title="No active members"
              description="This Team has no active memberships."
            />
          )}
        </SectionCard>
      </div>

      {command ? (
        <TeamCommandDialog
          command={command}
          team={teamScopeFromDetail(team)}
          name={team.name}
          branch={branch}
          department={department}
          leader={leaderName}
          onClose={() => setCommand(null)}
          onSaved={(message) => {
            setCommand(null);
            setNotice(message);
            setRefresh((value) => value + 1);
          }}
        />
      ) : null}
    </PageContainer>
  );
}
