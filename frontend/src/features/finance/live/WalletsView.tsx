import { useState } from "react";
import {
  CompactDateTime,
  DataTable,
  Drawer,
  EmptyState,
  ExportButton,
  InfoField,
  InfoGrid,
  Pagination,
  RecordCount,
  SectionCard,
  type DataTableColumn,
} from "../../../design-system";
import { useResource } from "../../../app/api/useResource";
import { Points, Text } from "./financeCells";
import { personText, useCaseLabels, useEmployeeLabels } from "./financeLabels";
import type {
  WalletDetail,
  WalletRecord,
  WalletTransaction,
} from "./financeRecords";
import { ServerTableSection } from "../../../shared/table/ServerTableSection";
import {
  resourceFeedback,
  useServerTable,
  type ServerColumn,
} from "../../../shared/table/serverTable";
import { FinanceToolbar } from "./financeTable";
import styles from "./FinancePage.module.css";

const TABLE_ID = "finance-wallets";

export function WalletsView({ refresh }: { refresh: number }) {
  const [selected, setSelected] = useState<WalletRecord | null>(null);
  const table = useServerTable<WalletRecord>(
    TABLE_ID,
    "/finance/wallets",
    "",
    refresh,
  );
  const people = useEmployeeLabels(table.rows.map((row) => row.employee_id));
  const columns: ServerColumn<WalletRecord>[] = [
    {
      key: "employee_id",
      label: "Employee",
      width: 240,
      render: (row) => <Text value={personText(people(row.employee_id))} />,
    },
    {
      key: "balance_points",
      label: "Points balance",
      width: 140,
      kind: "number",
      render: (row) => <Points value={row.balance_points} />,
    },
    {
      key: "created_at",
      label: "Opened",
      width: 150,
      kind: "datetime",
      render: (row) => <CompactDateTime value={row.created_at} />,
    },
  ];
  return (
    <div className={styles.panel}>
      <FinanceToolbar
        label="Points wallet actions"
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
      />
      <ServerTableSection
        table={table}
        tableId={TABLE_ID}
        ariaLabel="Points wallets"
        stackOnNarrow={false}
        columns={columns}
        filtered={false}
        loadingTitle="Loading points wallets"
        emptyTitle="No points wallets"
        emptyDescription="Wallets appear once employees are credited points."
        onRowActivate={setSelected}
        rowLabel={(row) => `${people(row.employee_id).name} wallet`}
      />
      <WalletDrawer
        record={selected}
        employee={selected ? personText(people(selected.employee_id)) : ""}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

function WalletDrawer({
  record,
  employee,
  onClose,
}: {
  record: WalletRecord | null;
  employee: string;
  onClose: () => void;
}) {
  const [paging, setPaging] = useState({ id: "", page: 1, size: 25 });
  const current = record && paging.id === record.employee_id;
  const page = current ? paging.page : 1;
  const size = paging.size;
  const detail = useResource<WalletDetail>(
    record
      ? `/finance/wallets/${encodeURIComponent(record.employee_id)}?page=${page}&pageSize=${size}`
      : null,
  );
  const transactions = detail.data?.transactions;
  const cases = useCaseLabels(
    (transactions?.items ?? []).map((row) => row.case_id),
  );
  const columns: DataTableColumn<WalletTransaction>[] = [
    {
      key: "case",
      header: "Case",
      width: "180px",
      render: (row) => <Text value={cases(row.case_id)} />,
    },
    {
      key: "points",
      header: "Points credited",
      width: "140px",
      kind: "number",
      render: (row) => <Points value={row.points_credited} />,
    },
    {
      key: "occurred",
      header: "Credited",
      width: "160px",
      kind: "datetime",
      render: (row) => <CompactDateTime value={row.occurred_at} />,
    },
  ];
  const total = transactions?.total ?? 0;
  const feedback = resourceFeedback(detail, "Loading wallet");
  const close = () => {
    setPaging((current) => ({ ...current, id: "", page: 1 }));
    onClose();
  };
  return (
    <Drawer
      open={Boolean(record)}
      size="wide"
      title={employee || "Points wallet"}
      description="Points wallet"
      onClose={close}
    >
      {feedback ?? (
        <div className={styles.drawerBody}>
          <SectionCard title="Wallet" compact>
            <InfoGrid>
              <InfoField label="Employee" value={<Text value={employee} />} />
              <InfoField
                label="Points balance"
                numeric
                value={<Points value={detail.data?.balancePoints} />}
              />
            </InfoGrid>
          </SectionCard>
          <SectionCard title="Transactions" compact className={styles.table}>
            <RecordCount count={total} />
            {total === 0 ? (
              <EmptyState
                title="No transactions"
                description="Credited points appear here."
              />
            ) : (
              <>
                <DataTable
                  ariaLabel="Wallet transactions"
                  density="compact"
                  columns={columns}
                  rows={transactions?.items ?? []}
                  rowKey={(row) => row.id}
                  loading={detail.updating}
                />
                <Pagination
                  page={page}
                  pageCount={Math.max(1, Math.ceil(total / size))}
                  onPageChange={(next) =>
                    record &&
                    setPaging({ id: record.employee_id, page: next, size })
                  }
                  pageSize={size}
                  onPageSizeChange={(next) =>
                    record &&
                    setPaging({ id: record.employee_id, page: 1, size: next })
                  }
                />
              </>
            )}
          </SectionCard>
        </div>
      )}
    </Drawer>
  );
}
