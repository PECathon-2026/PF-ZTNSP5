"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, type CSSProperties } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { FileCode2, GitBranch, LoaderCircle, PanelRightClose, RefreshCw, Shield, Square, Terminal, X } from "lucide-react";
import { api } from "@/lib/api";
import { agents, agentStatus, running } from "@/lib/mission";
import { useMission } from "@/lib/use-mission";
import type { Agent } from "@/lib/types";
import { AppHeader, Badge, Empty, MissionNavigation } from "./ui";
import { AgentArt } from "./agent-art";
import { ActivityList, EvidenceDrawer, EvidenceList, MissionActions, TaskCriteria } from "./mission-panels";
import { AgentDrawer } from "./agent-drawer";
import { BudgetNotice } from "./budget";
import { VerifierStatus } from "./verifier-status";
import { RecoveryPanel, recoveryStates } from "./recovery-panel";
import { MissionHeading } from "./mission-heading";

const CodePane = dynamic(() => import("./code-pane").then(m => m.CodePane), { ssr: false, loading: () => <Empty title="Loading code viewer…"/> });
const Graph = dynamic(() => import("./agent-graph"), { ssr: false, loading: () => <Empty title="Loading agent graph…"/> });
const Review = dynamic(() => import("./review-panel").then(m => m.ReviewPanel), { ssr: false });

export function MissionShell({ id, view }: { id: string; view: string }) {
  const router = useRouter();
  const search = useSearchParams();
  const { detail, events, repository, error, connection, refresh } = useMission(id);
  const [selectedCandidate, setCandidate] = useState(search.get("candidate") || "");
  const [file, setFile] = useState(search.get("file") || "");
  const [bottomTab, setBottomTab] = useState("dojo");
  const [agent, setAgent] = useState<Agent | null>(null);
  const [evidence, setEvidence] = useState<{ id: string; mission: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [showScope, setShowScope] = useState(true);
  const [changeTypes, setChangeTypes] = useState<Record<string, string>>({});
  const [openFiles, setOpenFiles] = useState<string[]>([]);
  const [allFilesClosed, setAllFilesClosed] = useState(false);
  const [line, setLine] = useState<number | undefined>(undefined);
  const candidateId = selectedCandidate || detail?.mission.active_candidate_id || detail?.candidates.at(-1)?.id || "";
  const candidate = detail?.candidates.find(c => c.id === candidateId);
  const returnTo = search.get("returnTo");
  const connected = connection === "live" || connection === "recorded";
  const files = [...new Set([...(detail?.repository_files || []), ...(candidate?.changed_files || [])])].sort();
  const selectedFile = file || (allFilesClosed ? "" : candidate?.changed_files[0] || files[0] || "");
  useEffect(() => {
    setFile(search.get("file") || ""); setCandidate(search.get("candidate") || ""); setAllFilesClosed(false);
    const requestedLine = Number(search.get("line"));
    setLine(Number.isInteger(requestedLine) && requestedLine > 0 ? requestedLine : undefined);
  }, [search]);
  useEffect(() => {
    if (selectedFile) setOpenFiles(old => old.includes(selectedFile) ? old : [...old, selectedFile]);
  }, [selectedFile]);
  useEffect(() => {
    const abort = new AbortController(); setChangeTypes({});
    if (candidateId) api<{ files?: { file_path: string; change_type: string }[] }>(`/missions/${id}/candidates/${candidateId}/diff`, undefined, abort.signal)
      .then(result => setChangeTypes(Object.fromEntries((result.files || []).map(f => [f.file_path, f.change_type]))))
      .catch(e => { if (!abort.signal.aborted) setActionError(e.message); });
    return () => abort.abort();
  }, [id, candidateId]);

  async function act(action: string, body: unknown = {}) {
    setBusy(true); setActionError("");
    try { await api(`/missions/${id}/${action}`, body); await refresh(); }
    catch (e) { setActionError((e as Error).message); await refresh().catch(() => {}); }
    finally { setBusy(false); }
  }
  function openFile(path: string, revision?: string, targetLine?: number) {
    if (view !== "workspace") router.push(`/missions/${id}/workspace?file=${encodeURIComponent(path)}&candidate=${revision || candidateId}${targetLine ? `&line=${targetLine}` : ""}${returnTo ? `&returnTo=${encodeURIComponent(returnTo)}` : ""}`);
    else { setFile(path); setLine(targetLine); setAllFilesClosed(false); if (revision) setCandidate(revision); setAgent(null); }
  }
  function closeFile(path: string) {
    const remaining = openFiles.filter(f => f !== path);
    setOpenFiles(remaining);
    if (selectedFile === path) { setFile(remaining.at(-1) || ""); setLine(undefined); setAllFilesClosed(!remaining.length); }
  }
  const inspect = (evidenceId: string, mission = id) => setEvidence({ id: evidenceId, mission });

  return <>
    <AppHeader/>
    <main id="main" className="mission-page">
      <div className="mission-titlebar">
        <MissionHeading id={id} repository={repository || detail?.mission.repository_id || "MISSION"} request={detail?.mission.request_text}/>
        <div className="mission-title-actions">
          <span className={`connection ${connection}`}><span className="dot"/>{connection}</span>
          {detail && <Badge value={detail.mission.status}/>}
          <button aria-label="Refresh mission" className="icon-button" onClick={() => refresh().catch(e => setActionError(e.message))}><RefreshCw size={16}/></button>
        </div>
      </div>
      <MissionNavigation id={id} view={view} returnTo={returnTo} candidate={selectedCandidate} file={selectedFile}/>
      {returnTo && <div className="historical-strip">HISTORICAL MISSION · browsing saved records</div>}
      {(error || actionError) && <div className="error-banner" role="alert">{actionError || error}<button className="quiet" onClick={() => window.location.reload()}>Reload</button></div>}
      {!detail ? <Empty title={error ? "Unable to load mission" : "Loading mission and recorded activity…"}/> : <>
        <MissionActions detail={detail} events={events} busy={busy} act={act}/>
        <BudgetNotice mission={detail.mission}/>
        <VerifierStatus detail={detail} events={events}/>
        {recoveryStates.has(detail.mission.status) && <RecoveryPanel mission={detail.mission} refresh={refresh} apiKeyReady={detail.api_key_ready}/>}
        <div className="workspace-toolbar">
          <div><span className="muted small-text">CANDIDATE</span><select aria-label="Candidate revision" value={selectedCandidate} onChange={e => { setCandidate(e.target.value); setFile(""); setLine(undefined); setAllFilesClosed(false); }}>
            <option value="">Follow active candidate</option>
            {detail.candidates.map((c, i) => <option value={c.id} key={c.id}>r{i} · {c.id} · {c.state}</option>)}
          </select></div>
          <div className="toolbar-stats">
            <span>{detail.mission.budgets.repair_rounds_used}/{detail.mission.budgets.max_repair_rounds} repairs</span><span>{detail.mission.budgets.tool_calls_used} tools</span>
            {busy && <LoaderCircle size={14} className="spin"/>}
            {running.has(detail.mission.status) && <button className="quiet" disabled={busy} onClick={() => act("cancel")}><Square size={11}/> Stop mission</button>}
            {view === "workspace" && <button className="icon-button" aria-label="Toggle task panel" aria-pressed={showScope} onClick={() => setShowScope(v => !v)}><PanelRightClose size={16}/></button>}
          </div>
        </div>
        {view === "workspace" ? <div className={`workspace-grid ${showScope ? "" : "scope-hidden"}`}>
          <aside className="file-panel">
            <h3 className="panel-heading">EXPLORER <span>{files.length}</span></h3><div className="repo-label"><GitBranch size={13}/>{repository || "Repository"}</div>
            {files.map(path => <button key={path} className={`file-row ${selectedFile === path ? "selected" : ""}`} onClick={() => openFile(path)} title={path}><FileCode2 size={14}/><span>{path}</span>{candidate?.changed_files.includes(path) && <span className="file-change" aria-label={changeTypes[path] || "Changed"}>{changeTypes[path]?.[0] || "●"}</span>}</button>)}
            {!files.length && <p className="muted small-text">Files appear after the baseline is captured.</p>}
            <div className="explorer-foot"><Shield size={13}/> Frozen source · read only</div>
          </aside>
          <div className="workspace-center">
            <div className="open-files" aria-label="Open files">{openFiles.map(path => <div key={path} className={path === selectedFile ? "selected" : ""}><button onClick={() => openFile(path)} title={path}><FileCode2 size={12}/>{path}</button><button aria-label={`Close ${path}`} onClick={() => closeFile(path)}><X size={12}/></button></div>)}</div>
            <CodePane missionId={id} candidateId={candidateId} path={selectedFile} line={line}/>
            <section className="bottom-panel">
              <div className="bottom-tabs">{[["checks", "Checks & output"], ["evidence", "Evidence"], ["dojo", "Dojo"], ["activity", "Activity"]].map(([key, title]) => <button key={key} className={bottomTab === key ? "selected" : ""} onClick={() => setBottomTab(key)}>{key === "dojo" ? <span>影</span> : <Terminal size={13}/>} {title}</button>)}</div>
              <div className="bottom-content">
                {bottomTab === "dojo" ? <div className="dojo-strip">{agents.map(a => {
                  const state = agentStatus(a.id, detail, events);
                  const working = connection === "live" && state === "working";
                  const visibleState = connected ? (working ? "working" : state === "working" ? "idle" : state) : "disconnected";
                  return <button key={a.id} className={`dojo-agent ${working ? "working" : ""}`} style={{ "--agent-color": a.color } as CSSProperties} onClick={() => setAgent(a.id)}>
                    <AgentArt agent={a.id} active={working}/>
                    <div><strong>{a.name}</strong><span>{a.role}</span><small className={`agent-state ${visibleState}`}>{working ? "Working now" : connected ? visibleState : "connection lost"}</small></div>
                  </button>;
                })}</div> : bottomTab === "activity" ? <ActivityList events={events} onEvidence={inspect}/> : <EvidenceList detail={bottomTab === "checks" ? { ...detail, evidence: detail.evidence.filter(e => e.command?.length) } : detail} candidateId={candidateId} onEvidence={inspect}/>}
              </div>
            </section>
          </div>
          {showScope && <TaskCriteria detail={candidateId !== detail.mission.active_candidate_id ? { ...detail, criteria: detail.criteria.map(c => ({ ...c, status: "NOT_VERIFIED", evidence_ids: [] })) } : detail} onEvidence={inspect} onFile={(path, targetLine, revision) => openFile(path, revision, targetLine)}/>}
        </div> : view === "graph" ? <div className={`graph-layout ${agent ? "graph-with-agent" : ""}`}>
          <Graph detail={detail} events={events} connected={connected} selected={agent} onSelect={setAgent} candidateId={candidateId} onEvidence={inspect} onInspectConnection={() => setAgent(null)} onCandidate={setCandidate}/>
          <div className="graph-mobile-nodes">{agents.map(a => <button className="button small" key={a.id} onClick={() => setAgent(a.id)}>{a.name}</button>)}</div>
        </div> : <Review key={candidateId} detail={detail} candidateId={candidateId} busy={busy} act={act} onEvidence={inspect}/>}
        {agent && <AgentDrawer key={agent} agent={agent} detail={detail} events={events} onClose={() => setAgent(null)} onEvidence={inspect} onFile={openFile}/>}
      </>}
      <footer className="mission-footer"><span>KAGE AI <span className="muted">/</span> THE ENGINEERING DOJO</span><span>{candidate?.content_fingerprint ? `SHA ${candidate.content_fingerprint.slice(0, 12)}` : "Awaiting candidate"}<span className="muted"> · </span>Original changes require approval</span></footer>
    </main>
    {evidence && <EvidenceDrawer id={evidence.id} missionId={evidence.mission} onClose={() => setEvidence(null)}/>}
  </>;
}
