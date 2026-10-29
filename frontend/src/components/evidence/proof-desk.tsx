"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowLeft, ArrowUpRight, Fingerprint, FileCheck2 } from "lucide-react";
import { useMissionDetail, useMissionEvents, useMissionReport } from "@/lib/use-missions";
import { briefFromMission, useMissionBriefSync } from "@/components/shell/mission-context";
import { LifecycleControls } from "@/components/mission/lifecycle-controls";
import { EvidenceDetail } from "@/components/mission/evidence-detail";
import { ActivityDock } from "@/components/cockpit/activity-dock";
import { criterionMeta, missionMeta } from "@/lib/status";
import "@/components/cockpit/cockpit.css";
import "./proof-desk.css";

const VIEWS = ["Acceptance gate", "Recorded checks", "Review findings", "Plan history"] as const;

export function ProofDesk({ missionId }: { missionId: string }) {
  const state = useMissionDetail(missionId);
  const reportState = useMissionReport(missionId);
  const { detail, mission, reload } = state;
  const stream = useMissionEvents(missionId, Boolean(mission) && !state.notFound, reload);
  const [view, setView] = useState<typeof VIEWS[number]>("Acceptance gate");
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const brief = useMemo(() => mission ? briefFromMission(mission) : null, [mission]);
  useMissionBriefSync(brief);
  if (!detail || !mission || state.notFound) return <div className="cockpit-unavailable"><FileCheck2 size={40} /><h1>{state.notFound ? "Mission not found" : state.loading ? "Opening the proof desk" : "Evidence could not be read"}</h1><p role="status">{state.error ?? "Reading recorded criteria and evidence…"}</p><Link className="btn btn--ghost" href="/missions">Back to missions</Link></div>;
  const passed = detail.criteria.filter((item) => item.status === "PASS").length;
  const failed = detail.criteria.filter((item) => item.status === "FAIL" || item.status === "BLOCKED").length;
  const counts = [detail.criteria.length, detail.evidence.length, detail.findings.length, reportState.report?.plan_history.length ?? 0];
  const active = detail.candidates.find((item) => item.id === mission.active_candidate_id);
  const inspect = (id: string) => <button key={id} className="proof-reference" onClick={() => setEvidenceId(id)}>Inspect evidence <ArrowUpRight size={12} /></button>;

  return <div className="proof-desk">
    <header className="cockpit-toolbar"><div className="cockpit-mission-id"><Link href={`/missions/${missionId}`} className="cockpit-icon-button" aria-label="Return to mission field"><ArrowLeft size={17} /></Link><div><span className="mono">INDEPENDENT VERIFICATION</span><h1>Proof before approval.</h1></div><span className="status" data-tone={missionMeta(mission.status).tone}>{missionMeta(mission.status).label}</span></div><div className="cockpit-toolbar-actions"><Link className="btn btn--ghost btn--sm" href={`/missions/${missionId}/forge`}>Review source<ArrowUpRight size={14} /></Link><Link className="btn btn--primary btn--sm" href={`/missions/${missionId}`}>Mission field<ArrowUpRight size={14} /></Link></div></header>
    <div className="proof-desk-body"><section className="proof-sheet" aria-label="Recorded proof sheet"><div className="proof-sheet-header"><div className="proof-seal" aria-hidden="true">核</div><div><span className="mono">ACCEPTANCE REGISTER</span><h2>Evidence earns the verdict.</h2><p>Recorded outcomes, bound to an exact candidate.</p></div><div className="proof-tally"><strong>{passed}<small>/{detail.criteria.length}</small></strong><span>criteria passed</span></div></div>
      <div className="proof-sheet-meta mono"><span>{missionId}</span><span>scope {mission.scope_version}</span><span>{failed} failed / blocked</span><span>{active ? `candidate ${active.id}` : "no active candidate"}</span></div>
      <div className="proof-views" role="tablist" aria-label="Proof desk view">{VIEWS.map((item, index) => <button key={item} role="tab" id={`proof-tab-${index}`} aria-selected={view === item} aria-controls="proof-panel" tabIndex={view === item ? 0 : -1} onClick={() => setView(item)} onKeyDown={(event) => { if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return; event.preventDefault(); const next = (index + (event.key === "ArrowRight" ? 1 : -1) + 4) % 4; setView(VIEWS[next]); document.getElementById(`proof-tab-${next}`)?.focus(); }}>{item}<span className="mono">{counts[index]}</span></button>)}</div>
      <div className="proof-paper-scroll" tabIndex={0} id="proof-panel" role="tabpanel" aria-labelledby={`proof-tab-${VIEWS.indexOf(view)}`}>
        {state.error && <p className="proof-refresh-error" role="alert">{state.error}<button onClick={reload}>Retry</button></p>}
        {view === "Acceptance gate" && (detail.criteria.length ? <ol className="proof-criteria">{detail.criteria.map((criterion, index) => <li key={criterion.id}><span className="proof-record-number mono">{String(index + 1).padStart(2, "0")}</span><div><h3>{criterion.description}</h3><p className="mono">{criterion.verification_method} · criteria version {criterion.criteria_version}</p><div className="proof-record-evidence">{criterion.evidence_ids.length ? criterion.evidence_ids.map(inspect) : <span>Awaiting bound evidence</span>}</div></div><span className="proof-outcome mono" data-status={criterion.status}>{criterionMeta(criterion.status).label}</span></li>)}</ol> : <div className="proof-none"><FileCheck2 size={35} /><h3>No acceptance criteria recorded</h3><p>Criteria appear when a mission brief or plan defines its acceptance gate.</p></div>)}
        {view === "Recorded checks" && (detail.evidence.length ? <ul className="proof-checks">{detail.evidence.map((record) => <li key={record.id}><div className="proof-check-head"><span className="mono">{record.kind}</span><span>{record.source}</span><span className="proof-outcome mono" data-status={record.exit_code === 0 ? "PASS" : record.exit_code === null ? "PENDING" : "FAIL"}>{record.exit_code === null ? "NO EXIT CODE" : `EXIT ${record.exit_code}`}</span></div><pre>{record.command.join(" ") || "No command recorded"}</pre><div className="proof-check-meta mono"><span>{record.duration_ms} ms</span><span>{record.candidate_id}</span><span>{record.fingerprint.slice(0, 16)}…</span></div><button className="proof-reference" onClick={() => setEvidenceId(record.id)}>Inspect recorded output<ArrowUpRight size={13} /></button></li>)}</ul> : <div className="proof-none"><FileCheck2 size={35} /><h3>No check evidence recorded</h3><p>Baseline and candidate runs will appear here with their actual commands and results.</p></div>)}
        {view === "Review findings" && (detail.findings.length ? <ul className="proof-findings">{detail.findings.map((finding) => <li key={finding.id}><span className="proof-outcome mono" data-status={finding.severity === "HIGH" || finding.severity === "BLOCKING" ? "FAIL" : "PENDING"}>{finding.severity} · {finding.status}</span><h3>{finding.title}</h3><p>{finding.description}</p><details><summary>Observed and expected behavior</summary><p><strong>Observed:</strong> {finding.observed_behavior}</p><p><strong>Expected:</strong> {finding.expected_behavior}</p></details>{finding.file_path && <Link className="proof-reference" href={`/missions/${missionId}/forge?file=${encodeURIComponent(finding.file_path)}`}>{finding.file_path}:{finding.line_start ?? "?"}<ArrowUpRight size={13} /></Link>}{finding.evidence_ids.map(inspect)}</li>)}</ul> : <div className="proof-none"><FileCheck2 size={35} /><h3>No review findings recorded</h3><p>The reviewer records observed behavior and evidence here after inspecting a candidate.</p></div>)}
        {view === "Plan history" && (reportState.error ? <div className="proof-none"><h3>Plan history could not be read</h3><p>{reportState.error}</p><button className="proof-reference" onClick={reportState.reload}>Retry history</button></div> : reportState.loading && !reportState.report ? <p role="status">Reading plan history…</p> : reportState.report?.plan_history.length ? <ol className="proof-history">{reportState.report.plan_history.map((entry) => <li key={entry.revision}><span className="mono">REVISION {entry.revision} · {entry.task_ids.length} TASKS</span><h3>{entry.summary}</h3></li>)}</ol> : <div className="proof-none"><h3>No plan revisions recorded</h3><p>Authorized planning and repair revisions appear here as the guild records them.</p></div>)}
      </div>
      <footer className="proof-sheet-footer mono"><Fingerprint size={14} />{active ? active.content_fingerprint : "No candidate fingerprint is bound yet."}</footer>
    </section><aside className="proof-controls" aria-label="Verification and approval"><div className="proof-controls-heading mono">HUMAN DECISION GATE</div><div className="proof-controls-scroll" tabIndex={0}><LifecycleControls detail={detail} onChange={() => { reload(); reportState.reload(); }} /></div></aside></div>
    <ActivityDock stream={stream} onEvidence={setEvidenceId} />
    {evidenceId && <EvidenceDetail key={evidenceId} missionId={missionId} evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />}
  </div>;
}
