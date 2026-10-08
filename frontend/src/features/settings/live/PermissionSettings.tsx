import { useEffect, useMemo, useState } from "react";
import {
  Button,
  ConfirmationDialog,
  EmptyState,
  ErrorState,
  InlineNotice,
  LoadingState,
  PermissionDeniedState,
  StatusBadge,
  StickyActionBar,
  Switch,
  UnsavedChangesDialog,
  formatDubaiTimestamp,
  formatFullNumber,
} from "../../../design-system";
import { ApiFailure } from "../../../app/api/http";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import { Info } from "lucide-react";
import {
  permissionCounts,
  savedGrant,
  type PermissionItem,
} from "./permissionPresentation";
import layout from "./PermissionSettings.module.css";
import styles from "./SettingsPage.module.css";

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

type Notice = {
  tone: "success" | "error";
  title: string;
  text: string;
  conflict?: boolean;
};

function changeSummary(
  type: UserType | undefined,
  drafts: Record<string, boolean>,
) {
  if (!type) return [];
  return type.permissions.filter(
    (item) =>
      item.configurable &&
      item.key in drafts &&
      drafts[item.key] !== savedGrant(item),
  );
}

export function PermissionSettings() {
  const { api } = useSession();
  const resource = useResource<PermissionConfiguration>(
    "/permission-configuration",
  );
  const [confirmed, setConfirmed] = useState<PermissionConfiguration | null>(
    null,
  );
  const config = confirmed ?? resource.data;
  const [selectedId, setSelectedId] = useState("");
  const [selectedModule, setSelectedModule] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, boolean>>({});
  const [pendingType, setPendingType] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  const userTypes = useMemo(() => config?.userTypes ?? [], [config]);
  const selected = userTypes.find((type) => type.id === selectedId);
  const changes = changeSummary(selected, drafts);
  const dirty = changes.length > 0;
  const canEdit = Boolean(
    config?.canManage && selected && selected.name !== "Owner",
  );

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
  if (userTypes.length === 0)
    return (
      <EmptyState
        title="No User Types"
        description="No approved User Types are available."
      />
    );

  const chooseType = (id: string) => {
    if (id === selected?.id || busy) return;
    if (dirty) {
      setPendingType(id);
      return;
    }
    setSelectedId(id);
    setSelectedModule(null);
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
    if (!selected || !canEdit || !dirty) return;
    setBusy(true);
    setNotice(null);
    try {
      const result = await api.request<PermissionConfiguration>(
        `/permission-configuration/${selected.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            revision: selected.revision,
            grants: Object.fromEntries(
              changes.map((item) => [item.key, drafts[item.key]]),
            ),
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
        conflict:
          failure instanceof ApiFailure &&
          failure.code === "PERMISSION_CONFLICT",
      });
    } finally {
      setBusy(false);
    }
  };

  const accessCell = (item: PermissionItem) => {
    if (item.state === "fixed")
      return <StatusBadge tone="brand">Always granted</StatusBadge>;
    if (item.state === "unavailable")
      return <StatusBadge>Not permitted</StatusBadge>;
    const value = current(item);
    const changed = value !== savedGrant(item);
    const badge = changed ? (
      <StatusBadge tone="warning">
        {value ? "Will be granted" : "Will be revoked"}
      </StatusBadge>
    ) : (
      <StatusBadge tone={value ? "success" : "neutral"}>
        {value ? "Granted" : "Not granted"}
      </StatusBadge>
    );
    if (!canEdit || !item.configurable) return badge;
    return (
      <Switch
        id={`permission-${item.key}`}
        checked={value}
        disabled={busy}
        onChange={(next) => {
          setNotice((previous) =>
            previous?.tone === "success" ? null : previous,
          );
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

  const counts = permissionCounts(selected?.permissions ?? [], drafts);
  const modules = [
    ...new Set(selected?.permissions.map((item) => item.module) ?? []),
  ];
  const actions =
    selected?.permissions.filter((item) => item.module === selectedModule) ??
    [];
  const scopes = [
    ...new Set(
      actions.map((item) => item.dataScope).filter((scope) => scope !== null),
    ),
  ];
  // Repeated catalogue explanations belong to the module; specific restrictions stay by the action.
  const reasons = new Map<string, number>();
  for (const item of actions) {
    if (item.reason && !(selected?.name === "Owner" && item.state === "fixed"))
      reasons.set(item.reason, (reasons.get(item.reason) ?? 0) + 1);
  }
  const employees = selected
    ? `${formatFullNumber(selected.employeeCount)} ${
        selected.employeeCount === 1 ? "employee" : "employees"
      }`
    : "";
  const changed = selected?.lastChangedAt
    ? `Last changed ${formatDubaiTimestamp(selected.lastChangedAt)} by ${selected.lastChangedBy ?? "Unavailable"}`
    : "Not changed since setup";

  return (
    <div className={`${styles.panel} ${layout.page}`}>
      <details className={layout.rules}>
        <summary>
          <Info size={14} aria-hidden="true" /> Permission rules
        </summary>
        <div className={layout.rulesBody}>
          <p className={styles.support}>
            These rules are enforced by the server and cannot be changed here.
          </p>
          <dl>
            {config.restrictions.map((item) => (
              <div key={item.title}>
                <dt>{item.title}</dt>
                <dd>{item.description}</dd>
              </div>
            ))}
          </dl>
        </div>
      </details>
      {!config.canManage ? (
        <InlineNotice tone="info" title="View only">
          Only the Owner can change User Type permissions.
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
      <div className={layout.cards}>
        <section
          className={`${layout.card} ${layout.types}`}
          aria-labelledby="user-types-heading"
        >
          <h2 id="user-types-heading">User Types</h2>
          <div className={layout.choices} aria-label="User Types">
            {userTypes.map((type) => (
              <button
                key={type.id}
                type="button"
                aria-pressed={selected?.id === type.id}
                disabled={busy}
                onClick={() => chooseType(type.id)}
                className={layout.choice}
              >
                {type.name}
              </button>
            ))}
          </div>
        </section>
        <div
          className={`${layout.stage} ${selected ? layout.modulesOpen : ""}`}
        >
          {selected ? (
            <section className={layout.card} aria-labelledby="modules-heading">
              <h2 id="modules-heading">Modules</h2>
              <p className={layout.selectedType}>{selected.name}</p>
              <dl
                className={layout.counts}
                aria-label={`${selected.name} permission counts`}
              >
                <div>
                  <dt>Total</dt>
                  <dd>{formatFullNumber(counts.total)}</dd>
                </div>
                <div>
                  <dt>Allowed</dt>
                  <dd>{formatFullNumber(counts.allowed)}</dd>
                </div>
                <div>
                  <dt>Disabled</dt>
                  <dd>{formatFullNumber(counts.disabled)}</dd>
                </div>
                <div>
                  <dt>Not permitted</dt>
                  <dd>{formatFullNumber(counts.notPermitted)}</dd>
                </div>
              </dl>
              <p className={styles.support}>
                Listing a module does not grant access.
                {dirty ? " Counts include unsaved changes." : ""}
              </p>
              <div className={layout.choices} aria-label="Modules">
                {modules.map((module) => (
                  <button
                    key={module}
                    type="button"
                    aria-pressed={selectedModule === module}
                    disabled={busy}
                    onClick={() => setSelectedModule(module)}
                    className={layout.choice}
                  >
                    {module}
                  </button>
                ))}
              </div>
              <p className={styles.support}>
                {employees} · {changed}
              </p>
            </section>
          ) : null}
        </div>
        <div
          className={`${layout.stage} ${selectedModule && selected ? layout.permissionsOpen : ""}`}
        >
          {selectedModule && selected ? (
            <section
              key={`${selected.id}-${selectedModule}`}
              className={layout.card}
              aria-labelledby="permissions-heading"
            >
              <h2 id="permissions-heading">{selectedModule} permissions</h2>
              {selected.name === "Owner" ? (
                <p className={layout.explanation}>
                  Owner permissions are fixed. Business restrictions still
                  apply.
                </p>
              ) : (
                <p className={styles.support}>
                  Fixed access cannot be changed. Only configurable actions have
                  switches.
                </p>
              )}
              <div className={layout.scope}>
                <strong>Record scope</strong>
                <p>
                  {scopes.length
                    ? scopes.join(" · ")
                    : "No permitted actions in this module."}
                </p>
                {scopes.length > 1 ? (
                  <p>Scope is shown beside each applicable action.</p>
                ) : null}
              </div>
              <ul className={layout.actions}>
                {actions.map((item) => (
                  <li key={item.key} className={layout.action}>
                    <div className={layout.actionText}>
                      <span>{item.action}</span>
                      {scopes.length > 1 && item.dataScope ? (
                        <p className={styles.support}>
                          Scope: {item.dataScope}
                        </p>
                      ) : null}
                      {item.reason && reasons.get(item.reason) === 1 ? (
                        <p className={styles.support}>{item.reason}</p>
                      ) : null}
                    </div>
                    <div className={layout.access}>{accessCell(item)}</div>
                  </li>
                ))}
              </ul>
              {[...reasons].some(([, count]) => count > 1) ? (
                <div className={layout.sharedReasons}>
                  {[...reasons]
                    .filter(([, count]) => count > 1)
                    .map(([reason]) => (
                      <p key={reason} className={styles.support}>
                        {reason}
                      </p>
                    ))}
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
      </div>
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
          <Button
            disabled={!dirty}
            loading={busy}
            onClick={() => setConfirming(true)}
          >
            Save changes
          </Button>
        </StickyActionBar>
      ) : null}
      <ConfirmationDialog
        open={confirming}
        title={`Save ${selected?.name ?? "User Type"} permissions?`}
        confirmLabel="Save changes"
        busy={busy}
        onConfirm={() => void save()}
        onClose={() => setConfirming(false)}
      >
        <p className={styles.support}>
          {changes.length === 1 ? "This change applies" : "These changes apply"}{" "}
          to {employees} on their next request.
        </p>
        <ul className={styles.changeList}>
          {changes.map((item) => (
            <li key={item.key}>
              {drafts[item.key] ? "Grant" : "Revoke"}: {item.module} —{" "}
              {item.action}
            </li>
          ))}
        </ul>
      </ConfirmationDialog>
      <UnsavedChangesDialog
        open={pendingType !== null}
        busy={busy}
        onStay={() => setPendingType(null)}
        onLeave={() => {
          if (pendingType) {
            setSelectedId(pendingType);
            setSelectedModule(null);
          }
          setPendingType(null);
          setDrafts({});
          setNotice(null);
        }}
      />
    </div>
  );
}
