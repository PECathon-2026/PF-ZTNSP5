"use client";

import { useState } from "react";
import { Code2, ArrowUpRight, ShieldCheck } from "lucide-react";
import type { MissionDetail } from "@/lib/types";
import { LifecycleControls } from "@/components/mission/lifecycle-controls";

type Props = { detail: MissionDetail; path: string | null; content: string | null | undefined; language: string; onEvidence: (id: string) => void; onLine: (line: number) => void; onRefresh: () => void };
const VIEWS = ["File context", "Proof", "Controls"] as const;

export function FileContext({ detail, path, content, language, onEvidence, onLine, onRefresh }: Props) {
  const [view, setView] = useState<typeof VIEWS[number]>("File context");
  const [line, setLine] = useState("1");
  const lines = content == null ? 0 : content.split("\n").length;
  const findings = detail.findings.filter((finding) => finding.file_path === path);
  const candidate = detail.candidates.find((item) => item.id === detail.mission.active_candidate_id);
  return <aside className="file-context" aria-label="File inspector">
    <div className="file-context-head mono"><Code2 size={15} /> ENGINEERING DESK</div>
    <div className="file-context-tabs" role="tablist" aria-label="File inspector view">{VIEWS.map((item, index) => <button key={item} role="tab" id={`file-context-tab-${index}`} aria-selected={view === item} tabIndex={view === item ? 0 : -1} aria-controls="file-context-panel" onClick={() => setView(item)} onKeyDown={(event) => { if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return; event.preventDefault(); const next = (index + (event.key === "ArrowRight" ? 1 : -1) + 3) % 3; setView(VIEWS[next]); document.getElementById(`file-context-tab-${next}`)?.focus(); }}>{item}</button>)}</div>
    <div className="file-context-scroll" tabIndex={0} id="file-context-panel" role="tabpanel" aria-labelledby={`file-context-tab-${VIEWS.indexOf(view)}`}>
      {view === "Controls" ? <LifecycleControls detail={detail} onChange={onRefresh} /> : view === "Proof" ? <>
        <p className="dossier-kind mono">CANDIDATE &amp; EVIDENCE</p><h2 className="dossier-title">The proof desk</h2>
        <p className="dossier-description">{candidate ? `${candidate.ui_badge} · ${candidate.changed_files.length} changed files` : "No active candidate. Baseline evidence is still available for inspection."}</p>
        {candidate && <p className="dossier-fingerprint mono">{candidate.content_fingerprint}</p>}
        {detail.evidence.map((record) => <button className="dossier-reference" key={record.id} onClick={() => onEvidence(record.id)}>{record.kind} · {record.source}<ArrowUpRight size={13} /></button>)}
        {!detail.evidence.length && <p className="dossier-empty">No recorded checks for this mission.</p>}
      </> : <>
        <p className="dossier-kind mono">CURRENT WORKING SURFACE</p><h2 className="dossier-title">{path?.split("/").pop() ?? "Open a file"}</h2><p className="file-context-path mono">{path ?? "Choose a source file from the explorer."}</p>
        <div className="file-facts"><div><strong>{lines || "—"}</strong><span>lines</span></div><div><strong>{language}</strong><span>language</span></div></div>
        {lines > 0 && <form className="file-line-jump" onSubmit={(event) => { event.preventDefault(); onLine(Math.min(lines, Math.max(1, Number(line) || 1))); }}><label htmlFor="file-line">Jump to line</label><div><input id="file-line" type="number" min={1} max={lines} value={line} onChange={(event) => setLine(event.target.value)} required /><button type="submit">Go <ArrowUpRight size={13} /></button></div></form>}
        <div className="dossier-section"><h3>Review annotations <span>{findings.length}</span></h3>{findings.length ? findings.map((finding) => <div key={finding.id} className="file-finding"><span className="mono">{finding.severity} · line {finding.line_start ?? "?"}</span><h3>{finding.title}</h3><p>{finding.description}</p>{finding.line_start && <button className="text-link" onClick={() => onLine(finding.line_start!)}>Reveal source location →</button>}{finding.evidence_ids.map((id) => <button key={id} className="dossier-reference" onClick={() => onEvidence(id)}>Inspect evidence<ArrowUpRight size={13} /></button>)}</div>) : <p className="dossier-empty">{path ? "No review findings are recorded for this file." : "Annotations follow the file you select."}</p>}</div>
      </>}
    </div>
    <footer className="file-context-footer"><ShieldCheck size={14} /><span>Read-only source inspection</span></footer>
  </aside>;
}
