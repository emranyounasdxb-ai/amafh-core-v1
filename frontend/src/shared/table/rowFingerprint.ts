// A compact stale-selection identifier; exported values always come from fresh server reads.
function canonical(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("Invalid table value");
    return Object.is(value, -0) ? "0" : value.toString();
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .filter((key) => record[key] !== undefined)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonical(record[key])}`)
      .join(",")}}`;
  }
  throw new Error("Invalid table value");
}

export function rowFingerprint(row: Record<string, unknown>): string {
  let value = 0xcbf29ce484222325n;
  for (const byte of new TextEncoder().encode(canonical(row)))
    value = ((value ^ BigInt(byte)) * 0x100000001b3n) & 0xffffffffffffffffn;
  return value.toString(16).padStart(16, "0");
}
