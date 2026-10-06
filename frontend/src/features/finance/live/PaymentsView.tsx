import { useState } from "react";
import {
  Button,
  CompactDate,
  CompactDateTime,
  CompactMonthYear,
  Drawer,
  ExportButton,
  InfoField,
  InfoGrid,
  MonetaryAmount,
  SectionCard,
  type AppliedFilter,
} from "../../../design-system";
import { hasPermission } from "../../../access";
import { CommandFormDialog } from "../../../app/commands/CommandFormDialog";
import { useSession } from "../../../app/session/useSession";
import { RangeFilter, SelectFilter, Text } from "./financeCells";
import { PackageReference } from "./PackageReference";
import { rangeChip } from "./financeFilters";
import { paymentCommand } from "./financeCommands";
import {
  personText,
  useBranchLabels,
  useEmployeeLabels,
} from "./financeLabels";
import type { PaymentRecord } from "./financeRecords";
import { ServerTableSection } from "../../../shared/table/ServerTableSection";
import {
  filterQuery,
  useServerTable,
  type ServerColumn,
} from "../../../shared/table/serverTable";
import { FinanceToolbar } from "./financeTable";
import styles from "./FinancePage.module.css";

const TABLE_ID = "finance-payments";
const TYPES = [
  { value: "Salary", label: "Salary" },
  { value: "Commission", label: "Commission" },
];
const EMPTY = { paymentType: "", paymentFrom: "", paymentTo: "" };

export function PaymentsView({
  refresh,
  manage,
  onSaved,
}: {
  refresh: number;
  manage: boolean;
  onSaved: (message: string) => void;
}) {
  const { session } = useSession();
  const [filters, setFilters] = useState(EMPTY);
  const [selected, setSelected] = useState<PaymentRecord | null>(null);
  const [creating, setCreating] = useState(false);
  const table = useServerTable<PaymentRecord>(
    TABLE_ID,
    "/finance/payments",
    filterQuery(filters),
    refresh,
  );
  const people = useEmployeeLabels(
    table.rows.flatMap((row) => [row.employee_id, row.created_by_employee_id]),
  );
  const branches = useBranchLabels();
  const set = (patch: Partial<typeof EMPTY>) =>
    setFilters((current) => ({ ...current, ...patch }));
  const applied = [
    filters.paymentType && {
      id: "type",
      label: "Type",
      field: "Type",
      value: filters.paymentType,
      onRemove: () => set({ paymentType: "" }),
    },
    rangeChip(
      "paid",
      "Payment date",
      filters.paymentFrom,
      filters.paymentTo,
      () => set({ paymentFrom: "", paymentTo: "" }),
    ),
  ].filter(Boolean) as AppliedFilter[];
  const columns: ServerColumn<PaymentRecord>[] = [
    {
      key: "employee_id",
      label: "Employee",
      width: 220,
      render: (row) => <Text value={personText(people(row.employee_id))} />,
    },
    {
      key: "payment_type",
      label: "Type",
      width: 120,
      render: (row) => <Text value={row.payment_type} />,
    },
    {
      key: "amount_aed",
      label: "Amount",
      width: 120,
      kind: "money",
      render: (row) => <MonetaryAmount compact={false} value={row.amount_aed} />,
    },
    {
      key: "payment_month",
      label: "Month",
      width: 110,
      kind: "date",
      render: (row) => <CompactMonthYear value={row.payment_month} />,
    },
    {
      key: "payment_date",
      label: "Payment date",
      width: 130,
      kind: "date",
      render: (row) => <CompactDate value={row.payment_date} />,
    },
    {
      key: "branch_id",
      label: "Branch",
      width: 140,
      render: (row) => <Text value={branches.label(row.branch_id)} />,
    },
    {
      key: "created_by_employee_id",
      label: "Recorded by",
      width: 180,
      render: (row) => (
        <Text value={personText(people(row.created_by_employee_id))} />
      ),
    },
  ];
  return (
    <div className={styles.panel}>
      <FinanceToolbar
        label="Payment filters"
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
              <Button size="compact" onClick={() => setCreating(true)}>
                Record payment
              </Button>
            ) : null}
          </>
        }
      >
        <SelectFilter
          id="finance-payment-type"
          label="Payment type"
          placeholder="All types"
          value={filters.paymentType}
          options={TYPES}
          onChange={(paymentType) => set({ paymentType })}
        />
        <RangeFilter
          id="finance-payment-dates"
          label="Payment dates"
          start={filters.paymentFrom}
          end={filters.paymentTo}
          onChange={(paymentFrom, paymentTo) => set({ paymentFrom, paymentTo })}
        />
      </FinanceToolbar>
      <ServerTableSection
        table={table}
        tableId={TABLE_ID}
        ariaLabel="Payments"
        stackOnNarrow={false}
        columns={columns}
        filtered={applied.length > 0}
        loadingTitle="Loading payments"
        emptyTitle="No payments"
        emptyDescription="Recorded payments appear here."
        onRowActivate={setSelected}
        rowLabel={(row) =>
          `${row.payment_type} payment for ${people(row.employee_id).name}`
        }
      />
      <Drawer
        open={Boolean(selected)}
        title={selected ? personText(people(selected.employee_id)) : "Payment"}
        description={selected ? `${selected.payment_type} payment` : "Payment"}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <SectionCard title="Payment" compact>
            <InfoGrid>
              <InfoField
                label="Employee"
                value={<Text value={personText(people(selected.employee_id))} />}
              />
              <InfoField label="Type" value={<Text value={selected.payment_type} />} />
              <InfoField label="Amount" value={<MonetaryAmount compact={false} value={selected.amount_aed} align="start" />} />
              <InfoField label="Month" value={<CompactMonthYear value={selected.payment_month} />} />
              <InfoField label="Payment date" value={<CompactDate value={selected.payment_date} />} />
              <InfoField label="Branch" value={<Text value={branches.label(selected.branch_id)} />} />
              <InfoField
                label="Recorded by"
                value={<Text value={personText(people(selected.created_by_employee_id))} />}
              />
              <InfoField label="Recorded" value={<CompactDateTime value={selected.created_at} />} />
            </InfoGrid>
          </SectionCard>
        ) : null}
      </Drawer>
      {creating ? (
        <CommandFormDialog
          command={paymentCommand()}
          reference={
            session && hasPermission(session, "package.read")
              ? (values) =>
                  values.employeeId && values.paymentType === "Salary" ? (
                    <PackageReference
                      employeeId={String(values.employeeId)}
                      paymentDate={String(values.paymentDate ?? "")}
                      paymentMonth={String(values.paymentMonth ?? "")}
                    />
                  ) : null
              : undefined
          }
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            onSaved("Payment recorded.");
          }}
        />
      ) : null}
    </div>
  );
}
