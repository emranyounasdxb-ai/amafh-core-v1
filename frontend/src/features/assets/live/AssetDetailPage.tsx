import { useRef, useState, type ReactNode } from "react";
import {
  Avatar,
  Button,
  CompactDate,
  CompactDateTime,
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
  Pagination,
  PermissionDeniedState,
  RecordActions,
  RecordCount,
  RecordDetailHeader,
  SectionCard,
  Timeline,
  TruncatedText,
  formatFullNumber,
  type DataTableColumn,
  type MenuItem,
  type TimelineItem,
} from "../../../design-system";
import { canManageAssets, canOpenPage } from "../../../access";
import type { NamedRecord, Page } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { CommandFormDialog } from "../../../app/commands/CommandFormDialog";
import { useSession } from "../../../app/session/useSession";
import { useFocusRecovery } from "../../../shared/focus/useFocusRecovery";
import {
  isOffline,
  resourceFeedback,
} from "../../../shared/table/serverTable";
import {
  employeeAvatarSrc,
  employeeCode,
  employeeLookupPath,
  employeeName,
  namedLabel,
  readEmployeeLookup,
  type EmployeeDetailRecord,
} from "../../employees/live/employeePresentation";
import {
  ASSET_COMMAND_LABEL,
  assetCommand,
  assetCommandKinds,
  assetStatusTone,
  type AssetAssignment,
  type AssetCommandKind,
  type AssetHistoryEntry,
  type AssetMaintenance,
  type AssetRecord,
} from "./assetCommands";
import styles from "./AssetDetailPage.module.css";

function Text({ value }: { value: string | null | undefined }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

function Days({ value }: { value: number | null | undefined }) {
  return typeof value === "number" ? (
    <span className="ds-numeric">{formatFullNumber(value)}</span>
  ) : (
    <EmptyValue />
  );
}

function usePaged<T>(path: string, refresh: number) {
  const [state, setState] = useState({ path, page: 1, size: 10 });
  const page = state.path === path ? state.page : 1;
  const size = state.size;
  const resource = useResource<Page<T>>(
    `${path}?page=${page}&pageSize=${size}`,
    refresh,
  );
  const total = resource.data?.total ?? 0;
  return {
    resource,
    rows: resource.data?.items ?? [],
    total,
    page,
    size,
    pageCount: Math.max(1, Math.ceil(total / size)),
    setPage: (next: number) => setState({ path, page: next, size }),
    setSize: (next: number) => setState({ path, page: 1, size: next }),
  };
}

type Paged<T> = ReturnType<typeof usePaged<T>>;

function PagedSection<T>({
  title,
  paged,
  emptyTitle,
  emptyDescription,
  children,
}: {
  title: string;
  paged: Paged<T>;
  emptyTitle: string;
  emptyDescription: string;
  children: ReactNode;
}) {
  const feedback = resourceFeedback(paged.resource, `Loading ${title.toLowerCase()}`);
  return (
    <SectionCard compact title={title} className={styles.table}>
      {feedback ?? (
        <>
          <RecordCount count={paged.total} />
          {paged.total === 0 ? (
            <EmptyState title={emptyTitle} description={emptyDescription} />
          ) : (
            <>
              {children}
              <Pagination
                page={paged.page}
                pageCount={paged.pageCount}
                onPageChange={paged.setPage}
                pageSize={paged.size}
                onPageSizeChange={paged.setSize}
              />
            </>
          )}
        </>
      )}
    </SectionCard>
  );
}

export function AssetDetailPage({
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
  const [command, setCommand] = useState<AssetCommandKind | null>(null);
  const [notice, setNotice] = useState("");
  const base = `/assets/${encodeURIComponent(id)}`;
  const resource = useResource<{ asset: AssetRecord }>(base, refresh);
  const assignments = usePaged<AssetAssignment>(`${base}/assignments`, refresh);
  const maintenance = usePaged<AssetMaintenance>(`${base}/maintenance`, refresh);
  const history = usePaged<AssetHistoryEntry>(`${base}/history`, refresh);
  const branches = useResource<NamedRecord[]>("/branches");
  const asset = resource.data?.asset;
  const people = useResource<Record<string, EmployeeDetailRecord>>(
    employeeLookupPath([
      asset?.currentEmployeeId,
      ...assignments.rows.flatMap((row) => [
        row.employeeId,
        row.issuedByEmployeeId,
        row.returnedByEmployeeId,
      ]),
      ...maintenance.rows.flatMap((row) => [
        row.startedByEmployeeId,
        row.completedByEmployeeId,
      ]),
      ...history.rows.flatMap((row) => [row.employeeId, row.actorEmployeeId]),
    ]),
    refresh,
    readEmployeeLookup,
    "employee-lookup",
  );
  const pageRef = useRef<HTMLDivElement>(null);
  const armFocusRecovery = useFocusRecovery(resource.data, () => {
    const page = pageRef.current;
    return (
      page?.querySelector<HTMLElement>("[data-focus-fallback]") ??
      page?.querySelector<HTMLElement>('button[aria-label="Back"]')
    );
  });

  if (!session) return null;
  const mayWrite = canManageAssets(session);
  const canOpenEmployee = Boolean(
    openEmployee && canOpenPage(session, "employees"),
  );
  const unavailable = (
    <NotFoundState
      title="Asset unavailable"
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
  if (resource.error && !asset)
    return (
      <PageContainer>
        {isOffline(resource.error) ? (
          <OfflineState />
        ) : (
          <ErrorState description={resource.error} retry={resource.reload} />
        )}
      </PageContainer>
    );
  if (resource.loading && !asset)
    return (
      <PageContainer>
        <LoadingState title="Loading Asset" />
      </PageContainer>
    );
  if (!asset) return <PageContainer>{unavailable}</PageContainer>;

  const person = (
    employeeId: string | null | undefined,
    fallback = "Assigned employee",
  ) => {
    if (!employeeId) return "";
    const employee = people.data?.[employeeId];
    if (employee) return employeeName(employee, fallback);
    if (employeeId === session.employeeId) return session.displayName;
    return people.loading ? "Loading…" : fallback;
  };
  const branch = namedLabel(branches.data, asset.branchId);
  const holder = asset.currentEmployeeId
    ? people.data?.[asset.currentEmployeeId]
    : undefined;
  const holderName = person(asset.currentEmployeeId);
  const sim = asset.category === "SIM Card";
  const kinds = mayWrite ? assetCommandKinds(asset.status) : [];
  const primary = kinds.filter((kind) => kind !== "damage");
  const overflow: MenuItem[] = kinds.includes("damage")
    ? [
        {
          id: "damage",
          label: ASSET_COMMAND_LABEL.damage,
          danger: true,
          onSelect: () => setCommand("damage"),
        },
      ]
    : [];
  const title = asset.assetCode || "Asset";
  const subtitle = [asset.category, [asset.brand, asset.model].filter(Boolean).join(" ")]
    .filter(Boolean)
    .join(" · ");

  const assignmentColumns: DataTableColumn<AssetAssignment>[] = [
    {
      key: "employee",
      header: "Employee",
      width: "180px",
      render: (row) => <Text value={person(row.employeeId)} />,
    },
    {
      key: "issued",
      header: "Issued",
      width: "110px",
      kind: "date",
      render: (row) => <CompactDate value={row.issueDate} />,
    },
    {
      key: "returned",
      header: "Returned",
      width: "110px",
      kind: "date",
      render: (row) =>
        row.returnDate ? <CompactDate value={row.returnDate} /> : <EmptyValue />,
    },
    {
      key: "duration",
      header: "Days",
      width: "90px",
      kind: "number",
      render: (row) => <Days value={row.durationDays} />,
    },
    {
      key: "condition",
      header: "Condition on return",
      width: "160px",
      render: (row) => <Text value={row.conditionOnReturn} />,
    },
    {
      key: "reason",
      header: "Return reason",
      width: "200px",
      render: (row) => <Text value={row.returnReason} />,
    },
    {
      key: "issuedBy",
      header: "Issued by",
      width: "160px",
      render: (row) => <Text value={person(row.issuedByEmployeeId, "Team member")} />,
    },
    {
      key: "returnedBy",
      header: "Returned by",
      width: "160px",
      render: (row) => <Text value={person(row.returnedByEmployeeId, "Team member")} />,
    },
  ];
  const maintenanceColumns: DataTableColumn<AssetMaintenance>[] = [
    {
      key: "started",
      header: "Started",
      width: "110px",
      kind: "date",
      render: (row) => <CompactDate value={row.startDate} />,
    },
    {
      key: "completed",
      header: "Completed",
      width: "110px",
      kind: "date",
      render: (row) =>
        row.completionDate ? (
          <CompactDate value={row.completionDate} />
        ) : (
          <EmptyValue />
        ),
    },
    {
      key: "duration",
      header: "Days",
      width: "90px",
      kind: "number",
      render: (row) => <Days value={row.durationDays} />,
    },
    {
      key: "result",
      header: "Result",
      width: "130px",
      render: (row) => <Text value={row.resultingStatus} />,
    },
    {
      key: "notes",
      header: "Notes",
      width: "200px",
      render: (row) => <Text value={row.notes} />,
    },
    {
      key: "completionNotes",
      header: "Completion notes",
      width: "200px",
      render: (row) => <Text value={row.completionNotes} />,
    },
    {
      key: "startedBy",
      header: "Started by",
      width: "160px",
      render: (row) => <Text value={person(row.startedByEmployeeId, "Team member")} />,
    },
    {
      key: "completedBy",
      header: "Completed by",
      width: "160px",
      render: (row) => <Text value={person(row.completedByEmployeeId, "Team member")} />,
    },
  ];
  const timeline: TimelineItem[] = history.rows.map((entry) => {
    const change =
      entry.previousStatus && entry.newStatus
        ? `${entry.previousStatus} to ${entry.newStatus}`
        : entry.newStatus || "";
    const employee = entry.employeeId ? `Employee: ${person(entry.employeeId)}` : "";
    return {
      id: entry.id,
      time: <CompactDate value={entry.effectiveDate} />,
      title: entry.action,
      status: entry.newStatus || undefined,
      tone: entry.newStatus ? assetStatusTone(entry.newStatus) : undefined,
      description:
        [change, employee, entry.reason].filter(Boolean).join(" · ") ||
        undefined,
      actor: entry.actorEmployeeId
        ? `By ${person(entry.actorEmployeeId, "Team member")}`
        : undefined,
    };
  });
  const confirmation = {
    description: "Review the Asset before recording this lifecycle change.",
    facts: [
      { label: "Asset", value: title },
      { label: "Category", value: asset.category },
      { label: "Branch", value: branch },
      { label: "Current status", value: asset.status },
      ...(holderName ? [{ label: "Assigned to", value: holderName }] : []),
    ],
  };

  return (
    <PageContainer>
      <div className={styles.page} ref={pageRef}>
        <RecordDetailHeader
          title={title}
          subtitle={subtitle}
          status={asset.status}
          statusTone={assetStatusTone(asset.status)}
          onBack={back}
          actions={
            kinds.length ? (
              <RecordActions>
                {primary.map((kind, index) => (
                  <Button
                    key={kind}
                    size="compact"
                    variant={index === 0 ? "primary" : "secondary"}
                    data-focus-fallback={index === 0 || undefined}
                    onClick={() => setCommand(kind)}
                  >
                    {ASSET_COMMAND_LABEL[kind]}
                  </Button>
                ))}
                {overflow.length ? (
                  <OverflowMenu label="More Asset actions" items={overflow} />
                ) : null}
              </RecordActions>
            ) : undefined
          }
        />
        {resource.updating ? (
          <InlineNotice tone="info" title="Refreshing">
            Updating the Asset record.
          </InlineNotice>
        ) : null}
        {notice ? (
          <InlineNotice tone="success" title="Saved">
            {notice}
          </InlineNotice>
        ) : null}

        <SectionCard compact title="Asset information">
          <InfoGrid>
            <InfoField label="Asset code" value={<Text value={asset.assetCode} />} />
            <InfoField label="Category" value={<Text value={asset.category} />} />
            <InfoField label="Brand" value={<Text value={asset.brand} />} />
            <InfoField label="Model" value={<Text value={asset.model} />} />
            <InfoField label="Serial number" value={<Text value={asset.serialNumber} />} />
            {sim ? (
              <>
                <InfoField label="Mobile number" value={<Text value={asset.mobileNumber} />} />
                <InfoField
                  label="Operator / Provider"
                  value={<Text value={asset.operatorProvider} />}
                />
              </>
            ) : null}
            <InfoField label="Branch" value={<Text value={branch} />} />
            <InfoField label="Added" value={<CompactDateTime value={asset.createdAt} />} />
          </InfoGrid>
        </SectionCard>

        <SectionCard compact title="Assigned employee">
          {asset.currentEmployeeId ? (
            <div className={styles.person}>
              <Avatar
                name={holderName || "Assigned employee"}
                src={employeeAvatarSrc(holder)}
                size="md"
              />
              <div className={styles.personCopy}>
                <div className={styles.personName}>
                  <TruncatedText value={holderName || "Loading…"} />
                </div>
                <span>
                  {[holder?.designation, employeeCode(holder)]
                    .filter(Boolean)
                    .join(" · ") ||
                    (people.loading ? "Loading…" : "Details unavailable")}
                </span>
              </div>
              {holder && canOpenEmployee ? (
                <Button
                  size="compact"
                  variant="secondary"
                  onClick={() => openEmployee?.(holder.id)}
                >
                  View employee
                </Button>
              ) : null}
            </div>
          ) : (
            <p className={styles.support}>This Asset is not currently issued.</p>
          )}
        </SectionCard>

        <PagedSection
          title="Assignments"
          paged={assignments}
          emptyTitle="No assignments"
          emptyDescription="Issue and return records appear here."
        >
          <DataTable
            ariaLabel={`${title} assignments`}
            density="compact"
            columns={assignmentColumns}
            rows={assignments.rows}
            rowKey={(row) => row.id}
            loading={assignments.resource.updating}
          />
        </PagedSection>

        <PagedSection
          title="Maintenance"
          paged={maintenance}
          emptyTitle="No maintenance"
          emptyDescription="Maintenance records appear here."
        >
          <DataTable
            ariaLabel={`${title} maintenance`}
            density="compact"
            columns={maintenanceColumns}
            rows={maintenance.rows}
            rowKey={(row) => row.id}
            loading={maintenance.resource.updating}
          />
        </PagedSection>

        <PagedSection
          title="History"
          paged={history}
          emptyTitle="No history"
          emptyDescription="Lifecycle changes appear here."
        >
          <Timeline compact items={timeline} />
        </PagedSection>
      </div>

      {command ? (
        <CommandFormDialog
          command={assetCommand(command, asset, confirmation)}
          onClose={() => setCommand(null)}
          onSaved={() => {
            setNotice(`${ASSET_COMMAND_LABEL[command]} recorded.`);
            setCommand(null);
            setRefresh((value) => value + 1);
            armFocusRecovery();
          }}
        />
      ) : null}
    </PageContainer>
  );
}
