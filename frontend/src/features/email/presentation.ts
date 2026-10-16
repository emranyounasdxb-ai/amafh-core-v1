/** Display helpers only. Server sanitization and mailbox authorization stay authoritative. */
export function mailIdentity(value: string) {
  const first = value.trim();
  const address = first.match(/<([^>]+)>/);
  const email = address?.[1] ?? first;
  const name = address
    ? first.slice(0, address.index).trim().replace(/^"|"$/g, "")
    : "";
  const label = name || email || "Unknown sender";
  const initials = (name || email.split("@")[0] || "?")
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
  return { label, email, initials };
}

export function mailPreview(value: string) {
  const text = value.trim();
  // Header peeks may contain a truncated MIME boundary, not a decoded body.
  // Do not present protocol fragments as if they were message text.
  if (
    !text ||
    /(?:^--|content-(?:type|transfer-encoding|disposition):|mime-version:|boundary=|^=\?utf-8\?)/i.test(
      text,
    )
  )
    return "Open message to read";
  return text;
}

export function mailDate(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Dubai",
  }).format(date);
}

// Only this fixed stylesheet is permitted by the iframe's CSP. Received content
// cannot enable arbitrary inline styles, scripts, external images or fonts.
export const MAIL_DOCUMENT_STYLE =
  'body{margin:0;color:#1a171d;font:14px/1.75 "Segoe UI",Arial,sans-serif;overflow-wrap:anywhere}p{margin:0 0 16px}a{color:#5a1acf}blockquote{margin:16px 0;padding:4px 16px;border-left:3px solid #ddd7e4;color:#3e3946}ul,ol{padding-left:24px}';
