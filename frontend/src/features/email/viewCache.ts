/** Ephemeral view data only. Each EmailPage owns its caches; nothing is persisted. */
export class MailViewCache<T> {
  private readonly values = new Map<
    string,
    { value: T; expires: number; bytes: number }
  >();
  private bytes = 0;
  private readonly maxEntries: number;
  private readonly maxBytes: number;
  private readonly ttl: number;
  constructor(maxEntries: number, maxBytes: number, ttl = 60_000) {
    this.maxEntries = maxEntries;
    this.maxBytes = maxBytes;
    this.ttl = ttl;
  }
  get(key: string): T | null {
    const entry = this.values.get(key);
    return entry && entry.expires > Date.now() ? entry.value : null;
  }
  /** Retained view only: callers must still revalidate with the server. */
  peek(key: string): T | null {
    const entry = this.values.get(key);
    if (!entry) return null;
    // Keep recently viewed mail, rather than frequently refreshed pages alone.
    this.values.delete(key);
    this.values.set(key, entry);
    return entry.value;
  }
  set(key: string, value: T) {
    this.delete(key);
    const bytes = JSON.stringify(value).length * 2;
    if (bytes > this.maxBytes / 2) return;
    this.values.set(key, { value, expires: Date.now() + this.ttl, bytes });
    this.bytes += bytes;
    while (this.values.size > this.maxEntries || this.bytes > this.maxBytes) {
      const first = this.values.keys().next().value;
      if (first === undefined) break;
      this.delete(first);
    }
  }
  delete(key: string) {
    const entry = this.values.get(key);
    if (entry) this.bytes -= entry.bytes;
    this.values.delete(key);
  }
  clear() {
    this.values.clear();
    this.bytes = 0;
  }
}
