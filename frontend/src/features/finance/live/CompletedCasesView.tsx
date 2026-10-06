import { useState } from "react";
import {
  CompactDate,
  CompactDateTime,
  Drawer,
  ExportButton,
  InfoField,
  InfoGrid,
  MonetaryAmount,
  SectionCard,
  type AppliedFilter,
} from "../../../design-system";
import { useResource } from "../../../app/api/useResource";
import {
  PfSlab,
  Points,
  RangeFilter,
  SelectFilter,
  Text,
} from "./financeCells";
import { rangeChip } from "./financeFilters";
import {
  personText,
  useBranchLabels,
  useCatalogLabels,
  useEmployeeLabels,
} from "./financeLabels";
import {
  caseLabel,
  type CompletedCaseDetail,
  type CompletedCaseRecord,
  type FinancialRuleRecord,
} from "./financeRecords";
import { ServerTableSection } from "../../../shared/table/ServerTableSection";
import {
  filterQuery,
  resourceFeedback,
  useServerTable,
  type ServerColumn,
} from "../../../shared/table/serverTable";
import { FinanceToolbar } from "./financeTable";
import styles from "./FinancePage.module.css";

const TABLE_ID = "finance-completed-cases";
const PRODUCTS = [
  { value: "CC", label: "CC" },
  { value: "PF", label: "PF" },
];
const EMPTY = { productCode: "", branchId: "", completedFrom: "", completedTo: "" };

export function CompletedCasesView({
  refresh,
  showRule,
}: {
  refresh: number;
  showRule: boolean;
}) {
  const [filters, setFilters] = useState(EMPTY);
  const [selected, setSelected] = useState<CompletedCaseRecord | null>(null);
  const table = useServerTable<CompletedCaseRecord>(
    TABLE_ID,
    "/finance/completed-cases",
    filterQuery(filters),
    refresh,
  );
  const people = useEmployeeLabels(
    table.rows.map((row) => row.credited_owner_employee_id),
  );
  const branches = useBranchLabels();
  const set = (patch: Partial<typeof EMPTY>) =>
    setFilters((current) => ({ ...current, ...patch }));
  const applied = [
    filters.productCode && {
      id: "product",
      label: "Product",
      field: "Product",
      value: filters.productCode,
      onRemove: () => set({ productCode: "" }),
    },
    filters.branchId && {
      id: "branch",
      label: "Branch",
      field: "Branch",
      value: branches.label(filters.branchId),
      onRemove: () => set({ branchId: "" }),
    },
    rangeChip(
      "completed",
      "Completed",
      filters.completedFrom,
      filters.completedTo,
      () => set({ completedFrom: "", completedTo: "" }),
    ),
  ].filter(Boolean) as AppliedFilter[];

  const columns: ServerColumn<CompletedCaseRecord>[] = [
    {
      key: "internal_case_id",
      label: "Case",
      width: 150,
      render: (row) => <Text value={caseLabel(row.internal_case_id)} />,
    },
    {
      key: "product_code",
      label: "Product",
      width: 100,
      render: (row) => <Text value={row.product_code} />,
    },
    {
      key: "credited_owner_employee_id",
      label: "Credited employee",
      width: 200,
      render: (row) => (
        <Text value={personText(people(row.credited_owner_employee_id))} />
      ),
    },
    {
      key: "branch_id",
      label: "Branch",
      width: 140,
      render: (row) => <Text value={branches.label(row.branch_id)} />,
    },
    {
      key: "completed_at",
      label: "Completed",
      width: 150,
      kind: "datetime",
      render: (row) => <CompactDateTime value={row.completed_at} />,
    },
    {
      key: "cc_points",
      label: "CC points",
      width: 110,
      kind: "number",
      render: (row) => <Points value={row.cc_points} />,
    },
    {
      key: "pf_amount_aed",
      label: "PF amount",
      width: 120,
      kind: "money",
      render: (row) => <MonetaryAmount compact={false} value={row.pf_amount_aed} />,
    },
    {
      key: "commission_aed",
      label: "Commission",
      width: 120,
      kind: "money",
      render: (row) => <MonetaryAmount compact={false} value={row.commission_aed} />,
    },
  ];

  return (
    <div className={styles.panel}>
      <FinanceToolbar
        label="Completed case filters"
        applied={applied}
        onClearFilters={() => setFilters(EMPTY)}
        actions={
          table.selection.allowed ? (
            <ExportButton
              size="compact"
              selectedCount={table.selection.selectedCount}
              loading={table.selection.working}
              disabled={!table.selection.selectedCount}
              onClick={() => void table.selection.exportCsv()}
            />
          ) : null
        }
      >
        <SelectFilter
          id="finance-completed-product"
          label="Product"
          placeholder="All products"
          value={filters.productCode}
          options={PRODUCTS}
          onChange={(productCode) => set({ productCode })}
        />
        {branches.branches.length > 1 ? (
          <SelectFilter
            id="finance-completed-branch"
            label="Branch"
            placeholder="All branches"
            value={filters.branchId}
            options={branches.branches.map((branch) => ({
              value: branch.id,
              label: branch.name,
            }))}
            onChange={(branchId) => set({ branchId })}
          />
        ) : null}
        <RangeFilter
          id="finance-completed-dates"
          label="Completed dates"
          start={filters.completedFrom}
          end={filters.completedTo}
          onChange={(completedFrom, completedTo) =>
            set({ completedFrom, completedTo })
          }
        />
      </FinanceToolbar>
      <ServerTableSection
        table={table}
        tableId={TABLE_ID}
        ariaLabel="Completed cases"
        stackOnNarrow={false}
        columns={columns}
        filtered={applied.length > 0}
        loadingTitle="Loading completed cases"
        emptyTitle="No completed cases"
        emptyDescription="Completed cases appear here once they are credited."
        onRowActivate={setSelected}
        rowLabel={(row) => caseLabel(row.internal_case_id)}
      />
      <CompletedCaseDrawer
        record={selected}
        showRule={showRule}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

function CompletedCaseDrawer({
  record,
  showRule,
  onClose,
}: {
  record: CompletedCaseRecord | null;
  showRule: boolean;
  onClose: () => void;
}) {
  const detail = useResource<CompletedCaseDetail>(
    record
      ? `/finance/completed-cases/${encodeURIComponent(record.case_id)}`
      : null,
  );
  const rule = useResource<FinancialRuleRecord>(
    record && showRule
      ? `/finance/rules/${encodeURIComponent(record.financial_rule_id)}`
      : null,
  );
  const data = detail.data;
  const people = useEmployeeLabels([
    data?.credited_owner_employee_id,
    data?.current_owner_employee_id,
    data?.clawback?.case_owner_employee_id,
    data?.clawback?.created_by_employee_id,
  ]);
  const branches = useBranchLabels();
  const catalog = useCatalogLabels([
    { kind: "banks", id: rule.data?.bank_id },
    { kind: "product-types", id: rule.data?.product_type_id },
    { kind: "product-variants", id: rule.data?.product_variant_id },
  ]);
  const feedback = resourceFeedback(detail, "Loading completed case");
  return (
    <Drawer
      open={Boolean(record)}
      size="wide"
      title={record ? caseLabel(record.internal_case_id) : "Completed case"}
      description="Completed case credit"
      onClose={onClose}
    >
      {feedback ?? (
        <div className={styles.drawerBody}>
          <SectionCard title="Credit" compact>
            <InfoGrid>
              <InfoField label="Case" value={<Text value={caseLabel(data?.internal_case_id)} />} />
              <InfoField label="Product" value={<Text value={data?.product_code} />} />
              <InfoField
                label="Credited employee"
                value={<Text value={personText(people(data?.credited_owner_employee_id))} />}
              />
              <InfoField
                label="Current owner"
                value={<Text value={personText(people(data?.current_owner_employee_id))} />}
              />
              <InfoField label="Branch" value={<Text value={branches.label(data?.branch_id)} />} />
              <InfoField label="Completed" value={<CompactDateTime value={data?.completed_at} />} />
              <InfoField label="CC points" numeric value={<Points value={data?.cc_points} />} />
              <InfoField label="PF amount" value={<MonetaryAmount compact={false} value={data?.pf_amount_aed} align="start" />} />
              <InfoField label="Commission" value={<MonetaryAmount compact={false} value={data?.commission_aed} align="start" />} />
              <InfoField label="Rule effective" value={<CompactDate value={data?.rule_effective_date} />} />
              <InfoField label="Recorded" value={<CompactDateTime value={data?.created_at} />} />
            </InfoGrid>
          </SectionCard>
          {showRule ? (
            <SectionCard title="Financial rule" compact>
              {rule.data ? (
                <InfoGrid>
                  <InfoField label="Bank" value={<Text value={catalog(rule.data.bank_id)} />} />
                  <InfoField label="Product" value={<Text value={catalog(rule.data.product_type_id)} />} />
                  <InfoField
                    label="CC variant / PF slab"
                    value={
                      rule.data.product_variant_id ? (
                        <Text value={catalog(rule.data.product_variant_id)} />
                      ) : (
                        <PfSlab min={rule.data.pf_amount_min} max={rule.data.pf_amount_max} />
                      )
                    }
                  />
                  <InfoField label="Effective" value={<CompactDate value={rule.data.effective_date} />} />
                </InfoGrid>
              ) : (
                resourceFeedback(rule, "Loading financial rule")
              )}
            </SectionCard>
          ) : null}
          <SectionCard title="Clawback" compact>
            {data?.clawback ? (
              <InfoGrid>
                <InfoField label="Amount" value={<MonetaryAmount compact={false} value={data.clawback.amount_aed} align="start" />} />
                <InfoField label="Clawback date" value={<CompactDate value={data.clawback.clawback_date} />} />
                <InfoField
                  label="Case owner"
                  value={<Text value={personText(people(data.clawback.case_owner_employee_id))} />}
                />
                <InfoField
                  label="Recorded by"
                  value={<Text value={personText(people(data.clawback.created_by_employee_id))} />}
                />
                <InfoField label="Reason" value={<Text value={data.clawback.reason} />} />
              </InfoGrid>
            ) : (
              <p className={styles.support}>No clawback has been recorded for this case.</p>
            )}
          </SectionCard>
        </div>
      )}
    </Drawer>
  );
}
