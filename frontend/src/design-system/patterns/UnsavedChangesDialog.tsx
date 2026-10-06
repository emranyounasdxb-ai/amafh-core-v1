import { ConfirmationDialog } from "./ConfirmationDialog";

export function UnsavedChangesDialog({
  open,
  onStay,
  onLeave,
  busy,
}: {
  open: boolean;
  onStay: () => void;
  onLeave: () => void;
  busy?: boolean;
}) {
  return (
    <ConfirmationDialog
      open={open}
      title="Unsaved changes"
      confirmLabel="Leave without saving"
      cancelLabel="Stay"
      danger
      busy={busy}
      onClose={onStay}
      onConfirm={onLeave}
    >
      Changes on this page have not been saved. Leave anyway?
    </ConfirmationDialog>
  );
}
