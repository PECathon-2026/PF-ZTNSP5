"use client";

import { missionMeta } from "@/lib/status";
import type { MissionStatus } from "@/lib/types";

type BottomPanelProps = {
  status: MissionStatus;
  taskCounts: Record<string, number>;
};

export function BottomPanel({ status, taskCounts }: BottomPanelProps) {
  const meta = missionMeta(status as never);
  const total = Object.values(taskCounts).reduce((sum, value) => sum + value, 0);
  const running = (taskCounts["RUNNING"] ?? 0) + (taskCounts["CHECKING"] ?? 0) + (taskCounts["REPAIRING"] ?? 0);
  return (
    <section className="panel forge-bottom" aria-labelledby="bottom-title">
      <div className="panel-head">
        <span className="panel-title" id="bottom-title">
          LOG &amp; STATUS
        </span>
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
          {total === 0 && <span className="forge-bottom__log__empty">— nothing recorded yet —</span>}
        </div>
      </div>
    </section>
  );
}
