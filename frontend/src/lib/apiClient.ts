/** Typed fetch wrapper: bearer token in memory, single refresh-on-401, error envelope parsing. */

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: { fields?: Record<string, string[]> } & Record<string, unknown>;
  request_id?: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: ApiErrorBody,
  ) {
    super(body.message);
  }
  get fieldErrors(): Record<string, string[]> {
    return this.body.details?.fields ?? {};
  }
  /** Message safe and helpful to show a user. Server messages already explain business-rule errors. */
  get userMessage(): string {
    switch (this.body.code) {
      case "INVALID_STATE":
        return "This record was changed by someone else, so the action could not be applied. Refresh the page to see its latest state.";
      case "DUPLICATE_BANK_REFERENCE":
        return "That bank reference number has already been used on another deposit. Check the reference on your deposit slip.";
      case "ALREADY_SUBMITTED":
        return "Some of these collections were already submitted. Refresh to see what is left to submit.";
      case "SUBMISSION_NOT_ELIGIBLE":
        return "One or more submissions can no longer be deposited (not approved, or already deposited). Refresh and select again.";
      case "THROTTLED":
        return `Too many attempts. Please wait ${this.body.details?.wait ?? "a few"} seconds and try again.`;
      case "UNAUTHENTICATED":
        return "Your session has expired. Please sign in again.";
      case "FORBIDDEN":
        return "You do not have permission to do this.";
      case "IDEMPOTENCY_KEY_REUSED":
        return "This request was already sent with different details. Please start the action again.";
      case "SERVER_ERROR":
        return `Something went wrong on our side.${this.body.request_id ? ` If it keeps happening, quote reference ${this.body.request_id}.` : ""}`;
      default:
        return this.body.message;
    }
  }
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

let accessToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;
let onSessionExpired: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}
export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler;
}

const CLIENT_HEADER = { "X-CMRS-Client": "web" };

async function parseError(res: Response): Promise<ApiError> {
  let body: ApiErrorBody;
  try {
    body = await res.json();
  } catch {
    body = { code: "HTTP_ERROR", message: `Request failed (${res.status})` };
  }
  return new ApiError(res.status, body);
}

export async function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const res = await fetch("/api/v1/auth/refresh/", { method: "POST", headers: CLIENT_HEADER });
      if (!res.ok) {
        accessToken = null;
        return null;
      }
      const data = await res.json();
      accessToken = data.access;
      return data.access as string;
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  idempotencyKey?: string;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(`/api/v1${path}`, window.location.origin);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }
  const send = () => {
    const headers: Record<string, string> = {};
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
    return fetch(url, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  };

  let res = await send();
  if (res.status === 401 && !path.startsWith("/auth/")) {
    const token = await refreshAccessToken();
    if (token) {
      res = await send();
    } else {
      onSessionExpired?.();
    }
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const clientHeader = CLIENT_HEADER;

/** Download a CSV through the authenticated client (the bearer token lives in memory, not in a cookie). */
export async function downloadCsv(path: string, query: Record<string, string | undefined>, filename: string) {
  const url = new URL(`/api/v1${path}`, window.location.origin);
  for (const [k, v] of Object.entries(query)) if (v) url.searchParams.set(k, v);
  const get = () => fetch(url, { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} });
  let res = await get();
  if (res.status === 401 && (await refreshAccessToken())) res = await get();
  if (!res.ok) throw await parseError(res);
  const blob = await res.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}
