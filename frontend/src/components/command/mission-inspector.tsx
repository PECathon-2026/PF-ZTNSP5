"use client";

import { useState } from "react";
import { criterionMeta, formatInstant, GUILD, taskMeta } from "@/lib/status";
import type { AcceptanceCriterion, Mission, MissionTask } from "@/lib/types";

type MissionInspectorProps = {
  mission: Mission;
  criteria: AcceptanceCriterion[];
  tasks: MissionTask[];
};

type TabKey = "tasks" | "criteria" | "overview";

const TAB_LABELS: { key: TabKey; label: string }[] = [
  { key: "tasks", label: "Tasks" },
  { key: "criteria", label: "Criteria" },
  { key: "overview", label: "Overview" },
];

function ownerGlyph(owner: string): string {
  const member = GUILD.find((entry) => entry.id === owner);
  return member?.glyph ?? "◇";
}

export function MissionInspector({ mission, criteria, tasks }: MissionInspectorProps) {
  const [tab, setTab] = useState<TabKey>("tasks");

  return (
    <section className="panel inspector" aria-labelledby="inspector-title">
      <div className="panel-head">
        <span className="panel-title" id="inspector-title">
          INSPECTOR
        </span>
      </div>

      <div className="tabs" role="tablist" aria-label="Mission inspector">
        {TAB_LABELS.map((entry) => (
          <button
            key={entry.key}
            type="button"
            role="tab"
            id={`inspector-tab-${entry.key}`}
            aria-selected={tab === entry.key}
            aria-controls={`inspector-panel-${entry.key}`}
            className="tab"
            onClick={() => setTab(entry.key)}
          >
            {entry.label} 
            <span className="tab-count mono">
              {entry.key === "tasks" ? tasks.length : entry.key === "criteria" ? criteria.length : 1}
            </span>
          </button>
        ))}
      </div>

      <div className="inspector__body">
        {tab === "tasks" && (
          <div role="tabpanel" id="inspector-panel-tasks" aria-labelledby="inspector-tab-tasks">
            {tasks.length === 0 ? (
              <div className="state-block state-block--inline">
                <h3>No task plan yet</h3>
                <p>The Shogun records the task breakdown here once planning produces one.</p>
              </div>
            ) : (
              <ul className="task-list">
                {tasks.map((task) => {
                  const meta = taskMeta(task.status);
                  return (
                    <li key={task.id} className="task-card">
                      <div className="task-card__head">
                        <span className="task-card__owner mono" title={`Owner: ${task.owner_agent}`}>
                          <span aria-hidden="true">{ownerGlyph(task.owner_agent)}</span> {task.owner_agent}
                        </span>
                        <span className="status" data-tone={meta.tone}>
                          {meta.label}
                        </span>
                      </div>
                      <h3 className="task-card__title">{task.title}</h3>
                      {task.description && <p className="task-card__desc">{task.description}</p>}
                      {task.completion_condition && (
                        <p className="task-card__condition mono">done when: {task.completion_condition}</p>
                      )}
                      {task.result_summary && <p className="task-card__summary">{task.result_summary}</p>}
                      <p className="task-card__meta mono">
                        <span>attempt {task.attempt}</span>
                        {task.dependencies.length > 0 && <span>needs {task.dependencies.map((id) => id.slice(0, 8)).join(", ")}</span>}
                        {task.evidence_ids.length > 0 && <span>{task.evidence_ids.length} evidence</span>}
                        {task.candidate_id && <span>candidate {task.candidate_id.slice(0, 10)}</span>}
                      </p>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}

        {tab === "criteria" && (
          <div role="tabpanel" id="inspector-panel-criteria" aria-labelledby="inspector-tab-criteria">
            {criteria.length === 0 ? (
              <div className="state-block state-block--inline">
                <h3>No acceptance criteria</h3>
                <p>This mission was recorded without criteria, so verification has nothing to assert.</p>
              </div>
            ) : (
              <ul className="inspector-criteria">
                {criteria.map((criterion, index) => {
                  const meta = criterionMeta(criterion.status);
                  return (
                    <li key={criterion.id}>
                      <span className="criteria-index mono">{String(index + 1).padStart(2, "0")}</span>
                      <div>
                        <p>{criterion.description}</p>
                        <p className="inspector-criteria__meta mono">
                          <span className="status" data-tone={meta.tone}>
                            {meta.glyph} {meta.label}
                          </span>
                          <span>{criterion.verification_method}</span>
                          {criterion.evidence_ids.length > 0 && <span>{criterion.evidence_ids.length} evidence</span>}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}

        {tab === "overview" && (
          <div role="tabpanel" id="inspector-panel-overview" aria-labelledby="inspector-tab-overview">
            <dl className="meta-grid inspector-overview">
              <div className="meta-item">
                <dt>Mission</dt>
                <dd className="mono">{mission.id}</dd>
              </div>
              <div className="meta-item">
                <dt>Repository</dt>
                <dd className="mono">{mission.repository_id}</dd>
              </div>
              <div className="meta-item">
                <dt>Opened</dt>
                <dd>{formatInstant(mission.created_at)}</dd>
              </div>
              <div className="meta-item">
                <dt>Last update</dt>
                <dd>{formatInstant(mission.updated_at)}</dd>
              </div>
              <div className="meta-item">
                <dt>Scope version</dt>
                <dd className="mono">{mission.scope_version}</dd>
              </div>
              <div className="meta-item">
                <dt>Active candidate</dt>
                <dd className="mono">{mission.active_candidate_id ? mission.active_candidate_id.slice(0, 14) : "none"}</dd>
              </div>
              <div className="meta-item">
                <dt>Repair rounds</dt>
                <dd className="mono">
                  {mission.budgets.repair_rounds_used}/{mission.budgets.max_repair_rounds}
                </dd>
              </div>
              <div className="meta-item">
                <dt>Tool calls</dt>
                <dd className="mono">
                  {mission.budgets.tool_calls_used}/{mission.budgets.max_tool_calls}
                </dd>
              </div>
              <div className="meta-item">
                <dt>Model turns</dt>
                <dd className="mono">
                  {mission.budgets.model_turns_used}/{mission.budgets.max_model_turns}
                </dd>
              </div>
              <div className="meta-item">
                <dt>Cancel</dt>
                <dd>{mission.cancel_requested ? "requested" : "not requested"}</dd>
              </div>
            </dl>
          </div>
        )}
      </div>
    </section>
  );
}
