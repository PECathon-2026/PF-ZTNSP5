"use client";

import { useState } from "react";
import { addCriterion } from "@/lib/mission-draft";

export function MissionSetup() {
  const [criteria, setCriteria] = useState<string[]>([]);
  const [entry, setEntry] = useState("");
  const [message, setMessage] = useState("");

  function onAdd() {
    const result = addCriterion(criteria, entry);
    setCriteria(result.criteria);
    setMessage(result.error || "Criterion added to this draft.");
    if (!result.error) setEntry("");
  }

  return <div className="interior-page">
    <header className="interior-hero"><p className="eyebrow">NEW MISSION · THE BRIEF</p><h1>Define the work.<br /><em>Keep the proof.</em></h1><p>Set the boundary of the mission before the guild begins. Nothing is sent or executed until the backend supports it.</p></header>
    <div className="content-width setup-content"><p className="chapter-heading">01 / MISSION SETUP <span>THE REQUEST PRECEDES THE WORK</span></p><div className="setup-grid">
      <section className="glass-panel" aria-labelledby="repo-title"><p className="eyebrow">01 · SOURCE</p><h2 id="repo-title">The repository</h2><p>Enter a local folder path for backend validation when repository connection becomes available. This page cannot read your files.</p><label htmlFor="repository-path">Local repository path</label><input id="repository-path" type="text" spellCheck={false} autoComplete="off" placeholder="e.g. /projects/my-python-app" aria-describedby="repository-hint" /><small id="repository-hint">No folder is connected yet.</small><dl className="repo-facts"><div><dt>Project type</dt><dd>Not detected</dd></div><div><dt>Included files</dt><dd>Not scanned</dd></div><div><dt>Existing changes</dt><dd>Not checked</dd></div><div><dt>Execution profile</dt><dd>Not selected</dd></div></dl></section>
      <section className="glass-panel" aria-labelledby="brief-title"><p className="eyebrow">02 · INTENT</p><h2 id="brief-title">The mission brief</h2><p>Write what needs to change and define the outcomes you will review.</p><label htmlFor="mission-request">What should the guild build or fix?</label><textarea id="mission-request" rows={5} placeholder="Describe the change you want to make…" aria-describedby="request-hint" /><small id="request-hint">This draft stays on this page until you reload or close it; it is not sent to an agent.</small><label className="criteria-label" htmlFor="criterion-input">Acceptance criteria</label><p className="field-caption">Add specific, testable outcomes. Criteria here are written by you.</p><ul className="criteria-list" aria-label="Draft acceptance criteria">{criteria.map((criterion, index) => <li key={`${criterion}-${index}`}><span className="text-gold">{String(index + 1).padStart(2, "0")}</span><span>{criterion}</span><button type="button" aria-label={`Remove criterion ${index + 1}: ${criterion}`} onClick={() => { setCriteria(criteria.filter((_, i) => i !== index)); setMessage("Criterion removed."); }}>Remove</button></li>)}</ul><div className="criterion-add"><input id="criterion-input" value={entry} maxLength={300} onChange={(event) => setEntry(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); onAdd(); } }} placeholder="e.g. Invalid statuses are rejected" /><button className="outline-button" type="button" onClick={onAdd}>Add criterion</button></div><p className="field-caption" role="status">{message}</p></section>
    </div><section className="preflight" aria-labelledby="preflight-title"><div><p className="eyebrow">03 · PREFLIGHT</p><h2 id="preflight-title">Mission authorization</h2><p id="preflight-reason">Blocked: repository validation and mission creation are not available yet. Connect the backend before starting a mission.</p></div><div className="preflight-actions"><span className="blocked-badge">BLOCKED</span><button type="button" disabled aria-describedby="preflight-reason">Start mission ↗</button></div></section></div>
  </div>;
}
