import { useEffect, useState } from "react";
import { DsIcon } from "../../design-system";

export function DubaiClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const time = now.toLocaleTimeString("en-US", {
    timeZone: "Asia/Dubai",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
  const date = now.toLocaleDateString("en-GB", {
    timeZone: "Asia/Dubai",
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
  return (
    <p className={clockClass} aria-label={`Current Dubai date and time, ${date} ${time}`}>
      <DsIcon name="calendar" size={16} />
      <span>
        <b>{time}</b>
        <span aria-hidden="true"> · </span>
        {date}
      </span>
    </p>
  );
}

const clockClass = "ds-app-clock";
