import os
import re
from pathlib import Path
from typing import Any
from app.security.paths import is_path_excluded
from app.settings import get_settings


def search_text(
    workspace_dir: Path,
    query: str,
    regex: bool = False,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """
    Searches files within workspace_dir for literal query or regex pattern.
    Returns bounded list of matches with file_path, line_number, and snippet.
    """
    if not query:
        return []

    pattern = re.compile(query, re.IGNORECASE) if regex else None
    query_lower = query.lower() if not regex else None

    matches: list[dict[str, Any]] = []
    max_size = get_settings().max_file_size_bytes

    for root, dirs, files in os.walk(workspace_dir):
        rel_root = Path(root).relative_to(workspace_dir)

        # Filter excluded dirs
        dirs[:] = [d for d in dirs if not is_path_excluded(rel_root / d)]

        for f in sorted(files):
            rel_file = rel_root / f if str(rel_root) != "." else Path(f)
            if is_path_excluded(rel_file):
                continue

            full_path = Path(root) / f
            try:
                if full_path.stat().st_size > max_size:
                    continue

                with open(full_path, "r", encoding="utf-8", errors="replace") as fp:
                    for line_no, line in enumerate(fp, start=1):
                        matched = False
                        if regex and pattern and pattern.search(line):
                            matched = True
                        elif query_lower and query_lower in line.lower():
                            matched = True

                        if matched:
                            matches.append({
                                "file_path": str(rel_file).replace("\\", "/"),
                                "line_number": line_no,
                                "snippet": line.strip()[:200],
                            })
                            if len(matches) >= max_results:
                                return matches
            except (OSError, PermissionError):
                continue

    return matches

