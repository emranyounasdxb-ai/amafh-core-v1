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
  private generation = 0;
  private readonly pending = new Set<AbortController>();
  get sessionGeneration() {
    return this.generation;
  }
  assertSessionGeneration(generation: number) {
    if (generation !== this.generation)
      throw new DOMException("Authentication changed", "AbortError");
  }
  invalidateSession() {
    this.generation += 1;
    for (const controller of this.pending) controller.abort();
    this.pending.clear();
  }
  private readonly csrfToken: CsrfTokenProvider;
  private readonly fetcher: typeof fetch;
  private onAuthenticationLost: (code: string) => void;
  setAuthenticationLostHandler(handler: (code: string) => void) {
    this.onAuthenticationLost = handler;
  }
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
    const generation = this.generation;
    const response = await this.response(path, init);
    if (response.status === 204) return undefined as T;
    const data = (await response.json()) as T;
    this.assertSessionGeneration(generation);
    return data;
  }

  async response(path: string, init: RequestInit = {}): Promise<Response> {
    const generation = this.generation;
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
    const controller = new AbortController();
    this.pending.add(controller);
    try {
      const response = await this.fetcher(`/api/v1${path}`, {
        ...init,
        method,
        credentials: "include",
        headers,
        redirect: "error",
        signal: init.signal
          ? AbortSignal.any([init.signal, controller.signal])
          : controller.signal,
      });
      this.assertSessionGeneration(generation);
      if (!response.ok) {
        let body: unknown;
        try {
          body = await response.json();
        } catch {
          body = null;
        }
        this.assertSessionGeneration(generation);
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
    } finally {
      this.pending.delete(controller);
    }
  }
}
