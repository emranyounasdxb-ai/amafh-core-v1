/** Local serving policy. A production edge must apply equivalent headers. */
export function securityHeaders(development: boolean) {
  return {
    "Content-Security-Policy": [
      "default-src 'self'",
      // Vite's React refresh preamble is inline in development only.
      `script-src 'self'${development ? " 'unsafe-inline'" : ""}`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      `connect-src 'self'${development ? " ws://localhost:* wss://localhost:*" : ""}`,
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ].join("; "),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
  };
}
