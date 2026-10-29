"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, type Repository, type MissionDetail } from "@/lib/backend";
import { addCriterion } from "@/lib/mission-draft";

export function MissionSetup() {
  const router = useRouter();
  const [path, setPath] = useState("");
  const [repo, setRepo] = useState<Repository | null>(null);
  const [request, setRequest] = useState("");
  const [criteria, setCriteria] = useState<string[]>([]);
  const [entry, setEntry] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  function onAdd() {
    const result = addCriterion(criteria, entry);
    setCriteria(result.criteria);
    setMessage(result.error || "Criterion added.");
    if (!result.error) setEntry("");
  }

  async function connect() {
    setBusy(true);
    setMessage("");
    try {
      setRepo(await api<Repository>("/api/repositories/connect", { method: "POST", body: JSON.stringify({ path: path.trim() }) }));
      setMessage("Repository scanned by the backend. Review its preflight before starting.");
    } catch (error) { setRepo(null); setMessage(error instanceof Error ? error.message : "Connection failed"); }
    finally { setBusy(false); }
  }

  async function start() {
    if (!repo || !request.trim() || !criteria.length || repo.preflight.status === "BLOCKED") return;
    setBusy(true);
    try {
      const detail = await api<MissionDetail>("/api/missions", { method: "POST", body: JSON.stringify({ repository_id: repo.repository_id, request_text: request.trim(), criteria }) });
      await api(`/api/missions/${encodeURIComponent(detail.mission.id)}/plan`, { method: "POST" });
      router.push(`/dojo?mission=${encodeURIComponent(detail.mission.id)}`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Mission could not start"); }
    finally { setBusy(false); }
  }

  return <div className="interior-page">
    <header className="interior-hero"><p className="eyebrow">NEW MISSION · THE BRIEF</p><h1>Define the work.<br /><em>Keep the proof.</em></h1><p>The backend validates your repository before planning; implementation waits for your authorization.</p></header>
    <div className="content-width setup-content"><p className="chapter-heading">01 / MISSION SETUP <span>THE REQUEST PRECEDES THE WORK</span></p><div className="setup-grid">
      <section className="glass-panel"><p className="eyebrow">01 · SOURCE</p><h2>The repository</h2><p>Connect an existing local repository through the backend.</p><label htmlFor="repository-path">Local repository path</label><input id="repository-path" value={path} onChange={(event) => { setPath(event.target.value); setRepo(null); }} spellCheck={false} autoComplete="off" placeholder="D:/projects/my-python-app" /><button className="outline-button" type="button" onClick={connect} disabled={busy || !path.trim()}>Connect repository</button><dl className="repo-facts"><div><dt>Project type</dt><dd>{repo?.preflight.detected_profile ?? "Not detected"}</dd></div><div><dt>Included files</dt><dd>{repo?.preflight.file_count ?? "Not scanned"}</dd></div><div><dt>Existing changes</dt><dd>{repo ? (repo.preflight.existing_modifications ? "Yes" : "No") : "Not checked"}</dd></div><div><dt>Preflight</dt><dd>{repo?.preflight.status ?? "Not run"}</dd></div></dl>{repo?.preflight.blockers.map((blocker) => <p key={blocker} role="alert">{blocker}</p>)}{repo?.preflight.warnings.map((warning) => <p key={warning}>{warning}</p>)}</section>
      <section className="glass-panel"><p className="eyebrow">02 · INTENT</p><h2>The mission brief</h2><p>Write what needs to change and define the outcomes you will review.</p><label htmlFor="mission-request">What should the guild build or fix?</label><textarea id="mission-request" value={request} onChange={(event) => setRequest(event.target.value)} rows={5} placeholder="Describe the change you want to make…" /><label className="criteria-label" htmlFor="criterion-input">Acceptance criteria</label><ul className="criteria-list">{criteria.map((criterion, index) => <li key={`${criterion}-${index}`}><span className="text-gold">{String(index + 1).padStart(2, "0")}</span><span>{criterion}</span><button type="button" onClick={() => setCriteria(criteria.filter((_, i) => i !== index))}>Remove</button></li>)}</ul><div className="criterion-add"><input id="criterion-input" value={entry} maxLength={300} onChange={(event) => setEntry(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); onAdd(); } }} placeholder="e.g. Invalid statuses are rejected" /><button className="outline-button" type="button" onClick={onAdd}>Add criterion</button></div></section>
    </div><section className="preflight"><div><p className="eyebrow">03 · PREFLIGHT</p><h2>Mission authorization</h2><p role="status">{message || "Connect a repository, write a request and add at least one criterion."}</p></div><div className="preflight-actions"><span className="blocked-badge">{repo?.preflight.status ?? "NOT CONNECTED"}</span><button type="button" disabled={busy || !repo || repo.preflight.status === "BLOCKED" || !request.trim() || !criteria.length} onClick={start}>{busy ? "Working…" : "Start planning ↗"}</button></div></section></div>
  </div>;
}
