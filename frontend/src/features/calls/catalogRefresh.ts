export const CATALOG_POLL_MS = 5000;
export const CATALOG_READY_POLL_MS = 30000;

export type CatalogRefreshSource = {
  catalogReady: boolean;
  phase: string;
};

export function shouldPollCatalog(
  source: CatalogRefreshSource | null,
  hidden: boolean,
): boolean {
  if (hidden) return false;
  if (!source) return true;
  return source.phase !== "not_configured";
}
