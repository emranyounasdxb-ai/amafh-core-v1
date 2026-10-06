import { useMemo, useOptimistic, useState, useTransition } from "react";
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  NoResultsState,
  OfflineState,
  PageContainer,
  PageHeader,
  PermissionDeniedState,
  RecordCount,
  ResponsiveDataTable,
  SearchFilterToolbar,
  StatusBadge,
  CompactDateTime,
  TruncatedText,
  UnavailableState,
  type DataTableColumn,
} from "../../design-system";
import type { Page } from "../../app/api/models";
import { useResource } from "../../app/api/useResource";
import { useSession } from "../../app/session/useSession";
import type { PageId } from "../../access";
import {
  openNotificationDestination,
  type NotificationOpenResult,
} from "./openNotification";
import { notificationKindLabel } from "./notificationKind";

export type Notice = {
  id: string;
  message: string;
  kind: string;
  readAt: string | null;
  createdAt: string;
};

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

export function NotificationItems({
  items,
  onActivate,
  disabled,
}: {
  items: Notice[];
  onActivate: (item: Notice) => void;
  disabled?: boolean;
}) {
  if (!items.length) return null;
  return (
    <ul className="ds-app-notice-list">
      {items.map((item) => (
        <li key={item.id}>
          <button
            type="button"
            className="ds-app-notice"
            disabled={disabled}
            onClick={() => onActivate(item)}
          >
            <span
              className="ds-app-notice-mark"
              data-unread={item.readAt ? undefined : "true"}
              aria-hidden="true"
            />
            <span className="ds-app-notice-body">
              <span className="ds-app-notice-title">{item.message}</span>
              <small>
                {item.readAt ? "Read" : "Unread"} ·{" "}
                {notificationKindLabel(item.kind)} ·{" "}
                <CompactDateTime value={item.createdAt} />
              </small>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function NotificationsPage({
  onOpenRecord,
}: {
  onOpenRecord: (page: PageId, recordId?: string) => void;
}) {
  const { api, session } = useSession();
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<
    Exclude<NotificationOpenResult["status"], "opened"> | null
  >(null);
  const [, startTransition] = useTransition();
  const resource = useResource<Page<Notice>>(
    `/notifications?page=${page}&pageSize=25&readStatus=${filter}`,
    refresh,
  );
  const [items, setOptimistic] = useOptimistic(resource.data?.items ?? []);
  const visible = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return items;
    return items.filter(
      (item) =>
        item.message.toLowerCase().includes(term) ||
        notificationKindLabel(item.kind).toLowerCase().includes(term),
    );
  }, [items, search]);
  const mark = async (id?: string) => {
    setError("");
    const current = resource.data?.items ?? [];
    startTransition(() => {
      if (id) {
        setOptimistic(
          current.map((item) =>
            item.id === id
              ? { ...item, readAt: item.readAt || new Date().toISOString() }
              : item,
          ),
        );
      } else {
        setOptimistic(
          current.map((item) => ({
            ...item,
            readAt: item.readAt || new Date().toISOString(),
          })),
        );
      }
    });
    try {
      await api.request(
        id ? `/notifications/${id}/read` : "/notifications/read-all",
        { method: "POST" },
      );
      setRefresh((value) => value + 1);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Unable to update notifications",
      );
      resource.reload();
    }
  };
  const activate = async (item: Notice) => {
    if (busyId || !session) return;
    setBusyId(item.id);
    setFeedback(null);
    if (!item.readAt) void mark(item.id);
    const result = await openNotificationDestination(
      api,
      item.id,
      session,
    );
    setBusyId(null);
    if (result.status === "opened") {
      onOpenRecord(result.page, result.recordId);
      return;
    }
    setFeedback(result.status);
  };
  const total = resource.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / 25));
  const columns: DataTableColumn<Notice>[] = [
    {
      key: "message",
      header: "Notice",
      render: (row) => <TruncatedText value={row.message} />,
    },
    {
      key: "kind",
      header: "Kind",
      render: (row) => notificationKindLabel(row.kind),
    },
    {
      key: "readAt",
      header: "Status",
      render: (row) => (
        <StatusBadge tone={row.readAt ? "neutral" : "danger"}>
          {row.readAt ? "Read" : "Unread"}
        </StatusBadge>
      ),
    },
    {
      key: "createdAt",
      header: "Received",
      kind: "datetime",
      render: (row) => <CompactDateTime value={row.createdAt} />,
    },
  ];
  return (
    <PageContainer>
      <PageHeader
        title="Notifications"
        subtitle="Authorized notices for this account"
      />
      <SearchFilterToolbar
        searchId="notification-search"
        searchLabel="Search"
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search this page of notices"
        actions={
          <Button
            variant="secondary"
            size="compact"
            onClick={() => void mark()}
          >
            Mark all read
          </Button>
        }
        filters={[
          {
            id: "read-status",
            label: "Read status",
            value: filter,
            options: [
              { value: "all", label: "All" },
              { value: "unread", label: "Unread" },
              { value: "read", label: "Read" },
            ],
            onChange: (value) => {
              startTransition(() => {
                setFilter(value || "all");
                setPage(1);
                setFeedback(null);
              });
            },
          },
        ]}
        applied={
          search
            ? [
                {
                  id: "search",
                  field: "Search",
                  value: search,
                  label: `Search: ${search}`,
                  onRemove: () => setSearch(""),
                },
              ]
            : []
        }
        onClearFilters={() => setSearch("")}
      />
      {resource.denied ? (
        <PermissionDeniedState />
      ) : resource.error && isOffline(resource.error) ? (
        <OfflineState />
      ) : resource.error ? (
        <ErrorState description={resource.error} retry={resource.reload} />
      ) : resource.loading && !resource.data ? (
        <LoadingState />
      ) : total === 0 ? (
        <EmptyState
          title="No notifications"
          description="There are no retained notices in this filter."
        />
      ) : visible.length === 0 ? (
        <NoResultsState title="No matching notifications" />
      ) : (
        <>
        <RecordCount count={total} />
        <ResponsiveDataTable
          ariaLabel="Notifications"
          columns={columns}
          rows={visible}
          rowKey={(row) => row.id}
          page={page}
          pageCount={pageCount}
          onPageChange={setPage}
          onRowActivate={(row) => {
            if (!busyId) void activate(row);
          }}
        />
        </>
      )}
      {error ? <ErrorState description={error} /> : null}
      {feedback === "permission" ? <PermissionDeniedState /> : null}
      {feedback === "unavailable" ? (
        <UnavailableState title="Record unavailable" />
      ) : null}
    </PageContainer>
  );
}
