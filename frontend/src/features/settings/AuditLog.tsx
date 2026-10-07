import { useState } from "react";
import {
  AppliedFilterSummary,
  Button,
  CompactDateTime,
  DateTimePicker,
  DropdownSelect,
  EmptyValue,
  ErrorState,
  ExportButton,
  FeedbackState,
  FilterButton,
  FilterDrawer,
  FilterPopover,
  FilterToolbar,
  FilterToolbarItem,
  FormField,
  InlineNotice,
  SectionHeader,
  TextInput,
  TruncatedText,
  formatDubaiTimestamp,
  type AppliedFilter,
  type DateOnly,
  type ExportOptionSpec,
} from "../../design-system";
import { choices } from "../../app/api/choices";
import { download } from "../../app/api/download";
import type { ApiClient } from "../../app/api/http";
import type { DataRecord } from "../../app/api/models";
import { useResource } from "../../app/api/useResource";
import { readableLabel } from "../../app/presentation/labels";
import { useSession } from "../../app/session/useSession";
import { ServerTableSection } from "../../shared/table/ServerTableSection";
import { isOffline, useServerTable, type ServerColumn } from "../../shared/table/serverTable";
import { personText, useEmployeeLabels } from "../finance/live/financeLabels";
import { AuditEventDrawer } from "./AuditEventDrawer";
import {
  AUDIT_EMPTY,
  auditQuery,
  eventLabel,
  moduleLabel,
  rangeInvalid,
  recordTypeLabel,
  type AuditEvent,
  type AuditFilters,
} from "./auditPresentation";
import styles from "./AuditLog.module.css";

type ExportFormat = "csv" | "pdf";
type PanelValues = Omit<AuditFilters, "actorId">;

const loadChoices = (api: ApiClient, path: string, signal: AbortSignal) =>
  choices<DataRecord>(api, path, signal);

const pick = (value: string | string[]) =>
  Array.isArray(value) ? (value[0] ?? "") : value;

function Text({ value }: { value: string }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

function panelOf(filters: AuditFilters): PanelValues {
  const { actorId: _actorId, ...panel } = filters;
  void _actorId;
  return panel;
}

function stamp(date: string, time: string, end: boolean) {
  return formatDubaiTimestamp(
    `${date}T${time || (end ? "23:59" : "00:00")}:00+04:00`,
  );
}

export function AuditLog() {
  const { api } = useSession();
  const [filters, setFilters] = useState<AuditFilters>(AUDIT_EMPTY);
  const [selected, setSelected] = useState<AuditEvent | null>(null);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [failure, setFailure] = useState<{ format: ExportFormat; message: string } | null>(
    null,
  );
  const [drawerOpen, setDrawerOpen] = useState(false);
  const appliedPanel = panelOf(filters);
  const appliedKey = JSON.stringify(appliedPanel);
  const [draftState, setDraftState] = useState({ key: appliedKey, values: appliedPanel });
  const draft = draftState.key === appliedKey ? draftState.values : appliedPanel;
  const setDraft = (patch: Partial<PanelValues>) =>
    setDraftState({ key: appliedKey, values: { ...draft, ...patch } });
  const draftInvalid = rangeInvalid({ ...filters, ...draft });

  const query = auditQuery(filters);
  const table = useServerTable<AuditEvent>("settings-audit", "/audit-events", query, 0);
  const people = useEmployeeLabels(table.rows.map((row) => row.actorEmployeeId));
  const employees = useResource<DataRecord[]>("/employee-labels", 0, loadChoices, "choices");
  const actorOptions = (employees.data ?? []).flatMap((row) => {
    const label = readableLabel(row.fullName, "");
    if (!label) return [];
    const code = readableLabel(row.companyEmployeeCode || row.employeeCode, "");
    return [{ value: String(row.id), label, ...(code ? { description: code } : {}) }];
  });

  const apply = (panel: PanelValues) => setFilters({ ...filters, ...panel });
  const clearPanel = () => {
    const cleared = panelOf(AUDIT_EMPTY);
    setDraftState({ key: appliedKey, values: cleared });
    apply(cleared);
  };

  const runExport = async (format: ExportFormat) => {
    setExporting(format);
    setFailure(null);
    try {
      await download(api, `/audit-events/exports/${format}${query ? `?${query}` : ""}`);
    } catch (cause) {
      setFailure({
        format,
        message: cause instanceof Error ? cause.message : "The export could not be prepared.",
      });
    } finally {
      setExporting(null);
    }
  };

  const actorName = actorOptions.find((option) => option.value === filters.actorId)?.label;
  const chips: AppliedFilter[] = [
    filters.actorId && {
      id: "actor",
      label: "Actor",
      field: "Actor",
      value: actorName || personText(people(filters.actorId, "Team member")),
      onRemove: () => setFilters({ ...filters, actorId: "" }),
    },
    filters.module.trim() && {
      id: "module",
      label: "Module",
      field: "Module",
      value: moduleLabel(filters.module.trim()),
      onRemove: () => setFilters({ ...filters, module: "" }),
    },
    filters.action.trim() && {
      id: "action",
      label: "Event",
      field: "Event",
      value: eventLabel(filters.action.trim()),
      onRemove: () => setFilters({ ...filters, action: "" }),
    },
    filters.entityId.trim() && {
      id: "entity",
      label: "Record reference",
      field: "Record reference",
      value: "Applied",
      onRemove: () => setFilters({ ...filters, entityId: "" }),
    },
    filters.fromDate && {
      id: "from",
      label: "From",
      field: "From",
      value: stamp(filters.fromDate, filters.fromTime, false),
      onRemove: () => setFilters({ ...filters, fromDate: "", fromTime: "" }),
    },
    filters.toDate && {
      id: "to",
      label: "To",
      field: "To",
      value: stamp(filters.toDate, filters.toTime, true),
      onRemove: () => setFilters({ ...filters, toDate: "", toTime: "" }),
    },
  ].filter(Boolean) as AppliedFilter[];
  const panelCount = chips.filter((chip) => chip.id !== "actor").length;

  const panel = (
    <div className={styles.filterPanel}>
      <FormField label="Module" htmlFor="audit-module" hint="Exact module code, for example cases">
        <TextInput
          id="audit-module"
          compact
          placeholder="For example cases"
          value={draft.module}
          onChange={(event) => setDraft({ module: event.target.value })}
        />
      </FormField>
      <FormField label="Event" htmlFor="audit-action" hint="Exact event code, for example case.created">
        <TextInput
          id="audit-action"
          compact
          placeholder="For example case.created"
          value={draft.action}
          onChange={(event) => setDraft({ action: event.target.value })}
        />
      </FormField>
      <FormField label="Record reference" htmlFor="audit-entity" span>
        <TextInput
          id="audit-entity"
          compact
          value={draft.entityId}
          onChange={(event) => setDraft({ entityId: event.target.value })}
        />
      </FormField>
      <FormField label="From (Dubai)" htmlFor="audit-from" span>
        <DateTimePicker
          id="audit-from"
          compact
          invalid={draftInvalid}
          value={{ date: draft.fromDate as DateOnly | "", time: draft.fromTime }}
          onChange={(next) => setDraft({ fromDate: next.date, fromTime: next.time })}
        />
      </FormField>
      <FormField
        label="To (Dubai)"
        htmlFor="audit-to"
        span
        error={draftInvalid ? "The start must not follow the end." : undefined}
      >
        <DateTimePicker
          id="audit-to"
          compact
          invalid={draftInvalid}
          value={{ date: draft.toDate as DateOnly | "", time: draft.toTime }}
          onChange={(next) => setDraft({ toDate: next.date, toTime: next.time })}
        />
      </FormField>
    </div>
  );

  const columns: ServerColumn<AuditEvent>[] = [
    {
      key: "occurredAt",
      label: "Occurred (Dubai)",
      width: 150,
      kind: "datetime",
      render: (row) => <CompactDateTime value={row.occurredAt} />,
    },
    {
      key: "action",
      label: "Event",
      width: 220,
      render: (row) => <Text value={eventLabel(row.action)} />,
    },
    {
      key: "module",
      label: "Module",
      width: 130,
      render: (row) => <Text value={moduleLabel(row.module)} />,
    },
    {
      key: "entityType",
      label: "Record type",
      width: 170,
      render: (row) => <Text value={recordTypeLabel(row.entityType)} />,
    },
    {
      key: "actorEmployeeId",
      label: "Actor",
      width: 220,
      render: (row) =>
        row.actorEmployeeId ? (
          <Text value={personText(people(row.actorEmployeeId, "Team member"))} />
        ) : (
          <EmptyValue />
        ),
    },
    {
      key: "details",
      label: "Details",
      width: 120,
      render: (row) => (
        <Button
          size="compact"
          variant="ghost"
          aria-label={`View details for ${eventLabel(row.action)}, ${formatDubaiTimestamp(row.occurredAt)}`}
          onClick={() => setSelected(row)}
        >
          View details
        </Button>
      ),
    },
  ];

  const blocked = table.resource.loading || Boolean(table.resource.error) || !table.resource.data;
  const exportOptions: ExportOptionSpec[] = [
    {
      id: "csv",
      format: "csv",
      scope: "filtered",
      label: "CSV",
      description: "All events for the applied filters",
      disabled: blocked,
    },
    {
      id: "pdf",
      format: "pdf",
      scope: "filtered",
      label: "PDF",
      description: "All events for the applied filters",
      disabled: blocked,
    },
    ...(table.selection.allowed
      ? [
          {
            id: "selected",
            format: "csv" as const,
            scope: "selected" as const,
            label: `Selected rows CSV (${table.selection.selectedCount})`,
            description: "Only the events you selected",
            disabled: blocked || !table.selection.selectedCount,
          },
        ]
      : []),
  ];

  return (
    <div className={styles.panel}>
      <SectionHeader
        title="Audit log"
        description="Read-only history of retained system events. Times are shown in Dubai time."
      />
      <div className="ds-search-filter">
        <FilterToolbar label="Audit filters" className={styles.toolbar}>
          <FilterToolbarItem
            label="Actor"
            htmlFor="audit-actor"
            className="ds-filter-toolbar__item--quick"
          >
            <DropdownSelect
              id="audit-actor"
              label="Actor"
              compact
              clearable
              searchable
              placeholder="All actors"
              value={filters.actorId}
              loading={employees.loading && !employees.data}
              options={actorOptions}
              onChange={(value) => setFilters({ ...filters, actorId: pick(value) })}
            />
          </FilterToolbarItem>
          <FilterToolbarItem
            labeled={false}
            className="ds-filter-toolbar__item--filters ds-cq-wide"
          >
            <FilterPopover
              count={panelCount}
              onApply={draftInvalid ? undefined : () => apply(draft)}
              onReset={clearPanel}
            >
              {panel}
            </FilterPopover>
          </FilterToolbarItem>
          <FilterToolbarItem
            labeled={false}
            className="ds-filter-toolbar__item--filters ds-cq-narrow"
          >
            <FilterButton
              size="compact"
              count={panelCount}
              onClick={() => setDrawerOpen(true)}
            />
          </FilterToolbarItem>
          <FilterToolbarItem
            labeled={false}
            className="ds-filter-toolbar__item--page-actions"
          >
            <div className="ds-filter-toolbar__actions">
              <ExportButton
                size="compact"
                label="Export"
                loading={Boolean(exporting) || table.selection.working}
                disabled={blocked}
                options={exportOptions}
                onSelect={(option) =>
                  option.scope === "selected"
                    ? void table.selection.exportCsv()
                    : void runExport(option.format)
                }
              />
            </div>
          </FilterToolbarItem>
        </FilterToolbar>
        <AppliedFilterSummary
          items={chips}
          onClear={
            chips.length
              ? () => {
                  setDraftState({ key: appliedKey, values: panelOf(AUDIT_EMPTY) });
                  setFilters(AUDIT_EMPTY);
                }
              : undefined
          }
        />
        <FilterDrawer
          open={drawerOpen}
          title="Filters"
          onClose={() => setDrawerOpen(false)}
          onReset={clearPanel}
          onApply={
            draftInvalid
              ? undefined
              : () => {
                  apply(draft);
                  setDrawerOpen(false);
                }
          }
        >
          {panel}
        </FilterDrawer>
      </div>
      {failure ? (
        <InlineNotice tone="error" title="Export failed">
          <span className={styles.noticeBody}>
            {failure.message}
            <Button
              size="compact"
              variant="secondary"
              onClick={() => void runExport(failure.format)}
            >
              Retry {failure.format.toUpperCase()}
            </Button>
          </span>
        </InlineNotice>
      ) : null}
      {table.resource.error && !table.resource.denied ? (
        isOffline(table.resource.error) ||
        /failed to fetch|network/i.test(table.resource.error) ? (
          <FeedbackState
            kind="offline"
            title="Offline"
            description="Audit events could not be reached. Your filters are kept."
            action={
              <Button variant="secondary" size="compact" onClick={table.resource.reload}>
                Retry
              </Button>
            }
          />
        ) : (
          <ErrorState
            title="Audit events unavailable"
            description={table.resource.error}
            retry={table.resource.reload}
          />
        )
      ) : (
        <ServerTableSection
          table={table}
          tableId="settings-audit"
          ariaLabel="Audit events"
          stackOnNarrow={false}
          columns={columns}
          filtered={chips.length > 0}
          loadingTitle="Loading audit events"
          emptyTitle="No audit events"
          emptyDescription="Retained audit events appear here."
          noResultsDescription="No audit events match the applied filters."
          rowLabel={(row) => `${eventLabel(row.action)}, ${formatDubaiTimestamp(row.occurredAt)}`}
        />
      )}
      <AuditEventDrawer
        event={selected}
        actorLabel={
          selected?.actorEmployeeId
            ? personText(people(selected.actorEmployeeId, "Team member"))
            : undefined
        }
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
