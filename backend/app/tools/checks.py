import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from app.settings import get_settings


def is_docker_available() -> bool:
    """Checks whether Docker CLI exists and the daemon is reachable."""
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


def run_check(
    candidate_dir: Path,
    check_profile: str = "python_pytest",
    test_selector: str | None = None,
) -> dict[str, Any]:
    """
    Executes approved check profile in a restricted Linux container.
    STRICT PS-001 INVARIANT: If container isolation is unavailable,
    execution is BLOCKED. Never silently fall back to running on the host.
    """
    settings = get_settings()

    if not is_docker_available():
        return {
            "status": "BLOCKED",
            "exit_code": 126,
            "duration_ms": 0,
            "stdout": "",
            "stderr": (
                "BLOCKED: Docker Desktop Linux Engine is unavailable. "
                "PS-001 requires restricted container isolation for repository execution; "
                "silent fallback to host execution is strictly forbidden."
            ),
            "command": ["docker", "run", "--network", "none", "..."],
        }

    # Validate test_selector to prevent flag injection
    safe_selector = []
    if test_selector:
        # Sanitize selector: only alphanumeric, underscores, slashes, dots, and colons
        cleaned = "".join(c for c in test_selector if c.isalnum() or c in "/_.-:")
        if cleaned:
            safe_selector.append(cleaned)

    # Approved command profiles
    if check_profile == "python_pytest":
        cmd_in_container = ["pytest", "-q"] + safe_selector
    elif check_profile == "python_syntax":
        cmd_in_container = ["python", "-m", "compileall", "."]
    else:
        return {
            "status": "DENIED",
            "exit_code": 1,
            "duration_ms": 0,
            "stdout": "",
            "stderr": f"Disallowed check profile: '{check_profile}'. Only approved profiles may run.",
            "command": [],
        }

    abs_cand_dir = str(candidate_dir.resolve()).replace("\\", "/")

    docker_args = [
        "docker", "run", "--rm",
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--memory", "512m",
        "--cpus", "1.0",
        "--pids-limit", "64",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "-v", f"{abs_cand_dir}:/workspace:ro",
        "-w", "/workspace",
        settings.docker_image,
    ] + cmd_in_container

    start_time = time.perf_counter()
    try:
        res = subprocess.run(
            docker_args,
            capture_output=True,
            text=True,
            timeout=float(settings.check_timeout_seconds),
        )
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "status": "SUCCEEDED" if res.returncode == 0 else "FAILED",
            "exit_code": res.returncode,
            "duration_ms": duration_ms,
            "stdout": res.stdout[: settings.max_file_size_bytes],
            "stderr": res.stderr[: settings.max_file_size_bytes],
            "command": docker_args,
        }
    except subprocess.TimeoutExpired:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "status": "TIMED_OUT",
            "exit_code": 124,
            "duration_ms": duration_ms,
            "stdout": "",
            "stderr": f"Check execution timed out after {settings.check_timeout_seconds} seconds.",
            "command": docker_args,
        }
    except Exception as e:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "status": "FAILED",
            "exit_code": 1,
            "duration_ms": duration_ms,
            "stdout": "",
            "stderr": f"Container launch error: {str(e)}",
            "command": docker_args,
        }

