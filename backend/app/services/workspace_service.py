import difflib
import hashlib
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from app.schemas.candidate import Candidate, CandidateState
from app.security.paths import canonicalize_and_validate_path, is_path_excluded
from app.services.repository_service import get_repository_service
from app.settings import get_settings


class WriterLeaseError(Exception):
    """Raised when an agent violates the single workspace writer lease invariant."""
    pass


class WorkspaceService:
    """Manages disposable execution workspaces, candidate snapshots, and writer leases."""

    def __init__(self, base_workspaces_dir: Path | None = None):
        self.base_dir = (base_workspaces_dir or (get_settings().data_dir / "workspaces")).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # mission_id -> current lease holder agent name
        self._leases: dict[str, str] = {}
        # candidate_id -> metadata
        self._candidates: dict[str, Candidate] = {}

    def get_mission_workspace_dir(self, mission_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", mission_id):
            raise ValueError("Invalid mission workspace identifier.")
        return self.base_dir / mission_id / "workspace"

    def get_baseline_dir(self, mission_id: str) -> Path:
        return self.get_mission_workspace_dir(mission_id).parent / "baseline"

    def get_candidate_dir(self, mission_id: str, candidate_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", candidate_id):
            raise ValueError("Invalid candidate identifier.")
        return self.get_mission_workspace_dir(mission_id).parent / "candidates" / candidate_id

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
        if ws_dir.resolve().is_relative_to(repo_path.resolve()) or repo_path.resolve().is_relative_to(self.base_dir.resolve()):
            raise ValueError("Disposable storage and the original repository must not overlap.")
        if ws_dir.parent.exists():
            raise FileExistsError("Mission workspace already exists; implicit reset is forbidden.")
        ws_dir.mkdir(parents=True)
        baseline_dir = self.get_baseline_dir(mission_id)
        baseline_dir.mkdir()

        # Copy only approved included files
        for rel_file in repo["included_files"]:
            src = canonicalize_and_validate_path(repo_path, rel_file)
            dest = ws_dir / rel_file
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not src.is_file() or src.stat().st_size > get_settings().max_file_size_bytes:
                raise ValueError("Repository manifest changed; reconnect before creating a workspace.")
            shutil.copy2(src, dest)
            baseline_file = baseline_dir / rel_file
            baseline_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, baseline_file)

        return ws_dir

    def acquire_writer_lease(self, mission_id: str, agent_name: str) -> None:
        """
        Grants write access to an agent. Only one agent may hold the writer lease at a time.
        """
        current_holder = self._leases.get(mission_id)
        if current_holder:
            raise WriterLeaseError(
                f"Workspace write lease already held by '{current_holder}'. Agent '{agent_name}' denied write access."
            )
        self._leases[mission_id] = agent_name

    def release_writer_lease(self, mission_id: str, agent_name: str) -> None:
        if self._leases.get(mission_id) == agent_name:
            del self._leases[mission_id]

    def _compute_dir_hash(self, directory: Path) -> tuple[str, list[str]]:
        if not directory.is_dir():
            raise FileNotFoundError("Workspace snapshot is missing")
        hasher = hashlib.sha256()
        files_list: list[str] = []
        for root, dirs, files in os.walk(directory):
            rel_root = Path(root).relative_to(directory)
            dirs[:] = sorted(d for d in dirs if not is_path_excluded(rel_root / d))
            for f in sorted(files):
                rel_f = rel_root / f if str(rel_root) != "." else Path(f)
                if is_path_excluded(rel_f):
                    continue
                rel_str = str(rel_f).replace("\\", "/")
                files_list.append(rel_str)
                full_path = canonicalize_and_validate_path(directory, rel_str)
                path_bytes = rel_str.encode("utf-8")
                hasher.update(len(path_bytes).to_bytes(8, "big"))
                hasher.update(path_bytes)
                with open(full_path, "rb") as fp:
                    hasher.update(hashlib.sha256(fp.read()).digest())
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

        repo_path = self.get_baseline_dir(mission_id)
        _, baseline_list = self._compute_dir_hash(repo_path)
        baseline_files = set(baseline_list)

        changed_files: list[str] = []
        for rel_f in ws_files:
            ws_file_path = ws_dir / rel_f
            if rel_f not in baseline_files or not repo_path:
                changed_files.append(rel_f)
            else:
                base_file_path = repo_path / rel_f
                if not base_file_path.exists() or ws_file_path.read_bytes() != base_file_path.read_bytes():
                    changed_files.append(rel_f)

        changed_files.extend(sorted(baseline_files - set(ws_files)))
        cand_id = f"cand-{uuid4().hex[:16]}"
        candidate_dir = self.get_candidate_dir(mission_id, cand_id)
        candidate_dir.mkdir(parents=True)

        # Copy workspace to candidate dir
        for rel_f in ws_files:
            src = ws_dir / rel_f
            dst = candidate_dir / rel_f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        if self._compute_dir_hash(candidate_dir)[0] != content_fingerprint:
            raise ValueError("Candidate changed while being frozen")

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

    def validate_candidate(self, candidate: Candidate) -> None:
        if candidate.state != CandidateState.FROZEN:
            raise ValueError("Execution requires a frozen candidate")
        directory = self.get_candidate_dir(candidate.mission_id, candidate.id)
        if self._compute_dir_hash(directory)[0] != candidate.content_fingerprint:
            raise ValueError("Frozen candidate fingerprint mismatch")

    def generate_candidate_diff(self, mission_id: str, repository_id: str, candidate_id: str) -> dict[str, Any]:
        """Generates unified diff between original repository and frozen candidate snapshot."""
        candidate = self.get_candidate(candidate_id)
        if not candidate or candidate.mission_id != mission_id:
            raise KeyError(f"Candidate '{candidate_id}' not found.")

        repo_service = get_repository_service()
        repo = repo_service.get_repository(repository_id)
        if not repo:
            raise KeyError(f"Repository '{repository_id}' not found.")

        repo_path = self.get_baseline_dir(mission_id)
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

