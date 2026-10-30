"use client";

import { useEffect, useState } from "react";
import { ArrowRight, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { Mission } from "@/lib/types";

interface Limits { max_model_turns: number; max_tool_calls: number; max_tokens: number; max_time_seconds: number }
interface Recovery {
  can_continue: boolean; can_extend_budget: boolean; stage: string | null; checkpoint_token: string | null;
  partial_edits: boolean; changed_files: string[]; partial_files?: string[]; diff: string; diff_truncated: boolean;
  blockers: string[]; budget_blockers: string[]; budgets: Limits & Record<string, number>;
  checkpoint_candidate_id: string | null; new_agent_turn_limit: number;
}
const stages: Record<string, string> = { planning: "Continue planning", development: "Continue developer work", repair: "Continue repair planning", checks_and_review: "Retry checks & review" };
const maximums: Limits = { max_model_turns: 100, max_tool_calls: 500, max_tokens: 1000000, max_time_seconds: 3600 };
const labels: Record<keyof Limits, string> = { max_model_turns: "Total model-turn ceiling", max_tool_calls: "Total tool-call ceiling", max_tokens: "Total reported-token ceiling", max_time_seconds: "Total active seconds" };
export const recoveryStates = new Set(["BUDGET_EXHAUSTED", "BLOCKED", "INTERRUPTED", "FAILED_VERIFICATION", "REPAIRING", "READY_FOR_AUTHORIZATION", "AWAITING_CLARIFICATION"]);

export function RecoveryPanel({ mission, refresh, apiKeyReady }: { mission: Mission; refresh: () => Promise<unknown>; apiKeyReady?: boolean }) {
  const [data, setData] = useState<Recovery | null>(null);
  const [limits, setLimits] = useState<Limits | null>(null);
  const [accept, setAccept] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [partialFile, setPartialFile] = useState<{ path: string; content: string } | null>(null);
  const version = JSON.stringify(mission.budgets);
  function receive(result: Recovery) {
    if (typeof result.can_continue !== "boolean") throw new Error("Restart the updated backend to enable mission recovery.");
    setData(result); setAccept(false); setPartialFile(null);
    setLimits({ max_model_turns: result.budgets.max_model_turns, max_tool_calls: result.budgets.max_tool_calls,
      max_tokens: result.budgets.max_tokens, max_time_seconds: result.budgets.max_time_seconds });
  }
  async function reload() {
    receive(await api<Recovery>(`/missions/${mission.id}/recovery`));
  }
  useEffect(() => {
    const abort = new AbortController(); setError(""); setData(null);
    api<Recovery>(`/missions/${mission.id}/recovery`, undefined, abort.signal).then(result => {
      if (!abort.signal.aborted) receive(result);
    }).catch(e => { if (!abort.signal.aborted) setError(e.message === "Not Found" ? "Restart the updated backend to enable mission recovery." : e.message); });
    return () => abort.abort();
  }, [mission.id, mission.status, version, apiKeyReady]);
  async function action(kind: "continue" | "budget-extension") {
    if (!data?.checkpoint_token) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`/missions/${mission.id}/${kind}`, kind === "continue"
        ? { checkpoint_token: data.checkpoint_token, accept_partial_edits: accept }
        : { checkpoint_token: data.checkpoint_token, limits });
      setNotice(kind === "budget-extension" ? "Budget extended. Usage is preserved; continuation still needs your explicit action." : "Continuation claimed. The mission will continue from its validated checkpoint.");
      await refresh();
      await reload();
    } catch (e) { setError((e as Error).message); await reload().catch(() => {}); }
    finally { setBusy(false); }
  }
  function moreRoom() {
    if (!data) return;
    const b = data.budgets;
    setLimits({ max_model_turns: Math.min(100, b.max_model_turns + 20), max_tool_calls: Math.min(500, b.max_tool_calls + 50),
      max_tokens: Math.min(1000000, b.max_tokens + 160000), max_time_seconds: Math.min(3600, b.max_time_seconds + 300) });
  }
  async function inspectFile(path: string) {
    if (!data?.checkpoint_token) return;
    setError("");
    try {
      const file = await api<{ content: string; deleted?: boolean }>(`/missions/${mission.id}/recovery/file?checkpoint_token=${data.checkpoint_token}&path=${encodeURIComponent(path)}`);
      setPartialFile({ path, content: file.deleted ? "File deleted in the unverified workspace." : file.content });
    } catch (e) { setError((e as Error).message); }
  }
  return <section className="recovery-panel" aria-label="Mission recovery">
    <div className="recovery-heading"><div><span className="eyebrow">CONTINUE THIS MISSION</span><h3>{data?.stage ? stages[data.stage] : "Saved checkpoint & budget"}</h3></div><button className="icon-button" disabled={busy} aria-label="Refresh recovery checkpoint" onClick={() => reload().catch(e => setError(e.message))}><RefreshCw size={15}/></button></div>
    {error && <p role="alert" className="error-banner">{error}</p>}{notice && <p role="status" className="success-banner">{notice}</p>}
    {!data && !error && <p className="muted">Validating the saved checkpoint…</p>}
    {data && <>
      {data.checkpoint_candidate_id && <p className="muted small-text">Checkpoint: {data.checkpoint_candidate_id} · spent counters and completed work remain recorded.</p>}
      {data.blockers.map(text => <p className="recovery-blocker" key={text}>{text}</p>)}
      {data.budget_blockers.map(text => <p className="recovery-blocker" key={text}>{text}. Extend the ceiling below before continuing.</p>)}
      {data.partial_edits && <details open className="recovery-diff"><summary>Inspect unverified workspace changes</summary><p>These edits have not passed verification or approval. A fresh developer loop must inspect them before handoff.</p><div className="button-row">{[...new Set([...data.changed_files, ...(data.partial_files || [])])].map(path => <button className="button small" key={path} onClick={() => inspectFile(path)}>Inspect {path}</button>)}</div><pre>{data.diff || "Changes are already captured in this unverified checkpoint. Open its files above to inspect them."}</pre>{data.diff_truncated && <p className="muted">Preview truncated. Open the complete files above before accepting.</p>}{partialFile && <div><strong className="small-text">Unverified workspace / {partialFile.path}</strong><pre>{partialFile.content}</pre></div>}<label className="check-label"><input type="checkbox" checked={accept} onChange={e => setAccept(e.target.checked)}/> I inspected these unverified edits and authorize a fresh bounded developer attempt.</label></details>}
      {data.stage && <div className="recovery-continue"><p className="muted small-text">{data.stage === "development" ? `The new agent attempt has at most ${data.new_agent_turn_limit} model turns, within the remaining mission budget.` : "Pending work is resumed from the validated checkpoint. Original-repository application still requires approval."}</p><button className="button primary" disabled={busy || !data.can_continue || (data.partial_edits && !accept)} onClick={() => action("continue")}>{stages[data.stage]} <ArrowRight size={15}/></button></div>}
      {data.can_extend_budget && limits && <details className="budget-extension" open={data.budget_blockers.length > 0 || undefined}><summary>Extend this mission’s budget</summary><p className="muted small-text">New totals, not reset counters. Larger allowances can cost more. The three-repair cap cannot be increased.</p><button className="button small" disabled={busy} onClick={moreRoom}>Suggest bounded extra allowance</button><div className="budget-inputs">{(Object.keys(labels) as (keyof Limits)[]).map(key => <label key={key}>{labels[key]}<input type="number" min={data.budgets[key]} max={maximums[key]} value={limits[key]} onChange={e => setLimits({ ...limits, [key]: Number(e.target.value) })}/></label>)}</div><button className="button" disabled={busy || !data.checkpoint_token} onClick={() => action("budget-extension")}>Confirm budget extension</button></details>}
    </>}
  </section>;
}
