const key = "amafh-core:form-token";
// This token never establishes identity or scope; /auth/me and the HttpOnly
// session cookie remain authoritative on every application load.
export function readFormToken(): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}
export function writeFormToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(key, token);
    else sessionStorage.removeItem(key);
  } catch {
    /* Memory-only sessions remain usable until reload. */
  }
}

export function createFormTokenStore() {
  let token = readFormToken();
  return {
    get: () => token,
    set: (value: string | null) => {
      token = value;
      writeFormToken(value);
    },
  };
}
