import difflib
import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.schemas.candidate import Candidate, CandidateState
from app.security.paths import is_path_excluded
from app.services.repository_service import get_repository_service
from app.settings import get_settings


class WriterLeaseError(Exception):
    """Raised when an agent violates the single workspace writer lease invariant."""
    pass


class WorkspaceService:
    """Manages disposable execution workspaces, candidate snapshots, and writer leases."""

    def __init__(self, base_workspaces_dir: Path | None = None):
        self.base_dir = base_workspaces_dir or (get_settings().data_dir / "workspaces")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # mission_id -> current lease holder agent name
        self._leases: dict[str, str] = {}
        # candidate_id -> metadata
        self._candidates: dict[str, Candidate] = {}

    def get_mission_workspace_dir(self, mission_id: str) -> Path:
        return self.base_dir / mission_id / "workspace"

    def get_candidate_dir(self, mission_id: str, candidate_id: str) -> Path:
        return self.base_dir / mission_id / "candidates" / candidate_id

    def create_disposable_workspace(self, mission_id: str, repository_id: str) -> Path:
        """
        Creates an isolated disposable working directory containing only approved files.
        The original repository is never modified directly.
        """
        repo_service = get_repository_service()
        repo = repo_service.get_repository(repository_id)
        if not repo:
            raise KeyError(f"Repository '{repository_id}' is not registered.")

        repo_path = Path(repo["path"])
        ws_dir = self.get_mission_workspace_dir(mission_id)
        if ws_dir.exists():
            shutil.rmtree(ws_dir, ignore_errors=True)
        ws_dir.mkdir(parents=True, exist_ok=True)

        # Copy only approved included files
        for rel_file in repo["included_files"]:
            src = repo_path / rel_file
            dest = ws_dir / rel_file
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.copy2(src, dest)

        return ws_dir

    def acquire_writer_lease(self, mission_id: str, agent_name: str) -> None:
        """
        Grants write access to an agent. Only one agent may hold the writer lease at a time.
        """
        current_holder = self._leases.get(mission_id)
        if current_holder and current_holder != agent_name:
            raise WriterLeaseError(
                f"Workspace write lease already held by '{current_holder}'. Agent '{agent_name}' denied write access."
            )
        self._leases[mission_id] = agent_name

    def release_writer_lease(self, mission_id: str, agent_name: str) -> None:
        if self._leases.get(mission_id) == agent_name:
            del self._leases[mission_id]

    def _compute_dir_hash(self, directory: Path) -> tuple[str, list[str]]:
        hasher = hashlib.sha256()
        files_list: list[str] = []
        for root, _, files in os.walk(directory):
            rel_root = Path(root).relative_to(directory)
            for f in sorted(files):
                rel_f = rel_root / f if str(rel_root) != "." else Path(f)
                if is_path_excluded(rel_f):
                    continue
                rel_str = str(rel_f).replace("\\", "/")
                files_list.append(rel_str)
                full_path = Path(root) / f
                hasher.update(rel_str.encode("utf-8"))
                with open(full_path, "rb") as fp:
                    hasher.update(fp.read())
        return hasher.hexdigest(), sorted(files_list)

    def freeze_candidate(
        self,
        mission_id: str,
        repository_id: str,
        parent_candidate_id: str | None = None,
    ) -> Candidate:
        """
        Freezes the current mutable workspace into an immutable candidate snapshot.
        Computes changed files against the baseline repository.
        """
        ws_dir = self.get_mission_workspace_dir(mission_id)
        if not ws_dir.exists():
            raise FileNotFoundError(f"Mutable workspace for mission '{mission_id}' does not exist.")

        content_fingerprint, ws_files = self._compute_dir_hash(ws_dir)

        repo_service = get_repository_service()
        repo = repo_service.get_repository(repository_id)
        baseline_files = set(repo["included_files"]) if repo else set()
        repo_path = Path(repo["path"]) if repo else None

        changed_files: list[str] = []
        for rel_f in ws_files:
            ws_file_path = ws_dir / rel_f
            if rel_f not in baseline_files or not repo_path:
                changed_files.append(rel_f)
            else:
                base_file_path = repo_path / rel_f
                if not base_file_path.exists() or ws_file_path.read_bytes() != base_file_path.read_bytes():
                    changed_files.append(rel_f)

        cand_id = f"cand-{content_fingerprint[:8]}"
        candidate_dir = self.get_candidate_dir(mission_id, cand_id)
        if candidate_dir.exists():
            shutil.rmtree(candidate_dir, ignore_errors=True)
        candidate_dir.mkdir(parents=True, exist_ok=True)

        # Copy workspace to candidate dir
        for rel_f in ws_files:
            src = ws_dir / rel_f
            dst = candidate_dir / rel_f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        candidate = Candidate(
            id=cand_id,
            mission_id=mission_id,
            parent_candidate_id=parent_candidate_id,
            workspace_snapshot_id=cand_id,
            content_fingerprint=content_fingerprint,
            changed_files=changed_files,
            state=CandidateState.FROZEN,
            ui_badge="IN_CANDIDATE",
        )

        self._candidates[cand_id] = candidate
        return candidate

    def get_candidate(self, candidate_id: str) -> Candidate | None:
        return self._candidates.get(candidate_id)

    def generate_candidate_diff(self, mission_id: str, repository_id: str, candidate_id: str) -> dict[str, Any]:
        """Generates unified diff between original repository and frozen candidate snapshot."""
        candidate = self.get_candidate(candidate_id)
        if not candidate:
            raise KeyError(f"Candidate '{candidate_id}' not found.")

        repo_service = get_repository_service()
        repo = repo_service.get_repository(repository_id)
        if not repo:
            raise KeyError(f"Repository '{repository_id}' not found.")

        repo_path = Path(repo["path"])
        cand_dir = self.get_candidate_dir(mission_id, candidate_id)

        file_diffs: list[dict[str, Any]] = []
        full_diff_lines: list[str] = []

        for rel_file in candidate.changed_files:
            src_file = repo_path / rel_file
            cand_file = cand_dir / rel_file

            src_lines = src_file.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if src_file.exists() else []
            cand_lines = cand_file.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if cand_file.exists() else []

            diff = list(difflib.unified_diff(
                src_lines,
                cand_lines,
                fromfile=f"a/{rel_file}",
                tofile=f"b/{rel_file}",
            ))

            diff_text = "".join(diff)
            full_diff_lines.append(diff_text)
            file_diffs.append({
                "file_path": rel_file,
                "change_type": "MODIFIED" if src_file.exists() and cand_file.exists() else ("ADDED" if cand_file.exists() else "DELETED"),
                "diff": diff_text,
            })

        return {
            "candidate_id": candidate_id,
            "content_fingerprint": candidate.content_fingerprint,
            "changed_files_count": len(candidate.changed_files),
            "files": file_diffs,
            "unified_diff": "\n".join(full_diff_lines),
        }


_workspace_service_instance: WorkspaceService | None = None


def get_workspace_service() -> WorkspaceService:
    global _workspace_service_instance
    if _workspace_service_instance is None:
        _workspace_service_instance = WorkspaceService()
    return _workspace_service_instance

