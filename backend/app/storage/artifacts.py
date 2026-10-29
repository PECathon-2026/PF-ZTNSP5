import hashlib
from pathlib import Path
from app.settings import get_settings
from app.security.redaction import redact_secrets


class ArtifactStorage:
    """Manages secure, bounded file artifacts outside repository workspaces."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or get_settings().artifacts_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_size = get_settings().max_file_size_bytes

    def save_artifact(self, mission_id: str, artifact_name: str, content: str | bytes) -> tuple[str, str]:
        """
        Saves content to a mission-specific artifact file.
        Returns (artifact_id, sha256_fingerprint).
        """
        if isinstance(content, str):
            data = redact_secrets(content).encode("utf-8")
        else:
            data = content

        if len(data) > self.max_size:
            # Truncate content safely with notice
            notice = f"\n... [TRUNCATED - Output exceeded {self.max_size} bytes limit]".encode("utf-8")
            data = data[: self.max_size - len(notice)] + notice

        fingerprint = hashlib.sha256(data).hexdigest()
        artifact_id = f"art-{fingerprint[:12]}"

        mission_dir = self.base_dir / mission_id
        mission_dir.mkdir(parents=True, exist_ok=True)

        normalized_name = artifact_name.replace("/", "_").replace("\\", "_")
        safe_filename = f"{artifact_id}_{normalized_name}"
        file_path = mission_dir / safe_filename

        with open(file_path, "wb") as f:
            f.write(data)

        return artifact_id, fingerprint

    def read_artifact(self, mission_id: str, artifact_id: str) -> str | None:
        """Reads text content of an artifact by ID."""
        mission_dir = self.base_dir / mission_id
        if not mission_dir.exists():
            return None

        # Locate artifact file by prefix
        matches = list(mission_dir.glob(f"{artifact_id}_*"))
        if not matches:
            return None

        with open(matches[0], "r", encoding="utf-8", errors="replace") as f:
            return f.read()


_artifacts_instance: ArtifactStorage | None = None


def get_artifact_storage() -> ArtifactStorage:
    global _artifacts_instance
    if _artifacts_instance is None:
        _artifacts_instance = ArtifactStorage()
    return _artifacts_instance

