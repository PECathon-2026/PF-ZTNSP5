"use client";

import { agents } from "@/lib/mission";
import type { Agent } from "@/lib/types";

/** Original vector figurines: no external assets or animation services. */
export function AgentArt({ agent, active = false }: { agent: Agent; active?: boolean }) {
  const person = agents.find(a => a.id === agent)!;
  return <svg viewBox="0 0 160 160" role="img" aria-label={`${person.name}, ${person.role}`} className={`agent-art ${active ? "working" : ""}`} style={{ color: person.color }}>
    <ellipse cx="80" cy="144" rx="42" ry="9" fill="currentColor" opacity=".12"/>
    <g className="figure">
      <path d="M47 129L55 83Q80 69 105 83L116 129Q81 146 47 129" fill="#222930" stroke="currentColor" strokeWidth="2"/>
      <path d="M60 84L80 114L100 84M80 114V137" fill="none" stroke="currentColor" strokeWidth="3"/>
      <path d="M49 114H111L113 125H48Z" fill="currentColor" opacity=".75"/>
      <path d="M67 136L65 145M94 136L97 145" stroke="#363e43" strokeWidth="11" strokeLinecap="round"/>
      <ellipse cx="80" cy="61" rx="28" ry="30" fill="#d7c4a6"/>
      <path d="M53 58Q47 20 80 25Q117 20 107 61L99 45Q78 53 59 45Z" fill="#141b22"/>
      <path d="M61 64H70M89 64H98" stroke="#172029" strokeWidth="3" strokeLinecap="round"/>
      <path d="M64 74Q80 83 96 74V87Q80 98 64 87Z" fill="#222930"/>
      {agent === "SHOGUN" && <><path d="M45 42L57 13L80 26L103 13L115 42Z" fill="#25302e" stroke="currentColor" strokeWidth="2"/><circle cx="80" cy="31" r="6" fill="currentColor"/><path d="M32 106H126V127H32Z" fill="#cbb994"/><path d="M29 103V130M129 103V130" stroke="currentColor" strokeWidth="7"/><path d="M47 113H109M47 119H83" stroke="#7f745b" strokeWidth="2"/></>}
      {agent === "SAMURAI" && <><path d="M53 50Q80 32 107 50" stroke="currentColor" strokeWidth="7"/><path d="M105 48L124 54L110 65" fill="currentColor"/><path d="M37 112L80 104L123 112L80 132Z" fill="#171f25" stroke="currentColor" strokeWidth="2"/><path d="M57 115L69 111M74 112L85 109M77 123L98 117" stroke="currentColor" strokeWidth="2"/></>}
      {agent === "SENTINEL" && <><path d="M46 43Q80 9 114 43L106 53H54Z" fill="#283632" stroke="currentColor" strokeWidth="2"/><path d="M99 98L128 107L123 131L106 143L91 125Z" fill="#243830" stroke="currentColor" strokeWidth="2"/><path d="M100 117L108 125L121 109" fill="none" stroke="currentColor" strokeWidth="3"/></>}
      {agent === "SHADOW_COUNCIL" && <><path d="M46 67Q40 19 80 15Q121 20 114 67L100 53Q80 28 60 53Z" fill="#302c3c" stroke="currentColor" strokeWidth="2"/><path d="M42 106L80 118L118 103L116 130L80 143L43 131Z" fill="#bcaecc"/><path d="M80 118V143M50 116L71 123M89 123L109 115" stroke="#645572" strokeWidth="2"/></>}
      <circle cx="43" cy="108" r="8" fill="#d7c4a6"/><circle cx="116" cy="109" r="8" fill="#d7c4a6"/>
    </g>
    {active && <g className="sparks" fill="currentColor"><circle cx="23" cy="63" r="2"/><circle cx="133" cy="46" r="3"/><path d="M126 78h10m-5-5v10" stroke="currentColor"/></g>}
  </svg>;
}
