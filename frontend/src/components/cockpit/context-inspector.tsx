"use client";

import Link from "next/link";
import { PanelRightClose, ArrowUpRight } from "lucide-react";
import { GUILD, criterionMeta, taskMeta } from "@/lib/status";
import type { MissionDetail } from "@/lib/types";
import { LifecycleControls } from "@/components/mission/lifecycle-controls";
import type { NodeKind } from "./map-model";

export type Selection = { kind: NodeKind; entityId: string };
type Props = { detail: MissionDetail; selection: Selection; tab: "inspect" | "controls"; onTab: (tab: "inspect" | "controls") => void; onClose: () => void; onChange: () => void; onSelect: (kind: NodeKind, id: string) => void; onEvidence: (id: string) => void };

export function ContextInspector({ detail, selection, tab, onTab, onClose, onChange, onSelect, onEvidence }: Props) {
  const { mission } = detail;
  const role = GUILD.find((item) => item.id === selection.entityId);
  const task = detail.tasks.find((item) => item.id === selection.entityId);
  const candidate = detail.candidates.find((item) => item.id === selection.entityId);
  const evidence = detail.evidence.find((item) => item.id === selection.entityId);
  const finding = detail.findings.find((item) => item.id === selection.entityId);
  const title = selection.kind === "mission" ? "Mission brief" : selection.kind === "agent" ? role?.name : selection.kind === "task" ? task?.title : selection.kind === "candidate" ? "Candidate snapshot" : selection.kind === "evidence" ? evidence?.kind : finding?.title;

  function evidenceLinks(ids: string[]) {
    return ids.map((id) => <button key={id} className="dossier-reference" onClick={() => onEvidence(id)}>◎ {id}<ArrowUpRight size={13} /></button>);
  }
  function taskList(owner?: string) {
    const tasks = owner ? detail.tasks.filter((item) => item.owner_agent === owner) : detail.tasks;
    return tasks.length ? <ul className="dossier-task-list">{tasks.map((item) => <li key={item.id}><button onClick={() => onSelect("task", item.id)}><span className="status" data-tone={taskMeta(item.status).tone}>{item.status}</span><strong>{item.title}</strong><ArrowUpRight size={13} /></button></li>)}</ul> : <p className="dossier-empty">No task assignments recorded yet.</p>;
  }

  return <aside className="context-inspector" aria-label="Contextual inspector">
    <header className="dossier-header"><span className="mono">CONTEXT / DOSSIER</span><button className="cockpit-icon-button" aria-label="Hide inspector" onClick={onClose}><PanelRightClose size={17} /></button></header>
    <div className="dossier-tabs" role="tablist" aria-label="Inspector view">{(["inspect", "controls"] as const).map((item) => <button key={item} role="tab" id={`dossier-tab-${item}`} aria-selected={tab === item} aria-controls="dossier-panel" tabIndex={tab === item ? 0 : -1} onClick={() => onTab(item)} onKeyDown={(event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault(); const next = item === "inspect" ? "controls" : "inspect"; onTab(next); document.getElementById(`dossier-tab-${next}`)?.focus();
    }}>{item === "inspect" ? "Inspect" : "Mission controls"}</button>)}</div>
    <div className="dossier-scroll" key={tab === "controls" ? "controls" : `${selection.kind}:${selection.entityId}`} id="dossier-panel" role="tabpanel" aria-labelledby={`dossier-tab-${tab}`}>
      {tab === "controls" ? <LifecycleControls detail={detail} onChange={onChange} /> : <>
        <p className="dossier-kind mono">{selection.kind} / {selection.entityId}</p><h2 className="dossier-title">{title ?? "Item unavailable"}</h2>
        {selection.kind === "mission" && <>
          <p className="dossier-description">{mission.request_text}</p>
          {mission.failure_reason && <div className="dossier-blocker"><strong>Mission blocked</strong><p>{mission.failure_reason}</p><button className="text-link" onClick={() => onTab("controls")}>Inspect mission controls →</button></div>}
          <div className="dossier-section"><h3>Acceptance gate <span>{detail.criteria.filter((item) => item.status === "PASS").length}/{detail.criteria.length}</span></h3>
            {detail.criteria.length ? <ul className="dossier-criteria">{detail.criteria.map((item) => <li key={item.id}><span className="status" data-tone={criterionMeta(item.status).tone}>{criterionMeta(item.status).glyph}</span><div><p>{item.description}</p><span className="mono muted">{criterionMeta(item.status).label}</span>{evidenceLinks(item.evidence_ids)}</div></li>)}</ul> : <p className="dossier-empty">No acceptance criteria recorded.</p>}
          </div>
          <div className="dossier-section"><h3>Recorded work <span>{detail.tasks.length}</span></h3>{taskList()}</div>
        </>}
        {selection.kind === "agent" && role && <>
          <p className="dossier-role">{role.role}</p><p className="dossier-description">{role.purpose}</p>
          <div className="dossier-section"><h3>Owned tasks <span>{detail.tasks.filter((item) => item.owner_agent === role.id).length}</span></h3>{taskList(role.id)}</div>
          <div className="dossier-section"><h3>Recorded messages</h3>{detail.messages.filter((item) => item.sender === role.id).length ? detail.messages.filter((item) => item.sender === role.id).slice(-5).map((item) => <p key={item.id} className="dossier-message">{item.summary}</p>) : <p className="dossier-empty">This role has not sent a message for this mission.</p>}</div>
          <Link className="dossier-reference" href={`/missions/${mission.id}/forge`}>Open engineering workspace<ArrowUpRight size={14} /></Link>
        </>}
        {selection.kind === "task" && task && <>
          <span className="status" data-tone={taskMeta(task.status).tone}>{task.status}</span><p className="dossier-description">{task.description}</p>
          <dl className="dossier-properties"><div><dt>Owner</dt><dd>{task.owner_agent}</dd></div><div><dt>Attempt</dt><dd>{task.attempt}</dd></div><div><dt>Candidate</dt><dd>{task.candidate_id ?? "None recorded"}</dd></div></dl>
          <div className="dossier-section"><h3>Result</h3><p>{task.result_summary ?? task.completion_condition ?? "No result has been recorded."}</p></div>
          <div className="dossier-section"><h3>Depends on</h3>{task.dependencies.length ? task.dependencies.map((id) => <button className="dossier-reference" key={id} onClick={() => onSelect("task", id)}>{detail.tasks.find((item) => item.id === id)?.title ?? id}<ArrowUpRight size={13} /></button>) : <p className="dossier-empty">No prerequisites.</p>}</div>
          <div className="dossier-section"><h3>Evidence</h3>{task.evidence_ids.length ? evidenceLinks(task.evidence_ids) : <p className="dossier-empty">No evidence bound to this task.</p>}</div>
        </>}
        {selection.kind === "candidate" && candidate && <>
          <span className="status" data-tone={candidate.ui_badge === "VERIFIED" ? "jade" : "gold"}>{candidate.ui_badge}</span>
          <p className="dossier-description">A snapshot bound to criteria version {candidate.criteria_version}. State: {candidate.state}.</p>
          <div className="dossier-section"><h3>Content fingerprint</h3><p className="dossier-fingerprint mono">{candidate.content_fingerprint}</p></div>
          <div className="dossier-section"><h3>Changed files <span>{candidate.changed_files.length}</span></h3>{candidate.changed_files.map((file) => <Link key={file} className="dossier-reference" href={`/missions/${mission.id}/forge?file=${encodeURIComponent(file)}`}>{file}<ArrowUpRight size={13} /></Link>)}</div>
          <Link className="btn btn--primary" href={`/missions/${mission.id}/forge`}>Review candidate diff</Link>
          <button className="dossier-reference" onClick={() => onTab("controls")}>Verification &amp; approval<ArrowUpRight size={13} /></button>
        </>}
        {selection.kind === "evidence" && evidence && <>
          <p className="dossier-role">{evidence.source}</p><p className="dossier-description">Recorded against candidate {evidence.candidate_id}.</p>
          <dl className="dossier-properties"><div><dt>Exit code</dt><dd>{evidence.exit_code ?? "Not recorded"}</dd></div><div><dt>Duration</dt><dd>{evidence.duration_ms} ms</dd></div></dl>
          <div className="dossier-section"><h3>Command</h3><pre className="dossier-code">{evidence.command.join(" ") || "No command recorded"}</pre></div>
          <p className="dossier-fingerprint mono">{evidence.fingerprint}</p>
          <button className="btn btn--primary" onClick={() => onEvidence(evidence.id)}>Inspect recorded output</button>
        </>}
        {selection.kind === "finding" && finding && <>
          <span className="status" data-tone={finding.severity === "HIGH" || finding.severity === "BLOCKING" ? "red" : "warn"}>{finding.severity}</span>
          <p className="dossier-description">{finding.description}</p>
          <div className="dossier-section"><h3>Observed</h3><p>{finding.observed_behavior}</p></div>
          <div className="dossier-section"><h3>Expected</h3><p>{finding.expected_behavior}</p></div>
          {finding.file_path && <Link className="dossier-reference" href={`/missions/${mission.id}/forge?file=${encodeURIComponent(finding.file_path)}`}>{finding.file_path}:{finding.line_start ?? "?"}<ArrowUpRight size={13} /></Link>}
          {evidenceLinks(finding.evidence_ids)}
        </>}
        {!title && <p className="dossier-empty">The selected item is no longer in the latest mission response. Select another node or refresh.</p>}
      </>}
    </div>
    <footer className="dossier-footer mono">scope {mission.scope_version} <span>revision {detail.plan_revision}</span></footer>
  </aside>;
}
