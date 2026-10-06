import type { ReactNode } from "react";
import { DsIcon, type DsIconName } from "../icons";
import { cx } from "../lib/cx";
import {
  addDays,
  addMonths,
  compareDateOnly,
  dubaiTodayDateOnly,
  daysInMonth,
  monthLabel,
  parseDateOnly,
  startOfMonth,
  toDateOnly,
  weekdayJs,
  weekdayLabels,
  weekdayOffset,
  type DateOnly,
} from "../lib/dateOnly";
import { CompactDate } from "./CompactDate";
import { Button } from "./Button";
import { CompactNumber } from "./CompactValue";
import { EmptyState } from "./EmptyState";
import { EmptyValue, ProgressBar } from "./Display";
import { ErrorState } from "./ErrorState";
import { IconButton } from "./IconButton";
import { KpiCard } from "./KpiCard";
import { LoadingState } from "./LoadingState";
import { MonthPicker, YearPicker } from "./MonthPicker";
import { StatusBadge, type StatusTone } from "./StatusBadge";
import { Timeline, type TimelineItem } from "./Timeline";

export type AttendanceStatus =
  | "present"
  | "late"
  | "absent"
  | "leave"
  | "half-day"
  | "holiday"
  | "off"
  | "missing-in"
  | "missing-out"
  | "future";

export type AttendanceDayRecord = {
  date: DateOnly;
  status?: AttendanceStatus;
  checkIn?: string;
  checkOut?: string;
  worked?: string;
  late?: string;
  overtime?: string;
  note?: string;
  progress?: number;
};

const STATUS_META: Record<
  AttendanceStatus,
  { label: string; tone: StatusTone; icon: DsIconName }
> = {
  present: { label: "Present", tone: "success", icon: "success" },
  late: { label: "Late", tone: "warning", icon: "warning" },
  absent: { label: "Absent", tone: "danger", icon: "error" },
  leave: { label: "Leave", tone: "info", icon: "calendar" },
  "half-day": { label: "Half day", tone: "warning", icon: "time" },
  holiday: { label: "Holiday", tone: "brand", icon: "information" },
  off: { label: "Off", tone: "neutral", icon: "calendar" },
  "missing-in": { label: "Missing in", tone: "warning", icon: "warning" },
  "missing-out": { label: "Missing out", tone: "danger", icon: "error" },
  future: { label: "Upcoming", tone: "neutral", icon: "time" },
};

export function attendanceStatusMeta(status?: AttendanceStatus) {
  return status ? STATUS_META[status] : undefined;
}

export function AttendanceStatusBadge({
  status,
}: {
  status?: AttendanceStatus;
}) {
  const meta = attendanceStatusMeta(status);
  if (!meta) return null;
  return (
    <StatusBadge
      tone={meta.tone}
      className={`ds-att-status ds-att-status--${status}`}
    >
      <DsIcon name={meta.icon} size={14} />
      {meta.label}
    </StatusBadge>
  );
}

export function AttendanceLegend({
  statuses = [
    "present",
    "late",
    "absent",
    "leave",
    "half-day",
    "holiday",
    "off",
    "missing-in",
    "missing-out",
  ],
}: {
  statuses?: AttendanceStatus[];
}) {
  return (
    <ul className="ds-att-legend">
      {statuses.map((status) => {
        const meta = STATUS_META[status];
        return (
          <li key={status}>
            <span className={`ds-att-swatch ds-att-swatch--${status}`} />
            {meta.label}
          </li>
        );
      })}
    </ul>
  );
}

export function AttendanceMetricCard({
  label,
  value,
  meta,
  tone = "none",
}: {
  label: ReactNode;
  value: ReactNode;
  meta?: ReactNode;
  tone?: "success" | "warning" | "danger" | "info" | "brand" | "none";
}) {
  return (
    <KpiCard
      label={label}
      value={value}
      meta={meta}
      accent="none"
      className={
        tone !== "none"
          ? `ds-att-metric ds-att-metric--${tone}`
          : "ds-att-metric"
      }
    />
  );
}

export function AttendanceSummary({
  present,
  late,
  absent,
  leave,
  off,
  holidays,
  workedHours,
  requiredHours,
  overtimeHours,
  percentage,
  metrics,
}: {
  present?: number;
  late?: number;
  absent?: number;
  leave?: number;
  off?: number;
  holidays?: number;
  workedHours?: ReactNode;
  requiredHours?: ReactNode;
  overtimeHours?: ReactNode;
  percentage?: number;
  metrics?: {
    id: string;
    label: ReactNode;
    value: ReactNode;
    meta?: ReactNode;
    tone?: "success" | "warning" | "danger" | "info" | "brand" | "none";
  }[];
}) {
  const items = [
    {
      id: "present",
      label: "Present",
      value: present,
      tone: "success" as const,
    },
    { id: "late", label: "Late", value: late, tone: "warning" as const },
    { id: "absent", label: "Absent", value: absent, tone: "danger" as const },
    { id: "leave", label: "Leave", value: leave, tone: "info" as const },
    { id: "off", label: "Off", value: off, tone: "none" as const },
    {
      id: "holidays",
      label: "Holidays",
      value: holidays,
      tone: "brand" as const,
    },
  ];
  return (
    <div className="ds-att-summary-wrap">
      <div className="ds-att-summary">
      {items.map((item) =>
        item.value == null ? null : (
          <AttendanceMetricCard
            key={item.id}
            label={item.label}
            value={
              <CompactNumber
                value={item.value}
                fullDecimals={0}
                compactDecimals={0}
              />
            }
            tone={item.tone}
          />
        ),
      )}
      {percentage != null ? (
        <AttendanceMetricCard
          label="Attendance"
          value={`${percentage}%`}
          meta={
            workedHours != null ? (
              <>
                {workedHours}
                {requiredHours ? ` of ${requiredHours}` : null}
              </>
            ) : undefined
          }
          tone="brand"
        />
      ) : null}
      {overtimeHours ? (
        <AttendanceMetricCard label="Overtime" value={overtimeHours} />
      ) : null}
      {metrics?.map((metric) => (
        <AttendanceMetricCard
          key={metric.id}
          label={metric.label}
          value={metric.value}
          meta={metric.meta}
          tone={metric.tone}
        />
      ))}
      </div>
    </div>
  );
}

export function WorkingHoursProgress({
  workedLabel,
  requiredLabel,
  remainingLabel,
  overtimeLabel,
  percent,
  state = "active",
}: {
  workedLabel: ReactNode;
  requiredLabel?: ReactNode;
  remainingLabel?: ReactNode;
  overtimeLabel?: ReactNode;
  percent: number;
  state?: "active" | "complete" | "short" | "late";
}) {
  const tone =
    state === "complete"
      ? "success"
      : state === "short" || state === "late"
        ? "warning"
        : "brand";
  return (
    <div className="ds-att-progress">
      <div className="ds-att-progress__copy">
        <strong>
          {workedLabel}
          {requiredLabel ? <> of {requiredLabel}</> : null}
        </strong>
        <span>{Math.round(percent)}% complete</span>
      </div>
      <ProgressBar
        value={percent}
        max={100}
        tone={tone}
        label={`Worked ${workedLabel}${requiredLabel ? ` of ${requiredLabel}` : ""}`}
      />
      <div className="ds-att-progress__meta">
        {remainingLabel ? <span>Remaining {remainingLabel}</span> : null}
        {overtimeLabel ? (
          <span className="ds-att-progress__ot">OT {overtimeLabel}</span>
        ) : null}
      </div>
    </div>
  );
}

export function CheckInOutCard({
  checkIn,
  checkOut,
  scheduledStart,
  scheduledEnd,
  worked,
  required,
  late,
  earlyDeparture,
  overtime,
  status,
  source,
  compact,
}: {
  checkIn?: string;
  checkOut?: string;
  scheduledStart?: string;
  scheduledEnd?: string;
  worked?: string;
  required?: string;
  late?: string;
  earlyDeparture?: string;
  overtime?: string;
  status?: AttendanceStatus;
  source?: ReactNode;
  compact?: boolean;
}) {
  return (
    <article className={cx("ds-att-cio", compact && "ds-att-cio--compact")}>
      <div className="ds-att-cio__pair">
        <div>
          <DsIcon name="signIn" size={16} />
          <span>Check in</span>
          <strong>{checkIn ?? <EmptyValue />}</strong>
          {scheduledStart ? <em>Scheduled {scheduledStart}</em> : null}
        </div>
        <div>
          <DsIcon name="signOut" size={16} />
          <span>Check out</span>
          <strong>{checkOut ?? <EmptyValue />}</strong>
          {scheduledEnd ? <em>Scheduled {scheduledEnd}</em> : null}
        </div>
      </div>
      <div className="ds-att-cio__facts">
        {worked ? <span>Worked {worked}</span> : null}
        {required ? <span>Required {required}</span> : null}
        {late ? <span>Late {late}</span> : null}
        {earlyDeparture ? <span>Left early {earlyDeparture}</span> : null}
        {overtime ? <span>OT {overtime}</span> : null}
        {source ? <span>{source}</span> : null}
        <AttendanceStatusBadge status={status} />
      </div>
    </article>
  );
}

export function AttendanceTimeline({ items }: { items: TimelineItem[] }) {
  return <Timeline items={items} compact />;
}

export function AttendanceEmptyState() {
  return (
    <EmptyState
      title="No attendance records"
      description="No authorized attendance values are available for this period."
      icon={<DsIcon name="attendance" size={20} />}
    />
  );
}

export function AttendanceLoadingState() {
  return (
    <LoadingState
      title="Loading attendance"
      description="Retrieving authorized attendance records…"
    />
  );
}

export function AttendanceErrorState({ retry }: { retry?: () => void }) {
  return (
    <ErrorState
      description="Attendance could not be displayed. Retained values were not replaced."
      retry={retry}
    />
  );
}

export function AttendanceCalendarDay({
  date,
  outside,
  today,
  selected,
  record,
  onSelect,
}: {
  date: DateOnly;
  outside?: boolean;
  today?: boolean;
  selected?: boolean;
  record?: AttendanceDayRecord;
  onSelect?: (date: DateOnly) => void;
}) {
  const parts = parseDateOnly(date);
  const status = record?.status;
  return (
    <button
      type="button"
      className={cx(
        "ds-att-day",
        status && `ds-att-day--${status}`,
        outside && "ds-att-day--outside",
        today && "ds-att-day--today",
        selected && "ds-att-day--selected",
      )}
      aria-current={today ? "date" : undefined}
      aria-pressed={selected || undefined}
      onClick={() => onSelect?.(date)}
    >
      <span className="ds-att-day__date">{parts?.day}</span>
      {status && status !== "future" ? (
        <span className={`ds-att-day__mark ds-att-day__mark--${status}`}>
          <i />
          {STATUS_META[status].label}
        </span>
      ) : null}
      {record?.checkIn || record?.checkOut ? (
        <span className="ds-att-day__times">
          {record.checkIn ?? "—"} – {record.checkOut ?? "—"}
        </span>
      ) : null}
      {record?.worked ? (
        <span className="ds-att-day__hours">{record.worked}</span>
      ) : null}
      {record?.note ? (
        <span className="ds-att-day__note">{record.note}</span>
      ) : null}
    </button>
  );
}

export function AttendanceCalendarHeader({
  month,
  onMonthChange,
  onToday,
}: {
  month: DateOnly;
  onMonthChange: (month: DateOnly) => void;
  onToday?: () => void;
}) {
  const parts = parseDateOnly(startOfMonth(month));
  if (!parts) return null;
  const monthValue = `${parts.year}-${String(parts.month).padStart(2, "0")}`;
  return (
    <div className="ds-att-cal__header">
      <div className="ds-att-cal__nav">
        <IconButton
          label="Previous month"
          variant="ghost"
          size="compact"
          onClick={() => onMonthChange(addMonths(startOfMonth(month), -1))}
        >
          <DsIcon name="previous" size={16} />
        </IconButton>
        <h2>{monthLabel(parts.year, parts.month)}</h2>
        <IconButton
          label="Next month"
          variant="ghost"
          size="compact"
          onClick={() => onMonthChange(addMonths(startOfMonth(month), 1))}
        >
          <DsIcon name="next" size={16} />
        </IconButton>
      </div>
      <div className="ds-att-cal__pickers">
        <MonthPicker
          compact
          monthOnly
          label="Month"
          value={monthValue}
          onChange={(value) => onMonthChange(`${value}-01`)}
        />
        <YearPicker
          compact
          value={String(parts.year)}
          onChange={(year) =>
            onMonthChange(toDateOnly(Number(year), parts.month, 1))
          }
        />
        {onToday ? (
          <Button size="compact" variant="secondary" onClick={onToday}>
            Today
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function resolveRecord(
  date: DateOnly,
  records: Record<string, AttendanceDayRecord>,
  offWeekdays: number[],
  today: DateOnly,
): AttendanceDayRecord {
  const existing = records[date];
  if (existing) return existing;
  const parts = parseDateOnly(date);
  if (!parts) return { date };
  if (offWeekdays.includes(weekdayJs(parts.year, parts.month, parts.day))) {
    return { date, status: "off" };
  }
  if (compareDateOnly(date, today) > 0) return { date, status: "future" };
  return { date };
}

function weekdayName(date: DateOnly) {
  const parts = parseDateOnly(date);
  if (!parts) return "";
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(parts.year, parts.month - 1, parts.day)));
}

export function AttendanceAgendaDay({
  date,
  record,
  selected,
  today,
  onSelect,
}: {
  date: DateOnly;
  record?: AttendanceDayRecord;
  selected?: boolean;
  today?: boolean;
  onSelect?: (date: DateOnly) => void;
}) {
  const parts = parseDateOnly(date);
  const status = record?.status;
  return (
    <button
      type="button"
      className={cx(
        "ds-att-agenda-day",
        status && `ds-att-agenda-day--${status}`,
        today && "ds-att-agenda-day--today",
        selected && "ds-att-agenda-day--selected",
      )}
      aria-current={today ? "date" : undefined}
      aria-pressed={selected || undefined}
      onClick={() => onSelect?.(date)}
    >
      <span className="ds-att-agenda-day__when">
        <strong>{parts?.day}</strong>
        <em>{weekdayName(date)}</em>
      </span>
      <AttendanceStatusBadge status={status} />
      <span className="ds-att-agenda-day__times">
        {record?.checkIn ?? "—"} – {record?.checkOut ?? "—"}
      </span>
      {record?.worked ? (
        <span className="ds-att-agenda-day__hours">{record.worked}</span>
      ) : null}
      {record?.note ? (
        <span className="ds-att-agenda-day__note">{record.note}</span>
      ) : null}
    </button>
  );
}

export function AttendanceAgendaGroup({
  label,
  children,
}: {
  label?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="ds-att-agenda-group">
      {label ? <h3>{label}</h3> : null}
      <div className="ds-att-agenda-group__list">{children}</div>
    </section>
  );
}

export function AttendanceAgenda({
  month,
  records,
  selected,
  onSelect,
  weekStartsOn = 0,
  offWeekdays = [0],
  today = dubaiTodayDateOnly(),
}: {
  month: DateOnly;
  records?: AttendanceDayRecord[];
  selected?: DateOnly;
  onSelect?: (date: DateOnly) => void;
  weekStartsOn?: number;
  offWeekdays?: number[];
  today?: DateOnly;
}) {
  const parts = parseDateOnly(startOfMonth(month));
  if (!parts) return null;
  const byDate = Object.fromEntries(
    (records ?? []).map((record) => [record.date, record]),
  );
  const count = daysInMonth(parts.year, parts.month);
  const days = Array.from({ length: count }, (_, index) =>
    toDateOnly(parts.year, parts.month, index + 1),
  );
  const weeks: DateOnly[][] = [];
  days.forEach((date) => {
    const dayParts = parseDateOnly(date)!;
    const offset = weekdayOffset(
      dayParts.year,
      dayParts.month,
      dayParts.day,
      weekStartsOn,
    );
    if (offset === 0 || weeks.length === 0) weeks.push([]);
    weeks[weeks.length - 1]!.push(date);
  });
  return (
    <div className="ds-att-agenda" aria-label="Attendance agenda">
      {weeks.map((week, index) => (
        <AttendanceAgendaGroup key={week[0]} label={`Week ${index + 1}`}>
          {week.map((date) => {
            const record = resolveRecord(date, byDate, offWeekdays, today);
            return (
              <AttendanceAgendaDay
                key={date}
                date={date}
                record={record}
                today={date === today}
                selected={date === selected}
                onSelect={onSelect}
              />
            );
          })}
        </AttendanceAgendaGroup>
      ))}
    </div>
  );
}

export function AttendanceCalendar({
  month,
  onMonthChange,
  records,
  selected,
  onSelect,
  weekStartsOn = 0,
  offWeekdays = [0],
  today = dubaiTodayDateOnly(),
}: {
  month: DateOnly;
  onMonthChange: (month: DateOnly) => void;
  records?: AttendanceDayRecord[];
  selected?: DateOnly;
  onSelect?: (date: DateOnly) => void;
  weekStartsOn?: number;
  offWeekdays?: number[];
  today?: DateOnly;
}) {
  const parts = parseDateOnly(startOfMonth(month));
  if (!parts) return null;
  const byDate = Object.fromEntries(
    (records ?? []).map((record) => [record.date, record]),
  );
  const blanks = weekdayOffset(parts.year, parts.month, 1, weekStartsOn);
  const count = daysInMonth(parts.year, parts.month);
  const monthStart = toDateOnly(parts.year, parts.month, 1);
  const leading = Array.from({ length: blanks }, (_, index) =>
    addDays(monthStart, index - blanks),
  );
  const current = Array.from({ length: count }, (_, index) =>
    toDateOnly(parts.year, parts.month, index + 1),
  );
  const remainder = (blanks + count) % 7;
  const trailing = Array.from(
    { length: remainder === 0 ? 0 : 7 - remainder },
    (_, index) => addDays(current[current.length - 1]!, index + 1),
  );
  const cells = [
    ...leading.map((date) => ({ date, outside: true })),
    ...current.map((date) => ({ date, outside: false })),
    ...trailing.map((date) => ({ date, outside: true })),
  ];
  const labels = weekdayLabels(weekStartsOn);

  return (
    <section className="ds-att-cal" aria-label="Attendance calendar">
      <AttendanceCalendarHeader
        month={month}
        onMonthChange={onMonthChange}
        onToday={() => {
          onMonthChange(startOfMonth(today));
          onSelect?.(today);
        }}
      />
      <div className="ds-att-cal__weekdays">
        {labels.map((label, index) => {
          const weekday = (weekStartsOn + index) % 7;
          return (
            <span
              key={label}
              className={
                offWeekdays.includes(weekday)
                  ? "ds-att-cal__weekday--off"
                  : undefined
              }
            >
              {label}
            </span>
          );
        })}
      </div>
      <div className="ds-att-cal__grid" role="grid">
        {cells.map(({ date, outside }) => {
          const record = resolveRecord(date, byDate, offWeekdays, today);
          return (
            <AttendanceCalendarDay
              key={date}
              date={date}
              outside={outside}
              today={date === today}
              selected={date === selected}
              record={record}
              onSelect={onSelect}
            />
          );
        })}
      </div>
      <AttendanceAgenda
        month={month}
        records={records}
        selected={selected}
        onSelect={onSelect}
        weekStartsOn={weekStartsOn}
        offWeekdays={offWeekdays}
        today={today}
      />
      <details className="ds-att-legend-wrap">
        <summary>Status key</summary>
        <AttendanceLegend />
      </details>
    </section>
  );
}

export function AttendanceDayDetail({
  date,
  record,
  shift,
  progress,
  notes,
  timeline,
  source,
}: {
  date: DateOnly;
  record?: AttendanceDayRecord;
  shift?: ReactNode;
  progress?: ReactNode;
  notes?: ReactNode;
  timeline?: TimelineItem[];
  source?: ReactNode;
}) {
  return (
    <section className="ds-att-detail" aria-label="Selected day">
      <header>
        <h3>
          <CompactDate value={date} />
        </h3>
        <AttendanceStatusBadge status={record?.status} />
      </header>
      {shift ? <p className="ds-att-detail__shift">{shift}</p> : null}
      <CheckInOutCard
        checkIn={record?.checkIn}
        checkOut={record?.checkOut}
        worked={record?.worked}
        late={record?.late}
        overtime={record?.overtime}
        status={record?.status}
        source={source}
        compact
      />
      {progress}
      {notes ? <p className="ds-att-detail__notes">{notes}</p> : null}
      {timeline?.length ? <AttendanceTimeline items={timeline} /> : null}
    </section>
  );
}
