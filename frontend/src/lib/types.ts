export type PreflightStatus = "READY" | "WARNING" | "BLOCKED" | "CHECKING";

export type PreflightResult = {
  status: PreflightStatus;
  detected_profile: string;
  file_count: number;
  excluded_count: number;
  existing_modifications: boolean;
  warnings: string[];
  blockers: string[];
};

export type HealthResponse = {
  status: string;
  service: string;
  version: string;
  docker_available: boolean;
  model_configured: boolean;
  storage_ready: boolean;
  active_missions_count: number;
};

export type MissionStatus =
  | "CREATED"
  | "PREFLIGHT"
  | "AWAITING_CLARIFICATION"
  | "PLANNING"
  | "READY_FOR_AUTHORIZATION"
  | "RUNNING"
  | "CHECKING"
  | "REPAIRING"
  | "REVIEWING"
  | "VERIFYING"
  | "VERIFIED_AWAITING_APPROVAL"
  | "APPLYING"
  | "APPLIED"
  | "REJECTED"
  | "BLOCKED"
  | "FAILED_VERIFICATION"
  | "BUDGET_EXHAUSTED"
  | "CANCEL_REQUESTED"
  | "CANCELLED"
  | "INTERRUPTED";

export type CriterionStatus = "PENDING" | "PASS" | "FAIL" | "PARTIAL" | "NOT_VERIFIED" | "BLOCKED";

export type MissionBudgets = {
  max_repair_rounds: number;
  repair_rounds_used: number;
  max_time_seconds: number;
  time_used_seconds: number;
  max_tool_calls: number;
  tool_calls_used: number;
  max_model_turns: number;
  model_turns_used: number;
  max_tokens: number;
  input_tokens_used: number;
  output_tokens_used: number;
  max_clarifications: number;
  clarifications_used: number;
};

export type Mission = {
  id: string;
  repository_id: string;
  request_text: string;
  status: MissionStatus;
  created_at: string;
  updated_at: string;
  scope_version: number;
  active_candidate_id: string | null;
  budgets: MissionBudgets;
  unresolved_issues: string[];
  cancel_requested: boolean;
  failure_reason: string | null;
};

export type AcceptanceCriterion = {
  id: string;
  mission_id: string;
  description: string;
  verification_method: string;
  status: CriterionStatus;
  evidence_ids: string[];
  criteria_version: number;
};

export type TaskStatus = "PENDING" | "READY" | "RUNNING" | "BLOCKED" | "DONE" | "FAILED" | "CANCELLED";

export type MissionTask = {
  id: string;
  mission_id: string;
  title: string;
  description: string;
  owner_agent: string;
  dependencies: string[];
  status: TaskStatus;
  attempt: number;
  candidate_id: string | null;
  completion_condition: string | null;
  result_summary: string | null;
  evidence_ids: string[];
  created_at: string;
  updated_at: string;
};

export type MissionEvent = {
  sequence: number;
  mission_id: string;
  event_type: string;
  source: string;
  task_id: string | null;
  candidate_id: string | null;
  evidence_ids: string[];
  display_payload: Record<string, unknown>;
  created_at: string;
};

export type CandidateState = "MUTABLE" | "FROZEN" | "SUPERSEDED" | "APPROVED" | "APPLIED" | "REJECTED";

export type Candidate = {
  id: string;
  mission_id: string;
  parent_candidate_id: string | null;
  workspace_snapshot_id: string;
  content_fingerprint: string;
  changed_files: string[];
  criteria_version: number;
  state: CandidateState;
  ui_badge: string;
  created_at: string;
};

export type EvidenceKind = "TEST" | "BUILD" | "LINT" | "STATIC_SCAN" | "DIFF" | "REVIEW_FINDING" | "BASELINE";

export type Evidence = {
  id: string;
  mission_id: string;
  candidate_id: string;
  criterion_id: string | null;
  kind: EvidenceKind;
  source: string;
  command: string[];
  exit_code: number | null;
  duration_ms: number;
  stdout_artifact_id: string | null;
  stderr_artifact_id: string | null;
  fingerprint: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type EvidenceDetail = Evidence & { stdout: string; stderr: string };

export type FindingSeverity = "INFO" | "LOW" | "MEDIUM" | "HIGH" | "BLOCKING";
export type FindingStatus = "OPEN" | "IN_PROGRESS" | "RESOLVED" | "ACCEPTED_WITH_RISK" | "REJECTED";

export type Finding = {
  id: string;
  mission_id: string;
  source_agent: string;
  severity: FindingSeverity;
  title: string;
  description: string;
  file_path: string | null;
  line_start: number | null;
  line_end: number | null;
  observed_behavior: string;
  expected_behavior: string;
  evidence_ids: string[];
  candidate_id: string | null;
  status: FindingStatus;
  resolution_evidence_ids: string[];
  created_at: string;
};

export type MessageType =
  | "TASK_PROPOSAL"
  | "TASK_RESULT"
  | "FINDING"
  | "CLARIFICATION"
  | "CHECK_REQUEST"
  | "BLOCKER"
  | "HANDOFF";

export type AgentMessage = {
  id: string;
  mission_id: string;
  sender: string;
  recipient: string;
  type: MessageType;
  task_id: string | null;
  candidate_id: string | null;
  summary: string;
  payload: Record<string, unknown>;
  evidence_ids: string[];
  created_at: string;
};

export type ClarificationStatus = "OPEN" | "ANSWERED";

export type Clarification = {
  id: string;
  mission_id: string;
  question: string;
  reason: string;
  phase: "plan" | "repair";
  candidate_id: string;
  candidate_fingerprint: string;
  scope_version: number;
  status: ClarificationStatus;
  answer: string | null;
  created_at: string;
  answered_at: string | null;
};

export type ApprovalDecision = "APPROVED" | "REJECTED";

export type Approval = {
  id: string;
  mission_id: string;
  candidate_id: string;
  candidate_fingerprint: string;
  intended_action: string;
  decision: ApprovalDecision;
  decided_at: string;
  application_result_id: string | null;
};

export type MissionDetail = {
  mission: Mission;
  criteria: AcceptanceCriterion[];
  tasks: MissionTask[];
  candidates: Candidate[];
  evidence: Evidence[];
  findings: Finding[];
  messages: AgentMessage[];
  clarifications: Clarification[];
  plan_revision: number;
  approvals: Approval[];
  repository_files: string[];
};

export type PlanHistoryEntry = {
  revision: number;
  task_ids: string[];
  summary: string;
};

export type MissionReport = {
  mission: Mission;
  candidate: Candidate | null;
  criteria: AcceptanceCriterion[];
  plan_history: PlanHistoryEntry[];
  evidence: Evidence[];
  findings: Finding[];
  approvals: Approval[];
};

export type RepositoryConnectResponse = {
  repository_id: string;
  name: string;
  path: string;
  fingerprint: string;
  preflight: PreflightResult;
};

export type FileContentResponse = {
  file_path: string;
  content: string;
};

export type CandidateDiffFile = {
  file_path: string;
  change_type: string;
  diff: string;
};

export type CandidateDiffResponse = {
  candidate_id: string;
  content_fingerprint: string;
  changed_files_count: number;
  files: CandidateDiffFile[];
  unified_diff: string;
};

export type StoredRepository = {
  repository_id: string;
  name: string;
  path: string;
  fingerprint: string;
  preflight: PreflightResult;
  connected_at: number;
};

export type PatchExport = {
  filename: string;
  text: string;
};
