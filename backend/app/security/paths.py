import os
from pathlib import Path

# Sensitive files and extensions that should never be read or processed
EXCLUDED_PATTERNS = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".next",
    "dist",
    "build",
}

EXCLUDED_EXTENSIONS = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".iso",
    ".pyc",
    ".pyo",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
}


class PathSecurityError(Exception):
    """Raised when a path violates security or isolation boundaries."""
    pass


def canonicalize_and_validate_path(base_dir: Path, relative_path: str) -> Path:
    """
    Resolves relative_path against base_dir and ensures:
    1. It does not escape base_dir via '..' or symlinks/junctions.
    2. It does not access excluded or sensitive credential files.
    """
    if not relative_path:
        raise PathSecurityError("Relative path cannot be empty.")

    # Reject null bytes or suspicious path components
    if "\0" in relative_path:
        raise PathSecurityError("Null bytes detected in path.")

    base_resolved = base_dir.resolve()
    target_path = (base_dir / relative_path).resolve()

    # Verify containment within base_dir
    try:
        target_path.relative_to(base_resolved)
    except ValueError:
        raise PathSecurityError(f"Path traversal detected: '{relative_path}' escapes workspace boundary.")

    # Check against excluded filename patterns and extensions
    name = target_path.name.lower()
    if name in EXCLUDED_PATTERNS or any(part.lower() in EXCLUDED_PATTERNS for part in target_path.parts):
        raise PathSecurityError(f"Access to restricted path component is forbidden: '{name}'.")

    if target_path.suffix.lower() in EXCLUDED_EXTENSIONS:
        raise PathSecurityError(f"Access to file with restricted extension is forbidden: '{target_path.suffix}'.")

    return target_path


def is_path_excluded(rel_path: Path) -> bool:
    """Checks if a relative path matches any exclusion rule."""
    parts = [p.lower() for p in rel_path.parts]
    for part in parts:
        if part in EXCLUDED_PATTERNS or part.startswith(".git"):
            return True
    if rel_path.suffix.lower() in EXCLUDED_EXTENSIONS:
        return True
    return False

