"""Crash-recoverable, journaled application of approved candidate file changes.

Each individual replacement is atomic; a multi-file transaction is not globally
atomic for concurrent external readers. On crash, startup rolls incomplete writes
back to the recorded baseline before serving the API.
"""

import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from uuid import uuid4

from app.schemas.candidate import CandidateState
from app.schemas.mission import MissionStatus
from app.security.paths import canonicalize_and_validate_path, is_path_excluded
from app.services.repository_service import RepositoryService
from app.agents.samurai import SamuraiRunner
from app.settings import get_settings
from app.storage.guild import GuildConflict, GuildStore, now


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def safe_path(root, relative, *, changed=True):
    if is_path_excluded(Path(relative)) or (changed and SamuraiRunner._protected(relative)):
        raise GuildConflict("Protected path cannot be applied")
    raw = root / relative
    if raw.is_symlink() or any(parent.is_symlink() for parent in [*raw.parents] if parent != root and parent.is_relative_to(root)):
        raise GuildConflict("Symlinked repository path cannot be applied")
    return canonicalize_and_validate_path(root, relative)


def write_file(path, data, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".devpilot-", delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


class PatchApplication:
    def __init__(self, controller):
        self.controller = controller
        self.store = GuildStore(controller.db)
        self.journals = (get_settings().data_dir / "application-journals").resolve()
        self.journals.mkdir(parents=True, exist_ok=True)

    def _validate(self, mission, candidate, context, baseline_fingerprint):
        repo = Path(context["repository"]["path"]).resolve()
        baseline = self.controller.workspaces.get_baseline_dir(mission.id)
        snapshot = self.controller.workspaces.get_candidate_dir(mission.id, candidate.id)
        if self.controller.workspaces._compute_dir_hash(baseline)[0] != baseline_fingerprint:
            raise GuildConflict("Captured baseline must match its frozen fingerprint")
        if self.controller.workspaces._compute_dir_hash(snapshot)[0] != candidate.content_fingerprint:
            raise GuildConflict("Approved candidate snapshot changed")
        baseline_files = set(self.controller.workspaces._compute_dir_hash(baseline)[1])
        snapshot_files = set(self.controller.workspaces._compute_dir_hash(snapshot)[1])
        # Recompute the changed set; never trust model-proposed changed_files.
        changed = sorted(path for path in baseline_files & snapshot_files
                         if (baseline / path).read_bytes() != (snapshot / path).read_bytes())
        changed = sorted(set(changed) | (baseline_files ^ snapshot_files))
        if not changed or len(candidate.changed_files) != len(changed) or set(changed) != set(candidate.changed_files):
            raise GuildConflict("Candidate changed-file manifest is stale")
        for relative in snapshot_files:
            path = snapshot / relative
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != snapshot and parent.is_relative_to(snapshot)):
                raise GuildConflict("Candidate contains a symlink")
        scanner = RepositoryService()
        original_files, _, _ = scanner._scan_files(repo)
        if original_files != context["repository"]["included_files"] or set(original_files) != baseline_files:
            raise GuildConflict("Original repository manifest changed since preflight")
        for relative in sorted(baseline_files):
            target = safe_path(repo, relative, changed=False)
            source = canonicalize_and_validate_path(baseline, relative)
            if not target.is_file() or not source.is_file() or target.read_bytes() != source.read_bytes():
                raise GuildConflict("Original repository changed since preflight")
        entries = []
        for index, relative in enumerate(changed):
            target = safe_path(repo, relative)
            source = canonicalize_and_validate_path(snapshot, relative)
            original = (baseline / relative).read_bytes() if relative in baseline_files else None
            new = source.read_bytes() if relative in snapshot_files and source.is_file() else None
            if relative in snapshot_files and (not source.is_file() or source.is_symlink()):
                raise GuildConflict("Candidate contains a nonregular file")
            if new is not None and len(new) > get_settings().max_file_size_bytes:
                raise GuildConflict("Candidate file exceeds size limit")
            if original is None and target.exists():
                raise GuildConflict("New-file target already exists")
            entries.append({"relative": relative, "index": index, "before": digest(original), "after": digest(new),
                            "mode": stat.S_IMODE(target.stat().st_mode) if original is not None else stat.S_IMODE(source.stat().st_mode)})
        return repo, snapshot, entries

    def _journal(self, mission, candidate, repo, baseline, snapshot, entries):
        directory = self.journals / f"{mission.id}-{uuid4().hex}"
        directory.mkdir()
        for item in entries:
            index, relative = item["index"], item["relative"]
            if item["before"]:
                write_file(directory / f"before-{index}", (baseline / relative).read_bytes())
            if item["after"]:
                write_file(directory / f"after-{index}", (snapshot / relative).read_bytes())
        manifest = {"mission_id": mission.id, "candidate_id": candidate.id,
                    "fingerprint": candidate.content_fingerprint, "repository": str(repo), "entries": entries}
        write_file(directory / "manifest.json", json.dumps(manifest).encode("utf-8"))
        return directory

    def _read_journal(self, directory):
        if not directory.is_relative_to(self.journals) or directory.is_symlink():
            raise GuildConflict("Invalid application journal")
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        for entry in manifest["entries"]:
            for label, prefix in (("before", "before"), ("after", "after")):
                if entry[label]:
                    data = (directory / f"{prefix}-{entry['index']}").read_bytes()
                    if digest(data) != entry[label]:
                        raise GuildConflict("Application journal integrity check failed")
        return manifest

    def _replace_entry(self, repo, directory, item):
        target = safe_path(repo, item["relative"])
        if target.exists() and not target.is_file():
            raise GuildConflict("Repository target is not a regular file")
        present = digest(target.read_bytes()) if target.exists() else None
        if present != item["before"]:
            raise GuildConflict("Original repository changed during application")
        if item["after"] is None:
            target.unlink()
        else:
            write_file(target, (directory / f"after-{item['index']}").read_bytes(), item["mode"])

    def _rollback(self, repo, directory, manifest):
        # Inspect *every* path before changing any. Unknown external edits require
        # manual intervention rather than an automatic rollback that overwrites them.
        for item in manifest["entries"]:
            target = safe_path(repo, item["relative"])
            present = digest(target.read_bytes()) if target.exists() and target.is_file() else None
            if present not in {item["before"], item["after"]}:
                raise GuildConflict("Cannot safely roll back an externally modified file")
        for item in reversed(manifest["entries"]):
            target = safe_path(repo, item["relative"])
            present = digest(target.read_bytes()) if target.exists() else None
            if present == item["before"]:
                continue
            if item["before"] is None:
                target.unlink()
                parent = target.parent
                while parent != repo:
                    try:
                        parent.rmdir()
                    except OSError:
                        break
                    parent = parent.parent
            else:
                write_file(target, (directory / f"before-{item['index']}").read_bytes(), item["mode"])

    async def apply(self, mission, candidate, context):
        baseline = self.controller.workspaces.get_baseline_dir(mission.id)
        from app.schemas.candidate import Candidate
        baseline_candidate = next((c for c in await self.store.records(Candidate, mission.id)
                                   if c.id == context["baseline_candidate_id"]), None)
        if not baseline_candidate:
            raise GuildConflict("Captured baseline is missing")
        repo, snapshot, entries = self._validate(mission, candidate, context, baseline_candidate.content_fingerprint)
        directory = self._journal(mission, candidate, repo, baseline, snapshot, entries)
        claimed = False
        try:
            async with self.store.transaction() as db:
                current = await (await db.execute("SELECT status,active_candidate_id FROM missions WHERE id=?", (mission.id,))).fetchone()
                approval = await (await db.execute("SELECT * FROM approvals WHERE mission_id=? AND candidate_id=?", (mission.id, candidate.id))).fetchone()
                if not current or current["status"] != MissionStatus.VERIFIED_AWAITING_APPROVAL.value or current["active_candidate_id"] != candidate.id or not approval or approval["decision"] != "APPROVED" or approval["candidate_fingerprint"] != candidate.content_fingerprint or approval["application_result_id"]:
                    raise GuildConflict("Approval or candidate became stale")
                self._validate(mission, candidate, context, baseline_candidate.content_fingerprint)
                await db.execute("INSERT INTO application_operations VALUES (?,?,?)", (mission.id, candidate.id, str(directory)))
                await db.execute("UPDATE missions SET status='APPLYING',updated_at=? WHERE id=?", (now(), mission.id))
            claimed = True
            for item in entries:
                self._replace_entry(repo, directory, item)
            async with self.store.transaction() as db:
                current = await (await db.execute("SELECT status FROM missions WHERE id=?", (mission.id,))).fetchone()
                if not current or current[0] != MissionStatus.APPLYING.value:
                    raise GuildConflict("Application was interrupted")
                for item in entries:
                    target = safe_path(repo, item["relative"])
                    if (digest(target.read_bytes()) if target.exists() else None) != item["after"]:
                        raise GuildConflict("Applied file failed integrity check")
                await db.execute("UPDATE approvals SET application_result_id=? WHERE mission_id=? AND candidate_id=?", (candidate.id, mission.id, candidate.id))
                candidate.state = CandidateState.APPLIED
                await self.store._save(db, candidate)
                await db.execute("UPDATE missions SET status='APPLIED',updated_at=? WHERE id=?", (now(), mission.id))
                await db.execute("DELETE FROM application_operations WHERE mission_id=?", (mission.id,))
                await self.store._event(db, mission.id, "PATCH_APPLIED", candidate.id)
            claimed = False
            return await self.controller.db.get_mission(mission.id)
        except Exception:
            if claimed:
                await self.recover_pending(mission.id)
            raise
        finally:
            if not claimed:
                shutil.rmtree(directory, ignore_errors=True)

    async def recover_pending(self, mission_id=None):
        finished = []
        async with self.store.transaction() as db:
            rows = await (await db.execute("SELECT * FROM application_operations WHERE (? IS NULL OR mission_id=?)", (mission_id, mission_id))).fetchall()
            for row in rows:
                directory = Path(row["journal_path"])
                try:
                    manifest = self._read_journal(directory)
                    context = await (await db.execute("SELECT context_json FROM guild_context WHERE mission_id=?", (row["mission_id"],))).fetchone()
                    if (not context or manifest["mission_id"] != row["mission_id"] or
                            manifest["candidate_id"] != row["candidate_id"] or
                            manifest["repository"] != json.loads(context[0])["repository"]["path"]):
                        raise GuildConflict("Application journal does not match mission")
                    self._rollback(Path(manifest["repository"]), directory, manifest)
                    await db.execute("UPDATE missions SET status='INTERRUPTED',failure_reason=?,updated_at=? WHERE id=?",
                                     ("Incomplete apply rolled back after interruption", now(), row["mission_id"]))
                    await db.execute("DELETE FROM application_operations WHERE mission_id=?", (row["mission_id"],))
                    await self.store._event(db, row["mission_id"], "APPLY_ROLLED_BACK", row["candidate_id"])
                    finished.append(directory)
                except (OSError, ValueError, KeyError, GuildConflict):
                    await db.execute("UPDATE missions SET status='BLOCKED',failure_reason=?,updated_at=? WHERE id=?",
                                     ("Application recovery needs manual inspection; journal retained", now(), row["mission_id"]))
        for directory in finished:
            shutil.rmtree(directory, ignore_errors=True)
