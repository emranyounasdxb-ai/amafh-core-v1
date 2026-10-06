import { useState } from "react";
import {
  AppliedFilterSummary,
  Button,
  CompactDate,
  CompactDateTime,
  CompactMonthYear,
  DataTable,
  DateRangePicker,
  Drawer,
  DropdownSelect,
  EmptyState,
  EmptyValue,
  ErrorState,
  FilterToolbar,
  FilterToolbarItem,
  InfoField,
  InfoGrid,
  KpiSummary,
  LoadingState,
  MonetaryAmount,
  MonthPicker,
  NoResultsState,
  PageContainer,
  PageHeader,
  Pagination,
  RecordCount,
  RelatedRecordList,
  SectionCard,
  StatusBadge,
  TruncatedText,
  UnavailableState,
  addMonths,
  formatCompactDateRange,
  formatFullNumber,
  type AppliedFilter,
  type DataTableColumn,
  type DateOnly,
} from "../../design-system";
import { useResource } from "../../app/api/useResource";
import {
  KIND_LABEL,
  KIND_OPTIONS,
  KIND_STATUS,
  isWalletKind,
  transactionDescription,
  type WalletDetail,
  type WalletKind,
  type WalletPage,
  type WalletPeriod,
  type WalletSummary,
  type WalletTransaction,
} from "./walletRecords";
import { currentMonthPeriod, monthPeriod, periodMonth } from "./walletPeriod";
import styles from "./MyWalletPage.module.css";

function Text({ value }: { value: string | null | undefined }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

function Amount({ value }: { value: string | null | undefined }) {
  return <MonetaryAmount compact={false} value={value} align="start" />;
}

export function MyWalletPage({
  openCase,
}: {
  openCase?: (id: string) => void;
}) {
  const thisMonth = currentMonthPeriod();
  const [period, setPeriod] = useState<WalletPeriod>(thisMonth);
  const [kind, setKind] = useState<WalletKind | "">("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<WalletTransaction | null>(null);
  const range = `periodFrom=${period.start}&periodTo=${period.end}`;
  const summary = useResource<WalletSummary>(`/my-wallet/summary?${range}`);
  const list = useResource<WalletPage>(
    `/my-wallet/transactions?${range}&page=${page}&pageSize=${pageSize}${kind ? `&kind=${kind}` : ""}`,
  );
  const changePeriod = (next: WalletPeriod) => {
    setPeriod(next);
    setPage(1);
  };
  const isDefaultPeriod =
    period.start === thisMonth.start && period.end === thisMonth.end;
  const applied = [
    !isDefaultPeriod && {
      id: "period",
      field: "Period",
      value: formatCompactDateRange(period.start, period.end),
      label: `Period: ${formatCompactDateRange(period.start, period.end)}`,
      onRemove: () => changePeriod(thisMonth),
    },
    kind && {
      id: "kind",
      field: "Type",
      value: KIND_LABEL[kind],
      label: `Type: ${KIND_LABEL[kind]}`,
      onRemove: () => {
        setKind("");
        setPage(1);
      },
    },
  ].filter(Boolean) as AppliedFilter[];
  const lastMonth = monthPeriod(addMonths(thisMonth.start, -1));
  const caseCell = (row: WalletTransaction) => {
    if (!row.caseReference) return <EmptyValue />;
    const caseId = row.caseId;
    return caseId && openCase ? (
      <Button
        variant="ghost"
        size="compact"
        aria-label={`Open Case ${row.caseReference}`}
        onClick={() => openCase(caseId)}
      >
        {row.caseReference}
      </Button>
    ) : (
      <Text value={row.caseReference} />
    );
  };
  const columns: DataTableColumn<WalletTransaction>[] = [
    {
      key: "date",
      header: "Date",
      kind: "date",
      width: "100px",
      render: (row) => <CompactDate value={row.date} />,
    },
    {
      key: "kind",
      header: "Type",
      width: "150px",
      render: (row) => <Text value={KIND_LABEL[row.kind]} />,
    },
    {
      key: "reference",
      header: "Reference",
      width: "170px",
      render: (row) =>
        row.paymentMonth ? (
          <CompactMonthYear value={row.paymentMonth} />
        ) : (
          caseCell(row)
        ),
    },
    {
      key: "description",
      header: "Description",
      width: "220px",
      render: (row) => <Text value={transactionDescription(row)} />,
    },
    {
      key: "amountAed",
      header: "Amount",
      kind: "money",
      width: "120px",
      render: (row) => <MonetaryAmount compact={false} value={row.amountAed} />,
    },
    {
      key: "status",
      header: "Status",
      width: "110px",
      render: (row) => (
        <StatusBadge tone={KIND_STATUS[row.kind].tone}>
          {KIND_STATUS[row.kind].label}
        </StatusBadge>
      ),
    },
  ];
  const total = list.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const totals = summary.data;
  return (
    <PageContainer>
      <div className={styles.page}>
        <PageHeader
          title="My Wallet"
          subtitle="Your salary payments, commission and clawbacks from Finance records"
        />
        <div className={styles.toolbarStack}>
          <FilterToolbar label="Wallet filters" className={styles.toolbar}>
            <FilterToolbarItem
              label="Month"
              htmlFor="my-wallet-month"
              className="ds-filter-toolbar__item--quick"
            >
              <MonthPicker
                id="my-wallet-month"
                label="Month"
                compact
                value={periodMonth(period)}
                onChange={(month) => changePeriod(monthPeriod(`${month}-01`))}
              />
            </FilterToolbarItem>
            <FilterToolbarItem
              label="Period"
              htmlFor="my-wallet-period"
              className={styles.rangeControl}
            >
              <DateRangePicker
                id="my-wallet-period"
                compact
                compactRangeLabel
                presets={[
                  { id: "month", label: "This month", range: thisMonth },
                  { id: "last-month", label: "Last month", range: lastMonth },
                  { id: "custom", label: "Custom", range: { start: "", end: "" } },
                ]}
                value={period}
                onChange={(next) => {
                  if (next.start && next.end)
                    changePeriod({
                      start: next.start as DateOnly,
                      end: next.end as DateOnly,
                    });
                  else if (!next.start && !next.end) changePeriod(thisMonth);
                }}
              />
            </FilterToolbarItem>
            <FilterToolbarItem
              label="Type"
              htmlFor="my-wallet-type"
              className="ds-filter-toolbar__item--quick"
            >
              <DropdownSelect
                id="my-wallet-type"
                label="Type"
                compact
                clearable
                placeholder="All types"
                value={kind}
                options={KIND_OPTIONS}
                onChange={(next) => {
                  const value = Array.isArray(next) ? (next[0] ?? "") : next;
                  setKind(isWalletKind(value) ? value : "");
                  setPage(1);
                }}
              />
            </FilterToolbarItem>
          </FilterToolbar>
          <AppliedFilterSummary
            items={applied}
            onClear={() => {
              changePeriod(thisMonth);
              setKind("");
            }}
          />
        </div>
        {summary.error && !totals ? (
          <ErrorState description={summary.error} retry={summary.reload} />
        ) : summary.loading && !totals ? (
          <LoadingState title="Loading wallet summary" />
        ) : totals ? (
          <>
            <KpiSummary
              compact
              items={[
                {
                  id: "salary",
                  label: "Salary paid",
                  value: <MonetaryAmount compact={false} value={totals.salaryPaidAed} />,
                  meta: "Salary payments dated in this period",
                },
                {
                  id: "earned",
                  label: "Commission earned",
                  value: (
                    <MonetaryAmount compact={false} value={totals.commissionEarnedAed} />
                  ),
                  meta: "Completed Cases credited to you",
                },
                {
                  id: "commission-paid",
                  label: "Commission paid",
                  value: (
                    <MonetaryAmount compact={false} value={totals.commissionPaidAed} />
                  ),
                  meta: "Commission payments dated in this period",
                },
                {
                  id: "clawbacks",
                  label: "Clawbacks",
                  value: <MonetaryAmount compact={false} value={totals.clawbacksAed} />,
                  meta: "Clawbacks dated in this period",
                  accent: "pink",
                },
              ]}
            />
            <p className={styles.support}>
              Each total is shown separately. Payments and clawbacks are not
              deducted from one another.
            </p>
          </>
        ) : null}
        {list.error && !list.data ? (
          <ErrorState description={list.error} retry={list.reload} />
        ) : list.loading && !list.data ? (
          <LoadingState title="Loading wallet history" />
        ) : (
          <SectionCard compact className={styles.table}>
            <RecordCount count={total} />
            {total === 0 ? (
              kind ? (
                <NoResultsState
                  title="No matching transactions"
                  description="No transactions of this type in the selected period."
                />
              ) : (
                <EmptyState
                  title="No wallet activity"
                  description="No salary payments, commission or clawbacks in the selected period."
                />
              )
            ) : (
              <>
                <DataTable
                  ariaLabel="Wallet transactions"
                  density="compact"
                  columns={columns}
                  rows={list.data?.items ?? []}
                  rowKey={(row) => `${row.kind}:${row.id}`}
                  loading={list.updating}
                  onRowActivate={setSelected}
                  rowActivateLabel={(row) =>
                    `Open ${KIND_LABEL[row.kind].toLowerCase()} details`
                  }
                />
                <Pagination
                  page={page}
                  pageCount={pageCount}
                  onPageChange={setPage}
                  pageSize={pageSize}
                  onPageSizeChange={(size) => {
                    setPageSize(size);
                    setPage(1);
                  }}
                />
              </>
            )}
          </SectionCard>
        )}
      </div>
      <TransactionDrawer
        row={selected}
        onClose={() => setSelected(null)}
        openCase={openCase}
      />
    </PageContainer>
  );
}

function TransactionDrawer({
  row,
  onClose,
  openCase,
}: {
  row: WalletTransaction | null;
  onClose: () => void;
  openCase?: (id: string) => void;
}) {
  const detail = useResource<WalletDetail>(
    row ? `/my-wallet/transactions/${row.kind}/${row.id}` : null,
  );
  const item = detail.data && row && detail.data.id === row.id ? detail.data : null;
  return (
    <Drawer
      open={Boolean(row)}
      title={row ? KIND_LABEL[row.kind] : "Transaction"}
      description={row ? <CompactDate value={row.date} /> : undefined}
      onClose={onClose}
    >
      {!row ? null : detail.denied ? (
        <UnavailableState title="Record unavailable" />
      ) : detail.error && !item ? (
        <ErrorState description={detail.error} retry={detail.reload} />
      ) : !item ? (
        <LoadingState title="Loading details" />
      ) : (
        <div className={styles.drawerBody}>
          <DetailSection item={item} />
          {item.caseReference ? (
            <RelatedRecordList
              title="Related Case"
              items={[
                {
                  id: "case",
                  title: item.caseReference,
                  meta: item.caseId && openCase
                    ? "Open the Case record"
                    : "This Case is not available to open from your access",
                  onOpen:
                    item.caseId && openCase
                      ? () => openCase(item.caseId as string)
                      : undefined,
                },
              ]}
            />
          ) : null}
        </div>
      )}
    </Drawer>
  );
}

function DetailSection({ item }: { item: WalletDetail }) {
  const status = KIND_STATUS[item.kind];
  const badge = <StatusBadge tone={status.tone}>{status.label}</StatusBadge>;
  if (item.kind === "salary_payment" || item.kind === "commission_payment")
    return (
      <SectionCard title="Payment" compact>
        <InfoGrid>
          <InfoField label="Type" value={<Text value={KIND_LABEL[item.kind]} />} />
          <InfoField label="Amount" value={<Amount value={item.amountAed} />} />
          <InfoField
            label="Payroll month"
            value={<CompactMonthYear value={item.paymentMonth} />}
          />
          <InfoField label="Payment date" value={<CompactDate value={item.paymentDate} />} />
          <InfoField label="Status" value={badge} />
          <InfoField label="Recorded" value={<CompactDateTime value={item.recordedAt} />} />
        </InfoGrid>
      </SectionCard>
    );
  if (item.kind === "commission_earned")
    return (
      <SectionCard title="Commission breakdown" compact>
        <InfoGrid>
          <InfoField label="Case" value={<Text value={item.caseReference} />} />
          <InfoField label="Bank" value={<Text value={item.bankName} />} />
          <InfoField label="Product" value={<Text value={item.productName} />} />
          <InfoField label="Variant" value={<Text value={item.productVariantName} />} />
          <InfoField label="Completed" value={<CompactDate value={item.completedOn} />} />
          <InfoField label="Commission" value={<Amount value={item.commissionAed} />} />
          <InfoField
            label="CC points"
            value={
              typeof item.ccPoints === "number" ? (
                <span className="ds-numeric">{formatFullNumber(item.ccPoints)}</span>
              ) : (
                <EmptyValue />
              )
            }
          />
          {item.pfAmountAed ? (
            <InfoField label="Finance amount" value={<Amount value={item.pfAmountAed} />} />
          ) : null}
          <InfoField
            label="Rule effective"
            value={<CompactDate value={item.ruleEffectiveDate} />}
          />
          <InfoField label="Status" value={badge} />
        </InfoGrid>
      </SectionCard>
    );
  return (
    <SectionCard title="Clawback" compact>
      <InfoGrid>
        <InfoField label="Case" value={<Text value={item.caseReference} />} />
        <InfoField label="Amount" value={<Amount value={item.amountAed} />} />
        <InfoField label="Clawback date" value={<CompactDate value={item.clawbackDate} />} />
        <InfoField label="Reason" value={item.reason || <EmptyValue />} />
        <InfoField label="Status" value={badge} />
        <InfoField label="Recorded" value={<CompactDateTime value={item.recordedAt} />} />
      </InfoGrid>
    </SectionCard>
  );
}
