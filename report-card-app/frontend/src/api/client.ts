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

// A free-tier backend host spins down after a period of inactivity, so the
// first request after a while can time out before the cold instance wakes —
// the browser surfaces that as a bare "Failed to fetch" with no indication
// it's transient. Retry a couple of times with growing delays before
// surfacing a message that actually explains what's going on.
const COLD_START_RETRY_DELAYS_MS = [8000, 15000];

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithColdStartRetry(url: string, init: RequestInit): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await fetch(url, init);
    } catch (err) {
      // Only retry genuine network-level failures (fetch throws a TypeError
      // for those) — not an aborted request or anything else.
      if (!(err instanceof TypeError) || attempt >= COLD_START_RETRY_DELAYS_MS.length) {
        throw new Error("Could not reach the server. It may be waking up after being idle — please try again in a few seconds.");
      }
      await sleep(COLD_START_RETRY_DELAYS_MS[attempt]);
    }
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = options?.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetchWithColdStartRetry(`${API_BASE}${path}`, { ...options, headers: { ...headers, ...options?.headers } });
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
  subjectAnalysisUrl: (batchId: number, subject: string) => {
    const params = new URLSearchParams({ token: getToken() ?? "", subject });
    return `${API_BASE}/batches/${batchId}/subject-analysis?${params.toString()}`;
  },
  timetablePrintUrl: (classId: number) => {
    const params = new URLSearchParams({ token: getToken() ?? "" });
    return `${API_BASE}/timetable/classes/${classId}/timetable/print?${params.toString()}`;
  },
  substitutionSheetUrl: (date: string) => {
    const params = new URLSearchParams({ token: getToken() ?? "", date });
    return `${API_BASE}/timetable/substitutions/sheet?${params.toString()}`;
  },
  uploadTemplateUrl: () => `${API_BASE}/batches/upload-template`,
  schoolPhotoPreviewUrl: () => {
    const params = new URLSearchParams({ token: getToken() ?? "" });
    return `${API_BASE}/auth/school-photo?${params.toString()}`;
  },
};

export { UnauthorizedError };
