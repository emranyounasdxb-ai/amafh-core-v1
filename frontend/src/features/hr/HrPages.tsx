import { useMemo, useState } from "react";
import {
  Button,
  CompactDate,
  CompactDateTime,
  Dialog,
  DropdownSelect,
  EmptyState,
  EmptyValue,
  FormField,
  InlineNotice,
  MonetaryAmount,
  StatusBadge,
  type MenuItem,
} from "../../design-system";
import { choices } from "../../app/api/choices";
import type { ApiClient } from "../../app/api/http";
import { useResource } from "../../app/api/useResource";
import type { EmployeeSection } from "../../app/router/useAppRoute";
import { useSession } from "../../app/session/useSession";
import {
  EmployeeCommandDialog,
  type EmployeeCommandKind,
} from "../employees/live/EmployeeCommandDialog";
import {
  EMPLOYEE_STATUSES,
  canRecordLastWorkingDate,
  employeeCode,
  employeeName,
  employeeStatusTone,
  type EmployeeDetailRecord,
  type EmployeeListRecord,
} from "../employees/live/employeePresentation";
import {
  hrDocumentStatusTone,
  visaStatusTone,
  type HrDocumentItem,
  type HrDocumentStatus,
  type VisaStatus,
} from "../employees/live/hr/hrRecords";
import {
  HrListPage,
  HrText,
  type HrListColumn,
  type HrListFilter,
} from "./HrListPage";

export type OpenEmployee = (employeeId: string, section?: EmployeeSection) => void;

type Person = {
  employeeId: string;
  fullName: string | null;
  employeeCode: string | null;
  designation: string | null;
  branchName: string | null;
  departmentName: string | null;
  employeeStatus: string;
};

type PackageRow = Person & {
  currentTotalAed: string | null;
  currentEffectiveDate: string | null;
  upcomingTotalAed: string | null;
  upcomingEffectiveDate: string | null;
  versionCount: number;
};
type DocumentRow = Person & {
  currentCount: number;
  missingRequired: number;
  expiredCount: number;
  nextExpiryDate: string | null;
};
type VisaRow = Person & {
  visaStatus: VisaStatus | null;
  visaType: string | null;
  expiryDate: string | null;
  expired: boolean;
  workPermitExpiryDate: string | null;
  recordCount: number;
};
type IssuanceRow = HrDocumentItem & Person;
type Overview<Row> = { items: Row[] };

const HR_DOCUMENT_STATUSES: HrDocumentStatus[] = [
  "Prepared",
  "Pending Approval",
  "Issued",
  "Voided",
  "Cancelled",
];
const VISA_STATUSES: VisaStatus[] = [
  "Draft",
  "In Progress",
  "Active",
  "Renewal In Progress",
  "Cancellation In Progress",
  "Cancelled",
];

function personLabel(row: Person) {
  return employeeName(row);
}

function personSearch(row: Person) {
  return [
    employeeCode(row),
    employeeName(row, ""),
    row.designation,
    row.branchName,
    row.departmentName,
  ];
}

function personColumns<Row extends Person>(): HrListColumn<Row>[] {
  return [
    {
      key: "employeeCode",
      label: "Employee code",
      width: 130,
      sortable: true,
      render: (row) => <HrText value={employeeCode(row)} />,
    },
    {
      key: "fullName",
      label: "Name",
      width: 200,
      sortable: true,
      render: (row) => <HrText value={employeeName(row)} />,
    },
    {
      key: "designation",
      label: "Designation",
      width: 150,
      sortable: true,
      render: (row) => <HrText value={row.designation} />,
    },
    {
      key: "branchName",
      label: "Branch",
      width: 130,
      sortable: true,
      render: (row) => <HrText value={row.branchName} />,
    },
    {
      key: "employeeStatus",
      label: "Status",
      width: 120,
      sortable: true,
      render: (row) => (
        <StatusBadge tone={employeeStatusTone(row.employeeStatus)}>
          {row.employeeStatus}
        </StatusBadge>
      ),
    },
  ];
}

function personFilters<Row extends Person>(rows: Row[]): HrListFilter<Row>[] {
  const branches = [
    ...new Set(rows.map((row) => row.branchName).filter(Boolean)),
  ].sort() as string[];
  return [
    {
      id: "branch",
      label: "Branch",
      placeholder: "All Branches",
      options: branches,
      matches: (row, value) => row.branchName === value,
    },
    {
      id: "employeeStatus",
      label: "Employee status",
      placeholder: "All statuses",
      options: EMPLOYEE_STATUSES,
      matches: (row, value) => row.employeeStatus === value,
    },
  ];
}

function Count({ value }: { value: number }) {
  return <span>{value.toLocaleString("en-US")}</span>;
}

const NAME_SORT = { key: "fullName", direction: "asc" } as const;

export function HrPackagesPage({ open }: { open: OpenEmployee }) {
  const resource = useResource<Overview<PackageRow>>("/hr/packages");
  const rows = useMemo(() => resource.data?.items ?? [], [resource.data]);
  const filters = useMemo<HrListFilter<PackageRow>[]>(
    () => [
      ...personFilters(rows),
      {
        id: "package",
        label: "Package",
        placeholder: "All packages",
        options: ["Current package", "No current package", "Upcoming change"],
        matches: (row, value) =>
          value === "Current package"
            ? row.currentTotalAed !== null
            : value === "No current package"
              ? row.currentTotalAed === null
              : row.upcomingEffectiveDate !== null,
      },
    ],
    [rows],
  );
  return (
    <HrListPage
      tableId="hr-packages"
      title="Packages"
      subtitle="Monthly salary packages of authorized employees"
      searchPlaceholder="Search by code, name, designation or Branch"
      rows={rows}
      resource={resource}
      hasData={Boolean(resource.data)}
      columns={[
        ...personColumns<PackageRow>(),
        {
          key: "currentTotalAed",
          label: "Current package",
          width: 150,
          sortable: true,
          kind: "money",
          render: (row) => (
            <MonetaryAmount compact={false} value={row.currentTotalAed} />
          ),
        },
        {
          key: "currentEffectiveDate",
          label: "Effective from",
          width: 120,
          sortable: true,
          kind: "date",
          render: (row) => <CompactDate value={row.currentEffectiveDate} />,
        },
        {
          key: "upcomingEffectiveDate",
          label: "Next change",
          width: 120,
          sortable: true,
          kind: "date",
          render: (row) => <CompactDate value={row.upcomingEffectiveDate} />,
        },
        {
          key: "versionCount",
          label: "Versions",
          width: 100,
          sortable: true,
          kind: "number",
          render: (row) => <Count value={row.versionCount} />,
        },
      ]}
      filters={filters}
      searchText={personSearch}
      rowKey={(row) => row.employeeId}
      rowLabel={personLabel}
      onOpen={(row) => open(row.employeeId, "packages")}
      emptyTitle="No employees"
      emptyDescription="There are no employee records in this authorized view."
      initialSort={NAME_SORT}
    />
  );
}

export function HrDocumentsPage({ open }: { open: OpenEmployee }) {
  const resource = useResource<Overview<DocumentRow>>("/hr/documents");
  const rows = useMemo(() => resource.data?.items ?? [], [resource.data]);
  const filters = useMemo<HrListFilter<DocumentRow>[]>(
    () => [
      ...personFilters(rows),
      {
        id: "documents",
        label: "Documents",
        placeholder: "All employees",
        options: ["Missing required", "Expired", "Complete"],
        matches: (row, value) =>
          value === "Missing required"
            ? row.missingRequired > 0
            : value === "Expired"
              ? row.expiredCount > 0
              : row.missingRequired === 0,
      },
    ],
    [rows],
  );
  return (
    <HrListPage
      tableId="hr-documents"
      title="Documents"
      subtitle="Employee document checklists and expiries"
      searchPlaceholder="Search by code, name, designation or Branch"
      rows={rows}
      resource={resource}
      hasData={Boolean(resource.data)}
      columns={[
        ...personColumns<DocumentRow>(),
        {
          key: "missingRequired",
          label: "Missing required",
          width: 140,
          sortable: true,
          kind: "number",
          render: (row) => <Count value={row.missingRequired} />,
        },
        {
          key: "currentCount",
          label: "Current documents",
          width: 150,
          sortable: true,
          kind: "number",
          render: (row) => <Count value={row.currentCount} />,
        },
        {
          key: "expiredCount",
          label: "Expired",
          width: 100,
          sortable: true,
          kind: "number",
          render: (row) => <Count value={row.expiredCount} />,
        },
        {
          key: "nextExpiryDate",
          label: "Next expiry",
          width: 120,
          sortable: true,
          kind: "date",
          render: (row) => <CompactDate value={row.nextExpiryDate} />,
        },
      ]}
      filters={filters}
      searchText={personSearch}
      rowKey={(row) => row.employeeId}
      rowLabel={personLabel}
      onOpen={(row) => open(row.employeeId, "documents")}
      emptyTitle="No employees"
      emptyDescription="There are no employee records in this authorized view."
      initialSort={NAME_SORT}
    />
  );
}

export function HrVisaPage({ open }: { open: OpenEmployee }) {
  const resource = useResource<Overview<VisaRow>>("/hr/visa-records");
  const rows = useMemo(() => resource.data?.items ?? [], [resource.data]);
  const filters = useMemo<HrListFilter<VisaRow>[]>(
    () => [
      ...personFilters(rows),
      {
        id: "visaStatus",
        label: "Visa status",
        placeholder: "All visa statuses",
        options: [...VISA_STATUSES, "No visa record", "Expired"],
        matches: (row, value) =>
          value === "No visa record"
            ? row.visaStatus === null
            : value === "Expired"
              ? row.expired
              : row.visaStatus === value,
      },
    ],
    [rows],
  );
  return (
    <HrListPage
      tableId="hr-visa"
      title="Visa / PRO"
      subtitle="Current visa and work permit records of authorized employees"
      searchPlaceholder="Search by code, name, designation, Branch or visa type"
      rows={rows}
      resource={resource}
      hasData={Boolean(resource.data)}
      columns={[
        ...personColumns<VisaRow>(),
        {
          key: "visaStatus",
          label: "Visa status",
          width: 170,
          sortable: true,
          render: (row) =>
            row.visaStatus ? (
              <StatusBadge
                tone={row.expired ? "danger" : visaStatusTone(row.visaStatus)}
              >
                {row.expired ? `${row.visaStatus} · Expired` : row.visaStatus}
              </StatusBadge>
            ) : (
              <EmptyValue />
            ),
        },
        {
          key: "visaType",
          label: "Visa type",
          width: 150,
          sortable: true,
          render: (row) => <HrText value={row.visaType} />,
        },
        {
          key: "expiryDate",
          label: "Visa expiry",
          width: 120,
          sortable: true,
          kind: "date",
          render: (row) => <CompactDate value={row.expiryDate} />,
        },
        {
          key: "workPermitExpiryDate",
          label: "Work permit expiry",
          width: 150,
          sortable: true,
          kind: "date",
          render: (row) => <CompactDate value={row.workPermitExpiryDate} />,
        },
      ]}
      filters={filters}
      searchText={(row) => [...personSearch(row), row.visaType]}
      rowKey={(row) => row.employeeId}
      rowLabel={personLabel}
      onOpen={(row) => open(row.employeeId, "visa")}
      emptyTitle="No employees"
      emptyDescription="There are no employee records in this authorized view."
      initialSort={NAME_SORT}
    />
  );
}

function readDirectory(api: ApiClient, path: string, signal: AbortSignal) {
  return choices<EmployeeListRecord>(api, path, signal);
}

function EmployeePickerDialog({
  title,
  description,
  status,
  emptyTitle,
  emptyDescription,
  onClose,
  onSelect,
}: {
  title: string;
  description: string;
  status: "Active" | "Offboarded";
  emptyTitle: string;
  emptyDescription: string;
  onClose: () => void;
  onSelect: (employeeId: string) => void;
}) {
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const directory = useResource<EmployeeListRecord[]>(
    `/employees?status=${status}&sort=fullName&direction=asc`,
    0,
    readDirectory,
    "employee-directory",
  );
  const options = (directory.data ?? []).map((row) => ({
    value: row.id,
    label: employeeName(row),
    description:
      [employeeCode(row), row.designation].filter(Boolean).join(" · ") ||
      undefined,
  }));
  const empty = Boolean(directory.data) && options.length === 0;
  return (
    <Dialog
      open
      title={title}
      size="sm"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          {empty ? null : (
            <Button
              onClick={() => {
                if (!selected) {
                  setError("Select an employee");
                  return;
                }
                onSelect(selected);
              }}
            >
              Continue
            </Button>
          )}
        </>
      }
    >
      {empty ? (
        <EmptyState title={emptyTitle} description={emptyDescription} />
      ) : (
        <>
          <p>{description}</p>
          <FormField
            label="Employee"
            htmlFor="hr-employee-picker"
            required
            error={error || directory.error || undefined}
          >
            <DropdownSelect
              id="hr-employee-picker"
              searchable
              value={selected}
              placeholder="Select an employee"
              loading={directory.loading && !directory.data}
              options={options}
              onChange={(value) => {
                setSelected(Array.isArray(value) ? (value[0] ?? "") : value);
                setError("");
              }}
            />
          </FormField>
        </>
      )}
    </Dialog>
  );
}

function issuanceTitle(row: IssuanceRow) {
  return row.nocPurpose ? `${row.label} (${row.nocPurpose})` : row.label;
}

function HrIssuancesPage({
  category,
  open,
}: {
  category: "letter" | "certificate";
  open: OpenEmployee;
}) {
  const [picking, setPicking] = useState(false);
  const resource = useResource<
    Overview<IssuanceRow> & { canPrepare: boolean; canApprove: boolean }
  >(`/hr/hr-documents?category=${category}`);
  const rows = useMemo(() => resource.data?.items ?? [], [resource.data]);
  const certificates = category === "certificate";
  const filters = useMemo<HrListFilter<IssuanceRow>[]>(
    () => [
      {
        id: "status",
        label: "Status",
        placeholder: "All statuses",
        options: HR_DOCUMENT_STATUSES,
        matches: (row, value) => row.status === value,
      },
      ...(certificates
        ? []
        : [
            {
              id: "documentType",
              label: "Document",
              placeholder: "All letters",
              options: [...new Set(rows.map((row) => row.label))].sort(),
              matches: (row: IssuanceRow, value: string) => row.label === value,
            },
          ]),
      ...personFilters(rows).slice(0, 1),
    ],
    [rows, certificates],
  );
  const pendingApproval = rows.filter(
    (row) =>
      row.requiresApproval &&
      (row.status === "Prepared" || row.status === "Pending Approval"),
  ).length;
  return (
    <>
      <HrListPage
        tableId={certificates ? "hr-certificates" : "hr-letters"}
        title={certificates ? "Certificates" : "Letters"}
        subtitle={
          certificates
            ? "Experience certificates for Offboarded employees"
            : "Salary, employment, NOC and salary transfer letters"
        }
        searchPlaceholder="Search by document, number, employee or code"
        rows={rows}
        resource={resource}
        hasData={Boolean(resource.data)}
        columns={[
          {
            key: "label",
            label: "Document",
            width: 220,
            sortable: true,
            render: (row) => <HrText value={issuanceTitle(row)} />,
          },
          {
            key: "documentNumber",
            label: "Number",
            width: 170,
            sortable: true,
            render: (row) => <HrText value={row.documentNumber} />,
          },
          {
            key: "fullName",
            label: "Employee",
            width: 200,
            sortable: true,
            render: (row) => <HrText value={employeeName(row)} />,
          },
          {
            key: "employeeCode",
            label: "Employee code",
            width: 130,
            sortable: true,
            render: (row) => <HrText value={employeeCode(row)} />,
          },
          {
            key: "status",
            label: "Status",
            width: 150,
            sortable: true,
            render: (row) => (
              <StatusBadge tone={hrDocumentStatusTone(row.status)}>
                {row.status}
              </StatusBadge>
            ),
          },
          {
            key: "preparedAt",
            label: "Prepared",
            width: 150,
            sortable: true,
            kind: "datetime",
            render: (row) => <CompactDateTime value={row.preparedAt} />,
          },
          {
            key: "issuedAt",
            label: "Issued",
            width: 150,
            sortable: true,
            kind: "datetime",
            render: (row) => <CompactDateTime value={row.issuedAt} />,
          },
          {
            key: "preparedByName",
            label: "Prepared by",
            width: 170,
            sortable: true,
            render: (row) => <HrText value={row.preparedByName} />,
          },
        ]}
        filters={filters}
        searchText={(row) => [
          issuanceTitle(row),
          row.documentNumber,
          employeeName(row, ""),
          employeeCode(row),
          row.addressee,
        ]}
        rowKey={(row) => row.id}
        rowLabel={(row) => `${issuanceTitle(row)} for ${employeeName(row)}`}
        onOpen={(row) => open(row.employeeId, "letters")}
        actions={
          resource.data?.canPrepare ? (
            <Button size="compact" onClick={() => setPicking(true)}>
              {certificates ? "Prepare certificate" : "Prepare letter"}
            </Button>
          ) : null
        }
        notices={
          resource.data?.canApprove && pendingApproval ? (
            <InlineNotice tone="warning" title="Awaiting Owner approval">
              {`${pendingApproval.toLocaleString("en-US")} ${
                pendingApproval === 1 ? "document is" : "documents are"
              } awaiting approval. Open a row to review, approve and issue.`}
            </InlineNotice>
          ) : null
        }
        emptyTitle={certificates ? "No certificates" : "No letters"}
        emptyDescription={
          certificates
            ? "No experience certificate has been prepared."
            : "No letter has been prepared."
        }
        initialSort={{ key: "preparedAt", direction: "desc" }}
      />
      {picking ? (
        <EmployeePickerDialog
          title={certificates ? "Prepare certificate" : "Prepare letter"}
          description={
            certificates
              ? "Select the Offboarded employee. Their letters and certificates section opens, where the certificate is prepared."
              : "Select the Active employee. Their letters and certificates section opens, where the letter is prepared."
          }
          status={certificates ? "Offboarded" : "Active"}
          emptyTitle="No eligible employees"
          emptyDescription={
            certificates
              ? "Experience certificates are available only for Offboarded employees. There are none in this authorized view."
              : "Letters are available only for Active employees. There are none in this authorized view."
          }
          onClose={() => setPicking(false)}
          onSelect={(employeeId) => open(employeeId, "letters")}
        />
      ) : null}
    </>
  );
}

export function HrLettersPage({ open }: { open: OpenEmployee }) {
  return <HrIssuancesPage category="letter" open={open} />;
}

export function HrCertificatesPage({ open }: { open: OpenEmployee }) {
  return <HrIssuancesPage category="certificate" open={open} />;
}

type OffboardingRow = Person & {
  dateOfJoining: string | null;
  lastWorkingDate: string | null;
};

const OFFBOARDING_STAGES = [
  "Not offboarded",
  "Offboarded",
  "Last working date missing",
];

export function HrOffboardingPage({ open }: { open: OpenEmployee }) {
  const { session } = useSession();
  const [refresh, setRefresh] = useState(0);
  const [notice, setNotice] = useState("");
  const [command, setCommand] = useState<{
    kind: EmployeeCommandKind;
    id: string;
  } | null>(null);
  const directory = useResource<EmployeeListRecord[]>(
    "/employees?sort=fullName&direction=asc",
    refresh,
    readDirectory,
    "employee-directory",
  );
  const detail = useResource<EmployeeDetailRecord>(
    command ? `/employees/${encodeURIComponent(command.id)}` : null,
  );
  const rows = useMemo<OffboardingRow[]>(
    () =>
      (directory.data ?? []).map((row) => ({
        employeeId: row.id,
        fullName: row.fullName,
        employeeCode: employeeCode(row) || null,
        designation: row.designation,
        branchName: row.branchName,
        departmentName: row.departmentName,
        employeeStatus: row.status,
        dateOfJoining: row.dateOfJoining,
        lastWorkingDate: row.lastWorkingDate ?? null,
      })),
    [directory.data],
  );
  const filters = useMemo<HrListFilter<OffboardingRow>[]>(
    () => [
      {
        id: "stage",
        label: "Offboarding",
        placeholder: "All employees",
        options: OFFBOARDING_STAGES,
        matches: (row, value) =>
          value === "Not offboarded"
            ? row.employeeStatus !== "Offboarded"
            : value === "Offboarded"
              ? row.employeeStatus === "Offboarded"
              : row.employeeStatus === "Offboarded" && !row.lastWorkingDate,
      },
      ...personFilters(rows),
    ],
    [rows],
  );
  if (!session) return null;
  const actionsFor = (row: OffboardingRow): MenuItem[] => {
    const items: MenuItem[] = [];
    if (row.employeeStatus !== "Offboarded" && row.designation !== "Owner")
      items.push({
        id: "offboard",
        label: "Offboard employee",
        danger: true,
        onSelect: () => setCommand({ kind: "offboard", id: row.employeeId }),
      });
    if (
      canRecordLastWorkingDate(session.designation, {
        status: row.employeeStatus,
        lastWorkingDate: row.lastWorkingDate,
      })
    )
      items.push({
        id: "lastWorkingDate",
        label: "Record last working date",
        onSelect: () =>
          setCommand({ kind: "lastWorkingDate", id: row.employeeId }),
      });
    return items;
  };
  const activeRow = command
    ? rows.find((row) => row.employeeId === command.id)
    : undefined;
  const activeDetail =
    command && detail.data?.id === command.id ? detail.data : undefined;
  return (
    <>
      <HrListPage
        tableId="hr-offboarding"
        title="Offboarding"
        subtitle="Offboard employees and review last working dates"
        searchPlaceholder="Search by code, name, designation or Branch"
        rows={rows}
        resource={directory}
        hasData={Boolean(directory.data)}
        columns={[
          ...personColumns<OffboardingRow>(),
          {
            key: "departmentName",
            label: "Department",
            width: 150,
            sortable: true,
            render: (row) => <HrText value={row.departmentName} />,
          },
          {
            key: "dateOfJoining",
            label: "Join date",
            width: 110,
            sortable: true,
            kind: "date",
            render: (row) => <CompactDate value={row.dateOfJoining} />,
          },
          {
            key: "lastWorkingDate",
            label: "Last working date",
            width: 150,
            sortable: true,
            kind: "date",
            render: (row) =>
              row.employeeStatus !== "Offboarded" ? (
                <EmptyValue />
              ) : row.lastWorkingDate ? (
                <CompactDate value={row.lastWorkingDate} />
              ) : (
                <StatusBadge tone="warning">Not recorded</StatusBadge>
              ),
          },
        ]}
        filters={filters}
        searchText={personSearch}
        rowKey={(row) => row.employeeId}
        rowLabel={personLabel}
        onOpen={(row) => open(row.employeeId)}
        rowActions={actionsFor}
        notices={
          <>
            {notice ? (
              <InlineNotice tone="success" title="Saved">
                {notice}
              </InlineNotice>
            ) : null}
            {command && detail.error ? (
              <InlineNotice tone="error" title="Employee unavailable">
                The Employee record could not be loaded for this action.
              </InlineNotice>
            ) : null}
          </>
        }
        emptyTitle="No employees"
        emptyDescription="There are no employee records in this authorized view."
        initialSort={NAME_SORT}
      />
      {command && activeDetail ? (
        <EmployeeCommandDialog
          kind={command.kind}
          employee={activeDetail}
          branch={activeRow?.branchName ?? ""}
          department={activeRow?.departmentName ?? ""}
          onClose={() => setCommand(null)}
          onSaved={(message) => {
            setCommand(null);
            setNotice(message);
            setRefresh((value) => value + 1);
          }}
        />
      ) : null}
    </>
  );
}
