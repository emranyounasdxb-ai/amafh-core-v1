import { useState, type ReactNode } from "react";
import {
  Button,
  ConfirmationDialog,
  DestructiveConfirmationDialog,
  Drawer,
  ExportButton,
  InfoField,
  InfoGrid,
  InlineNotice,
  OverflowMenu,
  RecordActions,
  SectionCard,
  Stack,
  type AppliedFilter,
} from "../../../design-system";
import type { Command } from "../../../app/api/commands";
import { ApiFailure } from "../../../app/api/http";
import { CommandFormDialog } from "../../../app/commands/CommandFormDialog";
import { useSession } from "../../../app/session/useSession";
import { ServerTableSection } from "../../../shared/table/ServerTableSection";
import type {
  ServerColumn,
  ServerTable,
} from "../../../shared/table/serverTable";
import { FinanceToolbar } from "../../finance/live/financeTable";
import type { SettingsAction, SettingsFact } from "./settingsActions";
import styles from "./SettingsPage.module.css";

export function SettingsTable<T extends { id: string }>({
  table,
  tableId,
  ariaLabel,
  columns,
  rowLabel,
  title,
  kind,
  facts,
  actions,
  create,
  filters,
  applied = [],
  onClearFilters,
  emptyTitle,
  emptyDescription,
  loadingTitle,
  detail,
  onSaved,
  extraActions,
  notice,
  onNotice,
}: {
  table: ServerTable<T>;
  tableId: string;
  ariaLabel: string;
  columns: ServerColumn<T>[];
  rowLabel: (row: T) => string;
  title: (row: T) => string;
  kind: string;
  facts: (row: T) => SettingsFact[];
  actions?: (row: T) => SettingsAction[];
  create?: { label: string; command: Command; success: string };
  filters?: ReactNode;
  applied?: AppliedFilter[];
  onClearFilters?: () => void;
  emptyTitle: string;
  emptyDescription: string;
  loadingTitle: string;
  detail?: (row: T) => ReactNode;
  onSaved: () => void;
  extraActions?: ReactNode;
  notice?: string;
  onNotice?: (message: string) => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [running, setRunning] = useState<SettingsAction | null>(null);
  const [ownNotice, setOwnNotice] = useState("");
  const message = notice ?? ownNotice;
  const showNotice = onNotice ?? setOwnNotice;
  const [lastSelected, setLastSelected] = useState<T | null>(null);
  const selected = selectedId
    ? (table.rows.find((row) => row.id === selectedId) ?? lastSelected)
    : null;
  const open = (row: T) => {
    setLastSelected(row);
    setSelectedId(row.id);
  };
  const finish = (text: string) => {
    setRunning(null);
    setSelectedId(null);
    showNotice(text);
    onSaved();
  };
  const withActions: ServerColumn<T>[] = actions
    ? [
        ...columns,
        {
          key: "actions",
          label: "Actions",
          width: 96,
          fixed: true,
          render: (row: T) => {
            const items = actions(row);
            return items.length ? (
              <OverflowMenu
                label={`Actions for ${rowLabel(row)}`}
                items={items.map((item) => ({
                  id: item.id,
                  label: item.label,
                  danger: "confirm" in item && item.confirm.danger,
                  onSelect: () => setRunning(item),
                }))}
              />
            ) : null;
          },
        },
      ]
    : columns;
  const selectedActions = selected && actions ? actions(selected) : [];
  return (
    <div className={styles.panel}>
      {message ? (
        <InlineNotice tone="success" title="Saved">
          {message}
        </InlineNotice>
      ) : null}
      <FinanceToolbar
        label={`${ariaLabel} filters`}
        applied={applied}
        onClearFilters={onClearFilters}
        actions={
          <>
            {table.selection.allowed ? (
              <ExportButton
                size="compact"
                selectedCount={table.selection.selectedCount}
                loading={table.selection.working}
                disabled={!table.selection.selectedCount}
                onClick={() => void table.selection.exportCsv()}
              />
            ) : null}
            {extraActions}
            {create ? (
              <Button
                size="compact"
                data-focus-fallback
                onClick={() =>
                  setRunning({ id: "create", ...create, record: undefined })
                }
              >
                {create.label}
              </Button>
            ) : null}
          </>
        }
      >
        {filters}
      </FinanceToolbar>
      <ServerTableSection
        table={table}
        tableId={tableId}
        ariaLabel={ariaLabel}
        stackOnNarrow={false}
        columns={withActions}
        filtered={applied.length > 0}
        loadingTitle={loadingTitle}
        emptyTitle={emptyTitle}
        emptyDescription={emptyDescription}
        onRowActivate={open}
        rowLabel={rowLabel}
      />
      <Drawer
        open={Boolean(selected)}
        title={selected ? title(selected) : kind}
        description={kind}
        onClose={() => setSelectedId(null)}
        footer={
          selectedActions.length ? (
            <RecordActions>
              {selectedActions.map((item) => (
                <Button
                  key={item.id}
                  variant={
                    "confirm" in item && item.confirm.danger
                      ? "danger"
                      : "secondary"
                  }
                  onClick={() => setRunning(item)}
                >
                  {item.label}
                </Button>
              ))}
            </RecordActions>
          ) : undefined
        }
      >
        {selected ? (
          <div className={styles.drawerBody}>
            <SectionCard title="Details" compact>
              <Facts facts={facts(selected)} />
            </SectionCard>
            {detail?.(selected)}
          </div>
        ) : null}
      </Drawer>
      {running && "command" in running ? (
        <CommandFormDialog
          command={running.command}
          record={running.record}
          onClose={() => setRunning(null)}
          onSaved={() => finish(running.success)}
        />
      ) : null}
      {running && "confirm" in running ? (
        <StateDialog
          action={running}
          onClose={() => setRunning(null)}
          onSaved={finish}
        />
      ) : null}
    </div>
  );
}

export function Facts({ facts }: { facts: SettingsFact[] }) {
  return (
    <InfoGrid>
      {facts.map((fact) => (
        <InfoField
          key={fact.label}
          label={fact.label}
          value={fact.value}
          numeric={fact.numeric}
        />
      ))}
    </InfoGrid>
  );
}

function StateDialog({
  action,
  onClose,
  onSaved,
}: {
  action: Extract<SettingsAction, { confirm: unknown }>;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const { api } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = async () => {
    setBusy(true);
    setError("");
    try {
      await api.request(action.confirm.path, { method: "POST", body: "{}" });
      onSaved(action.success);
    } catch (failure) {
      setError(
        failure instanceof ApiFailure
          ? failure.message
          : "The request could not be completed. Retry safely when the connection returns.",
      );
    } finally {
      setBusy(false);
    }
  };
  const body = (
    <Stack>
      <p>{action.confirm.message}</p>
      {error ? (
        <InlineNotice tone="error" title="Unable to continue">
          {error}
        </InlineNotice>
      ) : null}
    </Stack>
  );
  const Confirm = action.confirm.danger
    ? DestructiveConfirmationDialog
    : ConfirmationDialog;
  return (
    <Confirm
      open
      title={action.confirm.title}
      confirmLabel={action.label}
      busy={busy}
      onClose={onClose}
      onConfirm={() => void run()}
    >
      {body}
    </Confirm>
  );
}
