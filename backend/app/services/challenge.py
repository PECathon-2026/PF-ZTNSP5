"""Bounded 'Challenge the Fix': safe AST variants tested only in Docker."""

import ast
import asyncio
import copy
import hashlib
import shutil
from pathlib import Path
from time import monotonic

from app.schemas.evidence import Evidence, EvidenceKind
from app.schemas.finding import Finding, FindingSeverity
from app.security.paths import canonicalize_and_validate_path
from app.services.test_reports import report_passes
from app.settings import get_settings


OPERATORS = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
             ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.And: ast.Or, ast.Or: ast.And}


def changed_functions(baseline: str, candidate: str):
    original = ast.parse(baseline)
    proposed = ast.parse(candidate)
    old = {n.name: ast.dump(n) for n in original.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return proposed, {n.name for n in proposed.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and old.get(n.name) != ast.dump(n)}


def variants(baseline: str, candidate: str, cap=3):
    """Emit a few single-operator variants of changed top-level functions."""
    tree, names = changed_functions(baseline, candidate)
    changes = []
    for func in tree.body:
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)) or func.name not in names:
            continue
        for node in ast.walk(func):
            if isinstance(node, ast.Constant) and type(node.value) is int:
                clone = copy.deepcopy(tree)
                target_func = next(n for n in clone.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func.name)
                target = next((n for n in ast.walk(target_func) if isinstance(n, ast.Constant) and
                               getattr(n, "lineno", None) == node.lineno and getattr(n, "col_offset", None) == node.col_offset), None)
                if target is not None:
                    target.value = node.value + 1
                    changes.append({"function": func.name, "operator": "integer_literal", "replacement": "+1",
                                    "source": ast.unparse(clone) + "\n"})
                    if len(changes) >= cap:
                        return changes
                continue
            field = "ops" if isinstance(node, ast.Compare) else "op" if isinstance(node, ast.BoolOp) else None
            if field == "ops":
                options = [(index, type(op)) for index, op in enumerate(node.ops)]
            elif field:
                options = [(None, type(node.op))]
            else:
                continue
            for index, op_type in options:
                if op_type not in OPERATORS:
                    continue
                clone = copy.deepcopy(tree)
                target_func = next(n for n in clone.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func.name)
                target = next((n for n in ast.walk(target_func) if type(n) is type(node) and getattr(n, "lineno", None) == node.lineno
                               and getattr(n, "col_offset", None) == node.col_offset), None)
                if target is None:
                    continue
                if index is None:
                    target.op = OPERATORS[op_type]()
                else:
                    target.ops[index] = OPERATORS[op_type]()
                changes.append({"function": func.name, "operator": op_type.__name__,
                                "replacement": OPERATORS[op_type].__name__, "source": ast.unparse(clone) + "\n"})
                if len(changes) >= cap:
                    return changes
    return changes


async def challenge_candidate(candidate, baseline_dir, candidate_dir, executor, artifacts, *, before_tool=None):
    attempts = []
    started = monotonic()
    root = get_settings().data_dir.resolve() / "challenges" / candidate.mission_id / candidate.id
    try:
        for relative in candidate.changed_files:
            if len(attempts) >= 3:
                break
            if not relative.endswith(".py") or Path(relative).name.startswith("test_"):
                continue
            source = canonicalize_and_validate_path(candidate_dir, relative)
            previous = canonicalize_and_validate_path(baseline_dir, relative)
            if not source.is_file():
                continue
            try:
                changes = variants(previous.read_text(encoding="utf-8") if previous.is_file() else "",
                                   source.read_text(encoding="utf-8"), 3 - len(attempts))
            except (SyntaxError, UnicodeError, ValueError):
                continue
            for change in changes:
                index = len(attempts)
                remaining = 120 - (monotonic() - started)
                if remaining <= 0:
                    attempts.append({"path": relative, "function": change["function"], "operator": change["operator"],
                                     "replacement": change["replacement"], "outcome": "INCONCLUSIVE", "exit_code": 124})
                    continue
                if before_tool:
                    await before_tool()
                target = root / f"variant-{index}"
                shutil.copytree(candidate_dir, target, symlinks=False)
                (target / relative).write_text(change.pop("source"), encoding="utf-8")
                try:
                    async with asyncio.timeout(remaining):
                        result = await executor.run(target, "python_pytest")
                    status = result["status"]
                    report = result.get("report")
                    if status == "SUCCEEDED" and report_passes(report):
                        outcome = "SURVIVED"
                    elif status == "FAILED" and report and any(t["outcome"] == "failed" and t.get("call") == "failed"
                                                                for t in report.get("tests", [])):
                        outcome = "DETECTED"
                    else:
                        outcome = "INCONCLUSIVE"
                except TimeoutError:
                    outcome = "INCONCLUSIVE"
                    result = {"exit_code": 124, "status": "TIMED_OUT"}
                attempts.append({"path": relative, "function": change["function"], "operator": change["operator"],
                                 "replacement": change["replacement"], "outcome": outcome,
                                 "exit_code": result["exit_code"], "duration_ms": result.get("duration_ms", 0)})
    finally:
        if root.exists():
            shutil.rmtree(root)
    fingerprint = hashlib.sha256(repr(attempts).encode()).hexdigest()
    artifact_id, artifact_hash = artifacts.save_artifact(candidate.mission_id, "challenge.json", __import__("json").dumps(attempts))
    evidence = Evidence(mission_id=candidate.mission_id, candidate_id=candidate.id,
                        fingerprint=candidate.content_fingerprint, kind=EvidenceKind.MUTATION, source="SENTINEL",
                        stdout_artifact_id=artifact_id, duration_ms=int((monotonic() - started) * 1000),
                        metadata={"attempts": attempts, "attempt_hash": fingerprint, "artifact_hash": artifact_hash,
                                  "status": "NOT_APPLICABLE" if not attempts else "COMPLETE" if all(a["outcome"] != "INCONCLUSIVE" for a in attempts) else "INCONCLUSIVE"})
    findings = [Finding(mission_id=candidate.mission_id, candidate_id=candidate.id, source_agent="SENTINEL",
                        severity=FindingSeverity.MEDIUM, title="Challenge variant survived existing tests",
                        description=f"A bounded operator variant in {attempt['path']}::{attempt['function']} survived. Review whether it affects required behavior.",
                        file_path=attempt["path"], observed_behavior="Approved tests passed against the faulty variant.",
                        expected_behavior="Tests should distinguish relevant incorrect behavior; equivalent variants may survive.",
                        evidence_ids=[evidence.id]) for attempt in attempts if attempt["outcome"] == "SURVIVED"]
    return evidence, findings
