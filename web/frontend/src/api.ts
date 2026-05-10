import type {
  BatchJob,
  BatchResult,
  BuildStatus,
  Catalog,
  DevFile,
  DevFileContent,
  SessionState,
} from "./types";

export const DEFAULT_MAP_ID = "twin_pass";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || response.statusText);
  }
  return response.json() as Promise<T>;
}

export function loadCatalog(): Promise<Catalog> {
  return request<Catalog>("/api/agents");
}

export function createSession(payload: Record<string, unknown>): Promise<SessionState> {
  return request<SessionState>("/api/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getSession(sessionId: string): Promise<SessionState> {
  return request<SessionState>(`/api/sessions/${sessionId}`);
}

export function stepSession(sessionId: string): Promise<SessionState> {
  return request<SessionState>(`/api/sessions/${sessionId}/step`, { method: "POST" });
}

export function roundSession(sessionId: string): Promise<SessionState> {
  return request<SessionState>(`/api/sessions/${sessionId}/round`, { method: "POST" });
}

export function closeSession(sessionId: string): Promise<{ closed: boolean }> {
  return request<{ closed: boolean }>(`/api/sessions/${sessionId}/close`, { method: "POST" });
}

export function runBatch(payload: Record<string, unknown>): Promise<BatchResult> {
  return request<BatchResult>("/api/lab/batch", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createBatchJob(payload: Record<string, unknown>): Promise<BatchJob> {
  return request<BatchJob>("/api/lab/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getBatchJob(jobId: string): Promise<BatchJob> {
  return request<BatchJob>(`/api/lab/jobs/${jobId}`);
}

export function cancelBatchJob(jobId: string): Promise<BatchJob> {
  return request<BatchJob>(`/api/lab/jobs/${jobId}/cancel`, { method: "POST" });
}

export function getDevStatus(): Promise<BuildStatus> {
  return request<BuildStatus>("/api/dev/status");
}

export function buildDevAgent(): Promise<BuildStatus> {
  return request<BuildStatus>("/api/dev/build", { method: "POST" });
}

export function listDevFiles(): Promise<{ files: DevFile[] }> {
  return request<{ files: DevFile[] }>("/api/dev/files");
}

export function readDevFile(path: string): Promise<DevFileContent> {
  return request<DevFileContent>(`/api/dev/files/${path}`);
}

export function writeDevFile(path: string, content: string): Promise<DevFileContent> {
  return request<DevFileContent>(`/api/dev/files/${path}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

export function createDevSession(payload: Record<string, unknown>): Promise<SessionState> {
  return request<SessionState>("/api/dev/session", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
