import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function PageContainer({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cx("ds-page", className)}>{children}</div>;
}

export function Stack({
  gap = 12,
  children,
  className,
}: {
  gap?: 8 | 12 | 16 | 20 | 24;
  children: ReactNode;
  className?: string;
}) {
  return <div className={cx(`ds-stack-${gap}`, className)}>{children}</div>;
}

export function InlineGroup({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cx("ds-cluster", className)}>{children}</div>;
}

export function Grid({
  columns = 3,
  children,
  className,
}: {
  columns?: 1 | 2 | 3;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx("ds-form-layout", `ds-form-layout--${columns}`, className)}
    >
      {children}
    </div>
  );
}

export function Divider() {
  return <hr className="ds-divider" />;
}

export function ScrollArea({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cx("ds-scroll", className)}>{children}</div>;
}

export function Collapsible({
  title,
  open,
  onOpenChange,
  children,
}: {
  title: ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
}) {
  return (
    <div className="ds-collapse">
      <button
        type="button"
        className="ds-collapse__trigger"
        aria-expanded={open}
        onClick={() => onOpenChange(!open)}
      >
        {title}
      </button>
      {open ? <div className="ds-collapse__body">{children}</div> : null}
    </div>
  );
}

export function Accordion({
  items,
  openId,
  onOpenChange,
}: {
  items: { id: string; title: ReactNode; content: ReactNode }[];
  openId: string | null;
  onOpenChange: (id: string | null) => void;
}) {
  return (
    <div className="ds-accordion">
      {items.map((item) => (
        <Collapsible
          key={item.id}
          title={item.title}
          open={openId === item.id}
          onOpenChange={(next) => onOpenChange(next ? item.id : null)}
        >
          {item.content}
        </Collapsible>
      ))}
    </div>
  );
}
