import type { ReactNode } from "react";
import {
  ChartCard,
  ChartGrid,
  CompactAmount,
  InfoGrid,
  PerformanceComparison,
  PerformanceEmptyState,
  PerformanceErrorState,
  PerformanceLoadingState,
  PerformancePeriodHeader,
  PerformanceRankingCard,
  PerformanceSummary,
  PerformanceTargetProgress,
  PerformanceTrend,
  SectionCard,
  type PerformanceMetric,
} from "../index";

const metrics: PerformanceMetric[] = [
  {
    id: "cases",
    label: "Cases",
    value: 128,
    target: 140,
    previous: 119,
    sparkline: [90, 102, 110, 118, 121, 128],
    tooltip: "Authorized completed Cases for October.",
  },
  {
    id: "approvals",
    label: "Approvals",
    value: 36,
    target: 40,
    previous: 33,
    status: "On track",
    statusTone: "success",
  },
  {
    id: "cc",
    label: "Credit Card points",
    value: 1840,
    target: 2000,
    kind: "points",
    previous: 1600,
  },
  {
    id: "pf",
    label: "Personal Finance",
    value: 1_250_000,
    target: 1_500_000,
    kind: "amount",
    currency: "AED",
    previous: 980_000,
  },
  {
    id: "conv",
    label: "Conversion rate",
    value: 18.4,
    target: 20,
    kind: "percent",
  },
];

const months = ["May", "Jun", "Jul", "Aug", "Sep", "Oct"];

function WidthFrame({
  width,
  caption,
  children,
}: {
  width?: "1080" | "960" | "768" | "640";
  caption: string;
  children: ReactNode;
}) {
  return (
    <div
      className={
        width
          ? `ds-content-frame ds-content-frame--${width}`
          : "ds-content-frame ds-content-frame--wide"
      }
    >
      <p className="ds-content-frame__caption">{caption}</p>
      {width ? (
        children
      ) : (
        <div className="ds-content-frame__canvas ds-content-frame__canvas--1280">
          {children}
        </div>
      )}
    </div>
  );
}

export function PerformanceSection() {
  return (
    <section id="performance" className="ds-stack-20">
      <SectionCard
        title="Performance"
        description="Metrics, targets, and comparisons are supplied. The design system does not calculate them."
      >
        <PerformancePeriodHeader
          title="Personal performance"
          period="October 2026 · North operations"
        />
        <strong>Wide container · five metrics in one row</strong>
        <PerformanceSummary metrics={metrics} />
        <strong>Metric container widths</strong>
        <WidthFrame
          width="1080"
          caption="~1080px · Conversion stays visible on the second row"
        >
          <PerformanceSummary metrics={metrics} />
        </WidthFrame>
        <WidthFrame
          width="960"
          caption="~960px · three then two metric cards"
        >
          <PerformanceSummary metrics={metrics} />
        </WidthFrame>
        <WidthFrame width="768" caption="Medium · two cards per row">
          <PerformanceSummary metrics={metrics} />
        </WidthFrame>
        <WidthFrame width="640" caption="Narrow · one or two readable cards">
          <PerformanceSummary metrics={metrics} />
        </WidthFrame>
        <InfoGrid>
          <PerformanceTargetProgress
            label="Credit Card points"
            current={1840}
            target={2000}
            kind="points"
            remaining="160 pts remaining"
          />
          <PerformanceTargetProgress
            label="Personal Finance"
            current={300_000_000}
            target={350_000_000}
            kind="amount"
            currency="AED"
            remaining={
              <>
                Remaining <CompactAmount value={50_000_000} currency="AED" />
              </>
            }
          />
        </InfoGrid>
        <ChartGrid>
          <ChartCard
            title="Monthly trend"
            description="Axis uses compact values. Hover shows the full amount."
            legend={[
              {
                id: "pf",
                label: "Personal Finance",
                color: "var(--ds-chart-1)",
              },
              { id: "target", label: "Target", color: "var(--ds-chart-2)" },
            ]}
          >
            <PerformanceTrend
              labels={months}
              kind="currency"
              currency="AED"
              series={[
                {
                  id: "pf",
                  label: "Personal Finance",
                  values: [
                    180_000_000, 210_000_000, 240_000_000, 265_000_000,
                    280_000_000, 300_000_000,
                  ],
                },
                {
                  id: "target",
                  label: "Target",
                  values: [
                    200_000_000, 220_000_000, 240_000_000, 260_000_000,
                    280_000_000, 300_000_000,
                  ],
                },
              ]}
            />
          </ChartCard>
          <ChartCard
            title="Desk comparison"
            description="Grouped authorized totals."
          >
            <PerformanceComparison
              labels={["North", "West", "Central"]}
              kind="number"
              series={[
                { id: "cases", label: "Cases", values: [128, 96, 141] },
                { id: "approvals", label: "Approvals", values: [36, 22, 40] },
              ]}
            />
          </ChartCard>
        </ChartGrid>
        <PerformanceRankingCard
          rank={4}
          total={18}
          name="A. Rahman"
          meta="Operations manager"
          value="128 Cases"
        />
        <PerformanceTargetProgress label="Monthly target" current={0} none />
        <PerformanceTargetProgress
          label="Branch target"
          current={0}
          unavailable
        />
        <PerformanceLoadingState />
        <PerformanceEmptyState />
        <PerformanceErrorState />
      </SectionCard>
    </section>
  );
}
