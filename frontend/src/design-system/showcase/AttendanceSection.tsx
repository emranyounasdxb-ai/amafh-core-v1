import { useMemo, useState } from "react";
import {
  AttendanceCalendar,
  AttendanceDayDetail,
  AttendanceEmptyState,
  AttendanceErrorState,
  AttendanceLoadingState,
  AttendanceSummary,
  CheckInOutCard,
  Drawer,
  InfoGrid,
  SectionCard,
  WorkingHoursProgress,
  type AttendanceDayRecord,
  type DateOnly,
} from "../index";
import { startOfMonth } from "../lib/dateOnly";

const TODAY: DateOnly = "2026-10-02";

const records: AttendanceDayRecord[] = [
  {
    date: "2026-10-01",
    status: "present",
    checkIn: "08:04",
    checkOut: "17:12",
    worked: "8h 08m",
    progress: 100,
  },
  {
    date: "2026-10-02",
    status: "late",
    checkIn: "08:46",
    checkOut: "17:21",
    worked: "7h 35m",
    late: "16m",
    progress: 94,
  },
  {
    date: "2026-10-05",
    status: "present",
    checkIn: "08:01",
    checkOut: "17:04",
    worked: "8h 03m",
    progress: 100,
  },
  {
    date: "2026-10-06",
    status: "late",
    checkIn: "09:12",
    checkOut: "17:18",
    worked: "7h 06m",
    late: "42m",
    progress: 88,
  },
  { date: "2026-10-07", status: "absent" },
  { date: "2026-10-08", status: "leave", note: "Approved annual leave" },
  { date: "2026-10-09", status: "holiday", note: "Public holiday" },
  {
    date: "2026-10-10",
    status: "half-day",
    checkIn: "08:05",
    checkOut: "13:02",
    worked: "4h 57m",
    progress: 62,
  },
  { date: "2026-10-12", status: "missing-in", checkOut: "17:08" },
  { date: "2026-10-13", status: "missing-out", checkIn: "08:11" },
  {
    date: "2026-10-14",
    status: "present",
    checkIn: "08:02",
    checkOut: "18:40",
    worked: "9h 38m",
    overtime: "1h 38m",
    progress: 100,
  },
];

export function AttendanceSection() {
  const [month, setMonth] = useState<DateOnly>("2026-10-01");
  const [selected, setSelected] = useState<DateOnly>(TODAY);
  const [drawer, setDrawer] = useState(false);
  const record = useMemo(
    () => records.find((item) => item.date === selected),
    [selected],
  );

  return (
    <section id="attendance" className="ds-stack-20">
      <SectionCard
        title="Attendance"
        description="Presentation only. Off days, statuses, hours, and dates are supplied by the feature page. Narrow containers switch to AttendanceAgenda instead of squeezing seven columns."
      >
        <AttendanceSummary
          present={18}
          late={3}
          absent={1}
          leave={1}
          off={4}
          holidays={1}
          workedHours="146h"
          requiredHours="160h"
          overtimeHours="4h 12m"
          percentage={94}
        />
        <AttendanceCalendar
          month={month}
          onMonthChange={setMonth}
          records={records}
          selected={selected}
          onSelect={(date) => {
            setSelected(date);
            setDrawer(true);
          }}
          weekStartsOn={0}
          offWeekdays={[0]}
          today={TODAY}
        />
        <InfoGrid>
          <CheckInOutCard
            checkIn="08:46"
            checkOut="17:21"
            scheduledStart="08:30"
            scheduledEnd="17:30"
            worked="7h 35m"
            required="8h"
            late="16m"
            status="late"
            source="Office turnstile"
          />
          <WorkingHoursProgress
            workedLabel="6h 30m"
            requiredLabel="8h"
            remainingLabel="1h 30m"
            percent={81}
            state="active"
          />
        </InfoGrid>
        <AttendanceDayDetail
          date={selected}
          record={record}
          shift="North operations · 08:30–17:30"
          progress={
            <WorkingHoursProgress
              workedLabel={record?.worked ?? "0h"}
              requiredLabel="8h"
              overtimeLabel={record?.overtime}
              percent={record?.progress ?? 0}
              state={record?.status === "present" ? "complete" : "late"}
            />
          }
          notes={record?.note}
          timeline={[
            {
              id: "in",
              time: record?.checkIn ?? "—",
              title: "Check in",
              tone: "success",
            },
            {
              id: "out",
              time: record?.checkOut ?? "—",
              title: "Check out",
              tone: "info",
            },
          ]}
          source="Office turnstile"
        />
        <div className="ds-narrow-frame">
          <strong>Narrow / agenda</strong>
          <AttendanceCalendar
            month={startOfMonth(month)}
            onMonthChange={setMonth}
            records={records}
            selected={selected}
            onSelect={setSelected}
            today={TODAY}
          />
        </div>
        <AttendanceLoadingState />
        <AttendanceEmptyState />
        <AttendanceErrorState />
      </SectionCard>
      <Drawer
        open={drawer}
        title="Selected day"
        onClose={() => setDrawer(false)}
      >
        <AttendanceDayDetail date={selected} record={record} />
      </Drawer>
    </section>
  );
}
