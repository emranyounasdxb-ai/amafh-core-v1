import type { ApiClient } from "./http";

export type ImageKind =
  "banks" | "product-types" | "product-variants" | "employee";
export type ImageUpload = { kind: ImageKind; label: string };
export type ImageRecord = {
  id: string;
  name?: string;
  fullName?: string;
  logo_file_id?: string | null;
  image_file_id?: string | null;
  avatarFileId?: string | null;
};

export const IMAGE_ACCEPT = "image/jpeg,image/png,image/webp";
export const MEDIA_UPDATED = "amafh:media-updated";

export function recordImagePath(kind: ImageKind, id: string) {
  const encoded = encodeURIComponent(id);
  return kind === "employee"
    ? `/employees/${encoded}/media/avatar`
    : `/catalog/${kind}/${encoded}/image`;
}

export function recordImageSrc(
  kind: ImageKind,
  record: ImageRecord | null | undefined,
) {
  const fileId =
    kind === "employee"
      ? record?.avatarFileId
      : kind === "banks"
        ? record?.logo_file_id
        : record?.image_file_id;
  return record?.id && fileId
    ? `/api/v1${recordImagePath(kind, record.id)}?v=${encodeURIComponent(fileId)}`
    : undefined;
}

export function imageFileError(file: File) {
  if (!IMAGE_ACCEPT.split(",").includes(file.type))
    return "Choose a JPEG, PNG, or WebP image.";
  if (!file.size || file.size > 5_000_000)
    return "Image must be between 1 and 5,000,000 bytes.";
  return "";
}

export async function uploadRecordImage(
  api: ApiClient,
  kind: ImageKind,
  id: string,
  file: File,
) {
  const body = new FormData();
  body.append("file", file);
  const result = await api.request<{ fileId: string }>(
    recordImagePath(kind, id),
    { method: "PUT", body },
  );
  window.dispatchEvent(
    new CustomEvent(MEDIA_UPDATED, { detail: { kind, id } }),
  );
  return result;
}
