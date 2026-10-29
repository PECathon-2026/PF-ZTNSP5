import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from app.schemas.common import PreflightResult, PreflightStatus
from app.security.paths import (
    canonicalize_and_validate_path,
    is_path_excluded,
    PathSecurityError,
)
from app.settings import get_settings


class RepositoryService:
    """Manages repository registration, preflight reconnaissance, and file exploration."""

    def __init__(self):
        self._repositories: dict[str, dict[str, Any]] = {}

    def _check_docker(self) -> bool:
        if not shutil.which("docker"):
            return False
        try:
            res = subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2.0,
            )
            return res.returncode == 0
        except Exception:
            return False

    def _detect_profile(self, repo_path: Path) -> str:
        if (repo_path / "pytest.ini").exists() or (repo_path / "pyproject.toml").exists() or (repo_path / "tests").exists():
            return "python_pytest"
        if (repo_path / "package.json").exists():
            return "node_npm"
        return "python_pytest"

    def _check_git_modifications(self, repo_path: Path) -> bool:
        if not (repo_path / ".git").exists() or not shutil.which("git"):
            return False
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            return bool(res.stdout.strip())
        except Exception:
            return False

    def _scan_files(self, repo_path: Path) -> tuple[list[str], int, str]:
        """
        Recursively scans repo_path, applies exclusion rules,
        computes baseline fingerprint, and returns (included_files, excluded_count, tree_hash).
        """
        included: list[str] = []
        excluded_count = 0
        hasher = hashlib.sha256()

        for root, dirs, files in os.walk(repo_path):
            rel_root = Path(root).relative_to(repo_path)
            
            # Prune excluded directories
            pruned_dirs = []
            for d in dirs:
                if is_path_excluded(rel_root / d):
                    excluded_count += 1
                else:
                    pruned_dirs.append(d)
            dirs[:] = pruned_dirs

            for f in sorted(files):
                rel_file = rel_root / f if str(rel_root) != "." else Path(f)
                if is_path_excluded(rel_file):
                    excluded_count += 1
                    continue

                full_path = Path(root) / f
                try:
                    size = full_path.stat().st_size
                    if size > get_settings().max_file_size_bytes:
                        excluded_count += 1
                        continue

                    rel_str = str(rel_file).replace("\\", "/")
                    included.append(rel_str)

                    # Update content hash
                    with open(full_path, "rb") as fp:
                        hasher.update(rel_str.encode("utf-8"))
                        hasher.update(fp.read())
                except (OSError, PermissionError):
                    excluded_count += 1

        included.sort()
        tree_hash = hasher.hexdigest()
        return included, excluded_count, tree_hash

    def connect_repository(self, raw_path: str) -> dict[str, Any]:
        """
        Registers and preflights an authorized local repository directory.
        """
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: '{raw_path}'")
        if not path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: '{raw_path}'")

        repo_id = f"repo-{hashlib.sha256(str(path).encode('utf-8')).hexdigest()[:8]}"
        name = path.name or "repository"

        # Reconnaissance
        detected_profile = self._detect_profile(path)
        existing_modifications = self._check_git_modifications(path)
        included_files, excluded_count, tree_hash = self._scan_files(path)

        warnings: list[str] = []
        blockers: list[str] = []

        if existing_modifications:
            warnings.append("Uncommitted changes detected in original repository.")

        docker_ready = self._check_docker()
        if not docker_ready:
            blockers.append(
                "Docker Desktop Linux Engine is unavailable. PS-001 requires restricted container execution; host execution is blocked."
            )

        status = PreflightStatus.BLOCKED if blockers else (
            PreflightStatus.WARNING if warnings else PreflightStatus.READY
        )

        preflight = PreflightResult(
            status=status,
            detected_profile=detected_profile,
            file_count=len(included_files),
            excluded_count=excluded_count,
            existing_modifications=existing_modifications,
            warnings=warnings,
            blockers=blockers,
        )

        repo_record = {
            "repository_id": repo_id,
            "name": name,
            "path": str(path),
            "fingerprint": tree_hash,
            "included_files": included_files,
            "preflight": preflight,
        }

        self._repositories[repo_id] = repo_record
        return repo_record

    def get_repository(self, repo_id: str) -> dict[str, Any] | None:
        return self._repositories.get(repo_id)

    def get_file_tree(self, repo_id: str) -> list[str]:
        repo = self.get_repository(repo_id)
        if not repo:
            raise KeyError(f"Repository '{repo_id}' not found.")
        return repo["included_files"]

    def read_file_content(self, repo_id: str, relative_path: str) -> str:
        repo = self.get_repository(repo_id)
        if not repo:
            raise KeyError(f"Repository '{repo_id}' not found.")

        base_path = Path(repo["path"])
        validated_path = canonicalize_and_validate_path(base_path, relative_path)

        if not validated_path.exists():
            raise FileNotFoundError(f"File not found: '{relative_path}'")

        max_size = get_settings().max_file_size_bytes
        if validated_path.stat().st_size > max_size:
            raise ValueError(f"File '{relative_path}' exceeds maximum size limit ({max_size} bytes).")

        with open(validated_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()


_repo_service_instance: RepositoryService | None = None


def get_repository_service() -> RepositoryService:
    global _repo_service_instance
    if _repo_service_instance is None:
        _repo_service_instance = RepositoryService()
    return _repo_service_instance

