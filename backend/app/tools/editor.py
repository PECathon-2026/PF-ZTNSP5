from pathlib import Path
from typing import Any
from app.security.paths import canonicalize_and_validate_path
from app.settings import get_settings


class PatchError(Exception):
    """Raised when patch application fails or encounters conflicts."""
    pass


def apply_patch(
    workspace_dir: Path,
    relative_path: str,
    target: str | None = None,
    replacement: str | None = None,
    content: str | None = None,
) -> dict[str, Any]:
    """
    Applies a targeted edit to a file inside the mutable workspace.
    Either replaces occurrences of `target` with `replacement`, or sets full `content`.
    """
    target_path = canonicalize_and_validate_path(workspace_dir, relative_path)

    # Mode 1: Full content write/create
    if content is not None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        max_size = get_settings().max_file_size_bytes
        if len(content.encode("utf-8")) > max_size:
            raise PatchError(f"Content exceeds size limit ({max_size} bytes).")

        old_lines = target_path.read_text(encoding="utf-8", errors="replace").count("\n") if target_path.exists() else 0
        target_path.write_text(content, encoding="utf-8")
        new_lines = content.count("\n")

        return {
            "file_path": relative_path.replace("\\", "/"),
            "status": "APPLIED",
            "mode": "full_content",
            "lines_before": old_lines,
            "lines_after": new_lines,
        }

    # Mode 2: Targeted string replacement
    if target is None or replacement is None:
        raise PatchError("Targeted patch requires both 'target' and 'replacement' parameters.")

    if not target_path.exists():
        raise PatchError(f"Target file '{relative_path}' does not exist for string replacement.")

    current_text = target_path.read_text(encoding="utf-8", errors="replace")
    if not target:
        raise PatchError("Target snippet cannot be empty.")
    if target not in current_text:
        raise PatchError(f"Target snippet not found in '{relative_path}'. Patch rejected.")

    occurrences = current_text.count(target)
    new_text = current_text.replace(target, replacement)
    if len(new_text.encode("utf-8")) > get_settings().max_file_size_bytes:
        raise PatchError("Patched content exceeds the file size limit.")
    target_path.write_text(new_text, encoding="utf-8")

    return {
        "file_path": relative_path.replace("\\", "/"),
        "status": "APPLIED",
        "mode": "targeted_replacement",
        "replacements_count": occurrences,
        "lines_before": current_text.count("\n"),
        "lines_after": new_text.count("\n"),
    }

