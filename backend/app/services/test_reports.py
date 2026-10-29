"""Validation of untrusted structured pytest reports; never infer success from text."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class TestResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    nodeid: str = Field(min_length=1, max_length=500)
    outcome: Literal["passed", "failed", "skipped", "error", "xfailed", "xpassed", "rerun"]
    setup: str | None = None
    call: str | None = None
    teardown: str | None = None


class TestReport(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    exitcode: int = Field(ge=0, le=255)
    summary: dict[str, int]
    truncated: bool
    tests: list[TestResult] = Field(max_length=500)
    collectors: list[dict] = Field(default_factory=list, max_length=500)


def normalize_report(value, exit_code):
    try:
        report = TestReport.model_validate(value)
    except ValidationError:
        return None
    if report.exitcode != exit_code or report.truncated:
        return None
    if len({t.nodeid for t in report.tests}) != len(report.tests):
        return None
    if report.summary.get("total") != len(report.tests) or any(n < 0 for n in report.summary.values()):
        return None
    if report.summary.get("passed", 0) != sum(t.outcome == "passed" for t in report.tests):
        return None
    return report.model_dump()


def report_passes(value, exit_code=0, selectors=()):
    report = normalize_report(value, exit_code)
    if not report or exit_code != 0 or not report["tests"]:
        return False
    if any(c.get("outcome") != "passed" for c in report["collectors"]):
        return False
    tests = report["tests"]
    if selectors:
        requested = set(selectors)
        # A function/class selector may expand to parameterized cases; every
        # returned case must belong to a requested node, and every node must run.
        matches = lambda actual, wanted: actual == wanted or actual.startswith(wanted + "[") or actual.startswith(wanted + "::")
        if not all(any(matches(t["nodeid"], s) for s in requested) for t in tests):
            return False
        if not all(any(matches(t["nodeid"], s) for t in tests) for s in requested):
            return False
    # Skips/xfails can remain in a regression suite, but a criterion cannot pass
    # based on skipped assertions or failed teardown.
    acceptable = tests if selectors else [t for t in tests if t["outcome"] not in {"skipped", "xfailed"}]
    return bool(acceptable) and all(t["outcome"] == "passed" and
                                  all(t[stage] == "passed" for stage in ("setup", "call", "teardown"))
                                  for t in acceptable)


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
