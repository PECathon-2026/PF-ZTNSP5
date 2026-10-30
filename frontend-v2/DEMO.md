# KAGE UI demo handoff

Ready-to-read narration and an exact 0:00–2:00 shot list:
[VIDEO_SCRIPT_2MIN.md](../VIDEO_SCRIPT_2MIN.md).

## Successful real workflow

Mission **`miss-aef4cc8a`** reached **APPLIED** through the new browser UI using the
configured real model and restricted Docker checks on a freshly generated demo repo.

- All four acceptance criteria passed: full pages (including size one), final
  partial page, empty input, and invalid-page validation.
- 13 model turns and 24 tool calls were recorded; 0 repair rounds for this mission.
- Source remained unchanged both before and immediately after approval.
- Application required a second explicit browser action.
- Frozen tests remained unchanged.
- Applied raw-byte fingerprint matched the approved candidate:
  `0118bf58d525c48738c035d5adc2048e1f5c3d045f2715c26bd15e59b7200131`.
- The browser recorded no uncaught errors for this successful workflow.

This was automated testing of approval/apply on the generated fixture, not approval
of user project changes. The initial test oracle incorrectly compared Windows CRLF
source with normalized LF API text. `integrity-recheck.json` records the subsequent
successful read-only raw-fingerprint verification; the initial report is retained.

Local artifacts:
`test-results/live-1793326118241/report.json`, `integrity-recheck.json`, `proof.json`,
`graph.png`, `review-before-approval.png`, and `failure.png` (the final applied page
when the original test oracle complained).

## Honest failure evidence

- `miss-6ba3daab`: full suite and criterion checks passed, but a transient Docker
  readiness failure before Bandit blocked the run. No approval or apply occurred.
- `miss-66cd825b`: the reviewer identified missing size-one coverage in the first
  fixture. Repair could not complete under the frozen-test constraint. It remains
  blocked; the next fresh fixture added that boundary case before planning.

The live exercise also exposed and fixed locale-dependent budget formatting that
caused the mission setup form to reset during hydration.

## Two-minute presentation

1. Open `/` and introduce the four roles.
2. Open `/missions/miss-aef4cc8a/workspace`; show the real source diff and checks.
3. Open its graph, click a connection, then open the linked execution evidence.
4. Click Samurai and compare **This mission** with **Previous missions**.
5. Open Review & apply; explain VERIFIED, APPROVED and APPLIED as separate states.
6. For a fresh live demonstration, use the generated pagination fixture with its
   tests included, choose Extended budget, and keep the request source-only.

Do not promise every arbitrary repo will finish within the demonstration window.
Docker readiness and model behavior can still stop a mission; the UI records those
failures rather than claiming success.
