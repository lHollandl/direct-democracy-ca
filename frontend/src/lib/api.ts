/**
 * The only place in the frontend that calls `fetch` (ARCHITECTURE.md §9).
 *
 * The access token is held in memory, never in localStorage, so a script on
 * another page cannot read it. The refresh token lives in an httpOnly cookie
 * the backend sets and this code can never see. A 401 triggers one silent
 * refresh and one retry; a second failure signs the person out.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

let accessToken: string | null = null;
let userId: number | null = null;
let refreshing: Promise<boolean> | null = null;

type Listener = () => void;
const listeners = new Set<Listener>();

export function onAuthChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function announce() {
  listeners.forEach((listener) => listener());
}

export function setSession(token: string | null, id: number | null) {
  accessToken = token;
  userId = id;
  announce();
}

export function currentUserId(): number | null {
  return userId;
}

export function isSignedIn(): boolean {
  return accessToken !== null;
}

export class ApiError extends Error {
  code: string;
  status: number;
  problems?: { field: string; problem: string }[];

  constructor(
    status: number,
    code: string,
    message: string,
    problems?: { field: string; problem: string }[],
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.problems = problems;
  }
}

async function raw(
  path: string,
  options: RequestInit & { json?: unknown } = {},
): Promise<Response> {
  const { json, ...rest } = options;
  const headers = new Headers(rest.headers);
  if (json !== undefined) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  return fetch(`${API_BASE}${path}`, {
    ...rest,
    headers,
    credentials: "include",
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
}

async function refreshOnce(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        setSession(null, null);
        return false;
      }
      const body = await response.json();
      setSession(body.access_token, body.user_id);
      return true;
    })().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

export async function api<T = unknown>(
  path: string,
  options: RequestInit & { json?: unknown } = {},
): Promise<T> {
  let response = await raw(path, options);

  if (response.status === 401 && !path.startsWith("/auth/")) {
    if (await refreshOnce()) {
      response = await raw(path, options);
    }
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const body = text ? JSON.parse(text) : {};

  if (!response.ok) {
    throw new ApiError(
      response.status,
      body.error ?? "unknown",
      body.message ?? "Something went wrong.",
      body.problems,
    );
  }
  return body as T;
}

export const get = <T>(path: string) => api<T>(path);
export const post = <T>(path: string, json?: unknown) =>
  api<T>(path, { method: "POST", json });
export const put = <T>(path: string, json?: unknown) =>
  api<T>(path, { method: "PUT", json });
export const patch = <T>(path: string, json?: unknown) =>
  api<T>(path, { method: "PATCH", json });
export const del = <T>(path: string, json?: unknown) =>
  api<T>(path, { method: "DELETE", json });

/** Sign in and keep the token in memory for the rest of the session. */
export async function signIn(email: string, password: string) {
  const body = await api<{ access_token: string; user_id: number; email_verified: boolean }>(
    "/auth/login",
    { method: "POST", json: { email, password } },
  );
  setSession(body.access_token, body.user_id);
  return body;
}

export async function signOut() {
  try {
    await post("/auth/logout");
  } finally {
    setSession(null, null);
  }
}

/** Called once when the app loads: the cookie may still be good. */
export async function restoreSession(): Promise<boolean> {
  if (accessToken) return true;
  return refreshOnce();
}

export function apiBase(): string {
  return API_BASE;
}

/**
 * A server-side, unauthenticated read for a Server Component (ARCHITECTURE.md
 * §9 — `api.ts` is the only file that calls `fetch`, including on the landing
 * page). Always `cache: "no-store"`, since anything a server component reads
 * here can decide what a page shows (CLAUDE.md Law 8) and must never be
 * baked into a static build. Returns `null` on any failure, so the caller can
 * fall back to wording that carries no number rather than a stale one (audit
 * demo-01 run 4, LOW).
 */
export async function serverGet<T = unknown>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}
