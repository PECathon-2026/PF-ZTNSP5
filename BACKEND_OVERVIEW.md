# DevPilot / KAGE AI — Backend Architecture & System Reference

> **Repository State:** PECathon-2026 / PF-ZTNSP5  
> **Milestones Completed:** M1 through M8  
> **Core Stack:** Python 3.12, FastAPI, SQLite (`aiosqlite`), Pydantic v2, Server-Sent Events (SSE), Docker / Sandboxed Checks

---

## 1. Executive Summary

The **DevPilot Backend** implements an autonomous multi-agent engineering guild (PS-001) designed to plan, implement, test, review, and verify code modifications in target software repositories under strict human-in-the-loop controls.

### Architectural Core Principles
1. **Zero Uncontrolled Mutation:** The user's original codebase is immutable during agent execution. All work occurs in ephemeral, isolated workspaces. Source code is only updated upon explicit, human cryptographic-like approval.
2. **Role-Specialized Multi-Agent Guild:** Work is divided among distinct agent roles with minimal privilege separation:
   - **Shogun:** Read-only planner and architect. Decomposes missions into task DAGs and requests clarifications.
   - **Samurai:** Exclusive-writer implementer. Edits files in disposable workspaces using strictly typed tools.
   - **Sentinel:** Independent verifier. Executes tests and syntax checks inside containerized environments.
   - **Shadow Council:** Read-only reviewer. Audits diffs and code, generating findings with evidence citations.
   - **Repair Planner:** Handles adaptive recovery loops (up to 3 rounds) when checks fail or blocking issues arise.
3. **Independent Verification & Cryptographic Candidate Binding:** A candidate patch is only verified when every acceptance criterion is backed by verified evidence matching the exact candidate content fingerprint.
4. **SSE Event Streaming with Resume:** Real-time event propagation to the frontend using Server-Sent Events with monotonic sequence IDs, heartbeat pings, and replay via `Last-Event-ID` or `?after=`.

---

## 2. Directory & File Structure

```
backend/
├── app/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── guild.py               # ShogunRunner, ShadowCouncilRunner, SentinelRunner, RepairPlanner
│   │   ├── guild_smoke.py         # End-to-end smoke test runner for the multi-agent guild
│   │   ├── model_adapter.py       # Resilient LLM client (Anthropic Messages API + Azure OpenAI Chat/Responses)
│   │   ├── openai_protocol.py     # Protocol translation for OpenAI / Azure endpoints
│   │   ├── recovery_smoke.py      # Smoke tests specifically validating M5 recovery loops
│   │   ├── samurai.py             # SamuraiRunner: single-writer agent tool loop & candidate generation
│   │   ├── smoke.py               # Standalone smoke test harness
│   │   └── tool_contracts.py      # Pydantic schemas and metadata contracts for all agent tools
│   ├── api/
│   │   ├── __init__.py
│   │   ├── events.py              # GET /api/missions/{id}/events (SSE event streaming & heartbeat)
│   │   ├── guild.py               # Planning, execution authorization, verification, approval, diffs, patches
│   │   ├── health.py              # GET /api/health (service probe, DB check, model & docker readiness)
│   │   ├── missions.py            # CRUD for missions, task/criteria queries, cancellation
│   │   └── repositories.py        # Connect local repo, file preflight, file tree, file content reader
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── agent_message.py       # AgentMessage schema (role, message type, token stats)
│   │   ├── approval.py            # Approval, ApprovalRequest, ApplyPatchRequest, ApprovalDecision
│   │   ├── candidate.py           # Candidate schema, CandidateState, content fingerprinting
│   │   ├── common.py              # PreflightResult, BudgetConfig, generic primitives
│   │   ├── events.py              # MissionEvent schema, monotonic sequence definition
│   │   ├── evidence.py            # Evidence schema, EvidenceKind (TEST_RUN, SYNTAX_CHECK, etc.)
│   │   ├── finding.py             # Finding schema, FindingSeverity (BLOCKING, HIGH, etc.), FindingStatus
│   │   ├── guild.py               # GuildPlan, ReviewReport, RepairPlan, Clarification schemas
│   │   ├── mission.py             # Mission, AcceptanceCriterion, MissionStatus, Creation requests
│   │   └── task.py                # MissionTask schema, TaskStatus, TaskDependency
│   ├── security/
│   │   ├── __init__.py
│   │   ├── paths.py               # Path canonicalization and directory traversal guards
│   │   └── redaction.py           # Automated regex redaction of API keys, tokens, and secrets
│   ├── services/
│   │   ├── approval_service.py    # Independent criteria verification, approval gates, patch application
│   │   ├── budgets.py             # BudgetMeter, BudgetedAdapter, token/tool/time limit enforcement
│   │   ├── execution_service.py   # ContainerExecutor: Docker/podman sandboxed execution
│   │   ├── guild_service.py       # GuildController: orchestrates the multi-agent mission lifecycle
│   │   ├── repository_service.py  # Repository indexing, preflight checks, inclusion manifests
│   │   ├── verifier.py            # Verification logic checking evidence records against criteria
│   │   └── workspace_service.py   # Ephemeral workspace manager, candidate hashing, diff calculator
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── artifacts.py           # Disk storage for test outputs, build logs, and agent artifacts
│   │   ├── database.py            # SQLite database schema, migrations, and transactional queries
│   │   └── guild.py               # GuildStore: durable context, atomic claims, and entity tables
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── checks.py              # Static syntax checks, AST validation, pytest runner
│   │   ├── diff.py                # Unified diff generator and parser
│   │   ├── editor.py              # Line-based and replacement editor for workspace files
│   │   ├── files.py               # Safe file read/write operations bounded by workspace root
│   │   ├── gateway.py             # ToolGateway: security-filtered tool dispatch for agents
│   │   └── search.py              # Bounded grep / ripgrep search within workspaces
│   ├── evaluation.py              # M8 5-scenario evaluation runner (controlled and live modes)
│   ├── main.py                    # FastAPI application entrypoint, CORS, router mounting, lifespan
│   └── settings.py                # Pydantic Settings loaded from .env (API keys, ports, paths, limits)
├── data/                          # Runtime data directory (gitignored)
│   ├── devpilot.db                # SQLite database file
│   ├── artifacts/                 # Output artifacts (stdout, stderr, diff files)
│   └── workspaces/                # Ephemeral workspace snapshots and candidate branches
├── tests/
│   ├── __init__.py
│   └── unit/
│       ├── test_foundation.py     # M1 tests: DB, schemas, repositories, health, missions
│       ├── test_m2_tools.py       # M2 tests: Tool contracts, editor, diff, path security
│       ├── test_m3_agents.py      # M3 tests: Model adapter, Samurai loop, token tracking
│       ├── test_m4_guild.py       # M4 tests: Shogun, Sentinel, Shadow Council, DAG coordination
│       ├── test_m5_recovery.py    # M5 tests: Adaptive repair, budget meters, clarifications
│       ├── test_m6_approval.py    # M6 tests: Independent verifier, human approval, patch application
│       ├── test_m7_events.py      # M7 tests: Monotonic SSE streaming, event replay, heartbeats
│       └── test_m8_scenarios.py   # M8 tests: 5-scenario evaluation verification
├── Dockerfile.checks              # Lightweight container image for sandboxed pytest execution
├── M3_STATUS.md ... M8_STATUS.md  # Milestone completion reports and audit notes
├── pytest.ini                     # Pytest configuration
└── requirements.txt               # Backend dependencies (fastapi, aiosqlite, pydantic, etc.)
```

---

## 3. The Multi-Agent Guild Architecture

```
                  ┌───────────────────────────────────────────────┐
                  │                 USER / CLIENT                 │
                  └────────┬──────────────────────────────▲───────┘
                           │ 1. Connect Repo & Mission    │
                           │ 2. Authorize Plan Scope      │ 7. SSE Events
                           │ 3. Answer Clarification      │ 8. Approve/Reject
                           │ 4. Apply Patch               │
                           ▼                              │
                  ┌───────────────────────────────────────┴───────┐
                  │          FastAPI Endpoints (api/)             │
                  └───────────────────────┬───────────────────────┘
                                          │
                                          ▼
                  ┌───────────────────────────────────────────────┐
                  │        GuildController (guild_service.py)     │
                  └───────┬───────────────────────────────┬───────┘
                          │                               │
       Phase: PLANNING    │                               │  Phase: EXECUTION
                          ▼                               ▼
       ┌────────────────────────────┐    ┌───────────────────────────────────┐
       │     SHOGUN (Architect)     │    │        SAMURAI (Developer)        │
       │ • Read-only inspection     │    │ • Exclusive workspace lease       │
       │ • Decomposes mission DAG   │    │ • Executes edits via ToolGateway  │
       │ • Prompts clarifications   │    │ • Emits Candidate + Fingerprint   │
       └────────────────────────────┘    └─────────────────┬─────────────────┘
                                                           │
                                                           ▼
       ┌────────────────────────────┐    ┌───────────────────────────────────┐
       │   SHADOW COUNCIL (Audit)   │    │        SENTINEL (Tester)          │
       │ • Read-only diff analysis  │    │ • Executes tests in Docker checks │
       │ • Cites exact evidence IDs │    │ • Captures stdout/stderr exitcode │
       │ • Emits structured Findings│    │ • Bounded execution timeouts      │
       └──────────────┬─────────────┘    └─────────────────┬─────────────────┘
                      │                                    │
                      └─────────────────┬──────────────────┘
                                        │
                                        ▼
                  ┌───────────────────────────────────────────────┐
                  │    REPAIR PLANNER (M5 Adaptive Recovery)      │
                  │ • Max 3 repair rounds                         │
                  │ • Reopens tasks upon failed check or finding  │
                  │ • Preserves user criteria, bounded budgets    │
                  └─────────────────────┬─────────────────────────┘
                                        │
                                        ▼
                  ┌───────────────────────────────────────────────┐
                  │      APPROVAL SERVICE & VERIFIER (M6 Gate)    │
                  │ • Matches 1:1 Criteria to Passing Evidence    │
                  │ • Blocks if unresolved high/critical findings  │
                  │ • Human-in-the-loop POST /approve & /apply    │
                  └───────────────────────────────────────────────┘
```

### Detailed Agent Profiles

| Agent Name | Privilege Level | Permitted Tools | Core Output |
|---|---|---|---|
| **Shogun** | Read-Only | `read_file`, `tree_list`, `ripgrep_search`, `submit_plan`, `request_clarification` | `GuildPlan` (Task DAG & Acceptance Criteria mapping) or `ClarificationProposal` |
| **Samurai** | Workspace Writer Lease | `read_file`, `edit_lines`, `write_file`, `view_diff`, `ast_check`, `create_candidate` | `Candidate` (isolated branch snapshot + SHA-256 content fingerprint) |
| **Sentinel** | Sandboxed Execution | Docker / container-isolated runner (`pytest`, syntax analyzers) | `Evidence` (Exit code, runtime ms, stdout artifact, stderr artifact) |
| **Shadow Council** | Read-Only | `read_file`, `view_diff`, `submit_review` | `ReviewReport` (`Finding` entries with severity, line ranges, evidence citations) |
| **Repair Planner** | Orchestration Logic | Evaluates failed Evidence & Review Findings | Revised `GuildPlan` incrementing `plan_revision`, spawning new Samurai repair tasks |

---

## 4. API Endpoints Reference

### 4.1 System & Repository Management
- **`GET /api/health`**
  - Returns backend health, SQLite responsiveness, Docker daemon availability, and configured LLM provider status (`anthropic` or `azure_openai`).
- **`POST /api/repositories/connect`**
  - Registers a local directory path.
  - Generates a file inclusion manifest, directory fingerprint, and runs security preflight (checks read permissions, ensures path is not `/` or system-critical).
- **`GET /api/repositories/{repo_id}/tree`**
  - Returns a filtered, security-sanitized file tree of the registered repository.
- **`GET /api/repositories/{repo_id}/file?path=...`**
  - Safely reads raw text from the baseline repository for file viewing in the frontend.

### 4.2 Mission Lifecycle
- **`POST /api/missions`**
  - Creates a new mission with `repository_id`, `request_text`, and acceptance criteria.
  - Initial state: `PLANNING`.
- **`GET /api/missions`**
  - Lists missions (ordered by creation date desc, supports pagination with `?limit=...`).
- **`GET /api/missions/{mission_id}`**
  - Authoritative detail response containing the `Mission`, `AcceptanceCriteria`, `MissionTasks`, `Candidates`, `Evidence`, `Findings`, `Messages`, `Clarifications`, `Approvals`, and `repository_files`.
- **`POST /api/missions/{mission_id}/cancel`**
  - Immediately cancels active background jobs and records cancellation event.

### 4.3 Guild Orchestration & Recovery
- **`POST /api/missions/{mission_id}/plan`** (Status: `202 Accepted`)
  - Initiates frozen baseline preflight checks and kicks off Shogun read-only planning.
- **`POST /api/missions/{mission_id}/authorize`** (Status: `202 Accepted`)
  - Body: `{ "scope_version": int, "auto_repair": bool }`.
  - Authorizes the task DAG to begin execution with Samurai, Sentinel, and Shadow Council.
- **`POST /api/missions/{mission_id}/clarifications`** (Status: `202 Accepted`)
  - Body: `{ "question_id": str, "answer": str }`.
  - Atomically records user clarification answer and resumes paused planning or execution.

### 4.4 Verification & Patch Application
- **`POST /api/missions/{mission_id}/verify`**
  - Runs independent criteria verification. If all criteria have valid passing evidence and no blocking findings exist, transitions mission to `VERIFIED_AWAITING_APPROVAL`.
- **`POST /api/missions/{mission_id}/approve`**
  - Body: `{ "candidate_id": str, "candidate_fingerprint": str, "decision": "APPROVED" | "REJECTED" }`.
  - Human sign-off on the candidate. Prevents stale candidate approval via fingerprint check.
- **`POST /api/missions/{mission_id}/apply`**
  - Body: `{ "candidate_id": str }`.
  - Atomically applies the approved candidate patch to the target repository. Validates that baseline has not drifted since the mission started.
- **`GET /api/missions/{mission_id}/patch`**
  - Returns raw unified git diff as `text/x-diff` attachment.
- **`GET /api/missions/{mission_id}/report`**
  - Summary audit payload for command center and post-mission reporting.

### 4.5 Candidate Inspection
- **`GET /api/missions/{mission_id}/candidates/{candidate_id}/diff`**
  - Calculates and returns unified diff and file change list between baseline and candidate snapshot.
- **`GET /api/missions/{mission_id}/candidates/{candidate_id}/file?path=...`**
  - Reads specific file content from the frozen candidate snapshot.
- **`GET /api/missions/{mission_id}/evidence/{evidence_id}`**
  - Fetches complete execution evidence, including stdout/stderr artifact logs.

### 4.6 Real-Time Event Streaming (SSE)
- **`GET /api/missions/{mission_id}/events`**
  - Content-Type: `text/event-stream`.
  - Monotonic event sequence: `id: <sequence>`, `event: mission`, `data: <JSON>`.
  - Supports replay via `Last-Event-ID` header or `?after=<sequence>` query param.
  - Emits `: heartbeat` comment frames every 15 seconds during idle periods.

---

## 5. Storage & Database Schema

The database is powered by SQLite via `aiosqlite` with foreign key enforcement and write-ahead locking.

### Key Database Tables

1. **`missions`**:
   - `id` (PK, string `miss-...`)
   - `repository_id`, `request_text`, `status` (`PLANNING`, `EXECUTING`, `VERIFYING`, `VERIFIED_AWAITING_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELLED`, `BUDGET_EXHAUSTED`, `BLOCKED`)
   - `active_candidate_id`, `failure_reason`, `created_at`, `updated_at`
2. **`acceptance_criteria`**:
   - `id` (PK), `mission_id` (FK), `description`, `status` (`PENDING`, `SATISFIED`, `VIOLATED`), `satisfied_by_candidate_id`
3. **`tasks`**:
   - `id` (PK), `mission_id` (FK), `title`, `description`, `assigned_agent` (`SHOGUN`, `SAMURAI`, `SENTINEL`, `SHADOW_COUNCIL`), `status` (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`), `dependencies_json`
4. **`events`**:
   - `mission_id` (PK compound), `sequence` (PK compound, monotonic integer)
   - `event_type`, `source`, `task_id`, `candidate_id`, `evidence_ids_json`, `display_payload_json`, `created_at`
5. **`artifacts`**:
   - `id` (PK), `mission_id` (FK), `name`, `kind`, `size_bytes`, `storage_path`, `content_hash`, `created_at`
6. **`workspaces`**:
   - `id` (PK), `mission_id` (FK), `repository_id`, `directory_path`, `is_active`, `created_at`
7. **`clarifications`**:
   - `id` (PK), `mission_id` (FK), `question`, `reason`, `phase`, `candidate_id`, `scope_version`, `status` (`PENDING`, `ANSWERED`), `answer`, `created_at`, `answered_at`
8. **`guild_context` & `guild_operations`**:
   - Stores current plan revisions, atomic execution claim tokens, and serialized state across restarts.

---

## 6. Security & Guardrails

1. **Path Traversal Protection (`app/security/paths.py`):**
   - All file operations use `canonicalize_and_validate_path()`.
   - Any attempt to reference files via `../`, symlinks pointing outside the workspace, or absolute system paths raises `PathSecurityError` and returns `403 Forbidden`.
2. **Secret Redaction (`app/security/redaction.py`):**
   - Automatically redacts sensitive patterns (API keys, Anthropic/OpenAI keys, bearer tokens, SSH private keys) from all display payloads, SSE frames, and model message logs.
3. **Bounded Autonomy & Budgets (`app/services/budgets.py`):**
   - Enforces configurable limits per mission:
     - Active elapsed time (default: 900s)
     - Total LLM turns (default: 12 per agent call)
     - Total tool invocations (default: 30 per turn)
     - Max repair attempts (capped at 3 rounds)
   - If exceeded, execution halts gracefully with status `BUDGET_EXHAUSTED`.
4. **Disposable Workspaces:**
   - Samurai edits files in a detached temporary folder (`data/workspaces/...`).
   - The user repository remains completely read-only until the human clicks Apply on an approved candidate.

---

## 7. Model Adapter & LLM Support

The model layer (`app/agents/model_adapter.py`) connects to LLMs via standard protocols:

- **Anthropic Messages API:** Supports Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`) or local compatible endpoints.
- **Azure OpenAI Service:** Supports Chat Completions and Responses API (`gpt-4o`, `gpt-6-astra`).
- **Resilience:**
  - Automatic exponential backoff with jitter on HTTP 429 and 5xx errors.
  - Token tracking per request and per session.
  - Sanitized error reporting: upstream credential leaks or network URLs are scrubbed from user-facing error messages.

---

## 8. Milestone Implementation Summary

| Milestone | Focus | Key Deliverables | Status |
|---|---|---|---|
| **M1** | Foundation | SQLite DB, FastAPI skeleton, Repository connect, Missions CRUD | **Done** |
| **M2** | Tool Gateway | File tools, AST check, safe patch editor, path security, diff generator | **Done** |
| **M3** | Agent Layer | Resilient ModelAdapter, Samurai loop, Candidate snapshotting | **Done** |
| **M4** | Multi-Agent Coordination | Shogun planning, Sentinel testing, Shadow Council review, Task DAGs | **Done** |
| **M5** | Adaptive Recovery | 3-round repair loops, Clarifications API, BudgetMeter | **Done** |
| **M6** | Independent Verification | Verifier, Criteria evidence matching, Human Approval & Apply patch | **Done** |
| **M7** | SSE & Frontend Integration | Monotonic SSE stream, Heartbeats, Replay cursors, Next.js integration | **Done** |
| **M8** | 5-Scenario Evaluation | Test suites for Bug, Feature, Recovery, Security, and Unexpected scenarios | **Done** |

---

## 9. Running and Testing the Backend

### Prerequisites
- Python 3.12+
- Docker (optional, needed for live container checks; fallback to controlled mode if unavailable)

### Setup & Launch
```bash
# From workspace root
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY or AZURE_OPENAI credentials

# Run FastAPI server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Running Tests
```bash
# Run complete unit test suite
pytest tests/unit

# Run specific milestone tests
pytest tests/unit/test_foundation.py
pytest tests/unit/test_m4_guild.py
pytest tests/unit/test_m6_approval.py
pytest tests/unit/test_m7_events.py
```
