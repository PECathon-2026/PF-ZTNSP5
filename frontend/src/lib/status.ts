import type { CriterionStatus, MissionStatus, PreflightStatus, TaskStatus } from "./types";

export const GUILD = [
  {
    id: "SHOGUN",
    name: "SHOGUN",
    role: "Planner",
    glyph: "◇",
    purpose: "Reads the request, surveys the repository, and decomposes the mission into tasks with acceptance criteria.",
  },
  {
    id: "SAMURAI",
    name: "SAMURAI",
    role: "Developer",
    glyph: "/",
    purpose: "Implements and repairs the change inside an isolated workspace, then freezes it as a candidate.",
  },
  {
    id: "SENTINEL",
    name: "SENTINEL",
    role: "Tester",
    glyph: "◎",
    purpose: "Runs authorized checks, investigates failures, and reruns them against the current candidate.",
  },
  {
    id: "SHADOW_COUNCIL",
    name: "SHADOW COUNCIL",
    role: "Reviewer",
    glyph: "◈",
    purpose: "Inspects diffs for regressions, correctness, and security concerns, filing structured findings.",
  },
] as const;

export const VERIFIER_IDENTITY = {
  name: "INDEPENDENT VERIFIER",
  role: "Verification process",
  glyph: "核",
  purpose: "Deterministically checks acceptance criteria against recorded evidence. Not an LLM agent.",
};

export type StageKey = "plan" | "build" | "test" | "review" | "verify" | "approve";

export const LIFECYCLE: { key: StageKey; label: string; detail: string }[] = [
  { key: "plan", label: "Plan", detail: "Shogun decomposes the request" },
  { key: "build", label: "Build", detail: "Samurai proposes a candidate" },
  { key: "test", label: "Test", detail: "Sentinel runs the checks" },
  { key: "review", label: "Review", detail: "Shadow Council files findings" },
  { key: "verify", label: "Verify", detail: "Deterministic evidence check" },
  { key: "approve", label: "Approve", detail: "You decide what lands" },
];

const STAGE_BY_STATUS: Record<MissionStatus, StageKey> = {
  CREATED: "plan",
  PREFLIGHT: "plan",
  AWAITING_CLARIFICATION: "plan",
  PLANNING: "plan",
  READY_FOR_AUTHORIZATION: "plan",
  RUNNING: "build",
  CHECKING: "test",
  REPAIRING: "build",
  REVIEWING: "review",
  VERIFYING: "verify",
  FAILED_VERIFICATION: "verify",
  VERIFIED_AWAITING_APPROVAL: "approve",
  APPLYING: "approve",
  APPLIED: "approve",
  REJECTED: "approve",
  BLOCKED: "plan",
  BUDGET_EXHAUSTED: "build",
  CANCEL_REQUESTED: "plan",
  CANCELLED: "plan",
  INTERRUPTED: "plan",
};

const TERMINAL: MissionStatus[] = ["APPLIED", "REJECTED", "CANCELLED", "BLOCKED", "BUDGET_EXHAUSTED", "INTERRUPTED"];

export function stageOf(status: MissionStatus): StageKey {
  return STAGE_BY_STATUS[status] ?? "plan";
}

export function isTerminal(status: MissionStatus): boolean {
  return TERMINAL.includes(status);
}

const MISSION_META: Record<MissionStatus, { label: string; tone: string; glyph: string }> = {
  CREATED: { label: "CREATED", tone: "plain", glyph: "◇" },
  PREFLIGHT: { label: "PREFLIGHT", tone: "info", glyph: "◇" },
  AWAITING_CLARIFICATION: { label: "AWAITING CLARIFICATION", tone: "warn", glyph: "?" },
  PLANNING: { label: "PLANNING", tone: "info", glyph: "◇" },
  READY_FOR_AUTHORIZATION: { label: "READY FOR AUTHORIZATION", tone: "gold", glyph: "◆" },
  RUNNING: { label: "RUNNING", tone: "gold", glyph: "◆" },
  CHECKING: { label: "CHECKING", tone: "info", glyph: "◎" },
  REPAIRING: { label: "REPAIRING", tone: "warn", glyph: "／" },
  REVIEWING: { label: "REVIEWING", tone: "info", glyph: "◈" },
  VERIFYING: { label: "VERIFYING", tone: "info", glyph: "核" },
  VERIFIED_AWAITING_APPROVAL: { label: "AWAITING APPROVAL", tone: "jade", glyph: "核" },
  APPLYING: { label: "APPLYING", tone: "gold", glyph: "◆" },
  APPLIED: { label: "APPLIED", tone: "jade", glyph: "✓" },
  REJECTED: { label: "REJECTED", tone: "red", glyph: "×" },
  BLOCKED: { label: "BLOCKED", tone: "red", glyph: "×" },
  FAILED_VERIFICATION: { label: "FAILED VERIFICATION", tone: "red", glyph: "×" },
  BUDGET_EXHAUSTED: { label: "BUDGET EXHAUSTED", tone: "warn", glyph: "!" },
  CANCEL_REQUESTED: { label: "CANCEL REQUESTED", tone: "warn", glyph: "!" },
  CANCELLED: { label: "CANCELLED", tone: "plain", glyph: "×" },
  INTERRUPTED: { label: "INTERRUPTED", tone: "warn", glyph: "!" },
};

export function missionMeta(status: MissionStatus) {
  return MISSION_META[status] ?? { label: status, tone: "plain", glyph: "◇" };
}

const CRITERION_META: Record<CriterionStatus, { label: string; tone: string; glyph: string }> = {
  PENDING: { label: "NOT VERIFIED", tone: "plain", glyph: "○" },
  PASS: { label: "PASS", tone: "jade", glyph: "✓" },
  FAIL: { label: "FAIL", tone: "red", glyph: "×" },
  PARTIAL: { label: "PARTIAL", tone: "warn", glyph: "◐" },
  NOT_VERIFIED: { label: "NOT VERIFIED", tone: "plain", glyph: "○" },
  BLOCKED: { label: "BLOCKED", tone: "red", glyph: "×" },
};

export function criterionMeta(status: CriterionStatus) {
  return CRITERION_META[status] ?? { label: status, tone: "plain", glyph: "○" };
}

const TASK_META: Record<TaskStatus, { label: string; tone: string }> = {
  PENDING: { label: "PENDING", tone: "plain" },
  READY: { label: "READY", tone: "info" },
  RUNNING: { label: "RUNNING", tone: "gold" },
  BLOCKED: { label: "BLOCKED", tone: "red" },
  DONE: { label: "DONE", tone: "jade" },
  FAILED: { label: "FAILED", tone: "red" },
  CANCELLED: { label: "CANCELLED", tone: "plain" },
};

export function taskMeta(status: TaskStatus) {
  return TASK_META[status] ?? { label: status, tone: "plain" };
}

const PREFLIGHT_META: Record<PreflightStatus, { label: string; tone: string; glyph: string }> = {
  CHECKING: { label: "CHECKING", tone: "info", glyph: "…" },
  READY: { label: "READY", tone: "jade", glyph: "✓" },
  WARNING: { label: "WARNING", tone: "warn", glyph: "!" },
  BLOCKED: { label: "BLOCKED", tone: "red", glyph: "×" },
};

export function preflightMeta(status: PreflightStatus) {
  return PREFLIGHT_META[status] ?? { label: status, tone: "plain", glyph: "?" };
}

const EVENT_LABELS: Record<string, string> = {
  MISSION_CREATED: "Mission initialized",
  MISSION_CANCELLED: "Mission cancelled",
  REQUIREMENTS_ANALYZED: "Requirements analyzed",
  REPOSITORY_INSPECTED: "Repository inspected",
  TASK_ASSIGNED: "Task assigned",
  FILE_READ: "File read",
  TOOL_EXECUTED: "Tool executed",
  CHANGE_PROPOSED: "Change proposed",
  CANDIDATE_CREATED: "Candidate frozen",
  CANDIDATE_UPDATED: "Candidate updated",
  TEST_STARTED: "Checks started",
  TEST_FAILED: "Check failed",
  TESTS_RERUN: "Checks rerun",
  REVIEW_FINDING: "Review finding filed",
  REPAIR_REQUESTED: "Repair requested",
  VERIFICATION_COMPLETED: "Verification completed",
  APPROVAL_REQUESTED: "Approval requested",
  APPROVAL_RECORDED: "Approval recorded",
  CANDIDATE_APPLIED: "Candidate applied",
  RUN_BLOCKED: "Run blocked",
  RUN_FAILED: "Run failed",
};

export function eventLabel(eventType: string): string {
  const known = EVENT_LABELS[eventType];
  if (known) return known;
  return eventType
    .toLowerCase()
    .split("_")
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1) : word))
    .join(" ");
}

export function eventTone(eventType: string): string {
  if (/_FAILED$|^RUN_FAILED$|BLOCKED$|REJECTED$/.test(eventType)) return "red";
  if (/_COMPLETED$|APPLIED$|RECORDED$/.test(eventType)) return "jade";
  if (/_RERUN$|REPAIR_REQUESTED$|CANCELLED$/.test(eventType)) return "warn";
  if (/_CREATED$|_ASSIGNED$|_PROPOSED$/.test(eventType)) return "gold";
  return "info";
}

export function agentFromSource(source: string): string {
  return source.toUpperCase().replace(/\s+/g, "_");
}

export function formatInstant(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function formatClock(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

export function formatRelative(iso: string, now = Date.now()): string {
  const date = new Date(iso).getTime();
  if (Number.isNaN(date)) return "unknown";
  const delta = Math.max(0, now - date) / 1000;
  if (delta < 45) return "just now";
  if (delta < 90) return "1 min ago";
  if (delta < 3600) return `${Math.round(delta / 60)} min ago`;
  if (delta < 86400) return `${Math.round(delta / 3600)} h ago`;
  return `${Math.round(delta / 86400)} d ago`;
}

export function formatElapsed(fromIso: string, now = Date.now()): string {
  const from = new Date(fromIso).getTime();
  if (Number.isNaN(from)) return "—";
  const total = Math.max(0, Math.floor((now - from) / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

export function basename(path: string): string {
  const trimmed = path.replace(/[\\/]+$/, "");
  const parts = trimmed.split(/[\\/]/);
  return parts[parts.length - 1] || trimmed || path;
}

export function shortPath(path: string, segments = 2): string {
  if (!path) return "—";
  const parts = path.split(/[\\/]/).filter(Boolean);
  if (parts.length <= segments + 1) return path;
  return `…/${parts.slice(-segments).join("/")}`;
}

export function fileGlyph(path: string): string {
  const name = basename(path).toLowerCase();
  if (name === "readme.md" || name.startsWith("readme")) return "◆";
  if (name.endsWith(".md")) return "❖";
  if (name.endsWith(".py")) return "▲";
  if (name.endsWith(".ts") || name.endsWith(".tsx")) return "◇";
  if (name.endsWith(".js") || name.endsWith(".jsx") || name.endsWith(".mjs")) return "◇";
  if (name.endsWith(".json")) return "▣";
  if (name.endsWith(".css") || name.endsWith(".scss")) return "▤";
  if (name.endsWith(".html")) return "▣";
  if (name.endsWith(".yml") || name.endsWith(".yaml") || name.endsWith(".toml")) return "▤";
  if (name.endsWith(".sh")) return "▸";
  if (name.endsWith(".sql")) return "▦";
  if (name.endsWith(".gitignore") || name.startsWith(".")) return "·";
  return "▪";
}

export function languageOf(path: string): string {
  const name = basename(path).toLowerCase();
  if (name.endsWith(".py")) return "python";
  if (name.endsWith(".ts") || name.endsWith(".tsx")) return "typescript";
  if (name.endsWith(".js") || name.endsWith(".jsx") || name.endsWith(".mjs") || name.endsWith(".cjs")) return "javascript";
  if (name.endsWith(".json")) return "json";
  if (name.endsWith(".css") || name.endsWith(".scss")) return "css";
  if (name.endsWith(".html")) return "html";
  if (name.endsWith(".md")) return "markdown";
  if (name.endsWith(".yml") || name.endsWith(".yaml")) return "yaml";
  if (name.endsWith(".toml")) return "toml";
  if (name.endsWith(".sh")) return "shell";
  if (name.endsWith(".sql")) return "sql";
  if (name.endsWith(".txt")) return "plaintext";
  return "plaintext";
}
