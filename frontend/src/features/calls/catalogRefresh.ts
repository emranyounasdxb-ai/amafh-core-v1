export const CATALOG_POLL_MS = 5000;

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
  if (!source.catalogReady) return true;
  return source.phase === "indexing" || source.phase === "updating" || source.phase === "offline";
}
