"use client";

import { useState } from "react";
import { eventLabel, formatClock, missionMeta } from "@/lib/status";
import type { MissionEventsState } from "@/lib/use-missions";
import type { MissionStatus } from "@/lib/types";

type BottomPanelProps = {
  status: MissionStatus;
  taskCounts: Record<string, number>;
  events: MissionEventsState;
};

export function BottomPanel({ status, taskCounts, events }: BottomPanelProps) {
  const [height, setHeight] = useState(190);
  const meta = missionMeta(status as never);
  const total = Object.values(taskCounts).reduce((sum, value) => sum + value, 0);
  const running = (taskCounts["RUNNING"] ?? 0) + (taskCounts["CHECKING"] ?? 0) + (taskCounts["REPAIRING"] ?? 0);
  return (
    <section className="panel forge-bottom" aria-labelledby="bottom-title" style={{ height, overflow: "auto" }}>
      <div className="panel-head">
        <span className="panel-title" id="bottom-title">
          LOG &amp; STATUS
        </span>
        <label className="mono" style={{ fontSize: ".7rem" }}>Log height <input type="range" min={150} max={500} step={10} value={height} onChange={(event) => setHeight(Number(event.target.value))} /></label>
        <span className="status" data-tone={events.phase === "live" ? "jade" : "warn"}>{events.phase === "live" ? "LIVE · SSE" : "CONNECTING"}</span>
      </div>
      <div className="forge-bottom__body">
        <p className="forge-bottom__line">
          <span className="status" data-tone={meta.tone}>
            {meta.glyph} {meta.label}
          </span>
          <span className="forge-bottom__counts mono">
            {total > 0 ? `${total} tasks` : "no tasks"} {running > 0 ? `· ${running} active` : ""}
          </span>
        </p>
        <p className="forge-bottom__line">
          {running > 0
            ? "The Samurai is at work — the log fills as tools run."
            : "Standing by. No orchestration run is active for this mission."}
        </p>
        <div className="forge-bottom__log" aria-live="polite">
          {events.events.length === 0 ? <span className="forge-bottom__log__empty">— no events recorded yet —</span> : events.events.map((event) => <p key={event.sequence} className="mono">#{event.sequence} {formatClock(event.created_at)} · {event.source} · {eventLabel(event.event_type)}</p>)}
        </div>
      </div>
    </section>
  );
}
