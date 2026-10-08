export type PermissionItem = {
  key: string;
  module: string;
  action: string;
  state: "granted" | "revoked" | "fixed" | "unavailable";
  configurable: boolean;
  dataScope: string | null;
  reason: string | null;
};

export const savedGrant = (item: PermissionItem) => item.state === "granted";

export function permissionCounts(
  items: PermissionItem[],
  drafts: Record<string, boolean> = {},
) {
  const unique = [...new Map(items.map((item) => [item.key, item])).values()];
  const counts = {
    total: unique.length,
    allowed: 0,
    disabled: 0,
    notPermitted: 0,
  };
  for (const item of unique) {
    if (item.state === "unavailable") counts.notPermitted++;
    else if (item.state === "fixed") counts.allowed++;
    else if (item.configurable && (drafts[item.key] ?? savedGrant(item)))
      counts.allowed++;
    else if (item.configurable) counts.disabled++;
    else if (savedGrant(item)) counts.allowed++;
  }
  return counts;
}
