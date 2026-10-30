"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowUpRight, Search } from "lucide-react";
import { AppHeader, Badge, Empty, PageTitle } from "@/components/ui";
import { api } from "@/lib/api";
import type { Mission } from "@/lib/types";
import { missionBrief } from "@/lib/mission-brief";

const nextLabel: Record<string, string> = {
  BUDGET_EXHAUSTED: "Continue", BLOCKED: "Continue", INTERRUPTED: "Continue", REPAIRING: "Continue", FAILED_VERIFICATION: "Continue",
  AWAITING_CLARIFICATION: "Answer & continue", READY_FOR_AUTHORIZATION: "Review plan", PLANNING: "Continue",
  VERIFYING: "Verify", VERIFIED_AWAITING_APPROVAL: "Review decision",
};

export default function Missions() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState(50);
  useEffect(() => {
    const abort = new AbortController(); setLoading(true);
    api<Mission[]>(`/missions?limit=${limit}`, undefined, abort.signal).then(setMissions).catch(e => { if (!abort.signal.aborted) setError(e.message); }).finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [limit]);
  const filtered = missions.filter(m => `${m.request_text} ${m.repository_id} ${m.id} ${m.status}`.toLowerCase().includes(query.toLowerCase()));
  return <><AppHeader/><main id="main" className="page">
    <PageTitle eyebrow="THE ARCHIVE" title="Every mission leaves a trace."><p>Inspect past work, continue a saved checkpoint, or start a follow-up.</p></PageTitle>
    <div className="search-bar"><Search size={17}/><input aria-label="Search missions" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search loaded missions, repositories or status…"/><span>{missions.length} loaded</span></div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <div className="mission-list">{filtered.map(m => <article key={m.id} className="mission-row">
      <Link href={`/missions/${m.id}/workspace`} className="mission-main-link"><div className="mission-icon">影</div><div className="mission-summary"><h3>{missionBrief(m.request_text).title}</h3><p>{m.repository_id} <span>·</span> {new Date(m.created_at).toLocaleString()} <span>·</span> {m.budgets.repair_rounds_used} repairs</p></div></Link>
      <Badge value={m.status}/><div className="mission-row-actions"><Link href={`/missions/${m.id}/${m.status === "VERIFIED_AWAITING_APPROVAL" ? "review" : "workspace"}`} className="button small">{nextLabel[m.status] || "Open"}<ArrowUpRight size={14}/></Link>{["APPLIED", "REJECTED", "CANCELLED"].includes(m.status) && <Link className="text-link" href={`/missions/new?from=${m.id}`}>Start follow-up</Link>}</div>
    </article>)}</div>
    {loading && <p className="muted">Loading saved missions…</p>}
    {!loading && !filtered.length && <Empty title={query ? "No matching missions" : "A fresh page in the archive"}>Create your first mission to see its tasks, agent activity and evidence here.</Empty>}
    {missions.length >= limit && <button className="button" disabled={loading} onClick={() => setLimit(n => n + 50)}>Load older missions</button>}
  </main></>;
}
