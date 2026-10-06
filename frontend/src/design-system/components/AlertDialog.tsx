import type { ReactNode } from "react";
import { Dialog } from "./Dialog";

export function AlertDialog({
  open,
  title,
  children,
  footer,
  onClose,
  busy,
}: {
  open: boolean;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  return (
    <Dialog
      open={open}
      title={title}
      footer={footer}
      onClose={onClose}
      size="sm"
      role="alertdialog"
      closeOnOutside={false}
      busy={busy}
    >
      {children}
    </Dialog>
  );
}
