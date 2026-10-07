import { useRef, useState } from "react";
import {
  Button,
  CompactDate,
  CompactDateTime,
  ConfirmationDialog,
  DestructiveConfirmationDialog,
  Drawer,
  ExportButton,
  InfoField,
  InfoGrid,
  InlineNotice,
  MonetaryAmount,
  OverflowMenu,
  RecordActions,
  SectionCard,
  Stack,
  StatusBadge,
  formatDateOnly,
  type AppliedFilter,
  type MenuItem,
} from "../../../design-system";
import { canManageFinance } from "../../../access";
import { ApiFailure } from "../../../app/api/http";
import type { NamedRecord, Page } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { CommandFormDialog } from "../../../app/commands/CommandFormDialog";
import { useSession } from "../../../app/session/useSession";
import { PfSlab, Points, SelectFilter, Text } from "./financeCells";
import {
  createRuleCommand,
  replaceRuleCommand,
  ruleStatePath,
} from "./financeCommands";
import { useCatalogLabels } from "./financeLabels";
import type { FinancialRuleRecord } from "./financeRecords";
import { useFocusRecovery } from "../../../shared/focus/useFocusRecovery";
import { ServerTableSection } from "../../../shared/table/ServerTableSection";
import {
  filterQuery,
  useServerTable,
  type ServerColumn,
} from "../../../shared/table/serverTable";
import { FinanceToolbar } from "./financeTable";
import styles from "./FinancePage.module.css";
import { recordImageSrc, type ImageKind } from "../../../app/api/recordImages";
import { RecordImage } from "../../../shared/media/RecordImage";

const TABLE_ID = "finance-rules";
const STATUSES = [
  { value: "true", label: "Active" },
  { value: "false", label: "Inactive or superseded" },
];
const EMPTY = { active: "", bankId: "", productTypeId: "" };

type RuleAction =
  | { kind: "create" }
  | { kind: "replace" | "activate" | "deactivate"; rule: FinancialRuleRecord };

function canReplace(rule: FinancialRuleRecord) {
  return rule.active && !rule.superseded_by_rule_id;
}

function canActivate(rule: FinancialRuleRecord) {
  return !rule.active && !rule.superseded_by_rule_id;
}

export function RulesView({
  refresh,
  onSaved,
}: {
  refresh: number;
  onSaved: (message: string) => void;
}) {
  const { session } = useSession();
  const manage = session ? canManageFinance(session) : false;
  const [filters, setFilters] = useState(EMPTY);
  const [selected, setSelected] = useState<FinancialRuleRecord | null>(null);
  const [action, setAction] = useState<RuleAction | null>(null);
  const table = useServerTable<FinancialRuleRecord>(
    TABLE_ID,
    "/finance/rules",
    filterQuery(filters),
    refresh,
  );
  const banks = useResource<Page<NamedRecord>>(
    "/catalog/banks?page=1&pageSize=100",
  );
  const products = useResource<Page<NamedRecord>>(
    "/catalog/product-types?page=1&pageSize=100",
  );
  const catalog = useCatalogLabels(
    [...table.rows, ...(selected ? [selected] : [])].flatMap((rule) => [
      { kind: "banks" as const, id: rule.bank_id },
      { kind: "product-types" as const, id: rule.product_type_id },
      { kind: "product-variants" as const, id: rule.product_variant_id },
    ]),
  );
  const optionsOf = (page: Page<NamedRecord> | null, kind: ImageKind) =>
    (page?.items ?? []).map((item) => ({
      value: item.id,
      label: item.name,
      leading: recordImageSrc(kind, item) ? (
        <RecordImage src={recordImageSrc(kind, item)} label={item.name} />
      ) : undefined,
    }));
  const set = (patch: Partial<typeof EMPTY>) =>
    setFilters((current) => ({ ...current, ...patch }));
  const applied = [
    filters.active && {
      id: "status",
      label: "Status",
      field: "Status",
      value: filters.active === "true" ? "Active" : "Inactive or superseded",
      onRemove: () => set({ active: "" }),
    },
    filters.bankId && {
      id: "bank",
      label: "Bank",
      field: "Bank",
      value:
        banks.data?.items.find((item) => item.id === filters.bankId)?.name ||
        "Selected bank",
      onRemove: () => set({ bankId: "" }),
    },
    filters.productTypeId && {
      id: "product",
      label: "Product",
      field: "Product",
      value:
        products.data?.items.find((item) => item.id === filters.productTypeId)
          ?.name || "Selected product",
      onRemove: () => set({ productTypeId: "" }),
    },
  ].filter(Boolean) as AppliedFilter[];

  const ruleName = (rule: FinancialRuleRecord) =>
    [catalog(rule.bank_id), catalog(rule.product_type_id)]
      .filter(Boolean)
      .join(" · ") || "Financial rule";
  const ruleRowName = (rule: FinancialRuleRecord) =>
    `${ruleName(rule)} · effective ${formatDateOnly(rule.effective_date)}`;
  const menu = (rule: FinancialRuleRecord): MenuItem[] => [
    ...(canReplace(rule)
      ? [
          {
            id: "replace",
            label: "Replace rule",
            onSelect: () => setAction({ kind: "replace", rule }),
          },
        ]
      : []),
    ...(canActivate(rule)
      ? [
          {
            id: "activate",
            label: "Activate rule",
            onSelect: () => setAction({ kind: "activate", rule }),
          },
        ]
      : []),
    ...(rule.active
      ? [
          {
            id: "deactivate",
            label: "Deactivate rule",
            danger: true,
            onSelect: () => setAction({ kind: "deactivate", rule }),
          },
        ]
      : []),
  ];

  const columns: ServerColumn<FinancialRuleRecord>[] = [
    {
      key: "bank_id",
      label: "Bank",
      width: 160,
      render: (row) => <Text value={catalog(row.bank_id)} />,
    },
    {
      key: "product_type_id",
      label: "Product",
      width: 150,
      render: (row) => <Text value={catalog(row.product_type_id)} />,
    },
    {
      key: "variant",
      label: "CC variant / PF slab",
      width: 200,
      kind: "mixed",
      render: (row) =>
        row.product_variant_id ? (
          <Text value={catalog(row.product_variant_id)} />
        ) : (
          <PfSlab min={row.pf_amount_min} max={row.pf_amount_max} />
        ),
    },
    {
      key: "cc_points",
      label: "CC points",
      width: 110,
      kind: "number",
      render: (row) => <Points value={row.cc_points} />,
    },
    {
      key: "commission_aed",
      label: "Commission",
      width: 120,
      kind: "money",
      render: (row) => (
        <MonetaryAmount compact={false} value={row.commission_aed} />
      ),
    },
    {
      key: "effective_date",
      label: "Effective",
      width: 120,
      kind: "date",
      render: (row) => <CompactDate value={row.effective_date} />,
    },
    {
      key: "active",
      label: "Status",
      width: 110,
      render: (row) => <RuleStatus rule={row} />,
    },
    ...(manage
      ? [
          {
            key: "actions",
            label: "Actions",
            width: 96,
            fixed: true,
            render: (row: FinancialRuleRecord) => {
              const items = menu(row);
              return items.length ? (
                <OverflowMenu
                  label={`Actions for ${ruleRowName(row)}`}
                  items={items}
                />
              ) : null;
            },
          },
        ]
      : []),
  ];

  const panelRef = useRef<HTMLDivElement>(null);
  const focusRuleId = useRef<string | null>(null);
  const armFocusRecovery = useFocusRecovery(table.resource.data, () => {
    const panel = panelRef.current;
    const rule = table.rows.find((row) => row.id === focusRuleId.current);
    const label = rule ? `Open ${ruleRowName(rule)}` : null;
    const row = [
      ...(panel?.querySelectorAll<HTMLElement>("tr[tabindex]") ?? []),
    ].find((node) => label && node.getAttribute("aria-label") === label);
    return row ?? panel?.querySelector<HTMLElement>("[data-focus-fallback]");
  });

  const saved = (message: string) => {
    focusRuleId.current =
      action && action.kind !== "create" ? action.rule.id : null;
    setAction(null);
    setSelected(null);
    onSaved(message);
    armFocusRecovery();
  };

  return (
    <div className={styles.panel} ref={panelRef}>
      <FinanceToolbar
        label="Financial rule filters"
        applied={applied}
        onClearFilters={() => setFilters(EMPTY)}
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
            {manage ? (
              <Button
                size="compact"
                data-focus-fallback
                onClick={() => setAction({ kind: "create" })}
              >
                Add Financial Rule
              </Button>
            ) : null}
          </>
        }
      >
        <SelectFilter
          id="finance-rule-status"
          label="Status"
          placeholder="All statuses"
          value={filters.active}
          options={STATUSES}
          onChange={(active) => set({ active })}
        />
        <SelectFilter
          id="finance-rule-bank"
          label="Bank"
          placeholder="All banks"
          value={filters.bankId}
          options={optionsOf(banks.data, "banks")}
          loading={banks.loading}
          onChange={(bankId) => set({ bankId })}
        />
        <SelectFilter
          id="finance-rule-product"
          label="Product"
          placeholder="All products"
          value={filters.productTypeId}
          options={optionsOf(products.data, "product-types")}
          loading={products.loading}
          onChange={(productTypeId) => set({ productTypeId })}
        />
      </FinanceToolbar>
      <ServerTableSection
        table={table}
        tableId={TABLE_ID}
        ariaLabel="Financial rules"
        stackOnNarrow={false}
        columns={columns}
        filtered={applied.length > 0}
        loadingTitle="Loading financial rules"
        emptyTitle="No financial rules"
        emptyDescription="Financial rules define CC points, PF slabs, and commission."
        onRowActivate={setSelected}
        rowLabel={ruleRowName}
      />
      <Drawer
        open={Boolean(selected)}
        title={selected ? ruleName(selected) : "Financial rule"}
        description="Financial rule"
        onClose={() => setSelected(null)}
        footer={
          selected && manage && menu(selected).length ? (
            <RecordActions>
              {canReplace(selected) ? (
                <Button
                  variant="secondary"
                  onClick={() => setAction({ kind: "replace", rule: selected })}
                >
                  Replace rule
                </Button>
              ) : null}
              {canActivate(selected) ? (
                <Button
                  onClick={() => setAction({ kind: "activate", rule: selected })}
                >
                  Activate rule
                </Button>
              ) : null}
              {selected.active ? (
                <Button
                  variant="danger"
                  onClick={() =>
                    setAction({ kind: "deactivate", rule: selected })
                  }
                >
                  Deactivate rule
                </Button>
              ) : null}
            </RecordActions>
          ) : undefined
        }
      >
        {selected ? (
          <SectionCard title="Rule" compact>
            <RuleFacts
              rule={selected}
              catalog={catalog}
              successor={table.rows.find(
                (row) => row.id === selected.superseded_by_rule_id,
              )}
            />
          </SectionCard>
        ) : null}
      </Drawer>
      {action?.kind === "create" ? (
        <CommandFormDialog
          command={createRuleCommand()}
          onClose={() => setAction(null)}
          onSaved={() => saved("Financial rule added.")}
        />
      ) : null}
      {action?.kind === "replace" ? (
        <CommandFormDialog
          command={replaceRuleCommand(action.rule.id, {
            description:
              "The current rule is deactivated and superseded by the replacement. The replacement keeps the same bank, product, and variant and needs a later effective date.",
            facts: [
              { label: "Bank", value: catalog(action.rule.bank_id) },
              { label: "Product", value: catalog(action.rule.product_type_id) },
              {
                label: "Current effective date",
                value: formatDateOnly(action.rule.effective_date),
              },
            ],
          })}
          record={action.rule}
          onClose={() => setAction(null)}
          onSaved={() => saved("Financial rule replaced.")}
        />
      ) : null}
      {action?.kind === "activate" || action?.kind === "deactivate" ? (
        <RuleStateDialog
          rule={action.rule}
          catalog={catalog}
          onClose={() => setAction(null)}
          onSaved={saved}
        />
      ) : null}
    </div>
  );
}

function RuleStatus({ rule }: { rule: FinancialRuleRecord }) {
  if (rule.active) return <StatusBadge tone="success">Active</StatusBadge>;
  return rule.superseded_by_rule_id ? (
    <StatusBadge tone="info">Superseded</StatusBadge>
  ) : (
    <StatusBadge tone="neutral">Inactive</StatusBadge>
  );
}

function replacementText(
  rule: FinancialRuleRecord,
  successor: FinancialRuleRecord | undefined,
) {
  if (!rule.superseded_by_rule_id) return "None";
  return successor
    ? `Replacement effective ${formatDateOnly(successor.effective_date)}`
    : "Replaced by a later rule";
}

function RuleFacts({
  rule,
  catalog,
  successor,
}: {
  rule: FinancialRuleRecord;
  catalog: (id: string | null | undefined) => string;
  successor?: FinancialRuleRecord;
}) {
  return (
    <InfoGrid>
      <InfoField label="Bank" value={<Text value={catalog(rule.bank_id)} />} />
      <InfoField label="Product" value={<Text value={catalog(rule.product_type_id)} />} />
      <InfoField
        label="CC variant / PF slab"
        value={
          rule.product_variant_id ? (
            <Text value={catalog(rule.product_variant_id)} />
          ) : (
            <PfSlab min={rule.pf_amount_min} max={rule.pf_amount_max} />
          )
        }
      />
      <InfoField label="CC points" numeric value={<Points value={rule.cc_points} />} />
      <InfoField label="Commission" value={<MonetaryAmount compact={false} value={rule.commission_aed} align="start" />} />
      <InfoField label="Effective" value={<CompactDate value={rule.effective_date} />} />
      <InfoField label="Status" value={<RuleStatus rule={rule} />} />
      <InfoField
        label="Superseded by"
        value={<Text value={replacementText(rule, successor)} />}
      />
      <InfoField label="Created" value={<CompactDateTime value={rule.created_at} />} />
    </InfoGrid>
  );
}

function RuleStateDialog({
  rule,
  catalog,
  onClose,
  onSaved,
}: {
  rule: FinancialRuleRecord;
  catalog: (id: string | null | undefined) => string;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const { api } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const deactivating = rule.active;
  const run = async () => {
    setBusy(true);
    setError("");
    try {
      await api.request(ruleStatePath(rule.id, rule.active), {
        method: "POST",
        body: "{}",
      });
      onSaved(
        deactivating ? "Financial rule deactivated." : "Financial rule activated.",
      );
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
      <RuleFacts rule={rule} catalog={catalog} />
      <p>
        {deactivating
          ? "This rule stops being active. The rule record is retained."
          : "This rule becomes active from its effective date. Activation is rejected when another active rule conflicts."}
      </p>
      {error ? (
        <InlineNotice tone="error" title="Unable to continue">
          {error}
        </InlineNotice>
      ) : null}
    </Stack>
  );
  return deactivating ? (
    <DestructiveConfirmationDialog
      open
      title="Deactivate Financial Rule"
      confirmLabel="Deactivate rule"
      busy={busy}
      onClose={onClose}
      onConfirm={() => void run()}
    >
      {body}
    </DestructiveConfirmationDialog>
  ) : (
    <ConfirmationDialog
      open
      title="Activate Financial Rule"
      confirmLabel="Activate rule"
      busy={busy}
      onClose={onClose}
      onConfirm={() => void run()}
    >
      {body}
    </ConfirmationDialog>
  );
}

export function FinancialRulesPanel() {
  const [refresh, setRefresh] = useState(0);
  const [notice, setNotice] = useState("");
  return (
    <div className={styles.page}>
      {notice ? (
        <InlineNotice tone="success" title="Saved">
          {notice}
        </InlineNotice>
      ) : null}
      <RulesView
        refresh={refresh}
        onSaved={(message) => {
          setNotice(message);
          setRefresh((value) => value + 1);
        }}
      />
    </div>
  );
}