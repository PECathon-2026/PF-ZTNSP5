"use client";

import Link from "next/link";
import type { Mission } from "@/lib/types";

export const budgetPresets = {
  standard: { max_model_turns: 25, max_tool_calls: 50, max_tokens: 160000, max_time_seconds: 600 },
  extended: { max_model_turns: 60, max_tool_calls: 100, max_tokens: 320000, max_time_seconds: 900 },
};
export type BudgetPreset = keyof typeof budgetPresets;

export function BudgetSelector({ value, onChange }: { value: BudgetPreset; onChange: (value: BudgetPreset) => void }) {
  const limits = budgetPresets[value];
  return <section className="budget-selector">
    <label htmlFor="mission-budget">04 / Mission budget</label>
    <select id="mission-budget" value={value} onChange={e => onChange(e.target.value as BudgetPreset)}>
      <option value="standard">Standard — small, focused changes</option>
      <option value="extended">Extended — multi-file work and acceptance-test design</option>
    </select>
    <p>{limits.max_model_turns} model turns · {limits.max_tool_calls} tools · {limits.max_tokens.toLocaleString("en-US")} reported tokens · {limits.max_time_seconds / 60} active minutes</p>
    <p className="muted small-text">Shared across planning, clarification, development, review and repairs. Larger allowances may cost more. Each developer task remains capped at 20 turns and 50 tool calls; repairs remain capped at 3.</p>
  </section>;
}

export function BudgetNotice({ mission }: { mission: Mission }) {
  const b = mission.budgets;
  const tokens = b.input_tokens_used == null || b.output_tokens_used == null ? null : b.input_tokens_used + b.output_tokens_used;
  const exhausted = mission.status === "BUDGET_EXHAUSTED";
  return <details className="budget-notice" open={exhausted || undefined}>
    <summary>Mission budget <span>{b.model_turns_used}/{b.max_model_turns} model turns · {b.tool_calls_used}/{b.max_tool_calls} tools</span></summary>
    <div className="budget-stats"><span>Model turns <strong>{b.model_turns_used} / {b.max_model_turns}</strong></span><span>Tool calls <strong>{b.tool_calls_used} / {b.max_tool_calls}</strong></span><span>Reported tokens <strong>{tokens == null ? "Not recorded" : `${tokens.toLocaleString("en-US")} / ${b.max_tokens?.toLocaleString("en-US") ?? "unknown"}`}</strong></span><span>Active time <strong>{b.time_used_seconds == null ? "Not recorded" : `${Math.round(b.time_used_seconds)} / ${b.max_time_seconds} seconds`}</strong></span></div>
    {exhausted && <><p>This run is stopped. Partial workspace edits have not been verified or approved. Inspect the recovery panel to continue this mission, or prepare a separate fresh mission below.</p><Link href={`/missions/new?from=${encodeURIComponent(mission.id)}`} className="button">Prepare a new mission with extended budget</Link></>}
  </details>;
}
