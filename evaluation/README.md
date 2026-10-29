# M8 evaluation

Five small checked-in fixtures live in `sample-repos/{feature,bug,recovery,security,unexpected}`.
Run these commands from `backend/`:

```powershell
python -m app.evaluation --mode controlled
python -m app.evaluation --mode live
```

Each invocation creates a unique `evaluation/results/run-*/` directory with
`summary.json`, one JSON report per scenario, SQLite state, candidate snapshots and
bounded evidence artifacts. The controlled run exercises the actual controller,
model protocol, workspace editing, candidate freezing, finding routing, repair
planning and clarification. Its model is scripted and its source-level check
oracle is **not pytest or a container execution**; records carry
`controlled_evaluation: true`, and the Independent Verifier refuses to promote
them to approved evidence. No fixture code is executed on the host.

The live mode uses the configured model and Docker-only check runner. Without
Docker Desktop's Linux engine, it writes five `BLOCKED` reports and exits 1
before any model calls. With Docker, build the check image first (see
`backend/README.md`). The live mode is nondeterministic and may fail a scenario
if the model chooses another trajectory; its reports preserve that outcome.
Neither mode approves or applies a project change to the original fixtures.

Latest five-for-five live run: `results/run-20261029T200847Z-c8bec9cb/summary.json`.
