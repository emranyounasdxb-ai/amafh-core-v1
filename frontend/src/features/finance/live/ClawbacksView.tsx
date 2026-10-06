import { useState } from "react";
import {
  Button,
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
import { CommandFormDialog } from "../../../app/commands/CommandFormDialog";
import { SelectFilter, Text } from "./financeCells";
import { clawbackCommand } from "./financeCommands";
import {
  personText,
  useBranchLabels,
  useEmployeeLabels,
} from "./financeLabels";
import { caseLabel, type ClawbackRecord } from "./financeRecords";
import { ServerTableSection } from "../../../shared/table/ServerTableSection";
import {
  filterQuery,
  useServerTable,
  type ServerColumn,
} from "../../../shared/table/serverTable";
import { FinanceToolbar } from "./financeTable";
import styles from "./FinancePage.module.css";

const TABLE_ID = "finance-clawbacks";

export function ClawbacksView({
  refresh,
  manage,
  onSaved,
}: {
  refresh: number;
  manage: boolean;
  onSaved: (message: string) => void;
}) {
  const [branchId, setBranchId] = useState("");
  const [selected, setSelected] = useState<ClawbackRecord | null>(null);
  const [creating, setCreating] = useState(false);
  const table = useServerTable<ClawbackRecord>(
    TABLE_ID,
    "/finance/clawbacks",
    filterQuery({ branchId }),
    refresh,
  );
  const people = useEmployeeLabels(
    table.rows.flatMap((row) => [
      row.case_owner_employee_id,
      row.created_by_employee_id,
    ]),
  );
  const branches = useBranchLabels();
  const applied: AppliedFilter[] = branchId
    ? [
        {
          id: "branch",
          label: "Branch",
          field: "Branch",
          value: branches.label(branchId),
          onRemove: () => setBranchId(""),
        },
      ]
    : [];
  const columns: ServerColumn<ClawbackRecord>[] = [
    {
      key: "internal_case_id",
      label: "Case",
      width: 150,
      render: (row) => <Text value={caseLabel(row.internal_case_id)} />,
    },
    {
      key: "case_owner_employee_id",
      label: "Case owner",
      width: 200,
      render: (row) => (
        <Text value={personText(people(row.case_owner_employee_id))} />
      ),
    },
    {
      key: "amount_aed",
      label: "Amount",
      width: 120,
      kind: "money",
      render: (row) => <MonetaryAmount compact={false} value={row.amount_aed} />,
    },
    {
      key: "clawback_date",
      label: "Clawback date",
      width: 130,
      kind: "date",
      render: (row) => <CompactDate value={row.clawback_date} />,
    },
    {
      key: "reason",
      label: "Reason",
      width: 220,
      render: (row) => <Text value={row.reason} />,
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
        label="Clawback filters"
        applied={applied}
        onClearFilters={() => setBranchId("")}
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
                Record clawback
              </Button>
            ) : null}
          </>
        }
      >
        {branches.branches.length > 1 ? (
          <SelectFilter
            id="finance-clawback-branch"
            label="Branch"
            placeholder="All branches"
            value={branchId}
            options={branches.branches.map((branch) => ({
              value: branch.id,
              label: branch.name,
            }))}
            onChange={setBranchId}
          />
        ) : null}
      </FinanceToolbar>
      <ServerTableSection
        table={table}
        tableId={TABLE_ID}
        ariaLabel="Clawbacks"
        stackOnNarrow={false}
        columns={columns}
        filtered={applied.length > 0}
        loadingTitle="Loading clawbacks"
        emptyTitle="No clawbacks"
        emptyDescription="Recorded clawbacks appear here."
        onRowActivate={setSelected}
        rowLabel={(row) => `clawback for ${caseLabel(row.internal_case_id)}`}
      />
      <Drawer
        open={Boolean(selected)}
        title={selected ? caseLabel(selected.internal_case_id) : "Clawback"}
        description="Clawback"
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <SectionCard title="Clawback" compact>
            <InfoGrid>
              <InfoField label="Case" value={<Text value={caseLabel(selected.internal_case_id)} />} />
              <InfoField
                label="Case owner"
                value={<Text value={personText(people(selected.case_owner_employee_id))} />}
              />
              <InfoField label="Amount" value={<MonetaryAmount compact={false} value={selected.amount_aed} align="start" />} />
              <InfoField label="Clawback date" value={<CompactDate value={selected.clawback_date} />} />
              <InfoField label="Branch" value={<Text value={branches.label(selected.branch_id)} />} />
              <InfoField
                label="Recorded by"
                value={<Text value={personText(people(selected.created_by_employee_id))} />}
              />
              <InfoField label="Recorded" value={<CompactDateTime value={selected.created_at} />} />
              <InfoField label="Reason" value={<Text value={selected.reason} />} />
            </InfoGrid>
          </SectionCard>
        ) : null}
      </Drawer>
      {creating ? (
        <CommandFormDialog
          command={clawbackCommand()}
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            onSaved("Clawback recorded.");
          }}
        />
      ) : null}
    </div>
  );
}
