import { useEffect, useState } from "react";
import type { ApiClient } from "../../app/api/http";

type Summary = { unread?: { inbox?: number } };

/** Mailbox refresh is a read. It must not call the human-activity endpoint. */
export function useInboxUnread(api: ApiClient, employeeId: string | null) {
  const [unread, setUnread] = useState(0);
  const [trackedEmployee, setTrackedEmployee] = useState(employeeId);
  if (trackedEmployee !== employeeId) {
    setTrackedEmployee(employeeId);
    setUnread(0);
  }
  useEffect(() => {
    if (!employeeId) return;
    let cancelled = false;
    let pending = false;
    const load = () => {
      if (pending) return;
      pending = true;
      void api
        .request<Summary>("/mailbox/summary")
        .then((summary) => {
          if (!cancelled) setUnread(summary.unread?.inbox ?? 0);
        })
        .catch(() => {
          if (!cancelled) setUnread(0);
        })
        .finally(() => {
          pending = false;
        });
    };
    load();
    const timer = window.setInterval(load, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [api, employeeId]);
  return unread;
}
