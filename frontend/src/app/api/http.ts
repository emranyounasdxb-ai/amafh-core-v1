export type ApiValidationErrors = Record<string, string[]>;

export class ApiFailure extends Error {
  readonly code: string;
  readonly status: number;
  readonly fieldErrors: ApiValidationErrors;
  constructor(
    code: string,
    message: string,
    status: number,
    fieldErrors: ApiValidationErrors = {},
  ) {
    super(message);
    this.name = "ApiFailure";
    this.code = code;
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

export type CsrfTokenProvider = () => { header: string; value: string } | null;

export class ApiClient {
  private readonly csrfToken: CsrfTokenProvider;
  private readonly fetcher: typeof fetch;
  private readonly onAuthenticationLost: (code: string) => void;
  private readonly onForbidden: () => void;
  constructor(
    csrfToken: CsrfTokenProvider,
    fetcher: typeof fetch = fetch,
    onAuthenticationLost: (code: string) => void = () => {},
    onForbidden: () => void = () => {},
  ) {
    this.csrfToken = csrfToken;
    this.fetcher = (...args) => fetcher(...args);
    this.onAuthenticationLost = onAuthenticationLost;
    this.onForbidden = onForbidden;
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await this.response(path, init);
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  async response(path: string, init: RequestInit = {}): Promise<Response> {
    if (!path.startsWith("/") || path.startsWith("//")) {
      throw new Error("API path must be a same-origin absolute path");
    }
    const method = (init.method ?? "GET").toUpperCase();
    const requestToken = this.csrfToken()?.value;
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (typeof init.body === "string")
      headers.set("Content-Type", "application/json");
    const publicCommand =
      method === "POST" &&
      ["/auth/login", "/auth/setup", "/auth/reset"].includes(path);
    if (!["GET", "HEAD", "OPTIONS"].includes(method) && !publicCommand) {
      const token = this.csrfToken();
      if (!token) {
        throw new ApiFailure(
          "CSRF_UNAVAILABLE",
          "The secure form token is unavailable. Please reload or sign in again.",
          0,
        );
      }
      headers.set(token.header, token.value);
    }
    const response = await this.fetcher(`/api/v1${path}`, {
      ...init,
      method,
      credentials: "include",
      headers,
      redirect: "error",
    });
    if (!response.ok) {
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        body = null;
      }
      const error =
        body && typeof body === "object"
          ? (body as Record<string, unknown>)
          : {};
      if (
        (response.status === 401 || error.code === "CSRF_INVALID") &&
        !publicCommand &&
        this.csrfToken()?.value === requestToken
      )
        this.onAuthenticationLost(
          typeof error.code === "string" ? error.code : "AUTH_REQUIRED",
        );
      if (response.status === 403 && error.code === "FORBIDDEN")
        this.onForbidden();
      throw new ApiFailure(
        typeof error.code === "string" ? error.code : "API_ERROR",
        typeof error.message === "string"
          ? error.message
          : `Request failed (${response.status})`,
        response.status,
        error.fieldErrors && typeof error.fieldErrors === "object"
          ? (error.fieldErrors as ApiValidationErrors)
          : {},
      );
    }
    return response;
  }
}
