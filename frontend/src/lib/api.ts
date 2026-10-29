import type {
  CandidateDiffResponse,
  FileContentResponse,
  HealthResponse,
  MissionDetail,
  Mission,
  MissionEvent,
  MissionReport,
  RepositoryConnectResponse,
} from "./types";

export const API_TIMEOUT_MS = 15000;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function extractDetail(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((entry) => {
          if (entry && typeof entry === "object" && "msg" in entry) {
            const msg = (entry as { msg: unknown }).msg;
            const loc = (entry as { loc?: unknown }).loc;
            const where = Array.isArray(loc) ? loc.slice(1).join(".") : "";
            return where ? `${where}: ${String(msg)}` : String(msg);
          }
          return String(entry);
        })
        .filter(Boolean);
      if (messages.length) return messages.join(" · ");
    }
    if (detail && typeof detail === "object") return JSON.stringify(detail);
  }
  if (body && typeof body === "object" && "message" in body) {
    const message = (body as { message: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}

type RequestOptions = {
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
  headers?: Record<string, string>;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal, timeoutMs = API_TIMEOUT_MS, headers = {} } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const onOuterAbort = () => controller.abort();
  signal?.addEventListener("abort", onOuterAbort);

  try {
    const response = await fetch(path, {
      method,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    const contentType = response.headers.get("content-type") ?? "";
    const isJson = contentType.toLowerCase().includes("application/json");
    const payload = isJson ? await response.json().catch(() => null) : await response.text().catch(() => "");

    if (!response.ok) {
      const detail = extractDetail(
        isJson ? payload : null,
        typeof payload === "string" && payload.trim()
          ? `Request failed with status ${response.status}`
          : `Request failed with status ${response.status}`,
      );
      throw new ApiError(response.status, detail);
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (signal?.aborted) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, "The request timed out before the backend responded.");
    }
    throw new ApiError(0, "The backend could not be reached. Check that it is running, then retry.");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onOuterAbort);
  }
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>("/api/health", { signal, timeoutMs: 6000 }),

  listMissions: (signal?: AbortSignal) => request<Mission[]>("/api/missions?limit=50", { signal }),

  getMission: (missionId: string, signal?: AbortSignal) =>
    request<MissionDetail>(`/api/missions/${encodeURIComponent(missionId)}`, { signal }),

  createMission: (input: { repository_id: string; request_text: string; criteria: string[] }) =>
    request<MissionDetail>("/api/missions", { method: "POST", body: input }),

  cancelMission: (missionId: string) =>
    request<MissionDetail>(`/api/missions/${encodeURIComponent(missionId)}/cancel`, { method: "POST" }),

  missionReport: (missionId: string, signal?: AbortSignal) =>
    request<MissionReport>(`/api/missions/${encodeURIComponent(missionId)}/report`, { signal }),

  missionEvents: (missionId: string, after = 0, signal?: AbortSignal) =>
    request<MissionEvent[]>(
      `/api/missions/${encodeURIComponent(missionId)}/events?after=${encodeURIComponent(String(after))}`,
      { signal, timeoutMs: 8000 },
    ),

  connectRepository: (path: string, signal?: AbortSignal) =>
    request<RepositoryConnectResponse>("/api/repositories/connect", {
      method: "POST",
      body: { path },
      signal,
      timeoutMs: 30000,
    }),

  repositoryTree: (repositoryId: string, signal?: AbortSignal) =>
    request<string[]>(`/api/repositories/${encodeURIComponent(repositoryId)}/tree`, { signal }),

  repositoryFile: (repositoryId: string, path: string, signal?: AbortSignal) =>
    request<FileContentResponse>(
      `/api/repositories/${encodeURIComponent(repositoryId)}/file?path=${encodeURIComponent(path)}`,
      { signal },
    ),

  candidateFile: (missionId: string, candidateId: string, path: string, signal?: AbortSignal) =>
    request<FileContentResponse>(
      `/api/missions/${encodeURIComponent(missionId)}/candidates/${encodeURIComponent(candidateId)}/file?path=${encodeURIComponent(path)}`,
      { signal },
    ),

  candidateDiff: (missionId: string, candidateId: string, repositoryId: string, signal?: AbortSignal) =>
    request<CandidateDiffResponse>(
      `/api/missions/${encodeURIComponent(missionId)}/candidates/${encodeURIComponent(candidateId)}/diff?repository_id=${encodeURIComponent(repositoryId)}`,
      { signal },
    ),
};
