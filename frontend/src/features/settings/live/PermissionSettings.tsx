import { useEffect, useMemo, useState } from "react";
import {
  Button,
  ConfirmationDialog,
  DetailGrid,
  EmptyState,
  ErrorState,
  InlineNotice,
  LoadingState,
  PermissionDeniedState,
  ResponsiveDataTable,
  Select,
  StatusBadge,
  StickyActionBar,
  Switch,
  UnsavedChangesDialog,
  formatDubaiTimestamp,
  formatFullNumber,
  type DataTableColumn,
} from "../../../design-system";
import { ApiFailure } from "../../../app/api/http";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import { Text } from "./settingsCells";
import styles from "./SettingsPage.module.css";

type PermissionState = "granted" | "revoked" | "fixed" | "unavailable";

type PermissionItem = {
  key: string;
  module: string;
  action: string;
  state: PermissionState;
  configurable: boolean;
  dataScope: string | null;
  reason: string | null;
};

type UserType = {
  id: string;
  name: string;
  employeeCount: number;
  revision: string;
  lastChangedAt: string | null;
  lastChangedBy: string | null;
  permissions: PermissionItem[];
};

type Restriction = { title: string; description: string };

type PermissionConfiguration = {
  canManage: boolean;
  userTypes: UserType[];
  restrictions: Restriction[];
};

type Notice = { tone: "success" | "error"; title: string; text: string; conflict?: boolean };

const savedGrant = (item: PermissionItem) => item.state === "granted";

function changeSummary(type: UserType | undefined, drafts: Record<string, boolean>) {
  if (!type) return [];
  return type.permissions.filter(
    (item) => item.configurable && item.key in drafts && drafts[item.key] !== savedGrant(item),
  );
}

export function PermissionSettings() {
  const { api } = useSession();
  const resource = useResource<PermissionConfiguration>("/permission-configuration");
  const [confirmed, setConfirmed] = useState<PermissionConfiguration | null>(null);
  const config = confirmed ?? resource.data;
  const [selectedId, setSelectedId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, boolean>>({});
  const [pendingType, setPendingType] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  const userTypes = useMemo(() => config?.userTypes ?? [], [config]);
  const selected = userTypes.find((type) => type.id === selectedId) ?? userTypes[0];
  const changes = changeSummary(selected, drafts);
  const dirty = changes.length > 0;
  const canEdit = Boolean(config?.canManage && selected && selected.name !== "Owner");

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (resource.denied)
    return (
      <PermissionDeniedState description="User Type permissions are outside your authorized access." />
    );
  if (!config)
    return resource.error ? (
      <ErrorState
        description="User Type permissions could not be loaded."
        retry={resource.reload}
      />
    ) : (
      <LoadingState
        title="Loading permissions"
        description="Retrieving User Types and their saved permissions…"
      />
    );
  if (!selected)
    return (
      <EmptyState
        title="No User Types"
        description="No approved User Types are available."
      />
    );

  const chooseType = (id: string) => {
    if (id === selected.id) return;
    if (dirty) {
      setPendingType(id);
      return;
    }
    setSelectedId(id);
    setDrafts({});
    setNotice(null);
  };

  const current = (item: PermissionItem) =>
    item.key in drafts ? drafts[item.key] : savedGrant(item);

  const reloadSaved = () => {
    setConfirmed(null);
    setNotice(null);
    resource.reload();
  };

  const save = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const result = await api.request<PermissionConfiguration>(
        `/permission-configuration/${selected.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            revision: selected.revision,
            grants: Object.fromEntries(changes.map((item) => [item.key, drafts[item.key]])),
          }),
        },
      );
      setConfirmed(result);
      setDrafts({});
      setConfirming(false);
      setNotice({
        tone: "success",
        title: "Permissions saved",
        text: `${selected.name} permissions were saved. Existing sessions use them on their next request.`,
      });
    } catch (failure) {
      setConfirming(false);
      setNotice({
        tone: "error",
        title: "Not saved",
        text:
          failure instanceof ApiFailure
            ? failure.message
            : "The server could not be reached. No change was saved.",
        conflict: failure instanceof ApiFailure && failure.code === "PERMISSION_CONFLICT",
      });
    } finally {
      setBusy(false);
    }
  };

  const accessCell = (item: PermissionItem) => {
    if (item.state === "fixed") return <StatusBadge tone="brand">Always granted</StatusBadge>;
    if (item.state === "unavailable") return <StatusBadge>Not permitted</StatusBadge>;
    const value = current(item);
    const changed = value !== savedGrant(item);
    const badge = changed ? (
      <StatusBadge tone="warning">{value ? "Will be granted" : "Will be revoked"}</StatusBadge>
    ) : (
      <StatusBadge tone={value ? "success" : "neutral"}>
        {value ? "Granted" : "Not granted"}
      </StatusBadge>
    );
    if (!canEdit) return badge;
    return (
      <Switch
        id={`permission-${item.key}`}
        checked={value}
        disabled={busy}
        onChange={(next) => {
          setNotice((previous) => (previous?.tone === "success" ? null : previous));
          setDrafts((previous) => {
            const updated = { ...previous };
            if (next === savedGrant(item)) delete updated[item.key];
            else updated[item.key] = next;
            return updated;
          });
        }}
        label={
          <>
            <span className={styles.srOnly}>
              {item.module}: {item.action}.{" "}
            </span>
            {badge}
          </>
        }
      />
    );
  };

  const columns: DataTableColumn<PermissionItem>[] = [
    { key: "module", header: "Module", width: "130px", render: (item) => <Text value={item.module} /> },
    { key: "action", header: "Action", width: "300px", render: (item) => <Text value={item.action} /> },
    {
      key: "scope",
      header: "Data scope",
      width: "230px",
      render: (item) => <Text value={item.dataScope} />,
    },
    { key: "access", header: "Access", width: "190px", render: accessCell },
    {
      key: "reason",
      header: "Notes",
      width: "340px",
      render: (item) => (
        <Text
          value={
            item.reason ??
            (canEdit ? "The Owner can grant or revoke this action." : "Configurable by the Owner.")
          }
        />
      ),
    },
  ];

  const changed = selected.lastChangedAt
    ? `Last changed ${formatDubaiTimestamp(selected.lastChangedAt)} by ${selected.lastChangedBy ?? "Unavailable"}`
    : "Not changed since setup";
  const employees = `${formatFullNumber(selected.employeeCount)} ${
    selected.employeeCount === 1 ? "employee" : "employees"
  }`;

  return (
    <div className={styles.panel}>
      {!config.canManage ? (
        <InlineNotice tone="info" title="View only">
          Only the Owner can change User Type permissions.
        </InlineNotice>
      ) : selected.name === "Owner" ? (
        <InlineNotice tone="info" title="Owner permissions are fixed">
          The Owner User Type holds full system authority. Its permissions cannot be changed.
        </InlineNotice>
      ) : null}
      {notice ? (
        <InlineNotice tone={notice.tone} title={notice.title}>
          {notice.text}{" "}
          {notice.conflict ? (
            <Button size="compact" variant="secondary" onClick={reloadSaved}>
              Reload saved values
            </Button>
          ) : null}
        </InlineNotice>
      ) : null}
      <ResponsiveDataTable
        title={selected.name}
        description={`${employees} · ${changed}`}
        actions={
          <div className={styles.typeSelect}>
            <Select
              id="permission-user-type"
              label="User Type"
              compact
              clearable={false}
              value={selected.id}
              disabled={busy}
              onChange={chooseType}
              options={userTypes.map((type) => ({
                value: type.id,
                label: type.name,
                description: `${formatFullNumber(type.employeeCount)} ${
                  type.employeeCount === 1 ? "employee" : "employees"
                }`,
              }))}
            />
          </div>
        }
        ariaLabel={`${selected.name} permissions`}
        columns={columns}
        rows={selected.permissions}
        rowKey={(item) => item.key}
        page={1}
        pageCount={1}
        onPageChange={() => undefined}
        loading={resource.updating && !confirmed}
      />
      {canEdit ? (
        <StickyActionBar>
          <p className={`${styles.support} ${styles.barStatus}`} role="status">
            {dirty
              ? `${changes.length} unsaved ${changes.length === 1 ? "change" : "changes"}`
              : "All changes saved"}
          </p>
          <Button
            variant="secondary"
            disabled={!dirty || busy}
            onClick={() => {
              setDrafts({});
              setNotice(null);
            }}
          >
            Discard changes
          </Button>
          <Button disabled={!dirty} loading={busy} onClick={() => setConfirming(true)}>
            Save changes
          </Button>
        </StickyActionBar>
      ) : null}
      <DetailGrid
        title="Mandatory restrictions"
        description="These rules are enforced by the server and cannot be changed here."
        items={config.restrictions.map((item) => ({
          label: item.title,
          value: item.description,
        }))}
      />
      <ConfirmationDialog
        open={confirming}
        title={`Save ${selected.name} permissions?`}
        confirmLabel="Save changes"
        busy={busy}
        onConfirm={() => void save()}
        onClose={() => setConfirming(false)}
      >
        <p className={styles.support}>
          {changes.length === 1 ? "This change applies" : "These changes apply"} to{" "}
          {employees} on their next request.
        </p>
        <ul className={styles.changeList}>
          {changes.map((item) => (
            <li key={item.key}>
              {drafts[item.key] ? "Grant" : "Revoke"}: {item.module} — {item.action}
            </li>
          ))}
        </ul>
      </ConfirmationDialog>
      <UnsavedChangesDialog
        open={pendingType !== null}
        onStay={() => setPendingType(null)}
        onLeave={() => {
          if (pendingType) setSelectedId(pendingType);
          setPendingType(null);
          setDrafts({});
          setNotice(null);
        }}
      />
    </div>
  );
}
