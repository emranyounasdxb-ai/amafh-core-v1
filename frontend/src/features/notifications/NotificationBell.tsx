import { useOptimistic, useState, useTransition } from "react";
import {
  Button,
  DsIcon,
  EmptyState,
  ErrorState,
  IconButton,
  LoadingState,
  PermissionDeniedState,
  Popover,
  SidebarBadge,
  UnavailableState,
} from "../../design-system";
import type { Page } from "../../app/api/models";
import { useResource } from "../../app/api/useResource";
import { useSession } from "../../app/session/useSession";
import type { PageId } from "../../access";
import { NotificationItems, type Notice } from "./NotificationsPage";
import {
  openNotificationDestination,
  type NotificationOpenResult,
} from "./openNotification";

export function NotificationBell({
  onViewAll,
  onOpenRecord,
}: {
  onViewAll: () => void;
  onOpenRecord: (page: PageId, recordId?: string) => void;
}) {
  const { api, session } = useSession();
  const [open, setOpen] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<
    Exclude<NotificationOpenResult["status"], "opened"> | null
  >(null);
  const [, startTransition] = useTransition();
  const unread = useResource<{ count: number }>(
    "/notifications/unread-count",
    refresh,
  );
  const recent = useResource<Page<Notice>>(
    open ? `/notifications?page=1&pageSize=5&readStatus=all` : null,
    refresh,
  );
  const count = unread.data?.count ?? 0;
  const [optimisticCount, setOptimisticCount] = useOptimistic(count);
  const items = recent.data?.items ?? [];
  const markRead = async (id: string) => {
    startTransition(() => {
      setOptimisticCount(Math.max(0, optimisticCount - 1));
    });
    try {
      await api.request(`/notifications/${id}/read`, { method: "POST" });
      setRefresh((value) => value + 1);
    } catch {
      unread.reload();
    }
  };
  const activate = async (item: Notice) => {
    if (busy || !session) return;
    setBusy(true);
    setFeedback(null);
    if (!item.readAt) void markRead(item.id);
    const result = await openNotificationDestination(
      api,
      item.id,
      session,
    );
    setBusy(false);
    if (result.status === "opened") {
      setOpen(false);
      onOpenRecord(result.page, result.recordId);
      return;
    }
    setFeedback(result.status);
  };
  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        setFeedback(null);
        if (next) setRefresh((value) => value + 1);
      }}
      placement="bottom-end"
      label="Notifications"
      trigger={
        <span className="ds-app-bell">
          <IconButton label="Notifications" variant="ghost">
            <DsIcon name="notification" size={18} />
          </IconButton>
          <SidebarBadge
            count={optimisticCount}
            tone="danger"
            label={`${optimisticCount} unread notifications`}
          />
        </span>
      }
    >
      <div className="ds-app-popover">
        <header className="ds-app-popover__header">
          <h2 className="ds-app-popover__title">Notifications</h2>
        </header>
        <div className="ds-app-popover__body">
          {recent.loading && !recent.data ? (
            <LoadingState title="Loading notices" />
          ) : null}
          {recent.error ? (
            <ErrorState description={recent.error} retry={recent.reload} />
          ) : !items.length && !recent.loading ? (
            <EmptyState title="No notifications" />
          ) : (
            <NotificationItems
              items={items}
              disabled={busy}
              onActivate={(item) => void activate(item)}
            />
          )}
          {feedback === "permission" ? <PermissionDeniedState /> : null}
          {feedback === "unavailable" ? (
            <UnavailableState title="Record unavailable" />
          ) : null}
        </div>
        <footer className="ds-app-popover__footer">
          <Button
            variant="secondary"
            size="compact"
            onClick={() => {
              setOpen(false);
              onViewAll();
            }}
          >
            View all notifications
          </Button>
        </footer>
      </div>
    </Popover>
  );
}
