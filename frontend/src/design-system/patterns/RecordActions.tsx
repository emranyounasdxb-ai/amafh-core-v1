import type { ReactNode } from "react";
import { ActionToolbar } from "../components/ActionToolbar";

export function RecordActions({ children }: { children: ReactNode }) {
  return <ActionToolbar>{children}</ActionToolbar>;
}
