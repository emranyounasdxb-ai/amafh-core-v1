/** Password-link secrets stay in memory and never enter browser storage. */
let token: string | null = null;
let linkPath: string | null = null;

export function capturePasswordLink() {
  const url = new URL(window.location.href);
  const isLink = ["/setup-password", "/reset-password"].includes(url.pathname);
  if (!isLink) {
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
