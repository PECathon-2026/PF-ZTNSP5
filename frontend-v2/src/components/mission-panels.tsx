"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, Check, ChevronRight, FileCode2, ShieldCheck, X } from "lucide-react";
import { Badge, Empty } from "./ui";
import { api } from "@/lib/api";
import { agents, label } from "@/lib/mission";
import type { Detail, Evidence, MissionEvent } from "@/lib/types";
import { evidenceDisplay } from "@/lib/evidence-display";

export function ActivityList({ events, onEvidence }: { events: MissionEvent[]; onEvidence: (id: string) => void }) {
  return <div className="activity-list">{!events.length && <Empty title="No recorded activity yet"/>}{[...events].reverse().map(event => <article key={event.sequence} className="activity-item"><div className={`activity-dot ${event.display_payload.stage === "failed" ? "failed" : ""}`}/><div><div className="activity-meta"><strong>{agents.find(a => a.id === event.source)?.name || event.source || "System"}</strong><span>#{event.sequence}</span><time>{event.created_at ? new Date(event.created_at).toLocaleTimeString() : ""}</time></div><p>{event.display_payload.summary || label(event.event_type)}</p>{event.display_payload.relative_path && <code>{event.display_payload.relative_path}</code>}<div className="inline-links">{event.evidence_ids?.map(id => <button key={id} onClick={() => onEvidence(id)}>Evidence <ChevronRight size={12}/></button>)}</div></div></article>)}</div>;
}

export function TaskCriteria({ detail, onEvidence, onFile }: { detail: Detail; onEvidence: (id: string) => void; onFile: (path: string, line?: number, candidate?: string) => void }) {
  return <aside className="task-panel">
    <h3 className="panel-heading">MISSION SCOPE <span>r{detail.plan_revision}</span></h3>
    <details open><summary>Acceptance criteria <span>{detail.criteria.length}</span></summary>{detail.criteria.map(c => <article className="criterion" key={c.id}><Badge value={c.status}/><p>{c.description}</p><details><summary className="small-text">Test mapping</summary><code>{c.verification_method}</code></details>{c.evidence_ids.map(id => <button key={id} className="text-link" onClick={() => onEvidence(id)}>View proof <ArrowRight size={12}/></button>)}</article>)}</details>
    <details open><summary>Tasks <span>{detail.tasks.length}</span></summary>{detail.tasks.map(t => <article className="task-card" key={t.id}><div><span className="muted small-text">{agents.find(a => a.id === t.owner_agent)?.name || t.owner_agent} · attempt {t.attempt}</span><Badge value={t.status}/></div><h4>{t.title}</h4><p>{t.description}</p>{t.result_summary && <p>{t.result_summary}</p>}</article>)}</details>
    <details open><summary>Findings <span>{detail.findings.length}</span></summary>{!detail.findings.length && <p className="muted small-text">No findings recorded.</p>}{detail.findings.map(f => <article className="finding-card" key={f.id}><Badge value={f.status === "RESOLVED" ? "RESOLVED" : f.severity}/><h4>{f.title}</h4><p>{f.description}</p>
      {f.file_path && <button className="text-link" onClick={() => onFile(f.file_path!, f.line_start || undefined, f.candidate_id)}><FileCode2 size={13}/>{f.file_path}{f.line_start ? `:${f.line_start}` : ""}</button>}
      <div className="inline-links">{f.evidence_ids.map(id => <button key={id} onClick={() => onEvidence(id)}>Evidence <ChevronRight size={12}/></button>)}</div>
    </article>)}</details>
  </aside>;
}

export function EvidenceList({ detail, candidateId, onEvidence }: { detail: Detail; candidateId: string; onEvidence: (id: string) => void }) {
  const items = detail.evidence.filter(e => e.candidate_id === candidateId);
  const candidate = detail.candidates.find(c => c.id === candidateId);
  return <div className="evidence-list">{!items.length && <Empty title="No evidence for this candidate">Checks and reviews appear here when the backend records them.</Empty>}{items.map(e => {
    const display = evidenceDisplay(e);
    const stale = e.fingerprint !== candidate?.content_fingerprint;
    return <button className="evidence-row" key={e.id} onClick={() => onEvidence(e.id)}><ShieldCheck size={18}/><div><strong>{display.title}</strong><span>{e.source} · {display.controlled ? "Controlled test fixture · " : ""}{e.id}</span>{display.selector && <code>{display.selector}</code>}</div><span className={`evidence-result ${stale ? "stale" : ""}`}>{stale ? "Stale binding" : display.result}</span><ChevronRight size={16}/></button>;
  })}</div>;
}

export function EvidenceDrawer({ id, missionId, onClose }: { id: string; missionId: string; onClose: () => void }) {
  const [data, setData] = useState<Evidence | null>(null);
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    const abort = new AbortController(); setData(null); setError("");
    api<Evidence>(`/missions/${missionId}/evidence/${id}`, undefined, abort.signal).then(setData).catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [id, missionId]);
  return <dialog ref={dialog} className="evidence-dialog" onCancel={onClose} aria-labelledby="evidence-title"><div className="drawer-heading"><div><span className="eyebrow">EXECUTION RECORD</span><h2 id="evidence-title">Evidence</h2></div><button className="icon-button" onClick={onClose} aria-label="Close evidence"><X/></button></div>{error && <p className="error-banner">{error}</p>}{data ? <><p className="mono muted">{data.id}</p><div className="evidence-facts"><span>Source <strong>{data.source}</strong></span><span>Exit code <strong>{data.exit_code ?? "Not applicable"}</strong></span><span>Duration <strong>{data.duration_ms == null ? "Not recorded" : `${data.duration_ms} ms`}</strong></span></div><h3>Candidate fingerprint</h3><code className="fingerprint">{data.fingerprint}</code><h3>Command</h3><pre>{data.command?.join(" ") || "No command for this record"}</pre><h3>Standard output</h3><pre>{data.stdout || "No output recorded"}</pre><h3>Standard error</h3><pre>{data.stderr || "No error output recorded"}</pre><details><summary>Structured metadata</summary><pre>{JSON.stringify(data.metadata, null, 2)}</pre></details></> : !error && <p>Loading evidence…</p>}</dialog>;
}

export function MissionActions({ detail, events, busy, act }: { detail: Detail; events: MissionEvent[]; busy: boolean; act: (action: string, body?: unknown) => Promise<void> }) {
  const [answer, setAnswer] = useState("");
  const [autoRepair, setAutoRepair] = useState(true);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [keyVerified, setKeyVerified] = useState(false);
  const [keyError, setKeyError] = useState("");
  const connectionDraft = useRef({ apiKey, baseUrl });
  connectionDraft.current = { apiKey, baseUrl };
  const checkingKey = useRef(false);
  async function testKey() {
    if (checkingKey.current) return;
    checkingKey.current = true;
    const submitted = connectionDraft.current;
    setKeyError(""); setKeyVerified(false);
    try {
      await api("/model-config/validate", { api_key: apiKey.trim(), ...(baseUrl.trim() ? { base_url: baseUrl.trim() } : {}) });
      if (connectionDraft.current.apiKey === submitted.apiKey && connectionDraft.current.baseUrl === submitted.baseUrl) setKeyVerified(true);
    }
    catch (e) { setKeyError((e as Error).message); }
    finally { checkingKey.current = false; }
  }
  const m = detail.mission;
  const question = detail.clarifications.find(q => q.status === "OPEN");
  const proposal = detail.acceptance_test_proposal;
  if (detail.own_api_key && !detail.api_key_ready && ["PLANNING", "READY_FOR_AUTHORIZATION", "AWAITING_CLARIFICATION", "BUDGET_EXHAUSTED", "BLOCKED", "INTERRUPTED", "FAILED_VERIFICATION", "REPAIRING"].includes(m.status)) return <section className="action-banner"><div><span className="eyebrow">YOUR MODEL CONNECTION IS REQUIRED</span><h3>Re-enter your key and base URL for this mission.</h3><p>The credentials stay in backend memory and are not saved across restarts. The server key will not be used for this mission.</p></div><form onSubmit={e => { e.preventDefault(); if (keyVerified) void act("credentials", { api_key: apiKey.trim(), ...(baseUrl.trim() ? { base_url: baseUrl.trim() } : {}) }); }}><label htmlFor="reenter-base-url">Model base URL (optional if backend endpoint is configured)</label><input id="reenter-base-url" aria-label="Mission model base URL" type="url" maxLength={2048} value={baseUrl} onChange={e => { setBaseUrl(e.target.value); setKeyVerified(false); }}/><label htmlFor="reenter-api-key">API key</label><input id="reenter-api-key" aria-label="Mission API key" type="password" autoComplete="off" spellCheck={false} maxLength={4096} required value={apiKey} onChange={e => { setApiKey(e.target.value); setKeyVerified(false); }}/><button type="button" className="button" disabled={busy || !apiKey.trim()} onClick={() => void testKey()}>Test connection</button>{keyVerified && <p role="status">Connection verified.</p>}{keyError && <p role="alert" className="error-banner">{keyError}</p>}<button className="button primary" disabled={busy || !keyVerified}>Use verified connection</button></form></section>;
  if (m.status === "AWAITING_CLARIFICATION" && question) return <section className="action-banner"><div><span className="eyebrow">SHOGUN NEEDS YOUR INPUT</span><h3>{question.question}</h3><p>{question.reason}</p></div><form onSubmit={e => { e.preventDefault(); act("clarifications", { question_id: question.id, answer: answer.trim() }); }}><input aria-label="Clarification answer" required value={answer} onChange={e => setAnswer(e.target.value)} placeholder="Your answer…"/><button className="button primary" disabled={busy || !answer.trim()}>Send answer <ArrowRight size={14}/></button></form></section>;
  if (m.status === "READY_FOR_AUTHORIZATION") return <section className="action-banner"><div><span className="eyebrow">THE PLAN IS READY</span><h3>Review the tasks and acceptance checks.</h3><p>Authorization allows bounded work in a disposable workspace.</p>{proposal && !proposal.accepted && <details className="test-proposal" open><summary>Review proposed acceptance tests</summary><p>These expectations require your decision before execution.</p><pre>{JSON.stringify(proposal.proposal, null, 2)}</pre><div className="button-row"><button disabled={busy} className="button" onClick={() => act("acceptance-tests/review", { proposal_hash: proposal.hash, accept: true })}>Accept test expectations</button><button disabled={busy} className="button danger" onClick={() => act("acceptance-tests/review", { proposal_hash: proposal.hash, accept: false })}>Decline</button></div></details>}</div><div className="authorization-controls"><label className="check-label"><input type="checkbox" checked={autoRepair} onChange={e => setAutoRepair(e.target.checked)}/> Allow bounded auto-repair</label><button className="button primary" disabled={busy || Boolean(proposal && !proposal.accepted)} onClick={() => act("authorize", { scope_version: m.scope_version, auto_repair: autoRepair })}>Authorize workspace work <Check size={16}/></button></div></section>;
  if (m.status === "VERIFYING") return <section className="action-banner"><div><span className="eyebrow">SOURCE REVIEW AND CHECKS RECORDED</span><h3>Run independent evidence verification.</h3><p>Shadow Council reviewed the code; the independent verifier checks the recorded tests and findings. It is not another AI reviewer.</p></div><button disabled={busy} className="button primary" onClick={() => act("verify")}>Run independent verifier <ShieldCheck size={16}/></button></section>;
  if (m.status === "VERIFIED_AWAITING_APPROVAL") return <section className="action-banner" role="status"><div><span className="eyebrow">READY TO SAVE TO YOUR REPOSITORY</span><h3>Verified changes are waiting for your decision.</h3><p>The agents edited a disposable copy. Review the exact diff, approve that candidate, then choose Save to existing repository to update your original files.</p></div><Link className="button primary" href={`/missions/${m.id}/review`}>Review and save changes <ArrowRight size={16}/></Link></section>;
  if (m.status === "APPLIED") return <section className="action-banner" role="status"><div><span className="eyebrow">SAVED TO YOUR REPOSITORY</span><h3>Approved changes were written to the original files.</h3><p>The saved candidate and its evidence remain available in the review tab.</p></div><Link className="button" href={`/missions/${m.id}/review`}>View saved change <ArrowRight size={16}/></Link></section>;
  const started = events.some(e => ["BASELINE_FROZEN", "SHOGUN_STARTED", "GUILD_OPERATION_STARTED", "PREFLIGHT_STARTED"].includes(e.event_type)) || detail.candidates.length > 0;
  if (m.status === "PLANNING" && !started) return <section className="action-banner"><div><span className="eyebrow">YOUR BRIEF IS SAVED</span><h3>Ready for Shogun to inspect the repository?</h3><p>Starting planning makes model calls using the configured backend.</p></div><button disabled={busy} className="button primary" onClick={() => act("plan")}>Start planning <ArrowRight size={16}/></button></section>;
  if (m.failure_reason) return <section className="error-banner"><strong>{label(m.status)}</strong><p>{m.failure_reason}</p></section>;
  return null;
}
