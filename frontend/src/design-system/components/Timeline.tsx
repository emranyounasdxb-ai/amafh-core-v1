import type { ReactNode } from "react";
import { cx } from "../lib/cx";
import { StatusBadge, type StatusTone } from "./StatusBadge";

export type TimelineItem = {
  id: string;
  time: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actor?: ReactNode;
  tone?: StatusTone;
  status?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
};

export function Timeline({
  items,
  compact,
  className,
}: {
  items: TimelineItem[];
  compact?: boolean;
  className?: string;
}) {
  return (
    <ol
      className={cx(
        "ds-timeline",
        compact && "ds-timeline--compact",
        className,
      )}
    >
      {items.map((item) => (
        <li key={item.id} className="ds-timeline__item">
          <div className="ds-timeline__rail">
            <span
              className={cx(
                "ds-timeline__dot",
                item.tone && `ds-timeline__dot--${item.tone}`,
              )}
              aria-hidden="true"
            >
              {item.icon}
            </span>
          </div>
          <div className="ds-timeline__body">
            <div className="ds-timeline__time">{item.time}</div>
            <div className="ds-timeline__heading">
              <h3 className="ds-timeline__title">{item.title}</h3>
              {item.status ? (
                <StatusBadge tone={item.tone}>{item.status}</StatusBadge>
              ) : null}
            </div>
            {item.description ? (
              <p className="ds-timeline__description">{item.description}</p>
            ) : null}
            {item.actor ? (
              <p className="ds-timeline__actor">{item.actor}</p>
            ) : null}
            {item.action ? (
              <div className="ds-timeline__action">{item.action}</div>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
