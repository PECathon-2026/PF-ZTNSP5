"use client";

import { useMemo, useState } from "react";
import type { MissionTask } from "@/lib/types";
import { taskMeta } from "@/lib/status";
import "./mission-tools.css";

export function TaskTopology({ tasks, onEvidence }: { tasks: MissionTask[]; onEvidence: (id: string) => void }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = tasks.find((task) => task.id === selectedId);
  const graph = useMemo(() => {
    const byId = new Map(tasks.map((task) => [task.id, task]));
    const levels = new Map<string, number>();
    function level(id: string, visiting = new Set<string>()): number {
      if (levels.has(id)) return levels.get(id)!;
      if (visiting.has(id) || !byId.has(id)) return 0;
      const next = new Set(visiting).add(id);
      const dependencies = byId.get(id)!.dependencies.filter((dep) => byId.has(dep));
      const result = dependencies.length ? Math.max(...dependencies.map((dep) => level(dep, next))) + 1 : 0;
      levels.set(id, result); return result;
    }
    const counts = new Map<number, number>();
    const positions = new Map(tasks.map((task) => {
      const column = level(task.id); const row = counts.get(column) ?? 0; counts.set(column, row + 1);
      return [task.id, { x: 24 + column * 250, y: 24 + row * 126 }];
    }));
    return { positions, width: Math.max(600, 48 + (Math.max(0, ...levels.values()) + 1) * 250), height: Math.max(190, 48 + Math.max(0, ...counts.values()) * 126) };
  }, [tasks]);
  return <section className="panel task-topology" aria-labelledby="topology-title">
    <div className="panel-head"><h2 className="panel-title" id="topology-title">TASK TOPOLOGY</h2><span className="mono muted">{tasks.length} recorded nodes · select to inspect</span></div>
    {!tasks.length ? <div className="state-block state-block--inline"><h3>No plan graph yet</h3><p>Real task nodes and dependencies appear when the backend records a plan.</p></div> : <>
      <div className="topology-scroll" tabIndex={0} aria-label="Scrollable task dependency graph">
        <div className="topology-canvas" style={{ width: graph.width, height: graph.height }}>
          <svg width={graph.width} height={graph.height} aria-hidden="true"><defs><marker id="dependency-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#C99A3A" /></marker></defs>
            {tasks.flatMap((task) => task.dependencies.map((dependency) => {
              const from = graph.positions.get(dependency); const to = graph.positions.get(task.id);
              return from && to ? <path key={`${dependency}-${task.id}`} d={`M ${from.x + 220} ${from.y + 48} C ${from.x + 235} ${from.y + 48}, ${to.x - 15} ${to.y + 48}, ${to.x} ${to.y + 48}`} fill="none" stroke="#C99A3A" strokeOpacity=".55" markerEnd="url(#dependency-arrow)" /> : null;
            }))}</svg>
          {tasks.map((task) => { const p = graph.positions.get(task.id)!; const meta = taskMeta(task.status);
            return <button key={task.id} className="topology-node" style={{ left: p.x, top: p.y }} aria-pressed={task.id === selectedId} onClick={() => setSelectedId(task.id)}>
              <span className="mono muted">{task.owner_agent}</span><strong>{task.title}</strong><span className="status" data-tone={meta.tone}>{task.status}</span>
            </button>; })}
        </div>
      </div>
      {selected && <div className="topology-inspector"><h3>{selected.title}</h3><p>{selected.description}</p>
        <p className="mono muted">{selected.id} · attempt {selected.attempt} · {selected.candidate_id ?? "no candidate bound"}</p>
        <p>{selected.result_summary ?? selected.completion_condition ?? "No result recorded yet."}</p>
        <p className="muted">Depends on: {selected.dependencies.map((id) => tasks.find((task) => task.id === id)?.title ?? id).join(", ") || "none"}</p>
        {selected.evidence_ids.map((id) => <button key={id} className="btn btn--ghost btn--sm" onClick={() => onEvidence(id)}>Inspect {id}</button>)}
      </div>}
    </>}
  </section>;
}
