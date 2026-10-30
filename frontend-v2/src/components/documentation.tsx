"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, ArrowUpRight, BookOpen, Check, ChevronRight, Clipboard, FileText, Github, Search, ShieldCheck, Terminal, X } from "lucide-react";
import { AppHeader } from "./ui";
import { docSections, projectUrl, searchDocs, type DocBlock } from "@/lib/documentation";

function CodeBlock({ title, text }: { title?: string; text: string }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!copied && !error) return;
    const timer = setTimeout(() => { setCopied(false); setError(false); }, 2500);
    return () => clearTimeout(timer);
  }, [copied, error]);
  async function copy() {
    try { await navigator.clipboard.writeText(text); setCopied(true); setError(false); }
    catch { setError(true); }
  }
  return <div className="docs-code"><div className="docs-code-heading"><span><Terminal size={14}/>{title || "Example"}</span><button type="button" onClick={copy} aria-label={`Copy ${title || "example"}`}><span aria-live="polite">{copied ? "Copied" : error ? "Select text to copy" : "Copy"}</span>{copied ? <Check size={13}/> : <Clipboard size={13}/>}</button></div><pre tabIndex={0} aria-label={title}><code>{text}</code></pre></div>;
}

function Block({ block }: { block: DocBlock }) {
  switch (block.kind) {
    case "text": return <p>{block.text}</p>;
    case "callout": return <aside className={`docs-callout ${block.tone || "gold"}`}><ShieldCheck size={19}/><div><h3>{block.title}</h3><p>{block.text}</p></div></aside>;
    case "code": return block.title === "Full MIT License"
      ? <details className="docs-license"><summary><FileText size={16}/> Read the full MIT License</summary><CodeBlock title={block.title} text={block.text || ""}/></details>
      : <CodeBlock title={block.title} text={block.text || ""}/>;
    case "steps": return <ol className="docs-steps">{block.items?.map((item, index) => <li key={item.title}><span className="docs-step-number">{String(index + 1).padStart(2, "0")}</span><div><h3>{item.title}</h3><p>{item.text}</p></div></li>)}</ol>;
    case "cards": return <div className="docs-cards">{block.items?.map(item => <div className="docs-card" key={item.title}><span className="tiny-diamond"/><h3>{item.title}</h3><p>{item.text}</p></div>)}</div>;
    case "table": return <div className="docs-table-wrap" tabIndex={0} role="region" aria-label={block.columns?.join(", ")}><table><thead><tr>{block.columns?.map(column => <th scope="col" key={column}>{column}</th>)}</tr></thead><tbody>{block.rows?.map(row => <tr key={row[0]}>{row.map((cell, index) => index === 0 ? <th scope="row" key={index}>{cell}</th> : <td key={index}>{cell}</td>)}</tr>)}</tbody></table></div>;
    case "faq": return <div className="docs-faq">{block.items?.map(item => <details key={item.title}><summary>{item.title}</summary><p>{item.text}</p></details>)}</div>;
    case "links": return <div className="docs-links">{block.items?.map(item => {
      const external = item.href?.startsWith("http");
      return <a key={item.title} href={item.href} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}><div><strong>{item.title}</strong><p>{item.text}</p></div>{external ? <ArrowUpRight size={17}/> : <ArrowRight size={17}/>}</a>;
    })}</div>;
  }
}

export function Documentation() {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState("overview");
  const sections = useMemo(() => searchDocs(query), [query]);
  useEffect(() => {
    if (!sections.length) return;
    setActive(sections[0].id);
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible[0]) setActive(visible[0].target.id);
    }, { rootMargin: "-8% 0px -65% 0px", threshold: 0 });
    sections.forEach(section => { const element = document.getElementById(section.id); if (element) observer.observe(element); });
    return () => observer.disconnect();
  }, [sections]);

  return <div className="docs-shell">
    <AppHeader/>
    <main id="main" className="docs-page">
      <section className="docs-hero">
        <div><span className="eyebrow"><BookOpen size={14}/> THE FIELD MANUAL · KAGE AI</span><h1>Know the tools.<br/><em>Keep the final word.</em></h1><p>Everything you need to set up the dojo, guide a mission, and turn a candidate patch into a decision you can explain.</p><div className="docs-hero-actions"><Link href="/missions/new" className="button primary">Start a mission <ArrowRight size={16}/></Link><a href="#quick-start" className="text-link" onClick={() => setQuery("")}>Read the setup guide <ChevronRight size={15}/></a></div></div>
        <aside className="docs-field-card"><span className="eyebrow">BEFORE YOU BEGIN</span><span className="docs-field-symbol" aria-hidden="true">書</span><div><span>Environment</span><strong>Local · single-user</strong></div><div><span>Workflow</span><strong>Python repositories</strong></div><div><span>Decision</span><strong>Evidence → approval → apply</strong></div><a href="#license" onClick={() => setQuery("")}><ShieldCheck size={14}/> MIT licensed <ArrowUpRight size={13}/></a></aside>
      </section>
      <div className="docs-layout">
        <aside className="docs-sidebar">
          <label className="docs-search-label" htmlFor="docs-search">Find an answer</label>
          <div className="docs-search"><Search size={16}/><input id="docs-search" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="API key, Docker, license…" autoComplete="off"/>{query && <button aria-label="Clear documentation search" onClick={() => setQuery("")}><X size={14}/></button>}</div>
          <nav aria-label="Documentation sections">{(["Start here", "Working with the guild", "Reference"] as const).map(group => {
            const items = sections.filter(section => section.group === group);
            return items.length ? <div className="docs-nav-group" key={group}><h2>{group}</h2>{items.map(section => <a key={section.id} href={`#${section.id}`} className={active === section.id ? "selected" : ""} aria-current={active === section.id ? "location" : undefined} onClick={() => setActive(section.id)}>{section.title}<ChevronRight size={13}/></a>)}</div> : null;
          })}</nav>
          <a href={projectUrl} className="docs-source" target="_blank" rel="noopener noreferrer"><Github size={15}/> Source & issues <ArrowUpRight size={13}/></a>
        </aside>
        <div className="docs-content">
          {query && <p className="docs-search-status" role="status">{sections.length} of {docSections.length} sections match “{query}”</p>}
          {!sections.length && <section className="docs-empty"><Search size={30}/><h2>No matching section.</h2><p>Try “Docker”, “API key”, “approval” or “license”.</p><button className="button" onClick={() => setQuery("")}>Show all documentation</button></section>}
          {sections.map(section => <section id={section.id} className="docs-section" key={section.id} aria-labelledby={`${section.id}-heading`}><header><span className="eyebrow">{section.group} · {String(docSections.indexOf(section) + 1).padStart(2, "0")}</span><h2 id={`${section.id}-heading`}><a href={`#${section.id}`} aria-label={`Link to ${section.title}`}>{section.title}<span aria-hidden="true">#</span></a></h2><p>{section.description}</p></header><div className="docs-section-body">{section.blocks.map((block, index) => <Block block={block} key={index}/>)}</div></section>)}
          <footer className="docs-bottom"><div><span className="eyebrow">READY WHEN YOU ARE</span><h2>A clear brief.<br/><em>A better next change.</em></h2></div><Link href="/missions/new" className="button primary">Enter the dojo <ArrowRight size={16}/></Link></footer>
        </div>
      </div>
      <footer className="docs-footer"><span>KAGE AI · PECATHON 2026 · PS-001</span><a href="/license">MIT License · © 2026 KAGE AI contributors</a><a href="#main">Back to top ↑</a></footer>
    </main>
  </div>;
}
