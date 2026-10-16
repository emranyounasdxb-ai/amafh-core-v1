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

// Fixed reader styles. Received inline formatting is sanitized on the server;
// scripts, stylesheets, images and fonts from the message cannot load remotely.
export const MAIL_DOCUMENT_STYLE =
  'body{margin:0;color:#1a171d;font:14px/1.7 "Segoe UI",Arial,sans-serif;overflow-wrap:anywhere}p{margin:0 0 16px}a{color:#5a1acf}blockquote{margin:16px 0;padding:4px 16px;border-left:3px solid #ddd7e4;color:#3e3946}ul,ol{padding-left:24px}h1,h2,h3,h4,h5,h6{line-height:1.35;margin:0 0 16px}table{max-width:100%;border-spacing:0}td,th{overflow-wrap:anywhere}pre,code,samp{white-space:pre-wrap;overflow-wrap:anywhere;font-family:Consolas,monospace}hr{border:0;border-top:1px solid #ddd7e4;margin:20px 0}';
