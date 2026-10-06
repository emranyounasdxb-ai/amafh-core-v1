import { useState, type ChangeEvent, type DragEvent } from "react";
import { cx } from "../lib/cx";
import { FormField } from "./FormField";

export function FileUpload({
  id,
  label,
  hint,
  accept,
  disabled,
  error,
  files,
  onChange,
  compact,
  busy,
}: {
  id: string;
  label: string;
  hint?: string;
  accept?: string;
  disabled?: boolean;
  error?: string;
  files?: FileList | null;
  onChange: (files: FileList | null) => void;
  compact?: boolean;
  busy?: boolean;
}) {
  const [active, setActive] = useState(false);
  const selected = files?.[0]?.name;
  const setFiles = (event: ChangeEvent<HTMLInputElement>) =>
    onChange(event.target.files);
  const drop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setActive(false);
    if (!disabled && !busy) onChange(event.dataTransfer.files);
  };
  return (
    <FormField label={label} htmlFor={id} hint={hint} error={error}>
      <label
        className={cx(
          "ds-file-upload",
          active && "ds-file-upload--active",
          compact && "ds-file-upload--compact",
          disabled && "ds-file-upload--disabled",
          busy && "ds-file-upload--busy",
          error && "ds-file-upload--invalid",
        )}
        htmlFor={id}
        aria-busy={busy || undefined}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled && !busy) setActive(true);
        }}
        onDragLeave={() => setActive(false)}
        onDrop={drop}
      >
        <span className="ds-file-upload__copy">
          <strong>{selected || "No file selected"}</strong>
          <span>
            {busy
              ? "Uploading…"
              : selected
                ? "Replace the current file or drop another."
                : "Drop a file or choose from this device."}
          </span>
        </span>
        <span className="ds-file-upload__action">
          {busy ? "Uploading" : "Choose file"}
        </span>
        <input
          id={id}
          className="ds-sr-only"
          type="file"
          accept={accept}
          disabled={disabled || busy}
          aria-invalid={Boolean(error) || undefined}
          onChange={setFiles}
        />
      </label>
    </FormField>
  );
}
