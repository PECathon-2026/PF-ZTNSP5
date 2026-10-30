import { mitLicense } from "./license";

export const projectUrl = "https://github.com/PECathon-2026/PF-ZTNSP5";

export interface DocBlock {
  kind: "text" | "callout" | "steps" | "cards" | "code" | "table" | "faq" | "links";
  title?: string;
  text?: string;
  tone?: "gold" | "jade";
  items?: { title: string; text: string; href?: string }[];
  columns?: string[];
  rows?: string[][];
}
export interface DocSection {
  id: string; title: string; group: "Start here" | "Working with the guild" | "Reference";
  description: string; blocks: DocBlock[];
}

export const docSections: DocSection[] = [
  {
    id: "overview", title: "Meet KAGE AI", group: "Start here",
    description: "One request. Four specialist agents. The final decision stays with you.",
    blocks: [
      { kind: "text", text: "KAGE AI is a local engineering workspace for small, existing Python repositories. Describe a change, let the guild prepare and check a candidate patch, then inspect the evidence before deciding whether to apply it." },
      { kind: "cards", items: [
        { title: "Shogun · Plan", text: "Explores relevant source and tests, proposes acceptance criteria, and turns your brief into tasks." },
        { title: "Samurai · Build", text: "Implements and repairs changes in a disposable copy, not your original repository." },
        { title: "Sentinel · Check", text: "Runs approved checks in restricted Docker containers and records structured results." },
        { title: "Shadow Council · Review", text: "Reviews source, requirements and security findings, with evidence-informed follow-up when needed." },
      ] },
      { kind: "callout", title: "The verifier is not another LLM", tone: "jade", text: "A deterministic verification step evaluates recorded, candidate-bound evidence. Passing a mapped test supports that checked behavior; it is not a formal proof that every possible input or natural-language requirement is correct." },
    ],
  },
  {
    id: "quick-start", title: "Local setup", group: "Start here",
    description: "Two application terminals, a running Docker engine, and a configured model provider.",
    blocks: [
      { kind: "table", columns: ["You need", "Details"], rows: [
        ["Python", "Python 3.12+ and pip for the backend."],
        ["Node.js", "Node.js 22.18+ or 24, with npm, for frontend-v2."],
        ["Docker", "Docker Desktop with the Linux engine on Windows, or a working Linux Docker engine."],
        ["Model access", "A key matching the configured Anthropic-compatible gateway or Azure OpenAI deployment."],
        ["Repository", "A local Python repository on the backend machine, with compatible pytest checks."],
      ] },
      { kind: "code", title: "1 / Get the project · PowerShell", text: `git clone ${projectUrl}.git
Set-Location PF-ZTNSP5` },
      { kind: "code", title: "2 / Backend terminal · from the project root", text: `Set-Location backend
python -m pip install -r requirements.txt
if (!(Test-Path -LiteralPath ".env")) { Copy-Item ".env.example" ".env" }
# Configure backend/.env with your provider, endpoint and model.
docker build -f Dockerfile.checks -t devpilot-checks:py312 .
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` },
      { kind: "code", title: "3 / Frontend terminal · from the project root", text: `Set-Location frontend-v2
npm ci
npm run dev` },
      { kind: "links", items: [
        { title: "Open the dojo", text: "The frontend runs at localhost:3001; the backend runs at localhost:8000.", href: "http://localhost:3001" },
        { title: "Backend setup reference", text: "Provider configuration, check image requirements, and CLI instructions.", href: `${projectUrl}/blob/main/backend/README.md` },
      ] },
      { kind: "callout", title: "Checks need their dependencies prepared", text: "The check runner does not install packages or pull images during a mission. Repositories with extra dependencies need a compatible prebuilt image, selected with DEVPILOT_DOCKER_IMAGE in backend/.env. If Docker is unavailable, execution blocks instead of running repository code on the host." },
    ],
  },
  {
    id: "api-keys", title: "Models & your API key", group: "Start here",
    description: "Choose between the backend’s configured key and a key supplied just for your mission.",
    blocks: [
      { kind: "steps", items: [
        { title: "Configure the provider on the backend", text: "In backend/.env, select DEVPILOT_MODEL_PROVIDER=anthropic or azure_openai. Configure its endpoint and model/deployment, then restart the backend." },
        { title: "Enable “Use my API key”", text: "On New mission, tick the option and paste your key in the masked field. The form shows the configured provider and model. Your key must be accepted by that exact provider/endpoint." },
        { title: "Create and start the mission", text: "Planning, execution and clarification resumes use the supplied mission key instead of the server key. An invalid key does not fall back to the server’s paid account." },
        { title: "Re-enter after a restart", text: "Keys are only held in backend memory. When prompted in the workspace, re-enter the mission key before further model work. Keys are also cleared when execution ends or the mission is stopped/cancelled." },
      ] },
      { kind: "code", title: "Azure OpenAI · backend/.env template", text: `DEVPILOT_MODEL_PROVIDER=azure_openai
AZURE_OPENAI_BASE_URL=https://YOUR-RESOURCE.openai.azure.com/openai/v1
AZURE_OPENAI_DEPLOYMENT=YOUR-DEPLOYMENT-NAME
AZURE_OPENAI_API=responses
# Set AZURE_OPENAI_API_KEY locally, or use your own key in New mission.` },
      { kind: "code", title: "Anthropic-compatible · backend/.env template", text: `DEVPILOT_MODEL_PROVIDER=anthropic
ANTHROPIC_BASE_URL=https://YOUR-COMPATIBLE-GATEWAY/v1
DEVPILOT_MODEL=YOUR-SUPPORTED-MODEL
# Set ANTHROPIC_API_KEY locally, or use your own key in New mission.` },
      { kind: "callout", title: "A mission budget is not a currency spending cap", text: "Live model calls may incur charges from your provider. Set provider-side limits or budget alerts separately. Never put keys in your request text, screenshots, repository files, or NEXT_PUBLIC_ variables. The API-key control does not add multi-user authentication." },
    ],
  },
  {
    id: "first-mission", title: "Your first mission", group: "Working with the guild",
    description: "Start with a focused change and review each explicit checkpoint.",
    blocks: [
      { kind: "steps", items: [
        { title: "Connect a repository", text: "Enter a local path on the backend machine, such as D:/projects/my-python-repo, then click Connect. This is not a GitHub URL or a browser upload. Read the included-file count and preflight blockers." },
        { title: "Write a concrete brief", text: "Explain the intended behavior and constraints. Acceptance criteria are optional; if omitted, Shogun proposes them. Choose a Standard or Extended budget and optionally supply your own API key." },
        { title: "Start planning", text: "Creating a mission saves the brief. Click Start planning to begin repository inspection, baseline checks and model calls." },
        { title: "Review the plan and test expectations", text: "Read tasks and criterion-to-test mappings. Answer clarifications. If new acceptance tests are proposed, inspect the assertions and explicitly accept or decline them before source work." },
        { title: "Authorize workspace work", text: "This allows bounded edits in the disposable workspace. The Allow bounded auto-repair option permits up to three repair rounds within the mission’s remaining limits." },
        { title: "Inspect and verify", text: "Review the candidate diff, checks, findings and recorded activity. When the mission is ready, click Verify candidate to evaluate the current candidate’s evidence." },
        { title: "Approve, then apply separately", text: "In Review & apply, approve or reject the exact candidate. Applying to the original repository is a separate action with its own confirmation and baseline checks." },
      ] },
      { kind: "code", title: "Example brief · a small behavioral change", text: `Make average(items) return 0 for an empty list.
Keep the existing behavior for non-empty lists.
Do not change the public function signature.

Optional acceptance criteria:
- average([]) returns 0.
- average([2, 4]) returns 3.
- Existing tests keep passing.` },
      { kind: "links", items: [{ title: "Create a mission", text: "Connect your repository and turn a focused brief into a plan.", href: "/missions/new" }] },
    ],
  },
  {
    id: "workspace", title: "Find your way around", group: "Working with the guild",
    description: "Different views of the same recorded mission, without inventing missing output.",
    blocks: [
      { kind: "cards", items: [
        { title: "Workspace", text: "Browse read-only source and candidate diffs with Monaco or the plain-text view. File tabs preserve inspection context. Findings can open their recorded file, line and candidate." },
        { title: "Checks & evidence", text: "Inspect command output, exit codes, structured reports and candidate fingerprints. Empty output means no output was recorded; it is not replaced with a simulated success." },
        { title: "Agent graph", text: "Select an agent for Now, This mission and Previous missions. Connections reflect saved agent messages; open a connection to inspect its evidence and candidate context." },
        { title: "Mission archive", text: "Search loaded saved missions and load older records. Historical inspection does not execute models, certify a different candidate, or approve code." },
      ] },
      { kind: "text", text: "The activity connection uses server-sent events and recorded history to recover missed messages. Connection loss stops live animation; reconnecting refreshes the backend’s canonical mission state. A task marked RUNNING alone is not evidence of current model activity." },
      { kind: "callout", title: "The editor is an inspection surface", tone: "jade", text: "The file viewer is read-only. KAGE AI does not provide a browser terminal for arbitrary commands or a human-editing endpoint. To request another source change, give the guild a clear brief rather than treating the viewer as a writable editor." },
    ],
  },
  {
    id: "budgets", title: "Budgets & stopped runs", group: "Working with the guild",
    description: "Keep the mission bounded, and inspect partial work before continuing.",
    blocks: [
      { kind: "table", columns: ["Allowance", "Standard", "Extended"], rows: [
        ["Model turns", "25", "60"], ["Tool calls", "50", "100"],
        ["Reported tokens", "160,000", "320,000"], ["Active time", "10 minutes", "15 minutes"],
      ] },
      { kind: "text", text: "These ceilings are shared across planning, clarifications, test design, development, review and repair. They are not all reserved for Samurai. Developer tasks still have their own limits, including 20 model turns and 50 tool calls; repairs are limited to three rounds." },
      { kind: "steps", items: [
        { title: "Read the stop reason", text: "Expand Mission budget and inspect actual usage. A stopped run’s partial edits are not automatically verified, approved or applied." },
        { title: "Inspect the recovery checkpoint", text: "When available, the recovery panel shows the preserved partial diff and blockers. Continue only after reviewing the checkpoint and any explicit budget extension. Changed or unsafe checkpoints can be refused." },
        { title: "Or create a fresh mission", text: "Prepare a new mission with extended budget copies the brief and criteria into a new form. Reconnect the repository, review the allowance, then explicitly create and start it. This does not resume the original partial writes." },
      ] },
    ],
  },
  {
    id: "verification", title: "Evidence, approval & apply", group: "Working with the guild",
    description: "A green check belongs to one exact candidate, not every future edit.",
    blocks: [
      { kind: "cards", items: [
        { title: "Candidate-bound evidence", text: "Tests, findings and approval records refer to a frozen candidate and its fingerprint. Later edits need their own evidence; old results cannot certify a changed patch." },
        { title: "Challenge the Fix", text: "Bounded temporary code variants test whether the accepted tests detect selected changes. DETECTED means a variant was caught; SURVIVED can indicate a test gap or an equivalent variant, not automatically a bug." },
        { title: "Human-reviewed expectations", text: "Review acceptance-test assertions and criterion mappings. A passing check establishes that its tested expectation passed, not that the expectation itself was complete." },
        { title: "Separate application", text: "Approval alone does not edit the original repository. Applying rechecks the original baseline and uses a durable journal for recoverable multi-file writes. Each file replacement is atomic; the whole set is not globally simultaneous." },
      ] },
      { kind: "text", text: "Before approving, compare the full diff with your brief, inspect failing or missing checks, review security findings and check the candidate fingerprint. If the original repository changed, refresh and inspect the conflict instead of forcing a stale patch." },
      { kind: "links", items: [{ title: "Backend evidence and proof reference", text: "Read the implementation’s verification boundaries and recorded run details.", href: `${projectUrl}/blob/main/backend/FINAL_VERIFICATION_REPORT.md` }] },
    ],
  },
  {
    id: "troubleshooting", title: "When something blocks", group: "Reference",
    description: "Common symptoms, likely causes, and the next useful action.",
    blocks: [
      { kind: "faq", items: [
        { title: "“Backend unavailable” or a 502 response", text: "Start FastAPI on port 8000 and refresh. If the backend is elsewhere, set KAGE_BACKEND_URL in frontend-v2/.env.local and restart the frontend. The browser talks to the same-origin proxy; it does not need provider credentials in public environment variables." },
        { title: "Docker unavailable / baseline checks blocked", text: "Start Docker Desktop’s Linux engine, run docker info, and build Dockerfile.checks from backend/. If the repository needs additional dependencies, prepare a compatible image. There is no host-execution fallback." },
        { title: "Model not configured or provider authentication fails", text: "Confirm provider, endpoint, supported model/deployment and key all match. Restart the backend after editing .env. The readiness indicator checks configuration presence, not whether the provider accepts your key. Check provider quota and permissions." },
        { title: "The mission asks for my API key again", text: "The key is not persisted and may have been cleared on a stop or backend restart. Re-enter it when prompted. Your own-key mission does not fall back to the server key. For a stopped run without a key prompt, prepare a fresh mission with your key." },
        { title: "BUDGET_EXHAUSTED", text: "Inspect actual model, tool, token and active-time usage. Review a recovery checkpoint where offered, or prepare a fresh mission with an extended budget. Raising a mission ceiling does not remove task-specific limits or provider charges." },
        { title: "409 conflict / snapshot or baseline changed", text: "Refresh the mission and inspect its current candidate or checkpoint. Avoid editing the original while a patch is being reviewed/applied. A candidate or recovery snapshot that changed is not safe to replay using old evidence." },
        { title: "Checks passed, but verification did not", text: "Inspect criterion mappings, missing evidence and unresolved findings. A green full-suite result alone does not necessarily support every acceptance criterion. Inconclusive challenge execution can block verification." },
        { title: "The editor is blank or cannot load", text: "Try the plain-text view. Re-run npm ci to prepare the local Monaco assets; check that the selected frozen file still exists. Locally served editor assets do not require a Monaco CDN." },
        { title: "The agent graph looks idle", text: "Confirm whether the mission is awaiting input, stopped, historical, or disconnected. Animation depends on recorded activity and connection state. Idle visuals are not permission to start a duplicate operation." },
      ] },
      { kind: "code", title: "Frontend checks · from frontend-v2/", text: `npm test
npm run typecheck
npm run build` },
      { kind: "code", title: "Backend checks · from backend/", text: "python -m pytest tests/unit -q" },
    ],
  },
  {
    id: "api-reference", title: "API & configuration", group: "Reference",
    description: "Useful entry points for developers integrating or inspecting the local backend.",
    blocks: [
      { kind: "table", columns: ["Endpoint", "Purpose"], rows: [
        ["GET /api/health", "Backend, Docker and model configuration readiness."],
        ["GET /api/model-config", "Configured provider and model, without keys."],
        ["POST /api/repositories/connect", "Connect a repository by backend-machine path."],
        ["POST /api/missions", "Save a new mission; optional api_key and budget limits."],
        ["POST /api/missions/{id}/plan", "Explicitly start planning and model work."],
        ["POST /api/missions/{id}/credentials", "Re-enter an existing own-key mission’s ephemeral key while idle."],
        ["POST /api/missions/{id}/authorize", "Authorize bounded disposable-workspace execution."],
        ["GET /api/missions/{id}/proof?format=markdown", "Read the candidate’s Markdown proof card."],
        ["GET /api/missions/{id}/patch", "Export the active candidate as a patch."],
        ["POST /api/missions/{id}/verify", "Evaluate recorded candidate evidence."],
        ["POST /api/missions/{id}/approve", "Record the exact-candidate approval/rejection decision."],
        ["POST /api/missions/{id}/apply", "Separately apply an approved candidate."],
      ] },
      { kind: "text", text: "The frontend proxies /api/backend/* to the configured backend’s /api/* routes. Set KAGE_BACKEND_URL in frontend-v2/.env.local to change that target. Run one FastAPI worker: the scheduler and local SQLite setup are not designed for multiple API workers sharing the same database." },
      { kind: "links", items: [
        { title: "Interactive API schemas", text: "FastAPI Swagger documentation on the default local backend. The backend must be running.", href: "http://localhost:8000/docs" },
        { title: "Source repository", text: "Code, setup references and issue tracking.", href: projectUrl },
      ] },
    ],
  },
  {
    id: "privacy", title: "Data & current boundaries", group: "Reference",
    description: "Know what is stored locally, what goes to your provider, and what this demo supports.",
    blocks: [
      { kind: "cards", items: [
        { title: "Local persistence", text: "Mission history, events, candidate snapshots, evidence and application journals are stored in backend-local SQLite/filesystem storage. These can contain repository content and check output. Back up or remove local artifacts with care." },
        { title: "Model provider traffic", text: "Relevant source, request context and tool results can be sent to the configured model provider. Local execution does not mean offline inference. Your provider’s terms, pricing and data handling apply to those requests." },
        { title: "Ephemeral user keys", text: "The API-key field is sent to the backend, kept in process memory for that mission, and redacted from recorded output while registered. It is not saved to mission records or browser storage. Use HTTPS for any remote access." },
        { title: "Single-user scope", text: "The current backend has no multi-user authentication or tenant isolation. Own API keys do not isolate repository access or mission history. This is a private local/demo workflow, not a publicly shared multi-user service." },
      ] },
      { kind: "text", text: "Repository checks run in restricted Docker containers with non-root execution, disabled networking and bounded resources. The configured model keys are not passed into check containers. These controls reduce exposure; they are not a guarantee that arbitrary untrusted repositories are harmless." },
      { kind: "text", text: "Monaco assets are served locally. The interface uses Google Fonts with system fallbacks; font loading can make external requests, but does not send repository code to the font service. This guide is available even when the backend is offline." },
    ],
  },
  {
    id: "license", title: "License & credits", group: "Reference",
    description: "MIT-licensed project code, clear attribution, and separate third-party terms.",
    blocks: [
      { kind: "callout", title: "MIT License · © 2026 KAGE AI contributors", tone: "jade", text: "You may use, copy, modify, distribute and sell copies of the project software, including commercially, provided the copyright and permission notice remain in copies or substantial portions. The software is provided without warranty. The full license below is the authoritative text." },
      { kind: "links", items: [
        { title: "Download the MIT license", text: "A plain-text copy you can keep with a redistribution.", href: "/license" },
        { title: "Project license file", text: "The repository’s root LICENSE file.", href: `${projectUrl}/blob/main/LICENSE` },
      ] },
      { kind: "code", title: "Full MIT License", text: mitLicense },
      { kind: "text", text: "Third-party packages, fonts and external model services retain their own licenses and terms; the project MIT license does not replace those obligations. Runtime dependencies are listed in frontend-v2/package.json and backend/requirements.txt." },
      { kind: "cards", items: [
        { title: "Interface & tooling", text: "Next.js, React, TypeScript, Lucide, Monaco and React Flow support the frontend. DM Sans and IBM Plex Mono are the interface fonts; original SVG agents and CSS scenery supply the visual identity." },
        { title: "Engineering guild", text: "FastAPI, Python, SQLite, pytest and Docker support the backend workflow. KAGE AI / DevPilot was built for PECATHON 2026, problem statement PS-001." },
      ] },
      { kind: "links", items: [{ title: "Report an issue", text: "Include reproduction steps, the status/error and relevant redacted output. Do not attach API keys or private repository files.", href: `${projectUrl}/issues` }] },
    ],
  },
];

export function searchDocs(query: string): DocSection[] {
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) return docSections;
  return docSections.filter(section => {
    const searchable = JSON.stringify(section).toLowerCase();
    return terms.every(term => searchable.includes(term));
  });
}
