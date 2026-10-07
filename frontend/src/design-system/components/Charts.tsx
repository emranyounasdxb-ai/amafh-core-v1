import { useState, type ReactNode } from "react";
import { DsIcon } from "../icons";
import {
  formatCompactAmount,
  formatCompactNumber,
  formatFullAmount,
  formatFullNumber,
} from "../lib/compactNumber";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";

export const chartSeriesColors = [
  "var(--ds-chart-1)",
  "var(--ds-chart-2)",
  "var(--ds-chart-3)",
  "var(--ds-chart-4)",
  "var(--ds-chart-5)",
  "var(--ds-chart-6)",
];

export type ChartValueKind = "number" | "currency" | "percent" | "points";
export type ChartState =
  "ready" | "loading" | "empty" | "error" | "unavailable" | "permission";

export type ChartSeries = {
  id: string;
  label: string;
  color?: string;
  values: number[];
};

export function formatChartValue(
  value: number,
  kind: ChartValueKind = "number",
  options: {
    compact?: boolean;
    currency?: string;
    compactDecimals?: number;
    fullDecimals?: number;
  } = {},
) {
  const compact = options.compact ?? true;
  const currency = options.currency ?? "AED";
  const format = {
    compactDecimals: options.compactDecimals,
    fullDecimals: options.fullDecimals,
  };
  if (kind === "percent") {
    return compact
      ? `${formatCompactNumber(value, format)}%`
      : `${formatFullNumber(value, {
          ...format,
          fullDecimals:
            options.fullDecimals ?? (Number.isInteger(value) ? 0 : 2),
        })}%`;
  }
  if (kind === "currency") {
    return compact
      ? formatCompactAmount(value, { ...format, currency })
      : formatFullAmount(value, {
          ...format,
          currency,
          fullDecimals:
            options.fullDecimals ?? (Number.isInteger(value) ? 0 : 2),
        });
  }
  const body = compact
    ? formatCompactNumber(value, format)
    : formatFullNumber(value, format);
  return kind === "points" ? `${body} pts` : body;
}

function chartAxis(value: number, kind: ChartValueKind, currency?: string) {
  return formatChartValue(value, kind, { compact: true, currency });
}

function chartTip(value: number, kind: ChartValueKind, currency?: string) {
  return formatChartValue(value, kind, { compact: false, currency });
}

export function ChartLegend({
  items,
}: {
  items: { id: string; label: string; color: string }[];
}) {
  return (
    <ul className="ds-chart-legend">
      {items.map((item) => (
        <li key={item.id}>
          <span style={{ background: item.color }} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

export function ChartTooltip({
  label,
  rows,
}: {
  label: ReactNode;
  rows: { label: string; value: string; color?: string }[];
}) {
  return (
    <div className="ds-chart-tooltip">
      <p>{label}</p>
      {rows.map((row) => (
        <div key={row.label}>
          <span>
            {row.color ? <i style={{ background: row.color }} /> : null}
            {row.label}
          </span>
          <strong>{row.value}</strong>
        </div>
      ))}
    </div>
  );
}

export function ChartHeader({
  title,
  description,
  actions,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="ds-chart-header">
      <div>
        <h3>{title}</h3>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="ds-chart-actions">{actions}</div> : null}
    </div>
  );
}

export function ChartActions({ children }: { children: ReactNode }) {
  return <div className="ds-chart-actions">{children}</div>;
}

export function ChartContainer({
  children,
  label,
  tooltip,
}: {
  children: ReactNode;
  label: string;
  tooltip?: ChartTip | null;
}) {
  return (
    <div className="ds-chart-wrap">
      <div className="ds-chart-container" role="img" aria-label={label}>
        {children}
      </div>
      <ChartHover tooltip={tooltip ?? null} />
    </div>
  );
}

function shortAxisLabel(label: string) {
  return label.length > 14 ? `${label.slice(0, 13)}…` : label;
}

type ChartTip = {
  label: ReactNode;
  rows: { label: string; value: string; color?: string }[];
};

function ChartHover({ tooltip }: { tooltip: ChartTip | null }) {
  if (!tooltip) return null;
  return (
    <div className="ds-chart-tooltip-layer">
      <ChartTooltip label={tooltip.label} rows={tooltip.rows} />
    </div>
  );
}

export function ChartEmptyState() {
  return (
    <EmptyState
      title="No chart data"
      description="No authorized values are available for this period."
      icon={<DsIcon name="information" size={24} />}
    />
  );
}

export function ChartLoadingState() {
  return (
    <div className="ds-chart-state" role="status">
      <span className="ds-spinner" />
      Retrieving authorized series…
    </div>
  );
}

export function ChartErrorState({ retry }: { retry?: () => void }) {
  return (
    <ErrorState
      title="Chart unavailable"
      description="The series could not be displayed. Retained values were not replaced."
      retry={retry}
    />
  );
}

export function ChartGrid({ children }: { children: ReactNode }) {
  return <div className="ds-chart-grid-cards">{children}</div>;
}

export function ChartCard({
  title,
  description,
  kpi,
  comparison,
  context,
  legend,
  actions,
  footer,
  state = "ready",
  children,
  retry,
  emptyMessage,
}: {
  title: ReactNode;
  description?: ReactNode;
  kpi?: ReactNode;
  comparison?: ReactNode;
  context?: ReactNode;
  legend?: { id: string; label: string; color: string }[];
  actions?: ReactNode;
  footer?: ReactNode;
  state?: ChartState;
  children?: ReactNode;
  retry?: () => void;
  emptyMessage?: string;
}) {
  return (
    <section className="ds-chart-card">
      <ChartHeader title={title} description={description} actions={actions} />
      {kpi || comparison || context ? (
        <div className="ds-chart-kpis">
          {kpi ? <div className="ds-chart-kpi">{kpi}</div> : null}
          {comparison ? (
            <div className="ds-chart-compare">{comparison}</div>
          ) : null}
          {context ? <p className="ds-chart-context">{context}</p> : null}
        </div>
      ) : null}
      {legend?.length ? <ChartLegend items={legend} /> : null}
      {state === "loading" ? (
        <ChartLoadingState />
      ) : state === "empty" ? (
        emptyMessage ? (
          <div className="ds-chart-empty-compact" role="status">
            <DsIcon name="performance" size={24} />
            <p>{emptyMessage}</p>
          </div>
        ) : (
          <ChartEmptyState />
        )
      ) : state === "error" ? (
        <ChartErrorState retry={retry} />
      ) : state === "permission" ? (
        <EmptyState
          title="Permission denied"
          description="This chart is outside the current authorized scope."
          icon={<DsIcon name="locked" size={24} />}
        />
      ) : state === "unavailable" ? (
        <EmptyState
          title="Unavailable"
          description="This chart cannot be shown with the current prerequisites."
          icon={<DsIcon name="blocked" size={24} />}
        />
      ) : (
        children
      )}
      {footer ? <p className="ds-chart-footer">{footer}</p> : null}
    </section>
  );
}

const PAD = { l: 52, r: 12, t: 12, b: 32 };

function axisMax(values: number[]) {
  const max = Math.max(0, ...values);
  const whole = values.every(Number.isInteger);
  if (max === 0) return whole ? 2 : 1;
  const exp = 10 ** Math.floor(Math.log10(max));
  const nice = Math.ceil(max / exp) * exp;
  // Whole-number series need a whole-number midpoint tick.
  return whole && exp === 1 && nice % 2 === 1 ? nice + 1 : nice;
}

export function LineChart({
  labels,
  series,
  kind = "number",
  currency,
}: {
  labels: string[];
  series: ChartSeries[];
  kind?: ChartValueKind;
  currency?: string;
}) {
  const width = 560;
  const height = 220;
  const innerW = width - PAD.l - PAD.r;
  const innerH = height - PAD.t - PAD.b;
  const max = axisMax(series.flatMap((item) => item.values));
  const x = (index: number) =>
    PAD.l +
    (labels.length <= 1 ? innerW / 2 : (index / (labels.length - 1)) * innerW);
  const y = (value: number) => PAD.t + innerH - (value / max) * innerH;
  const ticks = [0, 0.5, 1].map((part) => part * max);
  const [tooltip, setTooltip] = useState<ChartTip | null>(null);
  return (
    <ChartContainer label="Line chart" tooltip={tooltip}>
      <svg viewBox={`0 0 ${width} ${height}`} className="ds-chart-svg">
        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={PAD.l}
              x2={width - PAD.r}
              y1={y(tick)}
              y2={y(tick)}
              className="ds-chart-grid"
            />
            <text
              x={PAD.l - 8}
              y={y(tick) + 4}
              className="ds-chart-axis"
              textAnchor="end"
            >
              {chartAxis(tick, kind, currency)}
            </text>
          </g>
        ))}
        {labels.map((label, index) => (
          <text
            key={label}
            x={x(index)}
            y={height - 8}
            className="ds-chart-axis"
            textAnchor="middle"
          >
            {shortAxisLabel(label)}
          </text>
        ))}
        {series.map((item, seriesIndex) => {
          const color = item.color ?? chartSeriesColors[seriesIndex]!;
          const d = item.values
            .map(
              (value, index) =>
                `${index === 0 ? "M" : "L"} ${x(index)} ${y(value)}`,
            )
            .join(" ");
          return (
            <g key={item.id}>
              <path d={d} fill="none" stroke={color} strokeWidth="2" />
              {item.values.map((value, index) => (
                <circle
                  key={`${item.id}-${index}`}
                  cx={x(index)}
                  cy={y(value)}
                  r="3.5"
                  fill={color}
                  onMouseEnter={() =>
                    setTooltip({
                      label: labels[index],
                      rows: series.map((row, rowIndex) => ({
                        label: row.label,
                        value: chartTip(row.values[index] ?? 0, kind, currency),
                        color: row.color ?? chartSeriesColors[rowIndex],
                      })),
                    })
                  }
                  onMouseLeave={() => setTooltip(null)}
                />
              ))}
            </g>
          );
        })}
      </svg>
    </ChartContainer>
  );
}

export function BarChart({
  labels,
  series,
  kind = "number",
  grouped = false,
  currency,
}: {
  labels: string[];
  series: ChartSeries[];
  kind?: ChartValueKind;
  grouped?: boolean;
  currency?: string;
}) {
  const width = 560;
  const height = 220;
  const innerW = width - PAD.l - PAD.r;
  const innerH = height - PAD.t - PAD.b;
  const max = axisMax(series.flatMap((item) => item.values));
  const groupW = innerW / Math.max(labels.length, 1);
  const barW = grouped
    ? Math.max(8, (groupW - 16) / series.length)
    : Math.max(12, groupW * 0.56);
  const y = (value: number) => PAD.t + innerH - (value / max) * innerH;
  const ticks = [0, 0.5, 1].map((part) => part * max);
  const [tooltip, setTooltip] = useState<ChartTip | null>(null);
  const showIndex = (index: number) =>
    setTooltip({
      label: labels[index],
      rows: series.map((row, rowIndex) => ({
        label: row.label,
        value: chartTip(row.values[index] ?? 0, kind, currency),
        color: row.color ?? chartSeriesColors[rowIndex],
      })),
    });
  return (
    <ChartContainer label="Bar chart" tooltip={tooltip}>
      <svg viewBox={`0 0 ${width} ${height}`} className="ds-chart-svg">
        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={PAD.l}
              x2={width - PAD.r}
              y1={y(tick)}
              y2={y(tick)}
              className="ds-chart-grid"
            />
            <text
              x={PAD.l - 8}
              y={y(tick) + 4}
              className="ds-chart-axis"
              textAnchor="end"
            >
              {chartAxis(tick, kind, currency)}
            </text>
          </g>
        ))}
        {labels.map((label, index) => {
          const groupX = PAD.l + index * groupW + 8;
          return (
            <g key={label}>
              {series.map((item, seriesIndex) => {
                const value = item.values[index] ?? 0;
                const x = grouped
                  ? groupX + seriesIndex * barW
                  : groupX + (groupW - 16 - barW) / 2;
                const top = y(value);
                return (
                  <rect
                    key={`${item.id}-${label}`}
                    x={x}
                    y={top}
                    width={barW}
                    height={Math.max(0, PAD.t + innerH - top)}
                    rx="3"
                    fill={item.color ?? chartSeriesColors[seriesIndex]}
                    onMouseEnter={() => showIndex(index)}
                    onMouseLeave={() => setTooltip(null)}
                  />
                );
              })}
              <text
                x={PAD.l + index * groupW + groupW / 2}
                y={height - 8}
                className="ds-chart-axis"
                textAnchor="middle"
              >
                {shortAxisLabel(label)}
              </text>
            </g>
          );
        })}
      </svg>
    </ChartContainer>
  );
}

export function StackedBarChart({
  labels,
  series,
  kind = "number",
}: {
  labels: string[];
  series: ChartSeries[];
  kind?: ChartValueKind;
}) {
  const stacked = labels.map((_, index) =>
    series.reduce((sum, item) => sum + (item.values[index] ?? 0), 0),
  );
  const width = 560;
  const height = 220;
  const innerW = width - PAD.l - PAD.r;
  const innerH = height - PAD.t - PAD.b;
  const max = axisMax(stacked);
  const groupW = innerW / Math.max(labels.length, 1);
  const barW = Math.max(16, groupW * 0.5);
  const y = (value: number) => PAD.t + innerH - (value / max) * innerH;
  const [tooltip, setTooltip] = useState<ChartTip | null>(null);
  return (
    <ChartContainer label="Stacked bar chart" tooltip={tooltip}>
      <svg viewBox={`0 0 ${width} ${height}`} className="ds-chart-svg">
        {[0, 0.5, 1].map((part) => (
          <line
            key={part}
            x1={PAD.l}
            x2={width - PAD.r}
            y1={y(part * max)}
            y2={y(part * max)}
            className="ds-chart-grid"
          />
        ))}
        {labels.map((label, index) => {
          let acc = 0;
          const x = PAD.l + index * groupW + (groupW - barW) / 2;
          return (
            <g key={label}>
              {series.map((item, seriesIndex) => {
                const value = item.values[index] ?? 0;
                const top = y(acc + value);
                const heightValue = y(acc) - top;
                acc += value;
                return (
                  <rect
                    key={`${item.id}-${label}`}
                    x={x}
                    y={top}
                    width={barW}
                    height={Math.max(0, heightValue)}
                    fill={item.color ?? chartSeriesColors[seriesIndex]}
                    onMouseEnter={() =>
                      setTooltip({
                        label,
                        rows: series.map((row, rowIndex) => ({
                          label: row.label,
                          value: chartTip(row.values[index] ?? 0, kind),
                          color: row.color ?? chartSeriesColors[rowIndex],
                        })),
                      })
                    }
                    onMouseLeave={() => setTooltip(null)}
                  />
                );
              })}
              <text
                x={x + barW / 2}
                y={height - 8}
                className="ds-chart-axis"
                textAnchor="middle"
              >
                {shortAxisLabel(label)}
              </text>
            </g>
          );
        })}
      </svg>
    </ChartContainer>
  );
}

export function DonutChart({
  items,
  kind = "number",
  center,
}: {
  items: { id: string; label: string; value: number; color?: string }[];
  kind?: ChartValueKind;
  center?: ReactNode;
}) {
  const total = items.reduce((sum, item) => sum + item.value, 0) || 1;
  const r = 54;
  const c = 2 * Math.PI * r;
  const [tooltip, setTooltip] = useState<ChartTip | null>(null);
  return (
    <ChartContainer label="Donut chart" tooltip={tooltip}>
      <div className="ds-chart-donut">
        <svg viewBox="0 0 160 160" className="ds-chart-svg ds-chart-svg--donut">
          <circle cx="80" cy="80" r={r} className="ds-chart-donut-track" />
          {items.map((item, index) => {
            const len = (item.value / total) * c;
            const dash = `${len} ${c - len}`;
            const current = items
              .slice(0, index)
              .reduce((sum, row) => sum + (row.value / total) * c, 0);
            return (
              <circle
                key={item.id}
                cx="80"
                cy="80"
                r={r}
                fill="none"
                stroke={item.color ?? chartSeriesColors[index]}
                strokeWidth="16"
                strokeDasharray={dash}
                strokeDashoffset={-current}
                transform="rotate(-90 80 80)"
                onMouseEnter={() =>
                  setTooltip({
                    label: item.label,
                    rows: [
                      {
                        label: item.label,
                        value: chartTip(item.value, kind),
                        color: item.color ?? chartSeriesColors[index],
                      },
                    ],
                  })
                }
                onMouseLeave={() => setTooltip(null)}
              />
            );
          })}
        </svg>
        {center ? <div className="ds-chart-donut__center">{center}</div> : null}
      </div>
    </ChartContainer>
  );
}

export function Sparkline({
  values,
  color = "var(--ds-chart-1)",
  label,
}: {
  values: number[];
  color?: string;
  label: string;
}) {
  const width = 96;
  const height = 32;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const d = values
    .map((value, index) => {
      const x =
        values.length <= 1 ? width / 2 : (index / (values.length - 1)) * width;
      const y = height - ((value - min) / span) * height;
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="ds-sparkline"
      aria-label={label}
    >
      <path d={d} fill="none" stroke={color} strokeWidth="2" />
    </svg>
  );
}
