"use client";

import Link from "next/link";
import { useState } from "react";
import { criterionMeta, formatElapsed, formatInstant, isTerminal, LIFECYCLE, missionMeta, shortPath, stageOf } from "@/lib/status";
import type { AcceptanceCriterion, Mission, MissionTask } from "@/lib/types";

type MissionHeaderBarProps = {
  mission: Mission;
  criteria: AcceptanceCriterion[];
  tasks: MissionTask[];
  repositoryHint: string | null;
  onCancel: () => void;
  cancelling: boolean;
};

export function MissionHeaderBar({
  mission,
  criteria,
  tasks,
  repositoryHint,
  onCancel,
  cancelling,
}: MissionHeaderBarProps) {
  const [expandBrief, setExpandBrief] = useState(false);
  const meta = missionMeta(mission.status);
  const stage = stageOf(mission.status);
  const stageIndex = LIFECYCLE.findIndex((entry) => entry.key === stage);
  const passed = criteria.filter((criterion) => criterion.status === "PASS").length;
  const failed = criteria.filter((criterion) => criterion.status === "FAIL" || criterion.status === "BLOCKED").length;
  const terminal = isTerminal(mission.status);

  return (
    <header className="command-header panel">
      <div className="command-header__top">
        <div className="command-header__identity">
          <span className="command-seal" aria-hidden="true">
            任務
          </span>
          <div>
            <p className="command-header__id mono">{mission.id}</p>
            <p className="command-header__meta">
              <span className="status" data-tone={meta.tone}>
                {meta.glyph} {meta.label}
              </span>
              <span className="muted">
                {repositoryHint ? shortPath(repositoryHint, 1) : `repo ${mission.repository_id.slice(0, 12)}…`}
              </span>
              <span className="muted" title={formatInstant(mission.created_at)}>
                opened {formatElapsed(mission.created_at)}
              </span>
            </p>
          </div>
        </div>

        <div className="command-header__actions">
          <Link className="btn btn--ghost btn--sm" href={`/missions/${mission.id}/forge`}>
            Open forge
          </Link>
          <Link className="btn btn--ghost btn--sm" href={`/missions/${mission.id}/evidence`}>
            Evidence
          </Link>
          {terminal ? (
            <span className="status" data-tone="plain">
              CLOSED
            </span>
          ) : (
            <button type="button" className="btn btn--danger btn--sm" onClick={onCancel} disabled={cancelling || mission.cancel_requested}>
              {mission.cancel_requested ? "Cancel requested" : "Cancel mission"}
            </button>
          )}
        </div>
      </div>

      <button
        type="button"
        className="command-brief"
        aria-expanded={expandBrief}
        onClick={() => setExpandBrief((value) => !value)}
      >
        <span className={expandBrief ? "command-brief__text is-open" : "command-brief__text"}>
          {mission.request_text}
        </span>
        <span className="command-brief__toggle">{expandBrief ? "Collapse" : "Read the full brief"}</span>
      </button>

      <ol className="stage-rail" aria-label="Mission progress">
        {LIFECYCLE.map((entry, index) => {
          const state = index === stageIndex ? "current" : index < stageIndex ? "done" : "pending";
          return (
            <li key={entry.key} data-state={state}>
              <span className="stage-rail__dot" aria-hidden="true" />
              <span className="stage-rail__label">{entry.label}</span>
              <span className="stage-rail__detail">{entry.detail}</span>
            </li>
          );
        })}
      </ol>

      <div className="command-gate">
        <div className="command-gate__criteria" aria-label={`Acceptance criteria ${passed} of ${criteria.length} passed`}>
          <span className="panel-title">ACCEPTANCE</span>
          {criteria.length === 0 ? (
            <span className="muted">No criteria were recorded with this mission.</span>
          ) : (
            <ul>
              {criteria.map((criterion) => {
                const criterionStatus = criterionMeta(criterion.status);
                return (
                  <li key={criterion.id} title={`${criterionStatus.label}: ${criterion.description}`}>
                    <span className="gate-dot" data-tone={criterionStatus.tone} aria-hidden="true">
                      {criterionStatus.glyph}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <p className="command-gate__counts mono">
          {criteria.length > 0 ? `${passed} PASS · ${failed} FAIL/BLOCK · ${criteria.length - passed - failed} OPEN` : "—"}
          <span className="muted"> · {tasks.filter((task) => task.status === "DONE").length}/{tasks.length} tasks done</span>
        </p>
      </div>

      {(mission.failure_reason || mission.unresolved_issues.length > 0) && (
        <div className="command-flags" role="status">
          {mission.failure_reason && <p className="field-error">{mission.failure_reason}</p>}
          {mission.unresolved_issues.map((issue) => (
            <p key={issue} className="muted">
              {issue}
            </p>
          ))}
        </div>
      )}
    </header>
  );
}
