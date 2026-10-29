import os
from pathlib import Path
from typing import Any
from app.security.paths import canonicalize_and_validate_path, is_path_excluded
from app.settings import get_settings


def list_files(workspace_dir: Path, subpath: str = "") -> list[str]:
    """
    Returns bounded list of relative file paths in workspace_dir or workspace_dir/subpath.
    Filters excluded and restricted patterns.
    """
    target_dir = canonicalize_and_validate_path(workspace_dir, subpath) if subpath else workspace_dir.resolve()
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Target is not a directory: '{subpath}'")

    results: list[str] = []
    max_count = 500

    for root, dirs, files in os.walk(target_dir):
        rel_root = Path(root).relative_to(workspace_dir)

        # Filter excluded dirs
        dirs[:] = [d for d in dirs if not is_path_excluded(rel_root / d)]

        for f in sorted(files):
            rel_file = rel_root / f if str(rel_root) != "." else Path(f)
            if is_path_excluded(rel_file):
                continue

            results.append(str(rel_file).replace("\\", "/"))
            if len(results) >= max_count:
                break
        if len(results) >= max_count:
            break

    return sorted(results)


def read_file(
    workspace_dir: Path,
    relative_path: str,
    line_start: int | None = None,
    line_end: int | None = None,
) -> dict[str, Any]:
    """
    Reads file content with line bounding and size limits.
    """
    file_path = canonicalize_and_validate_path(workspace_dir, relative_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: '{relative_path}'")
    if file_path.is_dir():
        raise IsADirectoryError(f"Path is a directory, not a file: '{relative_path}'")

    max_size = get_settings().max_file_size_bytes
    if file_path.stat().st_size > max_size:
        raise ValueError(f"File '{relative_path}' exceeds maximum size cap ({max_size} bytes).")

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    total_lines = len(lines)
    start_idx = max(1, line_start) if line_start else 1
    end_idx = min(total_lines, line_end) if line_end else total_lines

    selected_lines = lines[start_idx - 1 : end_idx]
    content = "".join(selected_lines)

    return {
        "file_path": relative_path.replace("\\", "/"),
        "total_lines": total_lines,
        "line_start": start_idx,
        "line_end": end_idx,
        "content": content,
    }

