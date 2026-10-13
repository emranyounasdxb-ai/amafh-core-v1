/** Password-link secrets stay in memory and never enter browser storage. */
let token: string | null = null;
let linkPath: string | null = null;

export function passwordLinkKind() {
  if (window.location.pathname === "/setup-password") return "setup";
  if (window.location.pathname === "/reset-password") return "reset";
  return null;
}

export function capturePasswordLink() {
  const url = new URL(window.location.href);
  if (!passwordLinkKind()) {
    clearPasswordLink();
    return;
  }
  if (url.searchParams.has("token")) {
    token = url.searchParams.get("token");
    linkPath = url.pathname;
    url.searchParams.delete("token");
    window.history.replaceState(
      window.history.state,
      "",
      url.pathname + url.search + url.hash,
    );
  } else if (linkPath !== url.pathname) {
    clearPasswordLink();
  }
}

export function passwordLinkToken() {
  return linkPath === window.location.pathname ? token : null;
}

export function clearPasswordLink() {
  token = null;
  linkPath = null;
}
