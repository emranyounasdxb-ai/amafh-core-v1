import type { ReactNode } from "react";
import { Button } from "../components/Button";
import { Dialog } from "../components/Dialog";

export function ConfirmationDialog({
  open,
  title,
  children,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  busy = false,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={open}
      title={title}
      size="md"
      role="alertdialog"
      closeOnOutside={!busy}
      busy={busy}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" disabled={busy} onClick={onClose}>
            {cancelLabel}
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            loading={busy}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      {children}
    </Dialog>
  );
}

export function DestructiveConfirmationDialog({
  confirmLabel = "Delete",
  ...props
}: Omit<Parameters<typeof ConfirmationDialog>[0], "danger">) {
  return <ConfirmationDialog {...props} danger confirmLabel={confirmLabel} />;
}
