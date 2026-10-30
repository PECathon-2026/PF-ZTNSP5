/** Public backend contracts, kept separate from display state. */
export type Agent = "SHOGUN" | "SAMURAI" | "SENTINEL" | "SHADOW_COUNCIL";
export interface Mission {
  id: string; repository_id: string; request_text: string; status: string;
  created_at: string; scope_version: number; active_candidate_id: string | null;
  failure_reason: string | null;
  budgets: { repair_rounds_used: number; max_repair_rounds: number; tool_calls_used: number; max_tool_calls: number; model_turns_used: number; max_model_turns: number; input_tokens_used?: number; output_tokens_used?: number; max_tokens?: number; time_used_seconds?: number; max_time_seconds?: number };
}
export interface Task {
  id: string; title: string; description: string; owner_agent: Agent; status: string;
  attempt: number; dependencies: string[]; candidate_id: string | null;
  evidence_ids: string[]; result_summary: string | null;
}
export interface Candidate { id: string; state: string; content_fingerprint: string; changed_files: string[]; parent_candidate_id: string | null }
export interface Criterion { id: string; description: string; status: string; evidence_ids: string[]; verification_method: string }
export interface Finding {
  id: string; candidate_id: string; source_agent: string; title: string; description: string;
  severity: string; status: string; file_path: string | null; line_start?: number | null; evidence_ids: string[];
}
export interface Evidence {
  id: string; candidate_id: string; fingerprint: string; source: string; kind: string;
  command: string[] | null; exit_code: number | null; duration_ms: number | null;
  criterion_id: string | null; metadata: Record<string, unknown>; stdout?: string; stderr?: string;
}
export interface Message {
  id: string; sender: string; recipient: string; type: string; summary: string;
  candidate_id: string | null; evidence_ids: string[]; payload: Record<string, unknown>;
}
export interface MissionEvent {
  sequence: number; mission_id: string; event_type: string; source?: string;
  task_id?: string | null; candidate_id?: string | null; evidence_ids?: string[];
  created_at?: string; display_payload: { summary?: string; stage?: string; action?: string; relative_path?: string; status?: string; [key: string]: unknown };
}
export interface Detail {
  own_api_key?: boolean; api_key_ready?: boolean;
  mission: Mission; tasks: Task[]; criteria: Criterion[]; candidates: Candidate[];
  evidence: Evidence[]; findings: Finding[]; messages: Message[]; plan_revision: number;
  repository_files: string[];
  clarifications: { id: string; question: string; reason: string; status: string }[];
  approvals: { candidate_id: string; candidate_fingerprint: string; decision: string }[];
  acceptance_test_proposal?: { status?: string; proposal_hash?: string; hash?: string; [key: string]: unknown } | null;
}
export interface HistoryPage { events: MissionEvent[]; next_cursor: number; has_more: boolean; repository_name: string | null }
export interface Repo { repository_id: string; name: string; path: string; preflight: { status: string; blockers: string[]; warnings: string[]; file_count: number } }
export interface Health { docker_available: boolean; model_configured: boolean; storage_ready: boolean }
