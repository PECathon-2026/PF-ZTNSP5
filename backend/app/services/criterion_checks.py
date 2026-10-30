"""Approved, single-test selectors for deterministic criterion evidence."""

import ast
import json
import hashlib
import re
from pathlib import Path

from app.security.paths import canonicalize_and_validate_path
from app.settings import get_settings

SELECTOR = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.py::(?:Test[A-Za-z0-9_]+::)?test_[A-Za-z0-9_]+(?:\[[A-Za-z0-9_,. -]+\])?\Z")


def validate_selector(root: Path, selector: str) -> str:
    if len(selector) > 300 or ".." in selector or not SELECTOR.fullmatch(selector):
        raise ValueError("Criterion needs a single approved pytest node ID (file.py::test_name)")
    test_file = canonicalize_and_validate_path(root, selector.split("::", 1)[0])
    if not test_file.is_file() or not test_file.name.startswith("test_"):
        raise ValueError("Criterion selector must reference an existing test file")
    if test_file.stat().st_size > get_settings().max_file_size_bytes:
        raise ValueError("Criterion test file exceeds the read limit")
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeError):
        raise ValueError("Criterion test file cannot be parsed") from None
    parts = selector.split("::")[1:]
    nodes = tree.body
    if len(parts) == 2:
        nodes = next((node.body for node in tree.body if isinstance(node, ast.ClassDef) and node.name == parts[0]), [])
    function_name = parts[-1].split("[", 1)[0]
    if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name for node in nodes):
        raise ValueError("Criterion selector must name an existing test function or test method")
    return selector


def criterion_profile(criterion) -> tuple[str, str | None]:
    profile, selectors = criterion_selectors(criterion)
    return profile, selectors[0] if selectors else None


def criterion_selectors(criterion) -> tuple[str, list[str]]:
    method = criterion.verification_method
    if not method.startswith("test_profile:"):
        return "", []
    parts = method.removeprefix("test_profile:").split("|", 1)
    if len(parts) == 1:
        return parts[0], []
    if parts[1].startswith("["):
        try:
            selectors = json.loads(parts[1])
            if not isinstance(selectors, list) or not selectors or len(selectors) > 20 or not all(isinstance(s, str) for s in selectors):
                return parts[0], []
            return parts[0], list(dict.fromkeys(selectors))
        except ValueError:
            return parts[0], []
    return parts[0], [parts[1]]


def planned_selectors(criterion):
    if isinstance(criterion, dict):
        return sorted(set(criterion.get("test_selectors", []) + ([criterion["test_selector"]] if criterion.get("test_selector") else [])))
    return sorted(set(criterion.test_selectors + ([criterion.test_selector] if criterion.test_selector else [])))


def verification_contract_hash(directory, criteria, extra_files=None):
    from app.tools.files import list_files
    from app.services.test_reports import object_hash
    tests = {}
    for relative in list_files(directory):
        path = Path(relative)
        if (path.name.startswith("test_") or path.name.endswith("_test.py") or path.name in
                {"conftest.py", "pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"}):
            safe = canonicalize_and_validate_path(directory, relative)
            tests[relative] = hashlib.sha256(safe.read_bytes()).hexdigest()
    for relative, content in (extra_files or {}).items():
        if relative in tests or (directory / relative).exists():
            raise ValueError("Accepted test file collides with candidate")
        tests[relative] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return object_hash({"version": 1, "tests": sorted(tests.items()), "criteria": [
        {"id": c.id, "description": c.description, "method": c.verification_method, "version": c.criteria_version}
        for c in criteria]})
