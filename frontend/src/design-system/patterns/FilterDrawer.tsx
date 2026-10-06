import type { ReactNode } from "react";
import { Button } from "../components/Button";
import { Drawer } from "../components/Drawer";

export function FilterDrawer({
  open,
  title = "Filters",
  children,
  onClose,
  onApply,
  onReset,
  busy,
}: {
  open: boolean;
  title?: string;
  children: ReactNode;
  onClose: () => void;
  onApply?: () => void;
  onReset?: () => void;
  busy?: boolean;
}) {
  return (
    <Drawer
      open={open}
      title={title}
      onClose={onClose}
      busy={busy}
      footer={
        <>
          {onReset ? (
            <Button variant="ghost" disabled={busy} onClick={onReset}>
              Reset
            </Button>
          ) : null}
          {onApply ? (
            <Button loading={busy} onClick={onApply}>
              Apply
            </Button>
          ) : null}
        </>
      }
    >
      {children}
    </Drawer>
  );
}
