import { useState } from "react";
import {
  Button,
  CompactDate,
  CompactDateTime,
  DataTable,
  EmptyValue,
  ErrorState,
  InfoField,
  InfoGrid,
  InlineNotice,
  LoadingState,
  MonetaryAmount,
  SectionCard,
  StatusBadge,
  TruncatedText,
  type DataTableColumn,
  type StatusTone,
} from "../../../../design-system";
import type { Command } from "../../../../app/api/commands";
import { useResource } from "../../../../app/api/useResource";
import { CommandFormDialog } from "../../../../app/commands/CommandFormDialog";
import type { PackageList, PackageVersion } from "./hrRecords";
import styles from "./hrRecords.module.css";

type Row = PackageVersion & { state: "Current" | "Upcoming" | "Historical" };

const STATE_TONE: Record<Row["state"], StatusTone> = {
  Current: "success",
  Upcoming: "info",
  Historical: "neutral",
};

function packageCommand(employeeId: string): Command {
  return {
    title: "Add package version",
    path: `/employees/${employeeId}/packages`,
    idempotent: true,
    submitLabel: "Add version",
    fields: [
      {
        key: "effectiveDate",
        label: "Effective date (Dubai)",
        type: "date",
        required: true,
      },
      {
        key: "basicSalaryAed",
        label: "Basic salary (AED)",
        type: "decimal",
        required: true,
      },
      {
        key: "housingAllowanceAed",
        label: "Housing allowance (AED)",
        type: "decimal",
      },
      {
        key: "transportAllowanceAed",
        label: "Transport allowance (AED)",
        type: "decimal",
      },
      { key: "otherAllowanceLabel", label: "Other allowance label", max: 80 },
      {
        key: "otherAllowanceAed",
        label: "Other allowance (AED)",
        type: "decimal",
      },
      {
        key: "changeReason",
        label: "Change reason",
        type: "textarea",
        required: true,
        max: 500,
      },
    ],
  };
}

function Amount({ value }: { value: string | null }) {
  return value == null ? (
    <EmptyValue />
  ) : (
    <MonetaryAmount compact={false} value={value} />
  );
}

export function EmployeePackageSection({
  employeeId,
  employeeStatus,
  onChanged,
}: {
  employeeId: string;
  employeeStatus: string;
  onChanged?: () => void;
}) {
  const [refresh, setRefresh] = useState(0);
  const [adding, setAdding] = useState(false);
  const [notice, setNotice] = useState("");
  const resource = useResource<PackageList>(
    `/employees/${employeeId}/packages`,
    refresh,
  );
  const data = resource.data;
  const canAdd = Boolean(data?.canManage) && employeeStatus !== "Offboarded";

  const rows: Row[] = data
    ? [
        ...[...data.upcoming].reverse().map((row) => ({
          ...row,
          state: "Upcoming" as const,
        })),
        ...(data.current
          ? [{ ...data.current, state: "Current" as const }]
          : []),
        ...data.history.map((row) => ({
          ...row,
          state: "Historical" as const,
        })),
      ]
    : [];

  const columns: DataTableColumn<Row>[] = [
    {
      key: "effectiveDate",
      header: "Effective date",
      kind: "date",
      width: "120px",
      render: (row) => <CompactDate value={row.effectiveDate} />,
    },
    {
      key: "state",
      header: "Status",
      width: "112px",
      render: (row) => (
        <StatusBadge tone={STATE_TONE[row.state]}>{row.state}</StatusBadge>
      ),
    },
    {
      key: "basic",
      header: "Basic",
      kind: "money",
      width: "128px",
      render: (row) => <Amount value={row.basicSalaryAed} />,
    },
    {
      key: "housing",
      header: "Housing",
      kind: "money",
      width: "128px",
      render: (row) => <Amount value={row.housingAllowanceAed} />,
    },
    {
      key: "transport",
      header: "Transport",
      kind: "money",
      width: "128px",
      render: (row) => <Amount value={row.transportAllowanceAed} />,
    },
    {
      key: "other",
      header: "Other allowance",
      kind: "mixed",
      width: "180px",
      render: (row) =>
        row.otherAllowanceLabel ? (
          <span className={styles.inline}>
            <TruncatedText value={row.otherAllowanceLabel} />
            <MonetaryAmount
              compact={false}
              align="start"
              value={row.otherAllowanceAed}
            />
          </span>
        ) : (
          <EmptyValue />
        ),
    },
    {
      key: "total",
      header: "Total monthly",
      kind: "money",
      width: "136px",
      render: (row) => <Amount value={row.totalMonthlyAed} />,
    },
    {
      key: "reason",
      header: "Change reason",
      width: "220px",
      render: (row) => <TruncatedText value={row.changeReason} />,
    },
    {
      key: "recordedBy",
      header: "Recorded by",
      width: "160px",
      render: (row) => (
        <TruncatedText value={row.createdByName || "Team member"} />
      ),
    },
    {
      key: "recordedAt",
      header: "Recorded at",
      kind: "datetime",
      width: "150px",
      render: (row) => <CompactDateTime value={row.createdAt} />,
    },
  ];

  const current = data?.current;
  return (
    <SectionCard
      compact
      title="Package"
      description="Effective-dated salary package. Versions are append-only and dated in Dubai time."
      actions={
        canAdd ? (
          <Button
            size="compact"
            variant="secondary"
            onClick={() => {
              setNotice("");
              setAdding(true);
            }}
          >
            Add version
          </Button>
        ) : undefined
      }
    >
      {notice ? (
        <InlineNotice tone="success" title="Saved">
          {notice}
        </InlineNotice>
      ) : null}
      {resource.loading && !data ? (
        <LoadingState title="Loading package" />
      ) : resource.error && !data ? (
        <ErrorState description={resource.error} retry={resource.reload} />
      ) : !rows.length ? (
        <p className={styles.empty}>
          No salary package has been recorded for this employee.
        </p>
      ) : (
        <>
          {current ? (
            <InfoGrid>
              <InfoField
                label="Current total monthly"
                value={<Amount value={current.totalMonthlyAed} />}
              />
              <InfoField
                label="Basic salary"
                value={<Amount value={current.basicSalaryAed} />}
              />
              <InfoField
                label="Effective from"
                value={<CompactDate value={current.effectiveDate} />}
              />
              <InfoField
                label="Recorded"
                value={<CompactDateTime value={current.createdAt} />}
              />
            </InfoGrid>
          ) : (
            <InlineNotice tone="info" title="No current package">
              Only upcoming versions are recorded. The earliest one applies from
              its effective date.
            </InlineNotice>
          )}
          <DataTable
            ariaLabel="Package versions"
            density="compact"
            stackOnNarrow
            columns={columns}
            rows={rows}
            rowKey={(row) => row.id}
          />
        </>
      )}
      {adding ? (
        <CommandFormDialog
          command={packageCommand(employeeId)}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            setNotice("Package version added.");
            setRefresh((value) => value + 1);
            onChanged?.();
          }}
        />
      ) : null}
    </SectionCard>
  );
}
