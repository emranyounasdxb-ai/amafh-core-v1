import type { ReactNode } from "react";
import { Tooltip } from "./Tooltip";

export function FullValueTooltip({
  content,
  children,
}: {
  content: ReactNode;
  children: ReactNode;
}) {
  if (!content) return <>{children}</>;
  return (
    <Tooltip content={content} delay={80}>
      <span className="ds-compact-value" tabIndex={0}>
        {children}
      </span>
    </Tooltip>
  );
}
