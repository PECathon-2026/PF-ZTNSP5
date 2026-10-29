"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, FolderGit2, Feather, ShieldCheck, Check } from "lucide-react";
import { RepositoryPanel, restoreActiveRepository } from "./repository-panel";
import { MissionBrief, type BriefDraft } from "./mission-brief";
import { preflightMeta } from "@/lib/status";
import type { StoredRepository } from "@/lib/types";
import "./commissioning.css";

const STEPS = [{ title: "Connect the workspace", detail: "Repository & preflight", icon: FolderGit2 }, { title: "Write the intention", detail: "Brief & acceptance criteria", icon: Feather }, { title: "Review the commission", detail: "The exact recorded scope", icon: ShieldCheck }];

export function SetupScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [connected, setConnected] = useState<StoredRepository | null>(null);
  const [focusRequest, setFocusRequest] = useState(0);
  const [restored, setRestored] = useState(false);
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<BriefDraft>({ request: "", criteria: [], ready: false });
  const receiveDraft = useCallback((next: BriefDraft) => setDraft(next), []);
  useEffect(() => { const stored = restoreActiveRepository(); if (stored) setConnected(stored); setRestored(true); }, []);
  useEffect(() => { if (searchParams.get("focus") === "repository") { setStep(0); setFocusRequest((value) => value + 1); } }, [searchParams]);
  const words = draft.request.trim() ? draft.request.trim().split(/\s+/).length : 0;
  return <div className="commissioning-desk">
    <aside className="commissioning-rail"><Link className="commissioning-back" href="/"><ArrowLeft size={14} /> The threshold</Link><p className="mono commissioning-overline">A NEW COMMISSION</p><h1>Intention,<br />into action.</h1><p className="commissioning-description">Give the guild a place to work, a clear intention, and a definition of done.</p>
      <nav className="commissioning-steps" aria-label="Mission setup steps">{STEPS.map((item, index) => { const Icon = item.icon; const complete = index === 0 ? Boolean(connected) : index === 1 ? words > 2 : draft.ready;
        return <button key={item.title} aria-current={step === index ? "step" : undefined} onClick={() => setStep(index)}><span className="commissioning-step-icon">{complete && step !== index ? <Check size={17} /> : <Icon size={17} />}</span><span><strong>{item.title}</strong><small>{item.detail}</small></span><span className="mono commissioning-step-number">0{index + 1}</span></button>;
      })}</nav>
      <div className="commissioning-readout"><div><strong className="mono">{words}</strong><span>brief words</span></div><div><strong className="mono">{draft.criteria.length}</strong><span>criteria drafted</span></div></div>
      <p className="commissioning-boundary"><ShieldCheck size={16} /> Changes stay in a disposable workspace until a verified candidate receives your approval.</p>
    </aside>
    <section className="commissioning-stage" aria-label="Commission form"><header className="commissioning-stage-head"><span className="mono">0{step + 1} / {STEPS[step].detail.toUpperCase()}</span>{connected && <span className="status" data-tone={preflightMeta(connected.preflight.status).tone}>{connected.name} · {connected.preflight.status}</span>}</header>
      <div className="commissioning-content"><div hidden={step !== 0}><RepositoryPanel connected={connected} onConnected={setConnected} focusRequest={focusRequest} /></div><div hidden={step === 0}>{restored ? <MissionBrief connected={connected} phase={step === 2 ? "review" : "brief"} onDraftChange={receiveDraft} onStarted={(id) => router.push(`/missions/${id}`)} /> : <p role="status">Restoring the repository session…</p>}</div></div>
      <footer className="commissioning-actions"><p>{step === 0 ? "Repository access is preflighted before any execution." : step === 1 ? "Be specific about behavior. The guild will handle the implementation." : "Review scope and readiness before recording the mission."}</p>{step < 2 && <button className="btn btn--primary" onClick={() => setStep(step + 1)}>{step === 0 ? "Write the brief" : "Review commission"}<ArrowRight size={15} /></button>}{step > 0 && <button className="btn btn--ghost" onClick={() => setStep(step - 1)}><ArrowLeft size={14} /> Back</button>}</footer>
    </section>
  </div>;
}
