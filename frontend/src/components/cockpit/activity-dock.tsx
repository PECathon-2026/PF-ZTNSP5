"use client";

import { useState } from "react";
import { ChevronUp, ChevronDown, Radio } from "lucide-react";
import { eventLabel, eventTone, formatClock } from "@/lib/status";
import type { MissionEventsState } from "@/lib/use-missions";

export function ActivityDock({ stream, onEvidence }: { stream: MissionEventsState; onEvidence: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [source, setSource] = useState("all");
  const last = stream.events[stream.events.length - 1];
  const sources = Array.from(new Set(stream.events.map((event) => event.source)));
  const records = source === "all" ? stream.events : stream.events.filter((event) => event.source === source);
  return <section className={`activity-dock${expanded ? " is-expanded" : ""}`} aria-label="Mission chronicle">
    <header className="activity-dock__bar">
      <button className="chronicle-toggle" aria-expanded={expanded} aria-controls="chronicle-records" onClick={() => setExpanded((open) => !open)}><Radio size={15} /><span>Chronicle</span><span className="mono activity-count">{stream.events.length}</span>{expanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}</button>
      <p className="activity-latest mono">{last ? <><span>#{String(last.sequence).padStart(3, "0")}</span> {last.source} <strong>{eventLabel(last.event_type)}</strong></> : "Waiting for the first recorded event"}</p>
      <span className="activity-connection mono" role="status"><i className={stream.phase === "live" ? "is-live" : ""} />{stream.phase === "live" ? "SSE CONNECTED" : stream.phase === "connecting" ? "CONNECTING" : "RECONNECTING"}</span>
    </header>
    {expanded && <div id="chronicle-records" className="chronicle-records">
      <div className="chronicle-filter"><label>Source <select value={source} onChange={(event) => setSource(event.target.value)}><option value="all">All sources</option>{sources.map((item) => <option key={item}>{item}</option>)}</select></label><span className="mono">sequence {stream.lastSequence} · durable replay</span></div>
      {stream.error && <p className="field-error">{stream.error}</p>}
      <ol>{records.slice(-100).map((event) => <li key={event.sequence} data-tone={eventTone(event.event_type)}><time className="mono">{formatClock(event.created_at)}</time><span className="mono chronicle-source">{event.source}</span><strong>{eventLabel(event.event_type)}</strong><span className="mono chronicle-sequence">#{event.sequence}</span>
        {event.evidence_ids.map((id) => <button key={id} className="text-link" onClick={() => onEvidence(id)}>Inspect evidence</button>)}
      </li>)}</ol>
      {!records.length && <p className="dossier-empty">No events recorded for this source.</p>}
    </div>}
  </section>;
}
