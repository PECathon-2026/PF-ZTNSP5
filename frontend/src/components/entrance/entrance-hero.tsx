"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowUpRight, Layers, ScanLine } from "lucide-react";
import type { Mission } from "@/lib/types";
import { missionMeta } from "@/lib/status";

const GateScene = dynamic(() => import("./gate-scene"), { ssr: false });
type Props = { lastMission: Mission | null; missionCount: number; loading: boolean; archiveError: string | null; onArchive: () => void; onGuild: () => void; onReadiness: () => void };

export function EntranceHero({ lastMission, missionCount, loading, archiveError, onArchive, onGuild, onReadiness }: Props) {
  const router = useRouter();
  const [crossing, setCrossing] = useState(false);
  const [inside, setInside] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  function initialize() {
    if (crossing) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { router.push("/setup"); return; }
    setCrossing(true);
    timer.current = setTimeout(() => router.push("/setup"), 1000);
  }

  return <section className={`threshold${crossing ? " is-crossing" : ""}${inside ? " is-inside" : ""}`} aria-labelledby="threshold-title">
    <div className="threshold-backdrop" aria-hidden="true"><img src="/images/entrance-night.jpg" alt="" width={1600} height={900} fetchPriority="high" /><div className="threshold-backdrop-grade" /></div>
    <GateScene crossing={crossing} inside={inside} onInside={() => setInside((value) => !value)} />
    <div className="threshold-scrim" aria-hidden="true" />
    <div className="threshold-copy">
      <p className="threshold-overline mono"><span />AUTONOMOUS ENGINEERING, REIMAGINED</p>
      <p className="threshold-wordmark">KAGE <span>AI</span></p>
      <h1 id="threshold-title">One mission.<br />An entire guild.</h1>
      <p className="threshold-description">You set the intention. Four specialist agents plan, build, test, and review. Every change earns its evidence.</p>
      <div className="threshold-actions"><button className="threshold-primary" disabled={crossing} onClick={initialize}><span>{crossing ? "Entering the chamber…" : "Initialize a mission"}</span><ArrowRight size={20} /></button>
        <Link href="/setup?focus=repository" className="threshold-secondary">Connect repository <ArrowUpRight size={15} /></Link>
      </div>
      <p className="threshold-promise mono">DISPOSABLE WORKSPACE <span>/</span> HUMAN APPROVAL <span>/</span> VERIFIED EVIDENCE</p>
    </div>
    <div className="threshold-world-note" aria-hidden="true"><span className="threshold-world-kanji">影</span><span className="mono">THE THRESHOLD<br />MOVE YOUR POINTER TO EXPLORE</span></div>
    <div className="threshold-bottom">
      {lastMission ? <Link className="threshold-resume" href={`/missions/${lastMission.id}`}><div className="threshold-resume-mark" aria-hidden="true">◇</div><div><span className="mono">RETURN TO THE FIELD</span><strong>{lastMission.request_text}</strong><span className="threshold-resume-meta mono">{lastMission.id} <span data-tone={missionMeta(lastMission.status).tone}>{missionMeta(lastMission.status).label}</span></span></div><ArrowUpRight size={20} /></Link>
        : <div className="threshold-first"><span className="mono">{loading ? "READING THE ARCHIVE" : archiveError ? "ARCHIVE UNAVAILABLE" : "YOUR FIRST MISSION AWAITS"}</span><p>{archiveError ? "Open the mission archive to retry the connection." : loading ? "Checking for your last recorded mission…" : "Connect a repository. Give the guild its brief."}</p></div>}
      <div className="threshold-utilities"><button onClick={onGuild}><Layers size={17} /><span>The guild</span><ArrowUpRight size={13} /></button><button onClick={onReadiness}><ScanLine size={17} /><span>Runtime readiness</span><ArrowUpRight size={13} /></button><button onClick={onArchive}><span className="mono threshold-archive-count">{String(missionCount).padStart(2, "0")}</span><span>Mission archive</span><ArrowUpRight size={13} /></button></div>
    </div>
  </section>;
}
