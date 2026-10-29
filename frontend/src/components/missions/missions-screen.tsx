"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type PointerEvent } from "react";
import { ArrowUpRight, Search, Plus, LayoutGrid, List, RotateCw, Layers, ShieldCheck } from "lucide-react";
import { useMissions } from "@/lib/use-missions";
import { missionMeta, formatInstant } from "@/lib/status";
import "./mission-vault.css";

type Filter = "ALL" | "PLANNING" | "ACTIVE" | "TERMINAL";
const ACTIVE = ["RUNNING", "CHECKING", "REPAIRING", "REVIEWING", "VERIFYING", "APPLYING"];
const PLANNING = ["CREATED", "PLANNING", "PREFLIGHT", "READY_FOR_AUTHORIZATION", "AWAITING_CLARIFICATION"];
const TERMINAL = ["APPLIED", "REJECTED", "CANCELLED", "BLOCKED", "BUDGET_EXHAUSTED", "INTERRUPTED", "FAILED_VERIFICATION"];

export function MissionsScreen() {
  const { missions, loading, error, reload } = useMissions();
  const [filter, setFilter] = useState<Filter>("ALL");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<"grid" | "list">("grid");
  const filtered = useMemo(() => missions.filter((mission) => {
    const matches = `${mission.id} ${mission.request_text} ${mission.repository_id}`.toLowerCase().includes(query.toLowerCase());
    return matches && (filter === "ALL" || (filter === "PLANNING" ? PLANNING : filter === "ACTIVE" ? ACTIVE : TERMINAL).includes(mission.status));
  }), [missions, filter, query]);
  useEffect(() => { if (!filtered.some((mission) => mission.id === selectedId)) setSelectedId(filtered[0]?.id ?? null); }, [filtered, selectedId]);
  const selected = missions.find((mission) => mission.id === selectedId);
  const counts = { ALL: missions.length, PLANNING: missions.filter((mission) => PLANNING.includes(mission.status)).length, ACTIVE: missions.filter((mission) => ACTIVE.includes(mission.status)).length, TERMINAL: missions.filter((mission) => TERMINAL.includes(mission.status)).length };
  function tilt(event: PointerEvent<HTMLElement>) {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const rect = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--rx", `${-(event.clientY - rect.top - rect.height / 2) / rect.height * 4}deg`);
    event.currentTarget.style.setProperty("--ry", `${(event.clientX - rect.left - rect.width / 2) / rect.width * 4}deg`);
  }
  return <div className="mission-vault">
    <header className="vault-header"><div><p className="mono vault-overline">THE GUILD'S RECORD</p><h1>Every mission.<br />Its own story.</h1></div><div className="vault-header-right"><div className="vault-stats"><div><strong>{missions.length}</strong><span>recorded</span></div><div><strong>{counts.ACTIVE}</strong><span>in execution</span></div><div><strong>{missions.filter((mission) => mission.status === "APPLIED").length}</strong><span>applied</span></div></div><Link className="btn btn--primary" href="/setup"><Plus size={15} /> Commission a mission</Link></div></header>
    <div className="vault-toolbar"><div className="vault-filters">{(["ALL", "PLANNING", "ACTIVE", "TERMINAL"] as Filter[]).map((item) => <button key={item} aria-pressed={filter === item} onClick={() => setFilter(item)}>{item === "ALL" ? "All missions" : item === "PLANNING" ? "Planning" : item === "ACTIVE" ? "Executing" : "Closed"}<span className="mono">{counts[item]}</span></button>)}</div><label className="vault-search"><Search size={14} /><input aria-label="Search mission archive" placeholder="Search missions…" value={query} onChange={(event) => setQuery(event.target.value)} /></label><button className="vault-icon" aria-label="Grid view" aria-pressed={view === "grid"} onClick={() => setView("grid")}><LayoutGrid size={16} /></button><button className="vault-icon" aria-label="List view" aria-pressed={view === "list"} onClick={() => setView("list")}><List size={16} /></button><button className="vault-icon" aria-label="Refresh mission archive" onClick={reload}><RotateCw size={15} /></button></div>
    <div className="vault-content"><div className="vault-scroll">
      {loading && !missions.length ? <div className="vault-empty" role="status"><Layers size={35} /><h2>Opening the archive</h2><p>Reading recorded missions…</p></div> : error ? <div className="vault-empty" role="alert"><h2>The archive could not be read</h2><p>{error}</p><button className="btn btn--ghost" onClick={reload}>Retry connection</button></div> : !filtered.length ? <div className="vault-empty"><Layers size={35} /><h2>{missions.length ? "No matching missions" : "Your first story starts here"}</h2><p>{missions.length ? `No missions match ${query ? `“${query}”` : "this lifecycle filter"}.` : "Connect a repository and give the guild a mission."}</p>{missions.length ? <button className="btn btn--ghost" onClick={() => { setQuery(""); setFilter("ALL"); }}>Clear search &amp; filters</button> : <Link className="btn btn--primary" href="/setup">Commission a mission</Link>}</div> : <ul className={`vault-board${view === "list" ? " is-list" : ""}`} aria-label="Mission archive">
        {filtered.map((mission) => <li key={mission.id} className={`vault-card${mission.id === selectedId ? " is-selected" : ""}`} onPointerMove={tilt} onPointerLeave={(event) => { event.currentTarget.style.setProperty("--rx", "0deg"); event.currentTarget.style.setProperty("--ry", "0deg"); }}>
          <button className="vault-card-select" aria-label={`Inspect mission ${mission.id}`} aria-pressed={mission.id === selectedId} onClick={() => setSelectedId(mission.id)}><div className="vault-card-meta"><span className="mono">{mission.id}</span><span className="status" data-tone={missionMeta(mission.status).tone}>{missionMeta(mission.status).label}</span></div><h2>{mission.request_text}</h2><p className="mono">{mission.repository_id}</p></button>
          <div className="vault-card-foot"><time className="mono">{formatInstant(mission.created_at)}</time><Link href={`/missions/${mission.id}`} aria-label={`Open mission ${mission.id}`}><ArrowUpRight size={17} /></Link></div>
        </li>)}
      </ul>}
    </div><aside className="vault-dossier" aria-label="Selected mission dossier">{selected ? <><div className="vault-dossier-head"><span className="mono">SELECTED COMMISSION</span><ShieldCheck size={17} /></div><div className="vault-dossier-body" tabIndex={0} key={selected.id}><span className="status" data-tone={missionMeta(selected.status).tone}>{missionMeta(selected.status).label}</span><h2>{selected.id}</h2><p className="vault-dossier-brief">{selected.request_text}</p><dl><div><dt>Repository</dt><dd className="mono">{selected.repository_id}</dd></div><div><dt>Recorded</dt><dd>{formatInstant(selected.created_at)}</dd></div><div><dt>Scope</dt><dd>version {selected.scope_version}</dd></div><div><dt>Active candidate</dt><dd className="mono">{selected.active_candidate_id ?? "None recorded"}</dd></div></dl>{selected.failure_reason && <div className="vault-recorded-blocker"><span className="mono">RECORDED BLOCKER</span><p>{selected.failure_reason}</p></div>}<div className="vault-budget"><span className="mono">TOOL BUDGET</span><strong>{selected.budgets.tool_calls_used} <small>/ {selected.budgets.max_tool_calls}</small></strong><progress aria-label="Mission tool budget used" value={selected.budgets.tool_calls_used} max={selected.budgets.max_tool_calls} /></div></div><div className="vault-dossier-actions"><Link className="btn btn--primary" href={`/missions/${selected.id}`}>Enter the mission field<ArrowUpRight size={15} /></Link><Link className="text-link" href={`/missions/${selected.id}/forge`}>Open engineering workspace →</Link></div></> : <div className="vault-empty"><ShieldCheck size={32} /><p>Select a recorded mission to inspect its scope.</p></div>}</aside></div>
  </div>;
}
