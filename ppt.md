---
marp: true
theme: default
size: 16:9
paginate: true
style: |
  section { background: #090a0c; color: #efe4cd; font-family: Arial, sans-serif; padding: 55px 70px; font-size: 25px; line-height: 1.4; }
  h1 { color: #e8c66a; font-size: 46px; letter-spacing: -1px; }
  h2 { color: #efe4cd; font-size: 30px; }
  strong { color: #e8c66a; }
  a { color: #c9b787; }
  table { font-size: 21px; width: 100%; }
  th { background: #29251c; color: #e8c66a; }
  td { background: #14181f; color: #efe4cd; }
  pre { background: #14181f; color: #efe4cd; font-size: 19px; }
  section.lead h1 { font-size: 76px; }
  section.lead { text-align: center; }
  blockquote { border-left: 4px solid #c99a3a; color: #d5c7a7; padding-left: 20px; }
  footer { color: #a6a39d; font-size: 13px; }
footer: KAGE AI · PECathon 2026 · PS-001
---

<!-- _class: lead -->

# KAGE AI

## One mission. An entire guild.

**Evidence-first, multi-agent software engineering.**

Build in the shadows. Prove in the light.

PECathon 2026 · PS-001 · PF-ZTNSP5

<!--
SLIDE 1 — INTRO | ~20 seconds
Visual: full-bleed Japanese night threshold, a restrained gold wordmark, and one clear product promise. Keep the title readable over the image.
Say: "AI can generate a patch. KAGE brings an entire engineering guild to the change—and makes that change earn its evidence."
-->

---

# Generating code is easy. Trusting it is hard.

### The missing step is accountable engineering.

- **A plausible patch is not proof:** generated code still needs testing, review, and verification.
- **Context is fragmented:** developers jump between prompts, editors, test logs, and review tools.
- **Passing tests can mislead:** weak assertions or a changed test oracle can hide a bad fix.

> Developers need to understand **what changed, why it changed, and what actually validates it**.

<!--
SLIDE 2 — PROBLEM | ~35 seconds
Visual: a fragmented prompt → patch → logs → review workflow, contrasted with a missing evidence link.
Say: "The bottleneck is not producing code. It is turning that code into a change someone can confidently review and accept."
Audience: developers and reviewers working with small Python repositories.
-->

---

# Commission a change. Receive a candidate with receipts.

### Four specialist roles. One evidence-first workspace.

| Guild member | Engineering responsibility |
| --- | --- |
| **Shogun** | Understand the repository, plan tasks, map acceptance criteria. |
| **Samurai** | Implement and repair inside a disposable workspace. |
| **Sentinel** | Run restricted checks and record structured evidence. |
| **Shadow Council** | Review the candidate and file evidence-linked findings. |

An **independent deterministic verifier** evaluates the evidence.
**You** authorize execution and decide whether the verified candidate lands.

<!--
SLIDE 3 — SOLUTION | ~35 seconds
Visual: four guild seals around a candidate, with the verifier and human decision gate clearly separate.
Say: "These names represent actual engineering roles. The verifier is not another model saying the answer looks good—it checks recorded evidence."
-->

---

# A controlled pipeline—not an endless conversation.

```text
Repository + brief → Shogun plan → Human authorization
                              ↓
                    Samurai → Frozen candidate
                              ↓
               Sentinel checks + Shadow Council review
                              ↓
             Independent verification → Human approval
                              ↓
                       Apply / export patch
```

- **Bounded recovery:** failures route into repair, within time, token, tool-call, and repair budgets.
- **Traceable execution:** durable SSE events connect tasks, candidates, findings, and evidence.

**Stack:** Next.js / React / Monaco / Three.js → FastAPI → SQLite + restricted Docker checks.

<!--
SLIDE 4 — SYSTEM DESIGN | ~45 seconds
Visual: use the pipeline as the main diagram. Draw a small repair loop from checks/review back to implementation; show the human gates explicitly.
Say: "Only the developer role writes to the disposable workspace. The original repository is updated through a separate approval and application flow."
-->

---

# Watch the mission. Inspect the proof.

### Demo: reject negative debits without breaking positive or zero amounts.

1. **Commission:** connect a repository, write the brief, review the acceptance gate.
2. **Explore:** pan and zoom the mission map; select roles or tasks to inspect their work.
3. **Review:** open real source, compare the original with a frozen candidate, inspect findings.
4. **Verify:** follow each criterion to its recorded check output and candidate fingerprint.
5. **Decide:** approve or reject the candidate; application remains a separate action.

> A **3D threshold**, **interactive mission field**, **code workstation**, and **proof desk** turn the lifecycle into an explorable product.

<!--
SLIDE 5 — PRODUCT DEMO | ~60 seconds
Visual: three large, real screenshots—mission cockpit, Monaco comparison, and parchment proof desk. Spend the slide on the product, not a list of frameworks.
Say: "This brief does not name a source file or test. The guild discovers the relevant code, while the interface lets a human inspect the engineering decisions."
Demo preparation: use a configured model and Docker runtime for live execution. The documented unfamiliar-repository run is the evidence-backed recorded alternative. Keep UI interaction footage and recorded backend execution clearly labeled.
Frontend captures available locally: /tmp/opencode/shots/cockpit-1440.png, workbench-1440.png, and proof-desk-1440.png.
-->

---

# Our differentiator: challenge the fix itself.

- **Challenge the Fix:** run bounded mutated variants of changed functions. Do the accepted tests detect a damaged implementation?
- **Trusted test contracts:** named test nodes and test/report hashes bind the checks; unmapped criteria require human-reviewed test coverage.
- **Candidate-bound proof:** the frozen source fingerprint connects criteria, checks, findings, and approval. Changed bindings invalidate the decision.
- **A reviewable decision trail:** replayable events and exportable JSON/Markdown proof cards show how findings led to tasks and repairs.

> We probe the **strength of the evidence**, not just whether a test command returned success.

<!--
SLIDE 6 — INNOVATION | ~50 seconds
Visual: candidate → two challenge variants → accepted tests → detected/survived outcomes → review gate.
Say: "Mutation testing is an established technique. Our innovation is incorporating a bounded challenge into a candidate-bound, human-approved engineering workflow. A surviving variant is a possible test gap—not an automatic declaration that the fix is wrong."
Source: backend/INNOVATION_STATUS.md, especially items 1, 2, 5, and 6.
-->

---

# Built. Tested. Demonstrated.

| Engineering validation | Current frontend | Latest recorded challenge |
| --- | --- | --- |
| **193 backend tests passed**¹ | **8 frontend tests passed**² | **2 / 2 variants detected**¹ |

- **Unfamiliar-repository run:** a real hosted model discovered source and tests without filename hints; restricted Docker checks supported **both criteria passing**.
- **Human gate preserved:** the candidate reached `VERIFIED_AWAITING_APPROVAL`; the original repository remained unchanged.
- **Product validation:** typecheck, production build, desktop interaction checks, and automated accessibility scans passed for the current frontend.

**Value:** fewer context switches, reviewable engineering decisions, and bounded execution.
**Scope today:** small Python repositories. **Next:** more language runners and larger-repository indexing.

<!--
SLIDE 7 — VALIDATION, IMPACT & FEASIBILITY | ~35 seconds
Visual: three large evidence metrics, then a compact real demo result showing two PASS criteria and the human approval gate.
¹ Backend figures and live-run outcomes are documented in backend/FINAL_VERIFICATION_REPORT.md and backend/INNOVATION_STATUS.md. The unfamiliar-repository mission is miss-b186039f; its two challenge variants were detected. These are recorded backend results, not claims that this local frontend session reran them.
² The current param frontend has 8 passing unit tests, a passing typecheck/build, and Playwright checks at 1280/1440/1920. Backend documentation references an older 6-test frontend and does not supersede the current frontend results.
Do not claim measured productivity gains, production adoption, exhaustive mutation coverage, or a live original-repository application of the documented candidate.
-->

---

<!-- _class: lead -->

# Thank you.

## Let the guild write the patch.
## Let the evidence earn your trust.

**KAGE AI — Build in the shadows. Prove in the light.**

Questions? Let’s explore a mission.

[Project repository · frontend on `param`](https://github.com/PECathon-2026/PF-ZTNSP5/tree/param)

<!--
SLIDE 8 — THANK YOU & CLOSE | ~20 seconds
Visual: one KAGE seal, the closing statement, and a QR code pointing to the repository URL above.
Say: "KAGE is our answer to a simple question: when AI changes your code, what evidence should earn your approval? Thank you—we would love to show you the mission field."
Total target pitch: approximately five minutes including the demo.
-->
