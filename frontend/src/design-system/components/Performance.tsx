import type { ReactNode } from "react";
import { DsIcon } from "../icons";
import { cx } from "../lib/cx";
import { BarChart, LineChart, Sparkline } from "./Charts";
import { formatFullNumber } from "../lib/compactNumber";
import { MetricValue } from "./CompactValue";
import { MonetaryAmount } from "./MonetaryAmount";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { KpiCard } from "./KpiCard";
import { LoadingState } from "./LoadingState";
import { ProgressBar } from "./Display";
import { StatusBadge, type StatusTone } from "./StatusBadge";
import { Tooltip } from "./Tooltip";

export type PerformanceMetric = {
  id: string;
  label: string;
  value: number;
  target?: number;
  previous?: number;
  unit?: string;
  kind?: "number" | "amount" | "percent" | "points";
  currency?: string;
  status?: ReactNode;
  statusTone?: StatusTone;
  note?: ReactNode;
  sparkline?: number[];
  tooltip?: ReactNode;
  meta?: ReactNode;
};

function FullPoints({ value }: { value: number }) {
  return <span className="ds-numeric">{formatFullNumber(value)} pts</span>;
}

function FullValue({
  value,
  kind,
}: {
  value: number;
  kind: PerformanceMetric["kind"];
}) {
  if (kind === "points") return <FullPoints value={value} />;
  if (kind === "amount")
    return <MonetaryAmount value={value} compact={false} align="start" />;
  if (kind === "percent") return <MetricValue value={value} kind="percent" />;
  return <span className="ds-numeric">{formatFullNumber(value)}</span>;
}

export function PerformancePeriodHeader({
  title,
  period,
  actions,
}: {
  title: ReactNode;
  period?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="ds-perf-period">
      <div>
        <h2>{title}</h2>
        {period ? <p>{period}</p> : null}
      </div>
      {actions}
    </header>
  );
}

export function PerformanceMetricCard({
  metric,
}: {
  metric: PerformanceMetric;
}) {
  const percent =
    metric.target && metric.target !== 0
      ? Math.round((metric.value / metric.target) * 100)
      : undefined;
  const delta =
    metric.previous == null ? undefined : metric.value - metric.previous;
  const valueNode = <FullValue value={metric.value} kind={metric.kind} />;
  const body = (
    <article className="ds-perf-metric">
      <span className="ds-perf-metric__label">{metric.label}</span>
      <div className="ds-perf-metric__value">{valueNode}</div>
      <div className="ds-perf-metric__meta">
        {metric.meta != null ? (
          <span>{metric.meta}</span>
        ) : metric.target != null ? (
          <span>
            Target <FullValue value={metric.target} kind={metric.kind} />
            {percent != null ? ` · ${percent}%` : null}
          </span>
        ) : (
          <span>No target configured</span>
        )}
        {delta != null ? (
          <span
            className={cx(
              "ds-perf-delta",
              delta > 0 && "ds-perf-delta--up",
              delta < 0 && "ds-perf-delta--down",
            )}
          >
            {delta > 0 ? "↑" : delta < 0 ? "↓" : "→"}{" "}
            <span className="ds-numeric">{formatFullNumber(Math.abs(delta))}</span>
          </span>
        ) : null}
        {metric.status ? (
          <StatusBadge tone={metric.statusTone}>{metric.status}</StatusBadge>
        ) : null}
      </div>
      {metric.sparkline ? (
        <Sparkline values={metric.sparkline} label={`${metric.label} trend`} />
      ) : null}
      {metric.note ? (
        <p className="ds-perf-metric__note">{metric.note}</p>
      ) : null}
    </article>
  );
  if (!metric.tooltip) return body;
  return <Tooltip content={metric.tooltip}>{body}</Tooltip>;
}

export function PerformanceSummary({
  metrics,
}: {
  metrics: PerformanceMetric[];
}) {
  return (
    <div className="ds-perf-summary-wrap">
      <div className="ds-perf-summary">
        {metrics.map((metric) => (
          <PerformanceMetricCard key={metric.id} metric={metric} />
        ))}
      </div>
    </div>
  );
}

export function PerformanceTargetProgress({
  label,
  current,
  target,
  remaining,
  kind = "number",
  unavailable,
  none,
}: {
  label: ReactNode;
  current: number;
  target?: number;
  remaining?: ReactNode;
  kind?: "number" | "amount" | "percent" | "points";
  currency?: string;
  unavailable?: boolean;
  none?: boolean;
}) {
  if (unavailable) {
    return (
      <div className="ds-perf-target">
        <span>{label}</span>
        <p>Target unavailable</p>
      </div>
    );
  }
  if (none || target == null) {
    return (
      <div className="ds-perf-target">
        <span>{label}</span>
        <p>No target configured</p>
      </div>
    );
  }
  const percent = target === 0 ? 0 : Math.min(100, (current / target) * 100);
  const exceeded = current > target;
  return (
    <div className="ds-perf-target">
      <div className="ds-perf-target__copy">
        <span>{label}</span>
        <strong>
          <FullValue value={current} kind={kind} />
          {" of "}
          <FullValue value={target} kind={kind} />
        </strong>
      </div>
      <ProgressBar
        value={percent}
        max={100}
        tone={exceeded ? "success" : "brand"}
        label={`${label} progress`}
      />
      <div className="ds-perf-target__meta">
        <span>{Math.round(percent)}%</span>
        {remaining}
        {exceeded ? <StatusBadge tone="success">Exceeded</StatusBadge> : null}
      </div>
    </div>
  );
}

export function PerformanceComparison({
  labels,
  series,
  kind = "number",
  currency,
}: {
  labels: string[];
  series: { id: string; label: string; values: number[]; color?: string }[];
  kind?: "number" | "currency" | "percent" | "points";
  currency?: string;
}) {
  return (
    <BarChart
      labels={labels}
      series={series}
      kind={kind}
      grouped
      currency={currency}
    />
  );
}

export function PerformanceTrend({
  labels,
  series,
  kind = "number",
  currency,
}: {
  labels: string[];
  series: { id: string; label: string; values: number[]; color?: string }[];
  kind?: "number" | "currency" | "percent" | "points";
  currency?: string;
}) {
  return (
    <LineChart
      labels={labels}
      series={series}
      kind={kind}
      currency={currency}
    />
  );
}

export function PerformanceRankingCard({
  rank,
  total,
  name,
  meta,
  value,
}: {
  rank: number;
  total?: number;
  name: ReactNode;
  meta?: ReactNode;
  value?: ReactNode;
}) {
  return (
    <KpiCard
      accent="none"
      className="ds-perf-rank"
      label="Ranking"
      value={
        <>
          #{rank}
          {total ? <em> of {total}</em> : null}
        </>
      }
      meta={
        <>
          <strong>{name}</strong>
          {meta ? <span>{meta}</span> : null}
          {value}
        </>
      }
    />
  );
}

export function PerformanceEmptyState() {
  return (
    <EmptyState
      title="No performance values"
      description="No authorized performance metrics are available for this period."
      icon={<DsIcon name="performance" size={20} />}
    />
  );
}

export function PerformanceLoadingState() {
  return (
    <LoadingState
      title="Loading performance"
      description="Retrieving authorized performance metrics…"
    />
  );
}

export function PerformanceErrorState({ retry }: { retry?: () => void }) {
  return (
    <ErrorState
      description="Performance could not be displayed. Retained values were not replaced."
      retry={retry}
    />
  );
}
