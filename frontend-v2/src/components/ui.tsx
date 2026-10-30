"use client";

import Link from "next/link";
import { ArrowUpRight, BookOpen, CircleDot, Command, GitBranch, Layers, Plus, Sparkles } from "lucide-react";
import { label } from "@/lib/mission";
import type { ReactNode } from "react";

export function Brand() {
  return <Link href="/" className="brand" aria-label="KAGE AI home"><span className="brand-mark">影</span><span>KAGE<span className="brand-ai">AI</span></span></Link>;
}
export function AppHeader({ children }: { children?: ReactNode }) {
  return <header className="app-header"><Brand /><span className="header-divider"/><span className="header-caption">THE ENGINEERING DOJO</span><nav>{children}<Link href="/docs"><BookOpen size={15}/> Docs</Link><Link href="/missions"><Layers size={15}/> Missions</Link><Link href="/missions/new" className="button small"><Plus size={14}/> New mission</Link></nav></header>;
}
export function Badge({ value }: { value: string }) {
  const friendly: Record<string, string> = { VERIFIED_AWAITING_APPROVAL: "Ready for approval", READY_FOR_AUTHORIZATION: "Plan ready", AWAITING_CLARIFICATION: "Needs your answer", BUDGET_EXHAUSTED: "Budget reached", FAILED_VERIFICATION: "Verification failed", CANCEL_REQUESTED: "Stopping" };
  const good = ["PASS", "DONE", "APPLIED", "APPROVED", "SUCCEEDED", "RESOLVED", "VERIFIED_AWAITING_APPROVAL"].includes(value);
  const bad = ["FAIL", "FAILED", "BLOCKED", "FAILED_VERIFICATION", "BUDGET_EXHAUSTED", "HIGH", "BLOCKING", "ERROR"].includes(value);
  return <span title={value} className={`badge ${good ? "good" : bad ? "bad" : ""}`}><CircleDot size={10}/>{friendly[value] || label(value)}</span>;
}
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty"><Command size={28}/><h3>{title}</h3>{children && <p>{children}</p>}</div>;
}
export function PageTitle({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return <div className="page-title"><span className="eyebrow"><Sparkles size={13}/>{eyebrow}</span><h1>{title}</h1>{children}</div>;
}
export function MissionNavigation({ id, view, returnTo, candidate = "", file = "" }: { id: string; view: string; returnTo?: string | null; candidate?: string; file?: string }) {
  const query = new URLSearchParams();
  if (returnTo) query.set("returnTo", returnTo);
  if (candidate) query.set("candidate", candidate);
  if (file) query.set("file", file);
  return <div className="mission-nav"><div className="segmented">{["workspace", "graph", "review"].map(item => <Link key={item} className={view === item ? "selected" : ""} href={`/missions/${id}/${item}?${query}`}><GitBranch size={14}/>{item === "graph" ? "Agent graph" : item === "review" ? "Review & apply" : "Workspace"}</Link>)}</div>{returnTo && returnTo !== id && <Link href={`/missions/${encodeURIComponent(returnTo)}/graph`} className="text-link">Return to active mission <ArrowUpRight size={14}/></Link>}</div>;
}
