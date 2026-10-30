import type { Detail, HistoryPage, MissionEvent } from "./types";

export const endpoint = (path: string) => `/api/backend${path}`;
export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(endpoint(path), {
    method: body === undefined ? "GET" : "POST", cache: "no-store", signal,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : `Request failed (${response.status}). Refresh and try again.`);
  }
  return response.json();
}
export const getMission = (id: string, signal?: AbortSignal) => api<Detail>(`/missions/${encodeURIComponent(id)}`, undefined, signal);
export async function history(id: string, signal?: AbortSignal): Promise<{ events: MissionEvent[]; repository: string | null }> {
  const events: MissionEvent[] = [];
  let cursor = 0;
  let repository: string | null = null;
  while (true) {
    const page = await api<HistoryPage>(`/missions/${encodeURIComponent(id)}/history?after=${cursor}&limit=100`, undefined, signal);
    events.push(...page.events);
    repository = page.repository_name;
    if (!page.has_more || page.next_cursor <= cursor) break;
    cursor = page.next_cursor;
  }
  return { events, repository };
}
