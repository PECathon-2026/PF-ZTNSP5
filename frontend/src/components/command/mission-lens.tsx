"use client";

import { useState } from "react";
import { GUILD, criterionMeta, missionMeta, taskMeta } from "@/lib/status";
import type { MissionDetail } from "@/lib/types";
import type { MissionEventsState } from "@/lib/use-missions";
import { TaskTopology } from "@/components/mission/task-topology";
import { Timeline } from "./timeline";
import "./mission-lens.css";

const MODES = ["Guild field", "Chronicle", "Task topology"] as const;
type Mode = typeof MODES[number];
const POSITIONS = [{ x: 50, y: 15 }, { x: 81, y: 48 }, { x: 50, y: 82 }, { x: 19, y: 48 }];

export function MissionLens({ detail, events, onEvidence }: { detail: MissionDetail; events: MissionEventsState; onEvidence: (id: string) => void }) {
  const [mode, setMode] = useState<Mode>("Guild field");
  const [owner, setOwner] = useState<string>("SHOGUN");
  const member = GUILD.find((item) => item.id === owner)!;
  const owned = detail.tasks.filter((task) => task.owner_agent === owner);
  const candidate = detail.candidates.find((item) => item.id === detail.mission.active_candidate_id);
  const passed = detail.criteria.filter((item) => item.status === "PASS").length;
  const active = detail.tasks.filter((item) => item.status === "RUNNING").length;

  return <section className="panel mission-lens" aria-label="Mission exploration lenses">
    <div className="panel-head"><span className="panel-title">MISSION FIELD</span><span className="mono lens-stream" role="status">{events.phase === "live" ? "SSE connected" : "SSE reconnecting"} · seq {events.lastSequence}</span></div>
    <div className="lens-switch" role="tablist" aria-label="Mission lens">
      {MODES.map((item, index) => <button key={item} role="tab" id={`lens-tab-${index}`} aria-selected={mode === item} aria-controls={`lens-panel-${index}`} tabIndex={mode === item ? 0 : -1}
        onClick={() => setMode(item)} onKeyDown={(event) => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          const next = event.key === "Home" ? 0 : event.key === "End" ? 2 : (index + (event.key === "ArrowRight" ? 1 : -1) + 3) % 3;
          setMode(MODES[next]); document.getElementById(`lens-tab-${next}`)?.focus();
        }}>{item}</button>)}
    </div>
    <div className="lens-content" role="tabpanel" id={`lens-panel-${MODES.indexOf(mode)}`} aria-labelledby={`lens-tab-${MODES.indexOf(mode)}`}>
      {mode === "Chronicle" ? <Timeline events={events} /> : mode === "Task topology" ? <TaskTopology tasks={detail.tasks} onEvidence={onEvidence} /> : <>
        <div className="guild-field">
          <svg className="guild-field__lines" viewBox="0 0 500 420" aria-hidden="true">
            <defs><radialGradient id="field-glow"><stop stopColor="#c99a3a" stopOpacity=".14" /><stop offset="1" stopColor="#c99a3a" stopOpacity="0" /></radialGradient></defs>
            <circle cx="250" cy="202" r="185" fill="url(#field-glow)" />
            <circle cx="250" cy="202" r="144" fill="none" stroke="#c99a3a" strokeOpacity=".2" strokeDasharray="2 8" />
            <circle cx="250" cy="202" r="83" fill="none" stroke="#c99a3a" strokeOpacity=".25" />
            {POSITIONS.map((position, index) => <path key={index} d={`M 250 202 L ${position.x * 5} ${position.y * 4.2}`} stroke={owner === GUILD[index].id ? "#e8c66a" : "#c99a3a"} strokeOpacity={owner === GUILD[index].id ? .65 : .15} strokeDasharray="4 5" />)}
          </svg>
          <div className="guild-nucleus"><span className="guild-nucleus__seal" aria-hidden="true">影</span>
            <span className="status" data-tone={missionMeta(detail.mission.status).tone}>{missionMeta(detail.mission.status).label}</span>
            <span className="mono">{candidate ? candidate.ui_badge : "NO ACTIVE CANDIDATE"}</span>
          </div>
          {GUILD.map((item, index) => {
            const tasks = detail.tasks.filter((task) => task.owner_agent === item.id);
            const running = tasks.filter((task) => task.status === "RUNNING").length;
            return <button key={item.id} className="guild-orbit" style={{ left: `${POSITIONS[index].x}%`, top: `${POSITIONS[index].y}%` }} aria-pressed={owner === item.id} onClick={() => setOwner(item.id)}>
              <span className="guild-orbit__glyph" aria-hidden="true">{item.glyph}</span><strong>{item.name}</strong><span>{item.role}</span>
              <span className="mono">{running ? `${running} running` : `${tasks.length} assigned`}</span>
            </button>;
          })}
        </div>
        <div className="field-readout"><span><strong>{detail.tasks.length}</strong> recorded tasks</span><span><strong>{active}</strong> running</span><span><strong>{passed}/{detail.criteria.length}</strong> criteria passed</span></div>
        <div className="field-dossier" aria-live="polite"><div className="field-dossier__heading"><h3>{member.name}</h3><span>{member.role}</span></div><p>{member.purpose}</p>
          {!owned.length ? <p className="muted">No tasks assigned to this role yet. Select another seal to inspect recorded ownership.</p> : <ul>{owned.map((task) => <li key={task.id}><span className="status" data-tone={taskMeta(task.status).tone}>{task.status}</span><strong>{task.title}</strong><p>{task.result_summary ?? task.description}</p>
            {task.evidence_ids.map((id) => <button key={id} className="btn btn--ghost btn--sm" onClick={() => onEvidence(id)}>Inspect {id}</button>)}</li>)}</ul>}
        </div>
        {detail.criteria.length > 0 && <div className="field-criteria">{detail.criteria.map((criterion) => <div key={criterion.id}><span className="status" data-tone={criterionMeta(criterion.status).tone}>{criterionMeta(criterion.status).glyph}</span><span>{criterion.description}</span><span className="mono muted">{criterionMeta(criterion.status).label}</span></div>)}</div>}
      </>}
    </div>
  </section>;
}
