"""Safe, factual user-facing summaries derived from validated tool operations.

Never stream raw model text, arguments, file contents, diffs or check output.
The model's structured plan/review summaries remain distinguishable from observed
tool outcomes and from the later independent verification decision.
"""

import re

from app.security.redaction import redact_secrets


def safe_label(value: str, limit: int = 160) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", redact_secrets(value))
    return text[:limit].strip()


def tool_activity(role: str, tool: str, stage: str, *, path: str | None = None,
                  count: int | None = None, mode: str | None = None,
                  task_title: str | None = None, candidate_fingerprint: str | None = None) -> dict:
    """Render a bounded activity item. Only validated relative paths are accepted."""
    if role not in {"SHOGUN", "SAMURAI", "SHADOW_COUNCIL"} or stage not in {"intent", "outcome", "failed"}:
        raise ValueError("Invalid activity source or stage")
    if path and (path.startswith(("/", "\\")) or ".." in path.split("/")):
        path = None
    agent = {"SHOGUN": "Shogun", "SAMURAI": "Samurai", "SHADOW_COUNCIL": "Shadow Council"}[role]
    target = f" `{safe_label(path, 180)}`" if path else ""
    task = f" for {safe_label(task_title, 120)}" if task_title else ""
    if stage == "failed":
        summary = f"{agent} could not complete {tool}{target}; the operation was rejected."
    elif tool == "list_files":
        summary = (f"{agent} is listing approved files to understand the repository."
                   if stage == "intent" else f"{agent} found {count or 0} approved files.")
    elif tool == "repo_map":
        summary = (f"{agent} is mapping current source symbols and tests before choosing what to inspect."
                   if stage == "intent" else f"{agent} received a bounded map of current source and test locations.")
    elif tool == "search_text":
        summary = (f"{agent} is searching source for relevant code."
                   if stage == "intent" else f"{agent} found {count or 0} search matches.")
    elif tool == "read_file":
        summary = (f"{agent} is reading{target} to check existing behavior and conventions."
                   if stage == "intent" else f"{agent} read{target}; the file is now available for planning or review.")
    elif tool == "read_diff":
        summary = (f"{agent} is inspecting the diff for{target} to assess the change."
                   if stage == "intent" else f"{agent} inspected the diff for{target}.")
    elif tool == "apply_patch":
        action = "remove" if mode == "delete" else "create" if mode == "create" else "edit"
        past = {"remove": "removed", "create": "created", "edit": "edited"}[action]
        summary = (f"Samurai is attempting to {action}{target}{task} in the disposable workspace."
                   if stage == "intent" else f"Samurai {past}{target} in the disposable workspace; checks are still pending.")
    elif tool == "submit_candidate":
        summary = "Samurai froze the inspected candidate; independent checks and review are still pending."
    else:
        summary = f"{agent} {stage}: {safe_label(tool, 80)}."
    data = {"stage": stage, "action": tool, "summary": summary[:360]}
    if path:
        data["relative_path"] = safe_label(path, 180)
    if candidate_fingerprint:
        data["candidate_fingerprint"] = candidate_fingerprint
    return data
