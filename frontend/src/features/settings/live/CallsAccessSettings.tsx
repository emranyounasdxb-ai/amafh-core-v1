import { useCallback, useState } from "react";
import {
  Button,
  ConfirmationDialog,
  DataTable,
  EmptyState,
  ErrorState,
  InlineNotice,
  Pagination,
  PermissionDeniedState,
  PersonValue,
  SearchInput,
  SectionCard,
  Stack,
  StatusBadge,
  formatDubaiTimestamp,
  formatFullNumber,
} from "../../../design-system";
import { ApiFailure } from "../../../app/api/http";
import { useResource } from "../../../app/api/useResource";
import { recordImageSrc } from "../../../app/api/recordImages";
import { useSession } from "../../../app/session/useSession";

type CallsUser = {
  id: string;
  employeeId: string;
  name: string;
  employeeCode: string;
  avatarFileId: string | null;
  designation: string;
  branch: string | null;
  accountStatus: string;
  employeeStatus: string;
  granted: boolean;
  effective: boolean;
  fixed: boolean;
  revision: number;
  changedAt: string | null;
};

type CallsUsers = {
  items: CallsUser[];
  total: number;
  page: number;
  pageSize: number;
};

export function CallsAccessSettings() {
  const { api, session } = useSession();
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ error: boolean; text: string } | null>(
    null,
  );
  const [pending, setPending] = useState<{
    owner: typeof session;
    user: CallsUser;
    granted: boolean;
  } | null>(null);
  const path =
    session?.designation === "Owner"
      ? `/calls/access?query=${encodeURIComponent(appliedQuery)}&page=${page}&pageSize=25`
      : null;
  const resource = useResource<CallsUsers>(path, refresh);
  const applyQuery = useCallback((next: string) => {
    setAppliedQuery(next.trim().slice(0, 100));
    setPage(1);
  }, []);
  const selection = pending?.owner === session ? pending : null;

  const save = async () => {
    if (!selection || busy || session?.designation !== "Owner") return;
    setBusy(true);
    setNotice(null);
    try {
      await api.request<CallsUser>(
        `/calls/access/${encodeURIComponent(selection.user.id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            granted: selection.granted,
            revision: selection.user.revision,
          }),
        },
      );
      setNotice({
        error: false,
        text: selection.granted
          ? `Calls access allowed for ${selection.user.name}. Account status is unchanged.`
          : `Calls access blocked for ${selection.user.name}. New requests are blocked; active server streams stop within 15 seconds.`,
      });
      setPending(null);
      setRefresh((value) => value + 1);
    } catch (error) {
      setPending(null);
      setNotice({
        error: true,
        text:
          error instanceof ApiFailure
            ? error.message
            : "Calls access could not be saved. Refresh and try again.",
      });
      // A concurrent update must be reviewed, rather than overwritten from a stale row.
      if (error instanceof ApiFailure && error.code === "CALLS_ACCESS_CONFLICT")
        setRefresh((value) => value + 1);
    } finally {
      setBusy(false);
    }
  };

  if (session?.designation !== "Owner" || resource.denied)
    return (
      <PermissionDeniedState description="Only the Owner can manage individual Calls access." />
    );

  return (
    <Stack gap={16}>
      <InlineNotice tone="info" title="Individual access">
        Calls is available only to Owner, Managing Director, Sales Manager,
        Coordinator and Compliance. Existing access is preserved until blocked
        here. Owner access is protected. Allowing Calls does not activate a
        disabled account or change other permissions.
      </InlineNotice>
      {notice ? (
        <InlineNotice
          tone={notice.error ? "error" : "success"}
          title={notice.error ? "Not saved" : "Access saved"}
        >
          {notice.text}
        </InlineNotice>
      ) : null}
      <SectionCard
        title="Eligible users"
        description="Search by name, employee code or User Type."
      >
        <Stack gap={12}>
          <SearchInput
            id="calls-access-search"
            value={query}
            onChange={setQuery}
            onDebouncedChange={applyQuery}
            debounce={300}
            disabled={busy}
            placeholder="Search eligible users"
            label="Search eligible Calls users"
          />
          <div className="ds-cluster">
            <span>{formatFullNumber(resource.data?.total ?? 0)} users</span>
            <Button
              variant="secondary"
              size="compact"
              disabled={busy || resource.loading}
              onClick={() => setRefresh((value) => value + 1)}
            >
              Refresh
            </Button>
          </div>
          <DataTable<CallsUser>
            ariaLabel="Individual call recordings access"
            tableId="calls-individual-access"
            rowKey={(row) => row.id}
            rows={resource.data?.items ?? []}
            loading={resource.loading && !resource.data}
            error={
              resource.error ? (
                <ErrorState
                  description={resource.error}
                  retry={resource.reload}
                />
              ) : undefined
            }
            empty={
              <EmptyState
                title="No eligible accounts"
                description="Only provisioned accounts in the eligible Calls User Types appear here."
              />
            }
            columns={[
              {
                key: "name",
                header: "User",
                width: "300px",
                fixed: true,
                render: (row) => (
                  <PersonValue
                    name={row.name}
                    code={row.employeeCode}
                    src={recordImageSrc("employee", {
                      id: row.employeeId,
                      avatarFileId: row.avatarFileId,
                    })}
                  />
                ),
              },
              {
                key: "designation",
                header: "User Type",
                width: "180px",
                render: (row) => row.designation,
              },
              {
                key: "branch",
                header: "Branch",
                width: "140px",
                render: (row) => row.branch ?? "All branches",
              },
              {
                key: "account",
                header: "Account",
                width: "180px",
                render: (row) => `${row.accountStatus} · ${row.employeeStatus}`,
              },
              {
                key: "access",
                header: "Calls access",
                width: "160px",
                render: (row) => (
                  <StatusBadge
                    tone={
                      row.effective
                        ? "success"
                        : row.granted
                          ? "neutral"
                          : "warning"
                    }
                  >
                    {row.fixed
                      ? "Owner · protected"
                      : row.granted
                        ? "Allowed"
                        : "Blocked"}
                  </StatusBadge>
                ),
              },
              {
                key: "changed",
                header: "Last changed",
                width: "180px",
                render: (row) =>
                  row.changedAt
                    ? formatDubaiTimestamp(row.changedAt)
                    : "Not changed",
              },
              {
                key: "action",
                header: "Action",
                width: "150px",
                render: (row) => (
                  <Button
                    variant="secondary"
                    size="compact"
                    disabled={
                      row.fixed ||
                      busy ||
                      resource.loading ||
                      Boolean(resource.error)
                    }
                    onClick={() =>
                      setPending({
                        owner: session,
                        user: row,
                        granted: !row.granted,
                      })
                    }
                  >
                    {row.fixed
                      ? "Protected"
                      : row.granted
                        ? "Block Calls"
                        : "Allow Calls"}
                  </Button>
                ),
              },
            ]}
          />
          {resource.data && resource.data.total > 25 ? (
            <Pagination
              page={page}
              pageCount={Math.max(1, Math.ceil(resource.data.total / 25))}
              onPageChange={(next) => {
                if (!busy) setPage(next);
              }}
            />
          ) : null}
        </Stack>
      </SectionCard>
      <ConfirmationDialog
        open={Boolean(selection)}
        title={`${selection?.granted ? "Allow" : "Block"} Calls for ${selection?.user.name ?? "this user"}?`}
        confirmLabel={selection?.granted ? "Allow Calls" : "Block Calls"}
        busy={busy}
        onConfirm={() => void save()}
        onClose={() => {
          if (!busy) setPending(null);
        }}
      >
        <p>
          {selection?.granted
            ? "This allows recording search, playback and download within the existing Calls role boundary."
            : "This blocks recording search, playback and download. An active server stream stops on its next authorization check, within 15 seconds; audio already received cannot be recalled."}
        </p>
        <p>
          The account and all other module permissions remain unchanged. This
          action is recorded in Audit.
        </p>
      </ConfirmationDialog>
    </Stack>
  );
}
