"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { addCriterion } from "@/lib/mission-draft";
import { preflightMeta } from "@/lib/status";
import type { StoredRepository } from "@/lib/types";

const SAMPLE_REQUESTS = [
  "Add a status filter to the list endpoint and reject unknown statuses with a 400.",
  "Fix the off-by-one error in pagination so the last page is never empty.",
  "Extract duplicated validation logic into a shared helper and cover it with tests.",
];

type MissionBriefProps = {
  connected: StoredRepository | null;
  onStarted: (missionId: string) => void;
  phase?: "brief" | "review";
  onDraftChange?: (draft: BriefDraft) => void;
};
export type BriefDraft = { request: string; criteria: string[]; ready: boolean };

export function MissionBrief({ connected, onStarted, phase, onDraftChange }: MissionBriefProps) {
  const [request, setRequest] = useState("");
  const [criteria, setCriteria] = useState<string[]>([]);
  const [entry, setEntry] = useState("");
  const [draftMessage, setDraftMessage] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const preflight = connected?.preflight ?? null;
  const executionBlocked = preflight?.status === "BLOCKED";
  const canSubmit = useMemo(() => {
    if (!connected || submitting) return false;
    if (request.trim().length < 12) return false;
    if (executionBlocked && !acknowledged) return false;
    return true;
  }, [connected, submitting, request, executionBlocked, acknowledged]);
  useEffect(() => { onDraftChange?.({ request, criteria, ready: canSubmit }); }, [request, criteria, canSubmit, onDraftChange]);

  function addCriterionToList() {
    const result = addCriterion(criteria, entry);
    setCriteria(result.criteria);
    setDraftMessage(result.error || "Criterion added to the draft.");
    if (!result.error) setEntry("");
  }

  async function submit() {
    if (!connected || submitting) return;
    const text = request.trim();
    if (text.length < 12) {
      setSubmitError("Describe the work in at least a short sentence before starting the mission.");
      textareaRef.current?.focus();
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const detail = await api.createMission({
        repository_id: connected.repository_id,
        request_text: text,
        criteria,
      });
      onStarted(detail.mission.id);
    } catch (caught) {
      setSubmitError(
        caught instanceof ApiError
          ? caught.detail
          : "The mission could not be created. The backend did not confirm the request.",
      );
      setSubmitting(false);
    }
  }

  return (
    <section className="panel setup-panel" aria-labelledby={phase === "review" ? "commission-review-title" : "brief-title"}>
      <div className="panel-head">
        <span className="panel-title">02 · INTENT</span>
        <span className="panel-title">{criteria.length} CRITERIA</span>
      </div>

      <div className="setup-panel__body">
        <div hidden={phase === "review"} className="briefing-fields">
        <h2 id="brief-title">The mission brief</h2>
        <p className="muted">
          Write the change you want and the outcomes you will review. The Shogun reads this first —
          be specific about behaviour, not implementation.
        </p>

        <div className="field">
          <label htmlFor="mission-request">What should the guild build or fix?</label>
          <textarea
            id="mission-request"
            ref={textareaRef}
            className="textarea"
            rows={7}
            value={request}
            onChange={(event) => {
              setRequest(event.target.value);
              if (submitError) setSubmitError(null);
            }}
            placeholder="Describe the change, the behaviour it should produce, and anything it must not touch…"
            aria-describedby="request-hint"
            aria-invalid={Boolean(submitError)}
            disabled={submitting}
          />
          <small id="request-hint" className="field-hint">
            The brief is stored with the mission and drives planning, checks, and acceptance criteria.
          </small>
        </div>

        <div className="sample-requests">
          <span className="field-label">Examples of useful briefs</span>
          <div className="tag-row">
            {SAMPLE_REQUESTS.map((sample) => (
              <button
                key={sample}
                type="button"
                className="chip"
                onClick={() => {
                  setRequest(sample);
                  setSubmitError(null);
                  textareaRef.current?.focus();
                }}
                disabled={submitting}
              >
                {sample.length > 52 ? `${sample.slice(0, 52)}…` : sample}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label htmlFor="criterion-input">Acceptance criteria</label>
          <p className="field-hint">
            Testable outcomes you want verified. Each one is stored as an acceptance criterion the
            independent verifier will check against evidence.
          </p>
          <div className="criterion-add">
            <input
              id="criterion-input"
              className="input"
              value={entry}
              maxLength={300}
              onChange={(event) => setEntry(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addCriterionToList();
                }
              }}
              placeholder="e.g. Invalid statuses are rejected with a 400"
              disabled={submitting}
            />
            <button className="btn" type="button" onClick={addCriterionToList} disabled={submitting}>
              Add
            </button>
          </div>
          <p className="field-hint" role="status">
            {draftMessage}
          </p>
        </div>

        {criteria.length > 0 && (
          <ul className="criteria-list" aria-label="Draft acceptance criteria">
            {criteria.map((criterion, index) => (
              <li key={`${criterion}-${index}`}>
                <span className="criteria-index mono">{String(index + 1).padStart(2, "0")}</span>
                <span>{criterion}</span>
                <button
                  type="button"
                  className="btn btn--quiet btn--sm"
                  aria-label={`Remove criterion ${index + 1}`}
                  onClick={() => {
                    setCriteria(criteria.filter((_, position) => position !== index));
                    setDraftMessage("Criterion removed from the draft.");
                  }}
                  disabled={submitting}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}

        </div>
        {phase === "review" && <div className="commission-review"><span className="mono">THE FINAL BRIEF</span><h2 id="commission-review-title">Review the commission</h2><p className="commission-review-intro">This is the exact brief the backend will record. Execution and application require their own authorization later.</p>
          <div className="commission-review-block"><h3>Repository</h3><p className="mono">{connected?.name ?? "No repository connected"}</p><small>{connected?.path}</small></div>
          <div className="commission-review-block"><h3>Mission intention</h3><p className="commission-review-request">{request.trim() || "No mission brief written yet."}</p></div>
          <div className="commission-review-block"><h3>Acceptance gate · {criteria.length} criteria</h3>{criteria.length ? <ol>{criteria.map((criterion) => <li key={criterion}>{criterion}</li>)}</ol> : <p>No criteria added. The planner may propose criteria during planning.</p>}</div>
        </div>}
        <div className="preflight" hidden={phase === "brief"} aria-labelledby="preflight-title">
          <div className="preflight__summary">
            <p className="panel-title" id="preflight-title">
              03 · RECORDING READINESS
            </p>
            {preflight ? (
              <>
                <p className="preflight__line">
                  <span className="status" data-tone={preflightMeta(preflight.status).tone}>
                    {preflightMeta(preflight.status).glyph} {preflightMeta(preflight.status).label}
                  </span>
                  <span className="muted">
                    {executionBlocked
                      ? "Execution environment blocked — checks cannot run until the container runtime is available."
                      : preflight.status === "WARNING"
                        ? "Connected with warnings — review them before relying on the results."
                        : "Repository connected and preflighted."}
                  </span>
                </p>
                {executionBlocked && (
                  <label className="acknowledge">
                    <input
                      type="checkbox"
                      checked={acknowledged}
                      onChange={(event) => setAcknowledged(event.target.checked)}
                      disabled={submitting}
                    />
                    <span>
                      I understand the mission can be recorded now, but no tool, test, or check can
                      execute until the container runtime is available.
                    </span>
                  </label>
                )}
              </>
            ) : (
              <p className="preflight__line">
                <span className="status" data-tone="plain">
                  ◇ NOT CONNECTED
                </span>
                <span className="muted">Connect a repository to run preflight.</span>
              </p>
            )}
          </div>

          <div className="preflight__action">
            {submitError && (
              <p className="field-error" role="alert">
                {submitError}
              </p>
            )}
            <button
              type="button"
              className="btn btn--primary btn--lg btn--block"
              onClick={() => void submit()}
              disabled={!canSubmit}
              aria-describedby="start-reason"
            >
              {submitting ? <span className="btn-spinner" aria-hidden="true" /> : null}
              {submitting ? "Starting mission…" : "START MISSION"}
            </button>
            <small id="start-reason" className="field-hint">
              {!connected
                ? "Connect a repository first."
                : request.trim().length < 12
                  ? "Write a mission brief of at least a short sentence."
                  : executionBlocked && !acknowledged
                    ? "Acknowledge the execution blocker to record the mission."
                    : "Creates the mission through the backend and opens its command center."}
            </small>
          </div>
        </div>
      </div>
    </section>
  );
}
