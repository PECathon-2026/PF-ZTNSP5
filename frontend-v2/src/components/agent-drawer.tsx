"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Search, X } from "lucide-react";
import { api, getMission, history } from "@/lib/api";
import { agents, agentStatus, label } from "@/lib/mission";
import type { Agent, Detail, Mission, MissionEvent } from "@/lib/types";
import { AgentArt } from "./agent-art";
import { Badge, Empty } from "./ui";
import { ActivityList } from "./mission-panels";

export function AgentDrawer({ agent, detail, events, onClose, onEvidence, onFile }: {
  agent: Agent; detail: Detail; events: MissionEvent[]; onClose: () => void;
  onEvidence: (id: string, mission?: string) => void; onFile: (path: string, candidate?: string) => void;
}) {
  const person = agents.find(a => a.id === agent)!;
  const [tab, setTab] = useState("now");
  const [missions, setMissions] = useState<Mission[]>([]);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(50);
  const [past, setPast] = useState<{ detail: Detail; events: MissionEvent[]; repository: string | null } | null>(null);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => { closeButton.current?.focus(); }, []);
  useEffect(() => {
    if (tab !== "past") return;
    const abort = new AbortController(); setLoading(true); setError("");
    api<Mission[]>(`/missions?limit=${limit}`, undefined, abort.signal).then(setMissions).catch(e => { if (!abort.signal.aborted) setError(e.message); }).finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [tab, limit]);
  useEffect(() => {
    if (!selected) return;
    const abort = new AbortController(); setPast(null); setError("");
    Promise.all([getMission(selected, abort.signal), history(selected, abort.signal)]).then(([d, h]) => setPast({ detail: d, ...h })).catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [selected]);
  const currentEvents = events.filter(e => e.source === agent);
  const source = tab === "past" ? past?.detail : detail;
  const sourceEvents = (tab === "past" ? past?.events || [] : events).filter(e => e.source === agent);
  const tasks = source?.tasks.filter(t => t.owner_agent === agent) || [];
  const affected = new Set(tasks.map(t => t.candidate_id).filter(Boolean));
  const tools = [...new Set(sourceEvents.map(e => e.display_payload.action).filter(Boolean))];
  const previous = missions.filter(m => m.id !== detail.mission.id && new Date(m.created_at) < new Date(detail.mission.created_at) && `${m.request_text} ${m.repository_id} ${m.status}`.toLowerCase().includes(query.toLowerCase()));
  return <aside className="agent-drawer" aria-label={`${person.name} agent details`} onKeyDown={e => { if (e.key === "Escape") onClose(); }}><div className="drawer-heading"><div className="agent-title"><AgentArt agent={agent}/><div><span className="eyebrow">{person.role}</span><h2>{person.name}</h2></div></div><button ref={closeButton} className="icon-button" onClick={onClose} aria-label="Close agent details"><X size={18}/></button></div><div className="drawer-tabs">{[["now", "Now"], ["mission", "This mission"], ["past", "Previous missions"]].map(([key, title]) => <button key={key} aria-pressed={tab === key} className={tab === key ? "selected" : ""} onClick={() => setTab(key)}>{title}</button>)}</div><div className="drawer-content">
    {tab === "now" ? <><span className={`agent-state ${agentStatus(agent, detail, events)}`}>{agentStatus(agent, detail, events)}</span><h3>Current task</h3>{detail.tasks.filter(t => t.owner_agent === agent && t.status === "RUNNING").map(t => <article className="task-card" key={t.id}><h4>{t.title}</h4><p>{t.description}</p></article>)}{!detail.tasks.some(t => t.owner_agent === agent && t.status === "RUNNING") && <p className="muted">No executing task recorded for this agent.</p>}<h3>Latest recorded action</h3>{currentEvents.length ? <ActivityList events={currentEvents.slice(-1)} onEvidence={id => onEvidence(id)}/> : <Empty title="Awaiting agent activity"/>}<h3>Tools used in this task</h3><div className="tool-chips">{[...new Set(currentEvents.filter(e => e.task_id && detail.tasks.some(t => t.id === e.task_id && t.status === "RUNNING")).map(e => e.display_payload.action).filter(Boolean))].map(tool => <code key={tool}>{tool}</code>)}</div></> : <>
      {tab === "past" && <><div className="search-bar compact"><Search size={14}/><input aria-label="Search previous missions" placeholder="Search previous missions…" value={query} onChange={e => setQuery(e.target.value)}/></div><p className="muted small-text">Select a prior mission to inspect this agent’s saved work. Empty records are shown explicitly.</p><div className="past-mission-list">{previous.map(m => <button className={`past-mission ${selected === m.id ? "selected" : ""}`} key={m.id} onClick={() => setSelected(m.id)}><strong>{m.request_text}</strong><span>{m.repository_id} · {new Date(m.created_at).toLocaleDateString()}</span><Badge value={m.status}/></button>)}</div>{loading && <p className="muted">Loading missions…</p>}{!loading && !previous.length && <Empty title="No matching previous missions"/>}{missions.length >= limit && <button className="button small" onClick={() => setLimit(n => n + 50)}>Load older missions</button>}{error && <p className="error-banner">{error}</p>}{selected && !past && !error && <p>Loading historical records…</p>}{past && <div className="historical-banner"><span>HISTORICAL · {past.repository || past.detail.mission.repository_id}</span><Link href={`/missions/${past.detail.mission.id}/graph?returnTo=${detail.mission.id}`} className="text-link">Open historical graph <ArrowUpRight size={14}/></Link></div>}</>}
      {source && <><h3>{tab === "past" ? "Recorded work" : "Work in this mission"}</h3>{!tasks.length && <p className="muted">No task records for this agent. Planning and review may be recorded in activity below.</p>}{tasks.map(t => <article className="task-card" key={t.id}><Badge value={t.status}/><h4>{t.title}</h4><p>{t.description}</p><p>{t.result_summary}</p><span className="muted small-text">Attempt {t.attempt} · {t.candidate_id || "No candidate yet"}</span></article>)}<h3>Tools & actions used</h3><div className="tool-chips">{tools.length ? tools.map(tool => <code key={tool}>{tool}</code>) : <p className="muted">No tool activity recorded.</p>}</div><h3>Candidate handoffs</h3>{source.candidates.filter(c => affected.has(c.id)).map(c => <details key={c.id}><summary>{c.id} <Badge value={c.state}/></summary>{c.changed_files.map(path => tab === "past" ? <Link className="file-link" key={path} href={`/missions/${source.mission.id}/workspace?file=${encodeURIComponent(path)}&candidate=${c.id}&returnTo=${detail.mission.id}`}>{path} <ArrowUpRight size={12}/></Link> : <button className="file-link" key={path} onClick={() => onFile(path, c.id)}>{path}<ArrowUpRight size={12}/></button>)}</details>)}<h3>Received feedback</h3>{source.messages.filter(m => m.recipient === agent).map(m => <article className="feedback" key={m.id}><span className="eyebrow">{label(m.type)} · {m.sender}</span><p>{m.summary}</p>{m.evidence_ids.map(id => <button key={id} className="text-link" onClick={() => onEvidence(id, source.mission.id)}>View evidence</button>)}</article>)}<h3>Recorded activity</h3><ActivityList events={sourceEvents} onEvidence={id => onEvidence(id, source.mission.id)}/></>}
    </>}
  </div></aside>;
}
