# M3 implementation and exit evidence

Date: 2026-10-29

**Status: COMPLETE — automated regression checks and the real-model M3 exit check passed.**

## Implemented

- Anthropic-compatible model adapter with strict response parsing, token accounting,
  bounded HTTP/network retries and total deadlines.
- Azure OpenAI Responses and Chat Completions support, including validated function
  arguments, tool-result conversion, and private stateless reasoning continuation.
- Single Samurai tool loop on a disposable workspace, with strict tool contracts,
  writer leases, stale-fingerprint checks, duplicate-call handling, bounded autonomy,
  and mandatory source read-back/diff inspection before candidate handoff.
- Captured baseline, deterministic tree fingerprints, and separate frozen candidate
  copies; original source files are never patched by the loop.
- Reproducible real-model smoke command and deterministic regression tests.

See [README.md](README.md) for invocation and the boundary between source-level M3
inspection and later behavioral verification/mission orchestration.

## Automated checks

Run from `backend/`:

```powershell
python -m pytest tests/unit -q
```

The M1/M2/M3 suite passes: **85 passed**, with one dependency deprecation warning.
`git diff --check` also passes. Tests use mocked HTTP responses and real filesystem
tools; they are not evidence of a successful live model call.

## Live check: passed on Azure OpenAI Responses

Command: `python -m app.agents.smoke`

- Provider: `azure_openai`; API: `responses`; deployment: `gpt-6-astra`.
- Reasoning effort: `low`; response storage disabled.
- Exit code: **0**; `exit_check_passed: true`.
- Six model turns and six successful tool calls:
  `list_files → read_file → apply_patch → read_file → read_diff → submit_candidate`.
- All source-level checks passed: original unchanged, expected source edit,
  candidate fingerprint matches, and only the requested file changed.
- Runtime: 15,717 ms; reported tokens: 6,997 input and 206 output.
- Evidence: `data/artifacts/miss-499fb701fcaa4656/art-6d915b01b3b9_m3-smoke.json`.

The real model edited only the synthetic disposable workspace. This proves M3's
source-level tool loop; behavioral tests, independent acceptance verification, and
patch approval/application remain later milestones.

### Azure compatibility finding

The deployed `gpt-6-astra` rejected function tools with reasoning on Chat
Completions. It also rejected the API's suggested `reasoning_effort=none`
workaround. The successful configuration uses Responses with `low` reasoning,
preserving encrypted reasoning continuation items between stateless turns.

## Earlier attempt: retired Anthropic-compatible gateway (resolved)

Command: `python -m app.agents.smoke`

- Configured model: `claude-3-5-sonnet-20241022`.
- The Messages API returned **HTTP 410 Gone** before any tool executed.
- A separate unauthenticated GET of `https://api.argmin.run/v1` also returned 410.
- Original synthetic repository remained unchanged.
- Local failure evidence:
  `data/artifacts/miss-e30afdf273ca403b/art-14299b0dabdd_m3-smoke.json`.

This blocker was resolved by the user-provided Azure endpoint and credentials.
The key is stored only in the ignored `backend/.env`; no credentials appear in
this report or the smoke evidence.
