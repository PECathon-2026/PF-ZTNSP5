"""Bounded Python AST map inspired by Aider's repository-map approach.

No imports, execution, embeddings or persistent stale cache are used.
"""

import ast
import hashlib
import json
from pathlib import Path

from app.security.paths import canonicalize_and_validate_path
from app.settings import get_settings


def repository_map(directory: Path, max_files=80, max_symbols=200):
    from app.tools.files import list_files
    files = []
    symbols_left = max_symbols
    for relative in list_files(directory):
        if not relative.endswith(".py"):
            continue
        if len(files) >= max_files or symbols_left <= 0:
            break
        path = canonicalize_and_validate_path(directory, relative)
        if path.stat().st_size > get_settings().max_file_size_bytes:
            continue
        data = path.read_bytes()
        entry = {"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "symbols": [], "imports": [], "tests": []}
        try:
            tree = ast.parse(data)
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    entry["imports"].extend([alias.name for alias in node.names][:15])
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and symbols_left:
                    entry["symbols"].append({"name": node.name, "kind": type(node).__name__, "line": node.lineno,
                                             "parameters": [arg.arg for arg in node.args.args] if not isinstance(node, ast.ClassDef) else []})
                    symbols_left -= 1
                    if node.name.startswith("test_"):
                        entry["tests"].append(relative + "::" + node.name)
                    if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                        for method in node.body:
                            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith("test_"):
                                entry["tests"].append(f"{relative}::{node.name}::{method.name}")
        except (SyntaxError, ValueError, UnicodeError):
            entry["parse_error"] = True
        entry["imports"] = entry["imports"][:30]
        files.append(entry)
    return {"files": files, "truncated": len(files) >= max_files or symbols_left <= 0,
            "map_fingerprint": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
