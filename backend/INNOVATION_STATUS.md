# Evidence-first guild improvements — implementation status

Date: 2026-10-30. PS-001 rubric: Innovation 15, System Design 20, Problem Understanding 15, Tests 20, Feasibility 15, Presentation 15.

## Implemented and observed

1. **Structured checks:** sandbox image pins `pytest-json-report==1.5.0` with pytest 9.0.3. The image-owned runner writes a bounded JSON report in container `/tmp`, emits it to a bounded host capture and exits with pytest's actual exit code. Sentinel stores validated node IDs, collection outcomes, setup/call/teardown outcomes, command, report hash, contract hash, candidate fingerprint and report artifact. The verifier no longer parses `"1 passed"` from console text. Collection errors, missing reports, skipped-only, malformed summaries and mismatched selectors do not pass.
2. **Multiple mapped tests per criterion:** planner can select existing top-level, parametrized or class-method pytest nodes, and reuse one node across criteria. The candidate's verification contract includes criterion IDs/methods, accepted test-file hashes and contract version. Approval/application re-evaluate the contract and report artifacts; a changed test/report invalidates approval.
3. **Repository understanding:** bounded Python AST map of current functions/classes/imports/test nodes is supplied to Shogun and offered as an approved `repo_map` read-only tool to Shogun/Samurai. Hashes change with source; excluded files remain excluded. No embeddings, guessed symbol locations or arbitrary host imports.
4. **Security evidence:** image pins Bandit 1.9.4. Baseline/candidate scans run through the same restricted container (no network, non-root, read-only source). Sanitized JSON findings retain rule, severity, confidence and source line; raw source snippets are not persisted as Bandit results. HIGH findings route for repair; LOW/MEDIUM remain reviewable. Resolved baseline issues require new-candidate scan evidence.
5. **Challenge the Fix:** after approved checks pass, up to three isolated AST operator/integer-literal variants of changed top-level functions run the accepted pytest suite in Docker. Outcomes are `DETECTED`, `SURVIVED`, `INCONCLUSIVE` or `NOT_APPLICABLE`, fingerprint-bound to the unchanged candidate. Surviving variants are possible test gaps sent to review, **not** automatic code defects. Inconclusive execution blocks verification. Runtime is bounded by mission budgets and a 120-second total challenge cap.
6. **Decision timeline / proof card:** `GET /api/missions/{id}/proof` returns JSON, `?format=markdown` returns a bounded Markdown export with candidate, criteria, test/security/challenge results, finding-to-task causal links, plan revisions, budgets and approval status. No raw repository code, check stdout or private model reasoning is in the proof card.

### Independent unfamiliar-repository demonstration

`python -m app.agents.unfamiliar_demo` ran against `sample-repos/unfamiliar/` with a request that **did not name source or test files**. Mission `miss-b186039f` discovered `ledger.py` and its tests, used a real hosted model, ran real restricted Docker tests and Bandit, and reached `VERIFIED_AWAITING_APPROVAL` with both criteria `PASS` on candidate `cand-2541b169178e4db4` (fingerprint `7d383dd2c0f7d39a492f0679670b74626e4b75f631be8522d62d4cc97ce21706`). The challenge generated two variants, `<` → `<=` and an integer-literal change: **both were detected by real tests**. Original repository was unchanged. Evidence: `backend/data/demos/unfamiliar-miss-b186039f.json` and `GET /api/missions/miss-b186039f/proof` using this machine's local database.

Another live synthetic mission `miss-9de5c0a8` reached the same gate, with three mapped criteria and one detected integer-literal variant. Neither candidate has a human approval or applied original patch. Earlier M8 five-for-five runs predate these stronger contracts and must not be treated as new verifier passes.

## Explicit limitations / next decisions

- Test gaps now pause **before source authorization**: Sentinel proposes bounded pytest files and explicit criterion mappings; a human reads the complete assertions and accepts the proposal hash separately from authorizing Samurai. Accepted tests execute in temporary baseline/candidate verification views and are bound to the verification contract. Declined, changed or unaccepted proposals cannot authorize edits. The developer never writes or changes these test files. Proposed test expectations can still be wrong; human review is essential.
- Sentinel checks and Shadow Council's preliminary source review now start together on a frozen candidate. Material check findings or surviving challenge variants trigger a second evidence-informed review. The TUI reads persisted task states and may show both agents LIVE; it does not pretend the preliminary review saw unfinished checks.
- The repository map supports small Python projects and common top-level/class pytest functions; dependency graph ranking and large-repository semantic indexing are not implemented.
- The challenge uses a narrow bounded mutation set, not exhaustive `mutmut`. No mutmut package was installed. A surviving variant may be equivalent; reviewer/human judgment remains necessary.
- A verifier passing mapped tests establishes that those tests ran; it cannot prove the test expectations fully express natural-language intent.
- Multi-file application remains per-file atomic with durable rollback, not globally atomic to concurrent external readers. Human approval is still required; no sample-repo candidate was applied.
- The full manual browser walkthrough is deferred as requested. Controlled-model tests remain distinct from real-model/container evidence.
- The check-runner image was rescanned after installing pytest-json-report and Bandit: Docker Scout reports 28 remaining vulnerabilities (0 critical, 1 high, 1 medium, 26 low), the same count as before; no vulnerability exceptions were added.

## License/dependency notes

`pytest-json-report` is MIT-licensed and Bandit is Apache-2.0. Aider's repository-map design was a reference; the bounded AST implementation is original. `mutmut` is a design reference, not an installed dependency. No repository source code from these tools was copied into the backend. Keep pinned image packages and rerun Scout when they change.
