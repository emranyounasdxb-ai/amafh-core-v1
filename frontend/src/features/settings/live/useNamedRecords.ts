import type { ApiClient } from "../../../app/api/http";
import { choices } from "../../../app/api/choices";
import type { DataRecord } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { isUuid } from "../../../app/presentation/labels";

const loadNamed = (api: ApiClient, path: string, signal: AbortSignal) =>
  path.startsWith("/catalog/")
    ? choices<DataRecord>(api, path, signal)
    : api.request<DataRecord[]>(path, { signal });

/** Readable names for configuration records; never falls back to the identifier. */
export function useNamedRecords(path: string | null, refresh = 0) {
  const resource = useResource<DataRecord[]>(
    path,
    refresh,
    loadNamed,
    "settings-named",
  );
  const rows = resource.data ?? [];
  const label = (id: unknown, fallback = "Unavailable") => {
    if (!id) return "";
    const name = rows.find((row) => String(row.id) === String(id))?.name;
    if (typeof name === "string" && name.trim() && !isUuid(name)) return name;
    return resource.loading ? "Loading…" : fallback;
  };
  const options = (activeOnly = false) =>
    rows
      .filter((row) => !activeOnly || row.active !== false)
      .map((row) => ({ value: String(row.id), label: String(row.name ?? "") }));
  return { rows, label, options, loading: resource.loading };
}
