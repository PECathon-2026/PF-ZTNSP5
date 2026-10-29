import difflib
from pathlib import Path
from app.security.paths import canonicalize_and_validate_path


def read_diff(
    base_dir: Path,
    candidate_dir: Path,
    relative_path: str,
) -> str:
    """
    Computes unified diff for a single file between base_dir and candidate_dir.
    """
    base_file = canonicalize_and_validate_path(base_dir, relative_path)
    cand_file = canonicalize_and_validate_path(candidate_dir, relative_path)

    base_lines = base_file.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if base_file.exists() else []
    cand_lines = cand_file.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if cand_file.exists() else []

    diff = list(difflib.unified_diff(
        base_lines,
        cand_lines,
        fromfile=f"a/{relative_path}",
        tofile=f"b/{relative_path}",
    ))

    return "".join(diff)

