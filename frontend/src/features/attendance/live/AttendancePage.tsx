import { useState } from "react";
import {
  AttendanceCalendar,
  AttendanceDayDetail,
  AttendanceSummary,
  Avatar,
  CompactDateTime,
  DropdownSelect,
  EmptyState,
  ErrorState,
  ExportButton,
  FilterToolbar,
  FilterToolbarItem,
  FullValueTooltip,
  InlineNotice,
  LoadingState,
  MonthPicker,
  OfflineState,
  PageContainer,
  PageHeader,
  PermissionDeniedState,
  SectionCard,
  WorkingHoursProgress,
  dubaiTodayDateOnly,
  formatMonthYear,
  weekdayJs,
  parseDateOnly,
  type DateOnly,
} from "../../../design-system";
import { download } from "../../../app/api/download";
import type { NamedRecord } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import { employeeAvatarSrc } from "../../employees/live/employeePresentation";
import {
  clockTime,
  currentMonth,
  employeeCodeLabel,
  employeeLabel,
  formatDuration,
  formatDurationFull,
  monthEnd,
  monthStart,
  toDayRecord,
  type AttendanceEmployee,
  type AttendancePage as AttendancePageData,
  type AttendanceRecord,
} from "./attendancePresentation";
import { AttendanceImports } from "./AttendanceImports";
import styles from "./AttendancePage.module.css";

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

function Duration({ minutes }: { minutes: number | null | undefined }) {
  const short = formatDuration(minutes);
  if (!short) return <span>—</span>;
  const full = formatDurationFull(minutes);
  return (
    <FullValueTooltip content={full}>
      <span className="ds-numeric" aria-label={full}>
        {short}
      </span>
    </FullValueTooltip>
  );
}

function isSunday(date: DateOnly) {
  const parts = parseDateOnly(date);
  return parts ? weekdayJs(parts.year, parts.month, parts.day) === 0 : false;
}

export function AttendancePage({
  id,
  select,
}: {
  id?: string;
  select: (id?: string) => void;
}) {
  const { session, api } = useSession();
  const branchLocked = session?.designation === "Admin Staff";
  const [exporting, setExporting] = useState(false);
  const [exportFailed, setExportFailed] = useState(false);
  const [branchId, setBranchId] = useState(
    branchLocked ? (session?.branchId ?? "") : "",
  );
  const [employeeId, setEmployeeId] = useState("");
  const [month, setMonth] = useState<DateOnly>(currentMonth());
  const [selected, setSelected] = useState<DateOnly>(dubaiTodayDateOnly());
  const [appliedRecordId, setAppliedRecordId] = useState<string | undefined>();
  const [refresh, setRefresh] = useState(0);

  const linked = useResource<AttendanceRecord>(
    id ? `/attendance/${encodeURIComponent(id)}` : null,
  );
  if (id && linked.data?.id === id && appliedRecordId !== id) {
    setAppliedRecordId(id);
    if (!branchLocked) setBranchId(linked.data.branchId);
    setEmployeeId(linked.data.employeeId);
    setMonth(monthStart(linked.data.attendanceDate));
    setSelected(linked.data.attendanceDate);
  }

  const branches = useResource<NamedRecord[]>("/branches");
  const employees = useResource<{ items: AttendanceEmployee[] }>(
    `/attendance/employees${branchId ? `?branchId=${encodeURIComponent(branchId)}` : ""}`,
    refresh,
  );
  const choices = employees.data?.items ?? [];
  const employee = choices.find((item) => item.id === employeeId);
  const activeEmployeeId = employee ? employee.id : "";

  const query = new URLSearchParams({
    dateFrom: monthStart(month),
    dateTo: monthEnd(month),
    sort: "attendanceDate",
    direction: "asc",
    pageSize: activeEmployeeId ? "100" : "1",
  });
  if (branchId) query.set("branchId", branchId);
  if (activeEmployeeId) query.set("employeeId", activeEmployeeId);
  const records = useResource<AttendancePageData>(
    `/attendance?${query}`,
    refresh,
  );
  const exportQuery = new URLSearchParams(query);
  exportQuery.delete("pageSize");
  const data = records.data;
  const monthRecords =
    activeEmployeeId && data
      ? data.items.filter(
          (item) =>
            item.employeeId === activeEmployeeId &&
            item.attendanceDate.startsWith(month.slice(0, 7)),
        )
      : [];
  const dayRecords = monthRecords.map(toDayRecord);
  const selectedRecord = monthRecords.find(
    (item) => item.attendanceDate === selected,
  );

  if (!session) return null;

  const branchOptions = (branches.data ?? [])
    .filter((branch) => !branchLocked || branch.id === session.branchId)
    .map((branch) => ({ value: branch.id, label: branch.name }));
  const employeeOptions = choices.map((item) => {
    const name = employeeLabel(item);
    const code = employeeCodeLabel(item);
    return {
      value: item.id,
      label: name,
      description: [code, item.designation].filter(Boolean).join(" · "),
      keywords: [name, code, item.designation ?? ""],
      leading: <Avatar name={name} src={employeeAvatarSrc(item)} size="sm" />,
    };
  });
  const canExport =
    session.designation === "Owner" ||
    session.designation === "Managing Director";
  const exportMonth = async () => {
    setExporting(true);
    setExportFailed(false);
    try {
      await download(api, "/table-exports/csv", {
        method: "POST",
        body: JSON.stringify({
          sourcePath: `/attendance?${exportQuery}`,
          mode: "all",
        }),
      });
    } catch {
      setExportFailed(true);
    } finally {
      setExporting(false);
    }
  };
  const pickDay = (date: DateOnly) => {
    setSelected(date);
    if (id) select();
  };
  const changeMonth = (next: DateOnly) => {
    setMonth(monthStart(next));
    if (id) select();
  };
  const periodLabel = formatMonthYear(month);
  const sundayOff = !selectedRecord && isSunday(selected);
  const future = selected > dubaiTodayDateOnly();
  const percent =
    selectedRecord?.workedMinutes != null && selectedRecord.requiredMinutes
      ? Math.max(
          0,
          Math.min(
            100,
            (selectedRecord.workedMinutes / selectedRecord.requiredMinutes) * 100,
          ),
        )
      : null;

  return (
    <PageContainer>
      <div className={styles.page}>
        <PageHeader
          title="Attendance"
          subtitle="Daily attendance by Branch and employee"
        />

        <FilterToolbar label="Attendance scope" className={styles.scope}>
          <FilterToolbarItem label="Branch" htmlFor="attendance-branch">
            <DropdownSelect
              id="attendance-branch"
              compact
              clearable={!branchLocked}
              disabled={branchLocked}
              placeholder="All Branches"
              value={branchId}
              options={branchOptions}
              loading={branches.loading && !branches.data}
              onChange={(value) => {
                setBranchId(Array.isArray(value) ? (value[0] ?? "") : value);
                if (id) select();
              }}
            />
          </FilterToolbarItem>
          <FilterToolbarItem
            label="Employee"
            htmlFor="attendance-employee"
            className={styles.employeeControl}
          >
            <DropdownSelect
              id="attendance-employee"
              compact
              searchable
              clearable
              placeholder="Select employee"
              emptyLabel="No employees with attendance in this scope"
              value={activeEmployeeId}
              options={employeeOptions}
              loading={employees.loading && !employees.data}
              onChange={(value) => {
                setEmployeeId(Array.isArray(value) ? (value[0] ?? "") : value);
                if (id) select();
              }}
            />
          </FilterToolbarItem>
          <FilterToolbarItem
            label="Month"
            htmlFor="attendance-month"
            className={styles.monthControl}
          >
            <MonthPicker
              id="attendance-month"
              compact
              label="Month"
              value={month.slice(0, 7)}
              onChange={(value) => changeMonth(`${value}-01`)}
            />
          </FilterToolbarItem>
          {canExport ? (
            <FilterToolbarItem
              labeled={false}
              className="ds-filter-toolbar__item--page-actions"
            >
              <div className="ds-filter-toolbar__actions">
                <ExportButton
                  size="compact"
                  label="Export month"
                  loading={exporting}
                  disabled={!data?.total || exporting}
                  onClick={() => void exportMonth()}
                />
              </div>
            </FilterToolbarItem>
          ) : null}
        </FilterToolbar>

        {exportFailed ? (
          <InlineNotice tone="error" title="Export failed">
            The attendance CSV could not be exported. Try again.
          </InlineNotice>
        ) : null}

        {linked.denied && id ? (
          <InlineNotice tone="warning" title="Record unavailable">
            The linked attendance record is not available in your authorized
            Branch.
          </InlineNotice>
        ) : null}

        {records.denied ? (
          <PermissionDeniedState description="Attendance for this Branch is outside your authorized scope." />
        ) : records.error && !data ? (
          isOffline(records.error) ? (
            <OfflineState />
          ) : (
            <ErrorState
              description="Attendance could not be loaded for this period."
              retry={records.reload}
            />
          )
        ) : !data ? (
          <LoadingState title="Loading attendance" />
        ) : (
          <section
            className={styles.summary}
            aria-label={`Attendance summary for ${periodLabel}`}
            aria-busy={records.updating}
          >
            <AttendanceSummary
              present={data.presentCount}
              late={data.lateCount}
              absent={data.absentCount}
              metrics={[
                ...(data.sundayOffCount != null
                  ? [
                      {
                        id: "sunday-off",
                        label: "Sunday Off",
                        value: data.sundayOffCount,
                      },
                    ]
                  : []),
                {
                  id: "recorded",
                  label: "Recorded days",
                  value: data.total,
                },
                {
                  id: "worked",
                  label: "Total worked",
                  value: <Duration minutes={data.workedMinutes} />,
                },
                {
                  id: "average",
                  label: "Average worked",
                  value: <Duration minutes={data.averageWorkedMinutes} />,
                  meta: "Per present day",
                },
              ]}
            />
          </section>
        )}

        <div className={styles.workspace}>
          <div className={styles.calendar}>
            {activeEmployeeId ? (
              <AttendanceCalendar
                month={month}
                onMonthChange={changeMonth}
                records={dayRecords}
                selected={selected}
                onSelect={pickDay}
                weekStartsOn={1}
                offWeekdays={[0]}
              />
            ) : (
              <SectionCard compact title={periodLabel}>
                <EmptyState
                  title="Select an employee"
                  description="Choose an employee to review the monthly calendar and daily check-in and check-out."
                />
              </SectionCard>
            )}
          </div>
          {activeEmployeeId ? (
            <div className={styles.detail}>
              <AttendanceDayDetail
                date={selected}
                record={
                  selectedRecord
                    ? toDayRecord(selectedRecord)
                    : sundayOff
                      ? { date: selected, status: "off" }
                      : future
                        ? { date: selected, status: "future" }
                        : { date: selected }
                }
                shift={
                  selectedRecord?.officeStartTime ? (
                    <>
                      Office hours {clockTime(selectedRecord.officeStartTime)}–
                      {clockTime(selectedRecord.officeEndTime)}
                      {selectedRecord.requiredMinutes ? (
                        <>
                          {" · Required "}
                          <Duration minutes={selectedRecord.requiredMinutes} />
                        </>
                      ) : null}
                    </>
                  ) : undefined
                }
                progress={
                  selectedRecord && percent != null ? (
                    <WorkingHoursProgress
                      workedLabel={formatDuration(selectedRecord.workedMinutes)}
                      requiredLabel={formatDuration(
                        selectedRecord.requiredMinutes,
                      )}
                      percent={percent}
                      state={
                        selectedRecord.isLate
                          ? "late"
                          : percent >= 100
                            ? "complete"
                            : "short"
                      }
                    />
                  ) : undefined
                }
                source={
                  selectedRecord?.importedAt ? (
                    <>
                      Imported from CSV ·{" "}
                      <CompactDateTime value={selectedRecord.importedAt} />
                    </>
                  ) : selectedRecord ? (
                    "Recorded attendance"
                  ) : undefined
                }
                notes={
                  selectedRecord
                    ? undefined
                    : sundayOff
                      ? "Sunday is the weekly non-working day."
                      : future
                        ? "This day has not happened yet."
                        : "No attendance record for this day."
                }
              />
            </div>
          ) : null}
        </div>

        <AttendanceImports
          branchId={branchId}
          branchLocked={branchLocked}
          branches={branches.data}
          onApplied={() => setRefresh((value) => value + 1)}
        />
      </div>
    </PageContainer>
  );
}
