import { cx } from "../lib/cx";

export type StepStatus = "complete" | "current" | "upcoming" | "error";

export type StepItem = {
  id: string;
  label: string;
  status: StepStatus;
};

export function Stepper({
  items,
  label,
}: {
  items: StepItem[];
  label: string;
}) {
  return (
    <ol className="ds-stepper" aria-label={label}>
      {items.map((item, index) => (
        <li
          key={item.id}
          className={cx("ds-stepper__item", `ds-stepper__item--${item.status}`)}
        >
          <span className="ds-stepper__index" aria-hidden="true">
            {index + 1}
          </span>
          <span>{item.label}</span>
        </li>
      ))}
    </ol>
  );
}
