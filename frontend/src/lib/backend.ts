export type MissionEvent = { sequence: number; mission_id: string; event_type: string; source: string; candidate_id: string | null; display_payload: Record<string, unknown>; created_at: string };
export type Mission = { id: string; repository_id: string; request_text: string; status: string; active_candidate_id: string | null; scope_version: number; failure_reason: string | null; budgets: { repair_rounds_used: number; max_repair_rounds: number } };
export type Candidate = { id: string; content_fingerprint: string; changed_files: string[]; state: string; ui_badge: string };
export type Evidence = { id: string; candidate_id: string; fingerprint: string; kind: string; exit_code: number | null; metadata: { classification?: string; check_profile?: string; execution_status?: string } };
export type Finding = { id: string; candidate_id: string | null; title: string; severity: string; status: string; evidence_ids: string[] };
export type Task = { id: string; title: string; owner_agent: string; status: string; attempt: number; candidate_id: string | null };
export type Criterion = { id: string; description: string; status: string; evidence_ids: string[] };
export type Clarification = { id: string; question: string; status: string };
export type Approval = { id: string; candidate_id: string; candidate_fingerprint: string; decision: string };
export type MissionDetail = { mission: Mission; tasks: Task[]; criteria: Criterion[]; candidates: Candidate[]; evidence: Evidence[]; findings: Finding[]; messages: { id: string; sender: string; recipient: string; summary: string; candidate_id: string | null }[]; clarifications: Clarification[]; approvals: Approval[]; plan_revision: number; repository_files: string[] };
export type Repository = { repository_id: string; name: string; preflight: { status: string; detected_profile: string; file_count: number; existing_modifications: boolean; warnings: string[]; blockers: string[] } };

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...options, cache: "no-store", headers: { Accept: "application/json", ...(options?.body ? { "Content-Type": "application/json" } : {}), ...options?.headers } });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function activeCandidate(detail: MissionDetail): Candidate | undefined {
  return detail.candidates.find((candidate) => candidate.id === detail.mission.active_candidate_id);
}

export function checkedCandidate(detail: MissionDetail): boolean {
  const candidate = activeCandidate(detail);
  if (!candidate) return false;
  const checks = detail.evidence.filter((item) => item.candidate_id === candidate.id && item.fingerprint === candidate.content_fingerprint && item.metadata.check_profile);
  return checks.length > 0 && checks.every((item) => item.exit_code === 0 && item.metadata.execution_status === "SUCCEEDED");
}

export function approvedCandidate(detail: MissionDetail): boolean {
  const candidate = activeCandidate(detail);
  return !!candidate && detail.approvals.some((item) => item.candidate_id === candidate.id && item.candidate_fingerprint === candidate.content_fingerprint && item.decision === "APPROVED");
}

export const terminalStatuses = new Set(["APPLIED", "REJECTED", "CANCELLED", "BLOCKED", "FAILED_VERIFICATION", "BUDGET_EXHAUSTED", "INTERRUPTED"]);

export function sequenceUpdate(previous: number, received: number): "duplicate" | "next" | "gap" {
  if (!Number.isSafeInteger(received) || received < 1 || received <= previous) return "duplicate";
  return received === previous + 1 ? "next" : "gap";
}

export function eventSummary(event: MissionEvent): string {
  const value = event.display_payload?.summary;
  return typeof value === "string" && value.trim() ? value.slice(0, 360) : event.event_type;
}
