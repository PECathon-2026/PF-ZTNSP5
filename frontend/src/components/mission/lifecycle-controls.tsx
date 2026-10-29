"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import type { MissionDetail } from "@/lib/types";
import { Modal } from "./modal";
import "./mission-tools.css";

type Decision = "authorize" | "approve" | "reject" | "apply";

export function LifecycleControls({ detail, onChange }: { detail: MissionDetail; onChange: () => void }) {
  const { mission, candidates, clarifications, messages } = detail;
  const candidate = candidates.find((item) => item.id === mission.active_candidate_id);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [autoRepair, setAutoRepair] = useState(true);
  const [answer, setAnswer] = useState("");
  const [confirmation, setConfirmation] = useState<{ action: Decision; candidateId?: string; fingerprint?: string; scopeVersion: number } | null>(null);
  const question = clarifications.find((item) => item.status === "OPEN");
  const proposal = [...messages].reverse().find((item) => item.type === "TASK_PROPOSAL");

  async function run(label: string, operation: () => Promise<unknown>) {
    setBusy(label); setError(null); setNotice("");
    try { await operation(); setConfirmation(null); setNotice(`${label} recorded by the backend.`); }
    catch (caught) { setError(caught instanceof Error ? caught.message : `${label} could not be recorded.`); }
    finally { setBusy(null); onChange(); }
  }

  function confirm(action: Decision) {
    setError(null);
    setConfirmation({ action, candidateId: candidate?.id, fingerprint: candidate?.content_fingerprint, scopeVersion: mission.scope_version });
  }

  async function decide() {
    if (!confirmation) return;
    const captured = confirmation;
    if (captured.action === "authorize") {
      await run("Authorization", () => api.authorizeMission(mission.id, { scope_version: captured.scopeVersion, auto_repair: autoRepair }));
    } else if (captured.candidateId && captured.fingerprint) {
      if (captured.action === "apply") await run("Application", () => api.applyCandidate(mission.id, captured.candidateId!));
      else await run(captured.action === "approve" ? "Approval" : "Rejection", () => api.approveCandidate(mission.id, {
        candidate_id: captured.candidateId!, candidate_fingerprint: captured.fingerprint!,
        decision: captured.action === "approve" ? "APPROVED" : "REJECTED",
      }));
    }
  }

  async function downloadPatch() {
    await run("Patch export", async () => {
      const patch = await api.missionPatch(mission.id);
      const url = URL.createObjectURL(new Blob([patch.text], { type: "text/x-diff" }));
      const link = document.createElement("a"); link.href = url; link.download = patch.filename; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }

  const b = mission.budgets;
  const budgets = [
    ["Active seconds", Math.round(b.time_used_seconds ?? 0), b.max_time_seconds],
    ["Tool calls", b.tool_calls_used, b.max_tool_calls],
    ["Model turns", b.model_turns_used, b.max_model_turns],
    ["Tokens", (b.input_tokens_used ?? 0) + (b.output_tokens_used ?? 0), b.max_tokens],
    ["Repair rounds", b.repair_rounds_used, b.max_repair_rounds],
    ["Clarifications", b.clarifications_used ?? 0, b.max_clarifications ?? 0],
  ] as const;

  return <section className="panel mission-control" aria-labelledby="mission-control-title">
    <div className="panel-head"><h2 className="panel-title" id="mission-control-title">MISSION CONTROL</h2>
      <span className="mono muted">scope {mission.scope_version} · plan revision {detail.plan_revision}</span></div>
    <div className="mission-control__body">
      {mission.failure_reason && <p className="field-error" role="status">{mission.failure_reason}</p>}
      {mission.status === "PLANNING" && <div className="mission-gate"><div><h3>Brief recorded. Begin planning.</h3>
        <p>The guild freezes a baseline, runs checks, and asks Shogun for a plan. Docker and a configured model are required.</p></div>
        <button className="btn btn--primary" disabled={Boolean(busy)} onClick={() => void run("Planning", () => api.planMission(mission.id))}>Start planning</button></div>}
      {mission.status === "PREFLIGHT" && <p role="status">Baseline preparation and checks are in progress. Waiting for recorded results.</p>}
      {mission.status === "READY_FOR_AUTHORIZATION" && <div className="mission-gate"><div><h3>Review the plan. Authorize this scope.</h3>
        <p>{proposal?.summary ?? "Review the acceptance criteria and task dependencies below before authorizing execution."}</p>
        <label><input type="checkbox" checked={autoRepair} onChange={(event) => setAutoRepair(event.target.checked)} /> Allow adaptive repairs within the recorded budgets</label></div>
        <button className="btn btn--primary" disabled={Boolean(busy)} onClick={() => confirm("authorize")}>Authorize execution</button></div>}
      {mission.status === "AWAITING_CLARIFICATION" && question && <form className="mission-question" onSubmit={(event) => {
        event.preventDefault(); if (!answer.trim()) return;
        void run("Clarification", () => api.answerClarification(mission.id, { question_id: question.id, answer: answer.trim() }));
      }}><h3>{question.question}</h3><p>{question.reason}</p>
        <label htmlFor={`answer-${question.id}`}>Your answer · {question.phase} checkpoint</label>
        <textarea id={`answer-${question.id}`} value={answer} onChange={(event) => setAnswer(event.target.value)} required maxLength={4000} rows={3} />
        <button className="btn btn--primary" disabled={Boolean(busy)}>Submit answer and resume</button></form>}
      {mission.status === "VERIFYING" && <div className="mission-gate"><div><h3>Ready for independent verification</h3><p>The deterministic verifier binds criteria to evidence from this frozen candidate.</p></div>
        <button className="btn btn--primary" disabled={Boolean(busy)} onClick={() => void run("Verification", () => api.verifyMission(mission.id))}>Verify candidate</button></div>}
      {candidate && <div className="mission-candidate"><div><h3>{candidate.ui_badge} · {candidate.state}</h3>
        <p className="mission-fingerprint mono">{candidate.id} · {candidate.content_fingerprint}</p>
        <p>{candidate.changed_files.length} changed file{candidate.changed_files.length === 1 ? "" : "s"} · criteria version {candidate.criteria_version}</p></div>
        <div className="mission-actions"><Link className="btn btn--ghost" href={`/missions/${mission.id}/forge`}>Review diff</Link>
          <button className="btn btn--ghost" disabled={Boolean(busy)} onClick={() => void downloadPatch()}>Export patch</button>
          {mission.status === "VERIFIED_AWAITING_APPROVAL" && candidate.state === "FROZEN" && <>
            <button className="btn btn--primary" disabled={Boolean(busy)} onClick={() => confirm("approve")}>Approve candidate</button>
            <button className="btn btn--danger" disabled={Boolean(busy)} onClick={() => confirm("reject")}>Reject candidate</button></>}
          {mission.status === "VERIFIED_AWAITING_APPROVAL" && candidate.state === "APPROVED" &&
            <button className="btn btn--primary" disabled={Boolean(busy) || candidate.changed_files.length !== 1} onClick={() => confirm("apply")}>Apply approved change</button>}
        </div>
        {candidate.state === "APPROVED" && candidate.changed_files.length !== 1 && <p className="muted">Atomic application requires exactly one changed file. Export the patch to review and apply a multi-file change.</p>}
      </div>}
      {!candidate && <p className="muted">No active candidate. Approval becomes available after a frozen candidate passes independent verification.</p>}
      <div className="mission-budgets">{budgets.map(([label, used, max]) => <div key={label}>
        <label>{label}<span className="mono">{used.toLocaleString()} / {(max ?? 0).toLocaleString()}</span></label>
        <progress aria-label={label} value={used} max={Math.max(max ?? 0, 1)} /></div>)}</div>
      <p role="status" className="muted">{busy ? `${busy}…` : notice}</p>
      {error && !confirmation && <p role="alert" className="field-error">{error}</p>}
    </div>
    {confirmation && <Modal title={`${confirmation.action === "authorize" ? "Authorize execution" : confirmation.action === "apply" ? "Apply approved change" : confirmation.action === "approve" ? "Approve candidate" : "Reject candidate"}?`} onClose={() => { if (!busy) setConfirmation(null); }}>
      <p>{confirmation.action === "authorize" ? "Authorize bounded execution in the disposable workspace for this scope. The original repository is changed only by a separate approved apply action."
        : confirmation.action === "apply" ? "Apply the approved single-file change to the original repository. The backend rechecks the baseline, scope, and fingerprint before replacement."
        : confirmation.action === "approve" ? "Record approval for this exact frozen fingerprint. Applying the change is a separate action."
        : "Reject this candidate and end the mission. Recorded evidence remains available."}</p>
      <p className="mission-fingerprint mono">Scope {confirmation.scopeVersion}<br />{confirmation.candidateId}<br />{confirmation.fingerprint}</p>
      {error && <p role="alert" className="field-error">{error}</p>}
      <div className="dialog-actions"><button className="btn btn--quiet" disabled={Boolean(busy)} onClick={() => setConfirmation(null)}>Go back</button>
        <button className={confirmation.action === "reject" ? "btn btn--danger" : "btn btn--primary"} disabled={Boolean(busy)} onClick={() => void decide()}>{busy ? "Recording…" : "Confirm"}</button></div>
    </Modal>}
  </section>;
}
