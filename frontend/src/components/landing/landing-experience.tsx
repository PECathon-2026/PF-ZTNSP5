"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type Lenis from "lenis";
import type { MotionValues } from "./types";

const SamuraiScene = dynamic(() => import("./samurai-scene"), { ssr: false });

const guild = [
  { name: "Shogun", role: "Planner", symbol: "◇", description: "Turns your request into a clear plan, acceptance criteria, and assigned work.", line: "Every mission begins with intent." },
  { name: "Samurai", role: "Developer", symbol: "╱", description: "Investigates the repository and proposes a focused candidate change.", line: "A careful cut, never a blind one." },
  { name: "Sentinel", role: "Tester", symbol: "◎", description: "Runs authorized checks and returns real failures for repair.", line: "Evidence has the final word." },
  { name: "Shadow Council", role: "Reviewer", symbol: "◈", description: "Examines diffs for correctness, regressions, and risk.", line: "No change passes without scrutiny." },
];

function webGLAvailable() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch { return false; }
}

function SamuraiPoster() {
  return <svg className="samurai-poster" viewBox="0 0 300 560" fill="none" aria-hidden="true">
    <ellipse cx="151" cy="531" rx="118" ry="20" fill="#090b0b" opacity=".66" />
    <path d="M114 70 146 24l34 45 29 18-15 54h-92l-14-54z" fill="#171717" stroke="#8d602b" strokeWidth="3" />
    <path d="M69 110q81-38 165 0l-19 15q-67-22-126 1z" fill="#81231e" stroke="#c99a3a" strokeWidth="2" />
    <path d="M123 111h56l7 60-34 25-35-26z" fill="#181919" stroke="#946736" strokeWidth="2" />
    <path d="M122 160h60l18 38-50 22-47-23z" fill="#131515" />
    <path d="M99 191h108l28 168-83 43-83-45z" fill="#1c1d1c" stroke="#9d662b" strokeWidth="3" />
    <path d="M88 221h126m-121 42h118m-116 43h111" stroke="#a47435" strokeWidth="10" />
    <path d="M98 203 50 215l-25 52 53 25 31-42m99-47 46 14 22 53-47 23-34-43" fill="#202020" stroke="#965632" strokeWidth="3" />
    <path d="m87 338 63 46 69-46-17 60-39 23h-26l-43-23z" fill="#4d2720" />
    <path d="M102 405h44l-17 113H77zm53 0h44l28 113h-54z" fill="#181b1b" stroke="#6c4b31" strokeWidth="3" />
    <path d="M46 245 20 160" stroke="#c99a3a" strokeWidth="9" />
    <path d="m19 157-10-19" stroke="#f6e5b8" strokeWidth="8" />
    <path d="M29 186 11 120" stroke="#fae8bd" strokeWidth="3" />
    <path d="M31 186 8 120" stroke="#af301e" strokeWidth="1" />
  </svg>;
}

export function LandingExperience() {
  const journeyRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLElement>(null);
  const heroCopyRef = useRef<HTMLDivElement>(null);
  const agentsRef = useRef<HTMLElement>(null);
  const lenisRef = useRef<Lenis | null>(null);
  const motion = useRef<MotionValues>({ mouseX: 0, mouseY: 0, scroll: 0 });
  const [enhanced, setEnhanced] = useState(false);
  const [visible, setVisible] = useState(false);
  const [supported, setSupported] = useState(false);
  const [sceneReady, setSceneReady] = useState(false);
  const [agentIndex, setAgentIndex] = useState(0);
  const onSceneReady = useCallback(() => setSceneReady(true), []);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 769px) and (prefers-reduced-motion: no-preference)");
    const update = () => setEnhanced(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (!enhanced) return;
    setSupported(webGLAvailable());
    const intersection = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { rootMargin: "25% 0px" });
    if (journeyRef.current) intersection.observe(journeyRef.current);
    const visibility = () => { if (document.hidden) setVisible(false); else if (journeyRef.current) setVisible(journeyRef.current.getBoundingClientRect().bottom > 0); };
    document.addEventListener("visibilitychange", visibility);
    const pointer = (event: PointerEvent) => {
      motion.current.mouseX = (event.clientX / window.innerWidth - 0.5) * 2;
      motion.current.mouseY = (event.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener("pointermove", pointer, { passive: true });
    return () => { intersection.disconnect(); document.removeEventListener("visibilitychange", visibility); window.removeEventListener("pointermove", pointer); };
  }, [enhanced]);

  useEffect(() => {
    if (!enhanced || !journeyRef.current || !agentsRef.current || !heroRef.current) return;
    let cancelled = false;
    let dispose: (() => void) | undefined;
    void Promise.all([import("gsap"), import("gsap/ScrollTrigger"), import("lenis")]).then(([gsapModule, triggerModule, lenisModule]) => {
      if (cancelled) return;
      const gsap = gsapModule.gsap;
      const ScrollTrigger = triggerModule.ScrollTrigger;
      gsap.registerPlugin(ScrollTrigger);
      const lenis = new lenisModule.default({ smoothWheel: true, syncTouch: false, lerp: 0.12 });
      lenisRef.current = lenis;
      const onLenisScroll = () => ScrollTrigger.update();
      lenis.on("scroll", onLenisScroll);
      const ticker = (time: number) => lenis.raf(time * 1000);
      gsap.ticker.add(ticker);
      const scope = gsap.context(() => {
        gsap.to(heroCopyRef.current, {
          yPercent: -12, opacity: 0.25, ease: "none",
          scrollTrigger: { trigger: heroRef.current, start: "top top", end: "bottom top", scrub: 0.7 },
        });
        ScrollTrigger.create({
          trigger: agentsRef.current,
          start: "top top",
          end: () => `+=${Math.max(620, window.innerHeight) * (guild.length - 1)}`,
          pin: true,
          pinSpacing: true,
          scrub: 0.65,
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            const index = Math.min(guild.length - 1, Math.floor(self.progress * guild.length));
            setAgentIndex((previous) => previous === index ? previous : index);
            motion.current.scroll = 0.65 + self.progress * 1.5;
          },
          onLeaveBack: () => { motion.current.scroll = 0; setAgentIndex(0); },
        });
      }, journeyRef);
      const refresh = () => ScrollTrigger.refresh();
      window.addEventListener("load", refresh);
      void document.fonts.ready.then(() => { if (!cancelled) refresh(); });
      refresh();
      dispose = () => {
        window.removeEventListener("load", refresh);
        scope.revert();
        lenis.off("scroll", onLenisScroll);
        gsap.ticker.remove(ticker);
        lenis.destroy();
        lenisRef.current = null;
      };
    }).catch(() => { /* Native scrolling remains usable if motion code cannot load. */ });
    return () => { cancelled = true; dispose?.(); };
  }, [enhanced]);

  function scrollToAgents(event: React.MouseEvent<HTMLAnchorElement>) {
    if (lenisRef.current && agentsRef.current) {
      event.preventDefault();
      lenisRef.current.scrollTo(agentsRef.current);
    }
  }

  const current = guild[agentIndex];
  return <div className="cinematic-journey" ref={journeyRef}>
    <div className="cinematic-stage" aria-hidden="true">
      <div className={`scene-poster ${sceneReady && enhanced && visible && supported ? "scene-poster--dim" : ""}`}><span className="scene-sun" /><SamuraiPoster /></div>
      {enhanced && visible && supported && <div className="scene-canvas"><SamuraiScene motion={motion} agentIndex={agentIndex} onReady={onSceneReady} /></div>}
      <div className="scene-vignette" />
    </div>
    <div className="journey-panels">
      <section ref={heroRef} className="landing-hero landing-hero--cinematic" aria-labelledby="hero-title">
        <div className="landing-hero-content landing-hero-content--split" ref={heroCopyRef}>
          <p className="eyebrow">KAGE AI · AUTONOMOUS ENGINEERING GUILD</p>
          <span className="hero-emblem" aria-hidden="true">影</span>
          <h1 id="hero-title">Build in the<br /><em>shadows.</em></h1>
          <p className="hero-subtitle">Prove in the light.</p>
          <p className="hero-description">Your code. Our guild. Verified results. A multi-agent workspace that plans, builds, tests, and reviews changes before you approve them.</p>
          <div className="hero-actions"><Link href="/dojo" className="hero-cta">Open Dojo (IDE) <span aria-hidden="true">↗</span></Link><Link href="/setup" className="hero-secondary">Prepare a mission ↓</Link></div>
        </div>
        <a className="hero-scroll-cue" href="#agents" onClick={scrollToAgents}>Meet the guild <span aria-hidden="true">↓</span></a>
        <div className="hero-edge"><span>01 / THE THRESHOLD</span><span>SCROLL TO EXPLORE ↓</span></div>
      </section>
      <section ref={agentsRef} id="agents" className="agents-journey" aria-labelledby="agents-title">
        <div className="agents-journey-inner">
          <div className="agents-intro"><p className="eyebrow">02 · OUR AGENTS</p><h2 id="agents-title">The guild behind<br /><em>the work.</em></h2><p>Four distinct responsibilities. One evidence-led mission.</p></div>
          <div className="agent-feature" key={current.name} aria-live="polite">
            <div className="agent-feature-top"><span className="agent-feature-number">0{agentIndex + 1} / 0{guild.length}</span><span className="agent-feature-seal" aria-hidden="true">{current.symbol}</span></div>
            <p className="eyebrow">{current.role}</p><h3>{current.name}</h3><p className="agent-feature-line">{current.line}</p><p className="agent-feature-description">{current.description}</p>
            <div className="agent-progress" aria-label={`Agent ${agentIndex + 1} of ${guild.length}`}><i style={{ width: `${(agentIndex + 1) / guild.length * 100}%` }} /></div>
          </div>
          <div className="agent-mobile-list">{guild.map((agent, index) => <article key={agent.name} className="agent-mobile-card"><span className="eyebrow">0{index + 1} / {agent.role}</span><span aria-hidden="true">{agent.symbol}</span><h3>{agent.name}</h3><p>{agent.description}</p></article>)}</div>
          <p className="agents-aside">✦ Independent verification is a separate deterministic process, not an LLM agent.</p>
        </div>
      </section>
    </div>
  </div>;
}
