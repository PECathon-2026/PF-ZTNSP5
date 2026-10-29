"""Real-model M3 exit check: python -m app.agents.smoke (from backend/)."""

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.model_adapter import ModelAdapter
from app.agents.samurai import SamuraiRunner
from app.services.repository_service import get_repository_service
from app.services.workspace_service import get_workspace_service
from app.settings import get_settings
from app.storage.artifacts import get_artifact_storage


async def smoke() -> int:
    settings = get_settings()
    if not settings.model_configured:
        print("BLOCKED: configure the selected provider's endpoint, API key, and model/deployment in backend/.env.")
        return 2
    original = 'def greeting():\n    return "hello"\n'
    with TemporaryDirectory(prefix="devpilot-m3-") as directory:
        repo = Path(directory)
        (repo / "greeting.py").write_text(original, encoding="utf-8")
        repositories = get_repository_service()
        record = repositories.connect_repository(str(repo))
        try:
            async with ModelAdapter() as adapter:
                result = await SamuraiRunner(adapter).run(
                    record["repository_id"],
                    'Change greeting.py so greeting() returns "hello, DevPilot". '
                    "Preserve the function signature. Read first, apply a targeted patch, "
                    "read back, inspect the diff, then submit_candidate.",
                )
            checks = {"original_unchanged": (repo / "greeting.py").read_text(encoding="utf-8") == original}
            if result.candidate:
                candidate_dir = get_workspace_service().get_candidate_dir(result.mission_id, result.candidate.id)
                actual = (candidate_dir / "greeting.py").read_text(encoding="utf-8")
                # Source comparison only: never import/execute generated repository code on the host.
                checks["expected_source_change"] = actual == original.replace('"hello"', '"hello, DevPilot"')
                checks["candidate_fingerprint_matches"] = (
                    get_workspace_service()._compute_dir_hash(candidate_dir)[0]
                    == result.candidate.content_fingerprint
                )
                checks["only_requested_file_changed"] = result.candidate.changed_files == ["greeting.py"]
            succeeded = result.status == "CANDIDATE_READY" and len(checks) == 4 and all(checks.values())
            report = {
                "milestone": "M3", "real_model": True, "provider": settings.model_provider,
                "model": settings.configured_model_name,
                "exit_check_passed": succeeded, "checks": checks, "run": result.model_dump(mode="json"),
                "verification_scope": "Source bytes and tool trajectory only; no behavioral tests executed.",
            }
            serialized = json.dumps(report, indent=2).replace(settings.model_api_key, "[REDACTED]")
            artifact_id, _ = get_artifact_storage().save_artifact(result.mission_id, "m3-smoke.json", serialized)
            print(serialized)
            print(f"Evidence: {settings.artifacts_dir / result.mission_id / (artifact_id + '_m3-smoke.json')}")
            return 0 if succeeded else 1
        finally:
            repositories._repositories.pop(record["repository_id"], None)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(smoke()))
