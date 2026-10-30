import Link from "next/link";
import { ArrowRight, ArrowUpRight, Code2, GitBranch, ShieldCheck } from "lucide-react";
import { Brand } from "@/components/ui";
import { AgentArt } from "@/components/agent-art";
import { agents } from "@/lib/mission";

export default function Home() {
  return <main id="main" className="landing">
    <header className="landing-header"><Brand/><nav><a href="#guild">Meet the guild</a><Link href="/docs">Docs</Link><Link href="/missions">Mission archive</Link><Link href="/missions/new" className="button small">Enter the dojo <ArrowUpRight size={14}/></Link></nav></header>
    <section className="hero">
      <div className="hero-copy"><span className="eyebrow"><span className="tiny-diamond"/> PECATHON 2026 · PS—001</span><h1>Great code.<br/>A little <em>shadow</em><br/>work.</h1><p>Give your idea to the guild. Watch four agents plan, build, check and review—then decide what makes it into your code.</p><div className="hero-actions"><Link className="button primary" href="/missions/new">Start a mission <ArrowRight size={17}/></Link><a href="#guild" className="text-link">Meet your agents <ArrowUpRight size={15}/></a></div><div className="hero-note"><ShieldCheck size={15}/> Disposable workspace. Evidence first. You approve.</div></div>
      <div className="sanctuary" aria-label="Illustrated moonlit engineering sanctuary" role="img"><div className="moon"/><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="mountain mountain-back"/><div className="mountain mountain-front"/><div className="torii"><div className="torii-roof"/><div className="torii-beam"/><div className="torii-left"/><div className="torii-right"/><div className="torii-sign">影</div></div><div className="sanctuary-floor"/><div className="hero-figurine"><AgentArt agent="SAMURAI"/></div><span className="vertical-inscription">THE ART OF INTENTIONAL CODE</span><div className="scene-caption"><span className="tiny-diamond"/> THE GUILD AWAITS YOUR INSTRUCTION</div></div>
    </section>
    <div className="principle-strip"><span><Code2 size={17}/> A real developer workspace</span><span><GitBranch size={17}/> A visible agent workflow</span><span><ShieldCheck size={17}/> A human-owned decision</span></div>
    <section className="guild-section" id="guild"><div className="section-heading"><div><span className="eyebrow">FOUR DISCIPLINES. ONE GUILD.</span><h2>Meet your quiet overachievers.</h2></div><p>Different roles. Shared evidence.<br/>Every handoff leaves a trace.</p></div><div className="guild-grid">{agents.map((agent, i) => <article className="guild-card" key={agent.id}><div className="card-number">0{i + 1}<span>{agent.symbol}</span></div><AgentArt agent={agent.id}/><span className="eyebrow">{agent.role}</span><h3>{agent.name}</h3><p>{["Turns your request into clear tasks and acceptance criteria.", "Crafts changes in an isolated copy of your repository.", "Runs checks and records what passed—and what didn’t.", "Reviews the candidate and sends findings back to the guild."][i]}</p></article>)}</div></section>
    <section className="landing-cta"><span className="eyebrow">YOUR NEXT CHANGE STARTS HERE</span><h2>Let the guild do the groundwork.<br/><em>Keep the final word.</em></h2><Link href="/missions/new" className="button primary">Enter the dojo <ArrowRight size={17}/></Link></section>
    <footer className="landing-footer"><Brand/><span>Built for PECathon · Designed for developers.</span><Link href="/docs#license">Documentation & MIT License</Link></footer>
  </main>;
}
