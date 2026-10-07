import { useState } from "react";
import {
  Button,
  CompactDate,
  CompactDateTime,
  DataTable,
  EmptyState,
  ErrorState,
  SectionCard,
  formatDateOnly,
  type AppliedFilter,
} from "../../../design-system";
import type { Command } from "../../../app/api/commands";
import { effectiveField } from "../../../app/api/commands";
import { useResource } from "../../../app/api/useResource";
import { CommandFormDialog } from "../../../app/commands/CommandFormDialog";
import { useSession } from "../../../app/session/useSession";
import {
  filterQuery,
  useServerTable,
} from "../../../shared/table/serverTable";
import { SelectFilter } from "../../finance/live/financeCells";
import { personText, useEmployeeLabels } from "../../finance/live/financeLabels";
import { Text } from "./settingsCells";
import { useNamedRecords } from "./useNamedRecords";
import { canManageSettings } from "./settingsRegistry";
import { SettingsTable } from "./SettingsTable";
import { HolidayEntryDialog } from "./HolidayEntryDialog";
import styles from "./SettingsPage.module.css";

type OfficeTimingRecord = {
  id: string;
  branchId: string;
  effectiveDate: string;
  startTime: string;
  endTime: string;
  createdByEmployeeId: string | null;
};

type HolidayRecord = {
  id: string;
  holidayDate: string;
  applicableYear: number;
  name: string;
  sourceReference: string;
};

type HolidayYearRecord = {
  applicableYear: number;
  sourceReference: string;
  certifiedAt: string;
};

const time = (value: string) => value.slice(0, 5);

export function OfficeTimingSettings() {
  const { session } = useSession();
  const manage = canManageSettings(session, "office_timing.write");
  const [refresh, setRefresh] = useState(0);
  const [branchId, setBranchId] = useState("");
  const table = useServerTable<OfficeTimingRecord>(
    "settings-office-timings",
    "/office-timings",
    filterQuery({ branchId }),
    refresh,
  );
  const branches = useNamedRecords("/branches", refresh);
  const people = useEmployeeLabels(table.rows.map((row) => row.createdByEmployeeId));
  const name = (row: OfficeTimingRecord) =>
    `${branches.label(row.branchId)} · effective ${formatDateOnly(row.effectiveDate)}`;
  const applied: AppliedFilter[] = branchId
    ? [
        {
          id: "branch",
          label: "Branch",
          field: "Branch",
          value: branches.label(branchId, "Selected branch"),
          onRemove: () => setBranchId(""),
        },
      ]
    : [];
  const hours = (row: OfficeTimingRecord) => `${time(row.startTime)}–${time(row.endTime)}`;
  return (
    <SettingsTable
      table={table}
      tableId="settings-office-timings"
      ariaLabel="Office timings"
      kind="Office timing"
      loadingTitle="Loading office timings"
      emptyTitle="No office timings"
      emptyDescription="Office timings set the working hours used by attendance from their effective date."
      filters={
        <SelectFilter
          id="settings-office-timing-branch"
          label="Branch"
          placeholder="All branches"
          value={branchId}
          options={branches.options()}
          loading={branches.loading}
          onChange={setBranchId}
        />
      }
      applied={applied}
      onClearFilters={() => setBranchId("")}
      columns={[
        {
          key: "branchId",
          label: "Branch",
          width: 160,
          render: (row) => <Text value={branches.label(row.branchId)} />,
        },
        {
          key: "effectiveDate",
          label: "Effective",
          width: 120,
          kind: "date",
          render: (row) => <CompactDate value={row.effectiveDate} />,
        },
        { key: "startTime", label: "Start time", width: 110, render: (row) => <Text value={time(row.startTime)} /> },
        { key: "endTime", label: "End time", width: 110, render: (row) => <Text value={time(row.endTime)} /> },
        {
          key: "createdByEmployeeId",
          label: "Created by",
          width: 200,
          render: (row) => (
            <Text
              value={
                row.createdByEmployeeId
                  ? personText(people(row.createdByEmployeeId))
                  : "System"
              }
            />
          ),
        },
      ]}
      rowLabel={name}
      title={(row) => branches.label(row.branchId)}
      facts={(row) => [
        { label: "Branch", value: <Text value={branches.label(row.branchId)} /> },
        { label: "Effective", value: <CompactDate value={row.effectiveDate} /> },
        { label: "Working hours", value: <Text value={hours(row)} /> },
        {
          label: "Created by",
          value: (
            <Text
              value={
                row.createdByEmployeeId
                  ? personText(people(row.createdByEmployeeId))
                  : "System"
              }
            />
          ),
        },
      ]}
      create={
        manage
          ? {
              label: "Add Office Timing",
              success: "Office timing added.",
              command: {
                title: "Add Office Timing",
                path: "/office-timings",
                fields: [
                  {
                    key: "branchId",
                    label: "Branch",
                    required: true,
                    source: {
                      path: "/branches",
                      label: "name",
                      where: { active: "true" },
                      allowed: { operating_city: ["Dubai", "Abu Dhabi"] },
                    },
                  },
                  effectiveField,
                  { key: "startTime", label: "Start time", type: "time", required: true },
                  { key: "endTime", label: "End time", type: "time", required: true },
                ],
              },
            }
          : undefined
      }
      onSaved={() => setRefresh((value) => value + 1)}
    />
  );
}

const editHolidayCommand = (id: string): Command => ({
  title: "Edit Holiday",
  path: `/performance/uae-holidays/${id}`,
  method: "PATCH",
  fields: [
    { key: "holidayDate", label: "Holiday date", type: "date", required: true },
    { key: "name", label: "Holiday name", required: true, max: 200 },
    {
      key: "sourceReference",
      label: "Official source reference",
      required: true,
      max: 1000,
    },
  ],
});

const certifyCommand: Command = {
  title: "Certify Holiday Year",
  path: "/performance/uae-holiday-years/certify",
  fields: [
    { key: "applicableYear", label: "Year", type: "number", required: true },
    { key: "sourceReference", label: "Official source reference", required: true, max: 1000 },
  ],
};

export function HolidaySettings() {
  const { session } = useSession();
  const manage = canManageSettings(session, "target.write");
  const [refresh, setRefresh] = useState(0);
  const [year, setYear] = useState("");
  const [certifying, setCertifying] = useState(false);
  const [entry, setEntry] = useState<"single" | "bulk" | null>(null);
  const [notice, setNotice] = useState("");
  const table = useServerTable<HolidayRecord>(
    "settings-uae-holidays",
    "/performance/uae-holidays",
    filterQuery({ year }),
    refresh,
  );
  const years = useResource<{ items: HolidayYearRecord[] }>(
    "/performance/uae-holiday-years",
    refresh,
  );
  const certified = years.data?.items ?? [];
  const yearOptions = [
    ...new Set([
      ...certified.map((item) => item.applicableYear),
      ...table.rows.map((item) => item.applicableYear),
      new Date().getFullYear(),
    ]),
  ]
    .sort((a, b) => b - a)
    .map((value) => ({ value: String(value), label: String(value) }));
  const applied: AppliedFilter[] = year
    ? [
        {
          id: "year",
          label: "Year",
          field: "Year",
          value: year,
          onRemove: () => setYear(""),
        },
      ]
    : [];
  return (
    <div className={styles.panel}>
      <SettingsTable
        table={table}
        tableId="settings-uae-holidays"
        ariaLabel="UAE holidays"
        kind="UAE holiday"
        loadingTitle="Loading UAE holidays"
        emptyTitle="No UAE holidays"
        emptyDescription="Official UAE holidays are excluded from working days and target proration."
        notice={notice}
        onNotice={setNotice}
        filters={
          <SelectFilter
            id="settings-holiday-year"
            label="Year"
            placeholder="All years"
            value={year}
            options={yearOptions}
            loading={years.loading}
            onChange={setYear}
          />
        }
        applied={applied}
        onClearFilters={() => setYear("")}
        extraActions={
          manage ? (
            <>
              <Button size="compact" onClick={() => setEntry("single")}>
                Add Holiday
              </Button>
              <Button
                size="compact"
                variant="secondary"
                onClick={() => setEntry("bulk")}
              >
                Bulk Add Holidays
              </Button>
              <Button
                size="compact"
                variant="secondary"
                onClick={() => setCertifying(true)}
              >
                Certify Year
              </Button>
            </>
          ) : null
        }
        columns={[
          {
            key: "holidayDate",
            label: "Date",
            width: 120,
            kind: "date",
            render: (row) => <CompactDate value={row.holidayDate} />,
          },
          {
            key: "name",
            label: "Holiday",
            width: 240,
            render: (row) => <Text value={row.name} />,
          },
          {
            key: "sourceReference",
            label: "Official source",
            width: 280,
            render: (row) => <Text value={row.sourceReference} />,
          },
        ]}
        rowLabel={(row) => `${row.name} · ${formatDateOnly(row.holidayDate)}`}
        title={(row) => row.name}
        facts={(row) => [
          { label: "Date", value: <CompactDate value={row.holidayDate} /> },
          { label: "Holiday", value: <Text value={row.name} /> },
          { label: "Year", value: <Text value={String(row.applicableYear)} /> },
          {
            label: "Official source",
            value: <Text value={row.sourceReference} />,
          },
        ]}
        actions={
          manage
            ? (row) => [
                {
                  id: "edit",
                  label: "Edit",
                  success: "Holiday updated.",
                  command: editHolidayCommand(row.id),
                  record: { ...row },
                },
              ]
            : undefined
        }
        onSaved={() => setRefresh((value) => value + 1)}
      />
      <SectionCard title="Certified years" compact>
        {years.error ? (
          <ErrorState title="Certified years unavailable" description={years.error} />
        ) : (
          <DataTable
            ariaLabel="Certified holiday years"
            density="compact"
            loading={years.loading && !years.data}
            rows={certified}
            rowKey={(row) => String(row.applicableYear)}
            empty={
              <EmptyState
                title="No certified years"
                description="Certify a year after all of its official holidays are recorded."
              />
            }
            columns={[
              {
                key: "applicableYear",
                header: "Year",
                width: "100px",
                render: (row) => String(row.applicableYear),
              },
              {
                key: "sourceReference",
                header: "Official source",
                render: (row) => <Text value={row.sourceReference} />,
              },
              {
                key: "certifiedAt",
                header: "Certified",
                kind: "datetime",
                width: "160px",
                render: (row) => <CompactDateTime value={row.certifiedAt} />,
              },
            ]}
          />
        )}
      </SectionCard>
      {entry ? (
        <HolidayEntryDialog
          bulk={entry === "bulk"}
          onClose={() => setEntry(null)}
          onSaved={(count) => {
            setEntry(null);
            setNotice(
              `${count} holiday ${count === 1 ? "date" : "dates"} added.`,
            );
            setRefresh((value) => value + 1);
          }}
        />
      ) : null}
      {certifying ? (
        <CommandFormDialog
          command={certifyCommand}
          onClose={() => setCertifying(false)}
          onSaved={() => {
            setCertifying(false);
            setNotice("Holiday year certified.");
            setRefresh((value) => value + 1);
          }}
        />
      ) : null}
    </div>
  );
}
