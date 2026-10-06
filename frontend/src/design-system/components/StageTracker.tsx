import type { ReactNode } from "react";
import { cx } from "../lib/cx";
import { DsIcon, type DsIconName } from "../icons";
import { StatusBadge, type StatusTone } from "./StatusBadge";

export type StageStatus =
  | "completed"
  | "current"
  | "upcoming"
  | "blocked"
  | "failed"
  | "rejected"
  | "skipped"
  | "locked";

export type StageItem = {
  id: string;
  title: ReactNode;
  description?: ReactNode;
  time?: ReactNode;
  actor?: ReactNode;
  note?: ReactNode;
  status: StageStatus;
  statusLabel?: ReactNode;
  action?: ReactNode;
};

const stageIcon: Record<StageStatus, DsIconName | null> = {
  completed: "completed",
  current: "current",
  upcoming: null,
  blocked: "blocked",
  failed: "close",
  rejected: "close",
  skipped: "skipped",
  locked: "locked",
};

const stageTone: Record<StageStatus, StatusTone> = {
  completed: "success",
  current: "brand",
  upcoming: "neutral",
  blocked: "warning",
  failed: "danger",
  rejected: "danger",
  skipped: "neutral",
  locked: "neutral",
};

const stageLabel: Record<StageStatus, string> = {
  completed: "Completed",
  current: "Current",
  upcoming: "Upcoming",
  blocked: "Blocked",
  failed: "Failed",
  rejected: "Rejected",
  skipped: "Skipped",
  locked: "Locked",
};

export function StageConnector({
  status,
  orientation = "horizontal",
}: {
  status: StageStatus;
  orientation?: "horizontal" | "vertical";
}) {
  return (
    <span
      className={cx(
        "ds-stage-connector",
        `ds-stage-connector--${orientation}`,
        `ds-stage-connector--${status}`,
      )}
      aria-hidden="true"
    />
  );
}

export function StageNode({ status }: { status: StageStatus }) {
  const icon = stageIcon[status];
  return (
    <span className={cx("ds-stage-node", `ds-stage-node--${status}`)}>
      {icon ? <DsIcon name={icon} size={14} /> : null}
    </span>
  );
}

export function StageSummary({
  completed,
  total,
}: {
  completed: number;
  total: number;
}) {
  return (
    <p className="ds-stage-summary">
      {completed} of {total} stages complete
    </p>
  );
}

function StageCopy({
  item,
  compact,
  orientation = "horizontal",
}: {
  item: StageItem;
  compact?: boolean;
  orientation?: "horizontal" | "vertical";
}) {
  const detailed = orientation === "vertical" && !compact;
  return (
    <div className="ds-stage-copy">
      <div className="ds-stage-copy__title">
        <strong>{item.title}</strong>
        <StatusBadge tone={stageTone[item.status]}>
          {item.statusLabel ?? stageLabel[item.status]}
        </StatusBadge>
      </div>
      {detailed && item.description ? <p>{item.description}</p> : null}
      {item.actor || item.time ? (
        <p className="ds-stage-copy__meta">
          {[item.actor, item.time].filter(Boolean).map((part, index) => (
            <span key={index}>{part}</span>
          ))}
        </p>
      ) : null}
      {detailed && item.note ? (
        <p className="ds-stage-copy__note">{item.note}</p>
      ) : null}
      {item.action}
    </div>
  );
}

export function StageItem({
  item,
  compact,
  orientation = "horizontal",
  showConnector = false,
  focused = false,
}: {
  item: StageItem;
  compact?: boolean;
  orientation?: "horizontal" | "vertical";
  showConnector?: boolean;
  focused?: boolean;
}) {
  return (
    <li
      className={cx(
        "ds-stage-item",
        `ds-stage-item--${item.status}`,
        focused && "ds-stage-item--focused",
      )}
      tabIndex={0}
    >
      <div className="ds-stage-rail">
        <StageNode status={item.status} />
        {showConnector ? (
          <StageConnector status={item.status} orientation={orientation} />
        ) : null}
      </div>
      <StageCopy item={item} compact={compact} orientation={orientation} />
    </li>
  );
}

export function StageTracker({
  items,
  orientation = "horizontal",
  compact,
  label,
  focusedId,
}: {
  items: StageItem[];
  orientation?: "horizontal" | "vertical";
  compact?: boolean;
  label: string;
  focusedId?: string;
}) {
  const completed = items.filter((item) => item.status === "completed").length;
  return (
    <div
      className={cx(
        "ds-stage-tracker",
        `ds-stage-tracker--${orientation}`,
        compact && "ds-stage-tracker--compact",
      )}
    >
      <StageSummary completed={completed} total={items.length} />
      <ol className="ds-stage-list" aria-label={label}>
        {items.map((item, index) => (
          <StageItem
            key={item.id}
            item={item}
            compact={compact}
            orientation={orientation}
            showConnector={index < items.length - 1}
            focused={focusedId === item.id}
          />
        ))}
      </ol>
    </div>
  );
}

export function HorizontalStageTracker(
  props: Omit<Parameters<typeof StageTracker>[0], "orientation">,
) {
  return <StageTracker {...props} orientation="horizontal" />;
}

export function VerticalStageTracker(
  props: Omit<Parameters<typeof StageTracker>[0], "orientation">,
) {
  return <StageTracker {...props} orientation="vertical" />;
}
