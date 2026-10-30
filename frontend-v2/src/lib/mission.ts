import type { Agent, Detail, MissionEvent } from "./types.ts";

export const agents: { id: Agent; name: string; role: string; color: string; symbol: string }[] = [
  { id: "SHOGUN", name: "Shogun", role: "Planner", color: "#d9b66e", symbol: "将" },
  { id: "SAMURAI", name: "Samurai", role: "Developer", color: "#e6806d", symbol: "侍" },
  { id: "SENTINEL", name: "Sentinel", role: "Checks", color: "#91bbaa", symbol: "守" },
  { id: "SHADOW_COUNCIL", name: "Shadow Council", role: "Source reviewer", color: "#afa0d1", symbol: "影" },
];
export const label = (text: string) => text.toLowerCase().replaceAll("_", " ");
export const running = new Set(["PREFLIGHT", "PLANNING", "RUNNING", "CHECKING", "REPAIRING", "REVIEWING", "APPLYING", "CANCEL_REQUESTED"]);
export function mergeEvents(existing: MissionEvent[], incoming: MissionEvent[], missionId: string) {
  const map = new Map<number, MissionEvent>();
  for (const event of [...existing, ...incoming]) {
    if (event.mission_id === missionId && Number.isInteger(event.sequence) && event.sequence > 0) map.set(event.sequence, event);
  }
  return [...map.values()].sort((a, b) => a.sequence - b.sequence);
}
export function agentStatus(agent: Agent, detail: Detail, events: MissionEvent[]) {
  if (agent === "SHOGUN" && detail.mission.status === "AWAITING_CLARIFICATION") return "waiting for you";
  if (!running.has(detail.mission.status)) return "idle";
  const latest = events.filter(e => e.source === agent).at(-1);
  if (latest?.display_payload.stage === "failed") return "attention";
  if (latest?.display_payload.stage === "intent") return "working";
  if (agent === "SHOGUN" && ["PLANNING", "REPAIRING"].includes(detail.mission.status)) return "working";
  // The controller may reserve check/review tasks together before either starts.
  // A RUNNING task alone is not evidence that its character is doing work now.
  return "idle";
}

export function verifierStatus(detail: Detail, events: MissionEvent[]) {
  const { id, status, active_candidate_id } = detail.mission;
  if (!active_candidate_id) return "not started";
  const latest = events.filter(e => e.mission_id === id && e.candidate_id === active_candidate_id &&
    ["VERIFIER_STARTED", "VERIFIER_ERROR", "VERIFICATION_PASSED", "VERIFICATION_FAILED"].includes(e.event_type))
    .sort((a, b) => a.sequence - b.sequence).at(-1);
  if (latest?.event_type === "VERIFIER_ERROR") return "stopped without a verdict";
  if (latest?.event_type === "VERIFICATION_FAILED" || status === "FAILED_VERIFICATION") return "failed";
  if (latest?.event_type === "VERIFICATION_PASSED" || ["VERIFIED_AWAITING_APPROVAL", "APPLIED"].includes(status)) return "passed";
  if (status === "VERIFYING") return latest?.event_type === "VERIFIER_STARTED" ? "running" : "ready";
  return "not started";
}
export function approvalState(detail: Detail, selectedId: string) {
  const candidate = detail.candidates.find(c => c.id === selectedId);
  const current = candidate?.id === detail.mission.active_candidate_id;
  const ready = current && detail.mission.status === "VERIFIED_AWAITING_APPROVAL";
  const approved = detail.approvals.some(a => a.candidate_id === selectedId && a.candidate_fingerprint === candidate?.content_fingerprint && a.decision === "APPROVED");
  return { canApprove: Boolean(ready && candidate?.state === "FROZEN" && !approved), canApply: Boolean(ready && approved && candidate?.state === "APPROVED") };
}
export function graphLinks(detail: Detail, candidateId?: string) {
  // Only recorded inter-agent messages make edges. Never invent an execution order.
  const ids = new Set(agents.map(a => a.id as string));
  const links = new Map<string, { source: string; target: string; label: string; count: number; messageIds: string[] }>();
  for (const message of detail.messages) {
    if (candidateId && message.candidate_id !== candidateId) continue;
    if (!ids.has(message.sender) || !ids.has(message.recipient) || message.sender === message.recipient) continue;
    const key = `${message.sender}-${message.recipient}-${message.type}`;
    const old = links.get(key);
    links.set(key, { source: message.sender, target: message.recipient, label: label(message.type), count: (old?.count || 0) + 1, messageIds: [...(old?.messageIds || []), message.id] });
  }
  return [...links.entries()].map(([id, link]) => ({ id, ...link }));
}
