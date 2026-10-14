const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const TOKEN_KEY = "reportcard_app_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

class UnauthorizedError extends Error {}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = options?.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers: { ...headers, ...options?.headers } });
  if (res.status === 401) {
    setToken(null);
    throw new UnauthorizedError("Not authenticated");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "POST", body: data ? JSON.stringify(data) : undefined }),
  put: <T>(path: string, data?: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(data) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
  /** Token passed as a query param too — used for <iframe src>/<a href>
   * navigations, which can't carry an Authorization header. */
  reportUrl: (batchId: number, studentIds?: number[]) => {
    const params = new URLSearchParams({ token: getToken() ?? "" });
    if (studentIds && studentIds.length) params.set("ids", studentIds.join(","));
    return `${API_BASE}/batches/${batchId}/report?${params.toString()}`;
  },
};

export { UnauthorizedError };
