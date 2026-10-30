"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, FolderGit2, LoaderCircle } from "lucide-react";
import { AppHeader, Badge, PageTitle } from "@/components/ui";
import { BudgetSelector, budgetPresets, type BudgetPreset } from "@/components/budget";
import { api, getMission } from "@/lib/api";
import type { Detail, Health, Repo } from "@/lib/types";

export default function NewMission() {
  const router = useRouter();
  const [path, setPath] = useState("");
  const [repo, setRepo] = useState<Repo | null>(null);
  const [request, setRequest] = useState("");
  const [criteria, setCriteria] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [budget, setBudget] = useState<BudgetPreset>("standard");
  const [prefilled, setPrefilled] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [ownKey, setOwnKey] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [connectionVerified, setConnectionVerified] = useState(false);
  const connectionDraft = useRef({ apiKey, baseUrl, ownKey });
  connectionDraft.current = { apiKey, baseUrl, ownKey };
  const [modelConfig, setModelConfig] = useState<{ provider: string; model: string; endpoint_configured: boolean } | null>(null);
  useEffect(() => {
    const abort = new AbortController();
    api<Health>("/health", undefined, abort.signal).then(setHealth).catch(e => { if (!abort.signal.aborted) setError(e.message); });
    api<{ provider: string; model: string; endpoint_configured: boolean }>("/model-config", undefined, abort.signal).then(setModelConfig).catch(() => {});
    const from = new URLSearchParams(window.location.search).get("from");
    if (from && /^[a-zA-Z0-9_-]+$/.test(from)) {
      setBusy("prefill");
      getMission(from, abort.signal).then(detail => {
        if (abort.signal.aborted) return;
        setRequest(detail.mission.request_text);
        setCriteria(detail.criteria.map(c => c.description).join("\n"));
        setBudget("extended"); setPrefilled(true);
      }).catch(e => { if (!abort.signal.aborted) setError(e.message); })
        .finally(() => { if (!abort.signal.aborted) setBusy(""); });
    }
    return () => abort.abort();
  }, []);
  async function connect() {
    setBusy("connect"); setError("");
    try { setRepo(await api<Repo>("/repositories/connect", { path: path.trim() })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  }
  async function testConnection() {
    setBusy("model"); setError(""); setConnectionVerified(false);
    const submitted = connectionDraft.current;
    try {
      await api("/model-config/validate", { api_key: apiKey.trim(), ...(baseUrl.trim() ? { base_url: baseUrl.trim() } : {}) });
      const current = connectionDraft.current;
      if (current.apiKey === submitted.apiKey && current.baseUrl === submitted.baseUrl && current.ownKey === submitted.ownKey) setConnectionVerified(true);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  }
  async function start() {
    if (!repo || (ownKey && !connectionVerified)) return;
    setBusy("start"); setError("");
    try {
      const detail = await api<Detail>("/missions", {
        repository_id: repo.repository_id, request_text: request.trim(),
        criteria: criteria.split("\n").map(s => s.trim()).filter(Boolean), limits: budgetPresets[budget],
        ...(ownKey ? { api_key: apiKey.trim(), ...(baseUrl.trim() ? { base_url: baseUrl.trim() } : {}) } : {}),
      });
      if (ownKey && (!detail.own_api_key || !detail.api_key_ready)) {
        throw new Error("Backend does not support mission API keys yet. Restart the updated backend. This mission has not started.");
      }
      setApiKey(""); setBaseUrl(""); setConnectionVerified(false);
      const requested = budgetPresets[budget];
      if (detail.mission.budgets.max_model_turns !== requested.max_model_turns ||
          detail.mission.budgets.max_tool_calls !== requested.max_tool_calls ||
          detail.mission.budgets.max_tokens !== requested.max_tokens ||
          detail.mission.budgets.max_time_seconds !== requested.max_time_seconds) {
        throw new Error(`Backend did not honor the selected budget. Restart the updated backend before creating another mission. ${detail.mission.id} was saved but execution has not started.`);
      }
      router.push(`/missions/${detail.mission.id}/workspace`);
    } catch (e) { setError((e as Error).message); setBusy(""); }
  }
  return <>
    <AppHeader/>
    <main id="main" className="page narrow">
      <PageTitle eyebrow="MISSION BRIEF · 01" title="What are we building?"><p>A clear brief is the beginning of a good change.</p></PageTitle>
      {prefilled && <p className="success-banner">Previous request and criteria copied. Reconnect the original repository and review the extended allowance before creating a fresh mission.</p>}
      <div className="setup-grid">
        <section className="panel setup-form">
          <label htmlFor="repo">01 / Repository</label><p className="muted">A local path on the machine running your backend.</p>
          <div className="input-row"><input id="repo" placeholder="D:/projects/my-python-repo" value={path} onChange={e => { setPath(e.target.value); setRepo(null); }}/><button className="button" disabled={!path.trim() || !!busy} onClick={connect}>{busy === "connect" ? <LoaderCircle className="spin" size={15}/> : <FolderGit2 size={15}/>} Connect</button></div>
          {repo && <div className="connection-card"><strong>{repo.name}</strong><Badge value={repo.preflight.status}/><p>{repo.preflight.file_count} included files · {repo.path}</p>{[...repo.preflight.blockers, ...repo.preflight.warnings].map(text => <p key={text}>{text}</p>)}</div>}
          <label htmlFor="request">02 / Your request</label><textarea id="request" rows={5} disabled={busy === "prefill"} placeholder="Describe the behavior you want to add or fix…" value={request} onChange={e => setRequest(e.target.value)}/>
          <label htmlFor="criteria">03 / Acceptance criteria <span className="muted">Optional</span></label><textarea id="criteria" rows={4} disabled={busy === "prefill"} placeholder={"One observable requirement per line.\nFor example: Empty input returns zero."} value={criteria} onChange={e => setCriteria(e.target.value)}/>
          <BudgetSelector value={budget} onChange={setBudget}/>
          <label className="check-label"><input type="checkbox" checked={ownKey} onChange={e => { setOwnKey(e.target.checked); setApiKey(""); setBaseUrl(""); setConnectionVerified(false); }}/> Use my API key and base URL</label>
          {ownKey && <><p className="muted small-text">Uses the backend’s {modelConfig?.provider === "azure_openai" ? "Azure OpenAI" : modelConfig?.provider === "anthropic" ? "Anthropic-compatible" : "configured"} protocol{modelConfig?.model ? ` and model (${modelConfig.model})` : ""}. Enter your provider endpoint below, or leave it empty to use the backend endpoint. Key and URL remain in backend memory for this mission; re-enter both after a restart.</p><label htmlFor="mission-base-url">Model base URL <span className="muted">Optional if backend endpoint is configured</span></label><input id="mission-base-url" type="url" spellCheck={false} maxLength={2048} value={baseUrl} onChange={e => { setBaseUrl(e.target.value); setConnectionVerified(false); }} placeholder="https://provider.example/v1"/><label htmlFor="mission-api-key">Your API key</label><input id="mission-api-key" type="password" autoComplete="off" spellCheck={false} maxLength={4096} value={apiKey} onChange={e => { setApiKey(e.target.value); setConnectionVerified(false); }} placeholder="Paste your provider API key"/><button className="button" type="button" onClick={testConnection} disabled={!!busy || !apiKey.trim() || (!baseUrl.trim() && modelConfig?.endpoint_configured === false)}>{busy === "model" ? "Checking…" : "Test key and base URL"}</button>{connectionVerified && <p role="status" className="success-banner">Model connection verified for this key and endpoint.</p>}{modelConfig && !modelConfig.endpoint_configured && !baseUrl.trim() && <p className="error-banner">Enter a model base URL or configure the backend endpoint.</p>}</>}
          {error && <div role="alert" className="error-banner">{error}</div>}
          <button className="button primary" onClick={start} disabled={!!busy || !repo || !request.trim() || repo.preflight.status === "BLOCKED" || (ownKey && !connectionVerified)}>Create mission <ArrowRight size={16}/></button>
          <p className="muted small-text">You’ll review the plan before authorizing workspace changes.</p>
          <p className="small-text"><Link href="/docs#first-mission" className="text-link">First time here? Read the mission guide <ArrowRight size={13}/></Link></p>
        </section>
        <aside className="setup-aside"><span className="eyebrow">BEFORE THE FIRST EDIT</span><h2>Intent becomes<br/><em>instruction.</em></h2><ol><li>Connect your repository</li><li>Let Shogun inspect and plan</li><li>Review tasks and test mappings</li><li>Authorize the guild’s work</li></ol><div className="readiness"><h3>Environment</h3>{health ? <><p><span className={health.docker_available ? "dot good-dot" : "dot"}/>Docker {health.docker_available ? "ready" : "unavailable"}</p><p><span className={health.model_configured ? "dot good-dot" : "dot"}/>Model {health.model_configured ? "configured" : "not configured"}</p><p><span className={health.storage_ready ? "dot good-dot" : "dot"}/>Storage {health.storage_ready ? "ready" : "unavailable"}</p></> : <p className="muted">Checking backend availability…</p>}</div></aside>
      </div>
    </main>
  </>;
}
