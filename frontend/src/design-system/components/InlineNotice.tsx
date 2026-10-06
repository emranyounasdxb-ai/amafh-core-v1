import type { ReactNode } from "react";
import { Banner } from "./Banner";

export type NoticeTone = "info" | "success" | "warning" | "error";

export function InlineNotice({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: NoticeTone;
  title?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Banner tone={tone} level="inline" title={title} className={className}>
      {children}
    </Banner>
  );
}
