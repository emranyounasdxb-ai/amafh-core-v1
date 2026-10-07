import { useState, type ReactNode } from "react";
import {
  Avatar,
  Button,
  FileUpload,
  Stack,
  TruncatedText,
} from "../../design-system";
import {
  IMAGE_ACCEPT,
  recordImageSrc,
  type ImageRecord,
  type ImageUpload,
} from "../../app/api/recordImages";
import styles from "./RecordImage.module.css";

/** Catalog images retain their whole content; absent/broken images keep the text fallback. */
export function RecordImage({
  src,
  label,
  preview = false,
}: {
  src?: string;
  label: string;
  preview?: boolean;
}) {
  const [failed, setFailed] = useState<string | undefined>();
  if (!src || failed === src)
    return preview ? <span>No image available.</span> : null;
  return (
    <img
      src={src}
      alt={preview ? label : ""}
      className={preview ? styles.preview : styles.thumbnail}
      onError={() => setFailed(src)}
    />
  );
}

export function RecordImageLabel({
  src,
  label,
  children,
}: {
  src?: string;
  label: string;
  children?: ReactNode;
}) {
  return (
    <span className={styles.label}>
      <RecordImage src={src} label={label} />
      {children ?? <TruncatedText value={label} />}
    </span>
  );
}

export function ImageUploadField({
  upload,
  record,
  files,
  onChange,
  busy,
  error,
}: {
  upload: ImageUpload;
  record?: ImageRecord;
  files: FileList | null;
  onChange: (files: FileList | null) => void;
  busy: boolean;
  error?: string;
}) {
  const src = recordImageSrc(upload.kind, record);
  return (
    <Stack gap={8}>
      {upload.kind === "employee" ? (
        <Avatar
          name={record?.fullName || record?.name || upload.label}
          src={src}
          size="lg"
        />
      ) : (
        <RecordImage src={src} label={upload.label} preview />
      )}
      <FileUpload
        key={files?.[0]?.name || "empty"}
        id="record-image-upload"
        label={src ? `Replace ${upload.label.toLowerCase()}` : upload.label}
        hint="Optional. JPEG, PNG, or WebP; maximum 5 MB. Uploaded when you save."
        accept={IMAGE_ACCEPT}
        files={files}
        onChange={onChange}
        busy={busy}
        error={error}
        compact
      />
      {files?.length ? (
        <Button
          variant="ghost"
          size="compact"
          disabled={busy}
          onClick={() => onChange(null)}
        >
          Clear selected file
        </Button>
      ) : null}
    </Stack>
  );
}
