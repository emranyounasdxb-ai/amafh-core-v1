import {
  BarChart,
  ChartCard,
  ChartGrid,
  DateRangePicker,
  DropdownSelect,
  EmptyValue,
  ErrorState,
  FilterToolbar,
  FilterToolbarItem,
  InlineNotice,
  LineChart,
  LoadingState,
  PageContainer,
  PerformanceSummary,
  PerformanceTargetProgress,
  PermissionDeniedState,
  ProfileCoverActions,
  ProfileCoverBanner,
  ProfileCoverIdentity,
  ProfileCoverMetadata,
  SectionCard,
  dubaiTodayDateOnly,
  formatMonthYear,
} from "../../../design-system";
import { useResource } from "../../../app/api/useResource";
import { employeeAvatarSrc } from "../../employees/live/employeePresentation";
import {
  PRODUCTS,
  PRODUCT_COLOR,
  PRODUCT_LABEL,
  amount,
  datePresets,
  metricCards,
  outcomeSeries,
  percentage,
  performanceQuery,
  periodLabel,
  personCode,
  personName,
  productOptions,
  readable,
  stageSeries,
  valuesState,
  type EmployeeMetrics,
  type EmployeeTrend,
  type PerformanceFilters,
  type Product,
} from "./performancePresentation";
import styles from "./PerformancePage.module.css";

export function PerformanceDetail({
  employeeId,
  own,
  filters,
  product,
  onFilters,
  onProduct,
  onBack,
}: {
  employeeId: string;
  own: boolean;
  filters: PerformanceFilters;
  product: Product | "";
  onFilters: (patch: Partial<PerformanceFilters>) => void;
  onProduct: (product: Product | "") => void;
  onBack?: () => void;
}) {
  const query = performanceQuery(filters, product);
  const metricsPath = own
    ? `/performance/me?${query}`
    : `/performance/employees/${encodeURIComponent(employeeId)}?${query}`;
  const resource = useResource<EmployeeMetrics>(metricsPath);
  const trend = useResource<EmployeeTrend>(
    `/performance/employees/${encodeURIComponent(employeeId)}/trend?${performanceQuery(filters, "")}`,
  );
  const metrics = resource.data;
  const products = product ? [product] : PRODUCTS;

  if (resource.denied || !metrics)
    return (
      <PageContainer>
        {resource.denied ? (
          <PermissionDeniedState
            title="Performance unavailable"
            description="This employee's performance is outside your authorized scope."
          />
        ) : resource.error ? (
          <ErrorState
            title="Performance unavailable"
            description="Performance could not be loaded for the selected period."
            retry={resource.reload}
          />
        ) : (
          <LoadingState
            title="Loading performance"
            description="Retrieving authorized performance metrics…"
          />
        )}
      </PageContainer>
    );

  const name = personName(metrics);
  const outcomes = outcomeSeries(metrics);
  const stages = stageSeries(metrics);
  const months = trend.data?.items ?? [];
  const monthLabels = months.map((item) => formatMonthYear(item.label));
  const trendState = trend.denied
    ? "permission"
    : trend.error && !trend.data
      ? "error"
      : !trend.data
        ? "loading"
        : months.length
          ? "ready"
          : "empty";

  return (
    <PageContainer>
    <div className={styles.page}>
      <ProfileCoverBanner
        identity={
          <ProfileCoverIdentity
            name={name}
            designation={readable(metrics.designation) || undefined}
            code={personCode(metrics) || undefined}
            src={employeeAvatarSrc({
              id: metrics.employeeId,
              avatarFileId: metrics.avatarFileId,
            })}
            contextLabel={own ? "My performance" : "Performance"}
          />
        }
        actions={onBack ? <ProfileCoverActions onBack={onBack} /> : undefined}
        metadata={
          <ProfileCoverMetadata
            items={[
              {
                id: "branch",
                label: "Branch",
                icon: "branch",
                value: readable(metrics.branchName) || <EmptyValue />,
              },
              {
                id: "department",
                label: "Department",
                icon: "department",
                value: readable(metrics.departmentName) || <EmptyValue />,
              },
              {
                id: "product",
                label: "Product",
                icon: "performance",
                value: product ? PRODUCT_LABEL[product] : "All products",
              },
              {
                id: "period",
                label: "Period",
                icon: "calendar",
                value: periodLabel(metrics.startDate, metrics.endDate),
              },
            ]}
          />
        }
      />

      <FilterToolbar label="Performance period" className={styles.detailFilters}>
        <FilterToolbarItem label="Product" htmlFor="performance-detail-product">
          <DropdownSelect
            id="performance-detail-product"
            compact
            clearable
            placeholder="All products"
            value={product}
            options={productOptions}
            onChange={(value) => {
              const next = Array.isArray(value) ? (value[0] ?? "") : value;
              onProduct(next === "CC" || next === "PF" ? next : "");
            }}
          />
        </FilterToolbarItem>
        <FilterToolbarItem label="Period" htmlFor="performance-detail-period">
          <DateRangePicker
            id="performance-detail-period"
            compact
            compactRangeLabel
            max={dubaiTodayDateOnly()}
            presets={datePresets()}
            value={{ start: filters.startDate, end: filters.endDate }}
            onChange={(range) =>
              onFilters({
                startDate: range.start && range.end ? range.start : "",
                endDate: range.start && range.end ? range.end : "",
              })
            }
          />
        </FilterToolbarItem>
      </FilterToolbar>

      {resource.updating ? (
        <InlineNotice tone="info" title="Refreshing">
          Updating performance for the selected period. Current values stay
          visible until the update completes.
        </InlineNotice>
      ) : null}
      {resource.error ? (
        <InlineNotice tone="warning" title="Not updated">
          The selected period could not be loaded. The values shown are from
          the previous selection.
        </InlineNotice>
      ) : null}

      <PerformanceSummary metrics={metricCards(metrics, product)} />

      <SectionCard compact title="Targets">
        <div className={styles.targets}>
          {products.map((code) => {
            const progress = metrics.targetProgress[code];
            const achieved = percentage(progress?.achievementPercentage);
            return (
              <PerformanceTargetProgress
                key={code}
                label={`${PRODUCT_LABEL[code]} target achievement`}
                kind="percent"
                current={achieved ?? 0}
                target={100}
                none={!progress || progress.state === "No Target"}
                unavailable={
                  progress?.state === "Configured" && achieved == null
                }
              />
            );
          })}
        </div>
        <p className={styles.support}>
          {metrics.delayedMetricState === "Available"
            ? `${metrics.delayedCaseCount ?? 0} delayed cases in this period.`
            : "Delayed cases are unavailable until the holiday calendar is certified."}
        </p>
      </SectionCard>

      <ChartGrid>
        <ChartCard
          title="Case outcomes"
          description="Created, booked, completed, rejected and in-progress cases"
          state={outcomes.values.some(Boolean) ? "ready" : "empty"}
        >
          <BarChart
            labels={outcomes.labels}
            series={[{ id: "cases", label: "Cases", values: outcomes.values }]}
          />
        </ChartCard>
        <ChartCard
          title="In progress by stage"
          description="Open cases at each current stage"
          state={stages.labels.length ? "ready" : "empty"}
        >
          <BarChart
            labels={stages.labels}
            series={[{ id: "stage", label: "Cases", values: stages.values }]}
          />
        </ChartCard>
        <ChartCard
          title="Booked cases by month"
          description={
            product
              ? `${PRODUCT_LABEL[product]} booked and completed cases`
              : "Credit Card and Personal Finance compared"
          }
          legend={
            product
              ? undefined
              : products.map((code) => ({
                  id: code,
                  label: PRODUCT_LABEL[code],
                  color: PRODUCT_COLOR[code],
                }))
          }
          state={valuesState(
            trendState,
            months.flatMap((item) =>
              products.flatMap((code) => [
                item[code]?.bookedCaseCount ?? 0,
                item[code]?.completedCaseCount ?? 0,
              ]),
            ),
          )}
          retry={trend.reload}
        >
          <LineChart
            labels={monthLabels}
            series={
              product
                ? [
                    {
                      id: "booked",
                      label: "Booked",
                      color: PRODUCT_COLOR[product],
                      values: months.map(
                        (item) => item[product]?.bookedCaseCount ?? 0,
                      ),
                    },
                    {
                      id: "completed",
                      label: "Completed",
                      color: "var(--ds-chart-2)",
                      values: months.map(
                        (item) => item[product]?.completedCaseCount ?? 0,
                      ),
                    },
                  ]
                : products.map((code) => ({
                    id: code,
                    label: PRODUCT_LABEL[code],
                    color: PRODUCT_COLOR[code],
                    values: months.map(
                      (item) => item[code]?.bookedCaseCount ?? 0,
                    ),
                  }))
            }
          />
        </ChartCard>
        {products.includes("CC") ? (
          <ChartCard
            title="CC points by month"
            description="Credit Card points achieved"
            state={valuesState(
              trendState,
              months.map((item) => amount(item.CC?.achieved)),
            )}
            retry={trend.reload}
          >
            <LineChart
              labels={monthLabels}
              kind="points"
              series={[
                {
                  id: "cc",
                  label: "CC points",
                  color: PRODUCT_COLOR.CC,
                  values: months.map((item) => amount(item.CC?.achieved)),
                },
              ]}
            />
          </ChartCard>
        ) : null}
        {products.includes("PF") ? (
          <ChartCard
            title="PF amount by month"
            description="Personal Finance amount achieved"
            state={valuesState(
              trendState,
              months.map((item) => amount(item.PF?.achieved)),
            )}
            retry={trend.reload}
          >
            <LineChart
              labels={monthLabels}
              kind="currency"
              series={[
                {
                  id: "pf",
                  label: "PF amount",
                  color: PRODUCT_COLOR.PF,
                  values: months.map((item) => amount(item.PF?.achieved)),
                },
              ]}
            />
          </ChartCard>
        ) : null}
      </ChartGrid>
    </div>
    </PageContainer>
  );
}
