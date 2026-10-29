"""Cancellable, bounded, container-only execution for Sentinel."""

import asyncio
import json
import re
import shutil
from pathlib import Path
from time import monotonic
from uuid import uuid4

from app.settings import get_settings


REPORT_MARKER = "\nKAGE_CHECK_REPORT:"


class ContainerExecutor:
    async def available(self):
        if not shutil.which("docker"):
            return False
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "info", "--format", "{{.OSType}}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                stdout, _ = await asyncio.wait_for(process.communicate(), 8)
                return process.returncode == 0 and stdout.strip() == b"linux"
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
        except (OSError, TimeoutError):
            return False

    def command(self, directory: Path, profile: str, name: str, selector: str | None = None):
        if profile not in {"python_pytest", "python_collect", "python_syntax", "python_bandit"}:
            raise ValueError("Unsupported check profile")
        if selector and (
            not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./:\[\], -]*", selector)
            or ".." in selector or selector.startswith(("/", "-")) or ":" in selector.split("::")[0]
        ):
            raise ValueError("Invalid test selector")
        if profile in {"python_pytest", "python_collect"}:
            check = ["python", "/opt/kage/container_check_runner.py"]
            if profile == "python_collect":
                check.append("--collect-only")
            if selector:
                check += ["--", selector]
        elif profile == "python_bandit":
            if selector:
                raise ValueError("Bandit does not accept a test selector")
            check = ["python", "-m", "bandit", "-r", ".", "-f", "json", "-q", "--ignore-nosec"]
        else:
            check = ["python", "-X", "pycache_prefix=/tmp/pycache", "-m", "compileall", "-q", "."]
        settings = get_settings()
        return [
            "docker", "run", "--rm", "--pull", "never", "--name", name,
            "--network", "none", "--read-only", "--user", "1001:1001",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--memory", "512m", "--cpus", "1.0", "--pids-limit", "64",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/workspace",
            "-v", f"{directory.resolve().as_posix()}:/workspace:ro", "-w", "/workspace",
            settings.docker_image,
        ] + check

    async def _drain(self, reader, cap):
        kept = bytearray()
        truncated = False
        while chunk := await reader.read(8192):
            available = max(0, cap - len(kept))
            kept.extend(chunk[:available])
            truncated |= len(chunk) > available
        return kept.decode("utf-8", errors="replace"), truncated

    async def _remove(self, name):
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", name, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                await asyncio.wait_for(process.wait(), 5)
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
        except (OSError, TimeoutError):
            pass

    async def run(self, candidate_dir: Path, check_profile="python_pytest", test_selector=None):
        started = monotonic()
        name = "devpilot-" + uuid4().hex
        result = {"status": "BLOCKED", "exit_code": 126, "duration_ms": 0, "stdout": "", "stderr": "", "command": []}
        try:
            command = self.command(candidate_dir, check_profile, name, test_selector)
        except ValueError:
            return {**result, "status": "DENIED", "stderr": "Unsupported check profile or invalid test selector."}
        result["command"] = command
        result["execution_source"] = "docker"
        if not await self.available():
            result["stderr"] = (
                "BLOCKED: Docker Desktop Linux Engine is unavailable. Start Docker Desktop. "
                "A fallback to host execution is strictly forbidden."
            )
            return result
        process = None
        readers = []
        try:
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            cap = get_settings().max_file_size_bytes
            readers = [asyncio.create_task(self._drain(process.stdout, cap)), asyncio.create_task(self._drain(process.stderr, cap))]
            try:
                await asyncio.wait_for(process.wait(), get_settings().check_timeout_seconds)
                result["exit_code"] = process.returncode
                result["status"] = "SUCCEEDED" if process.returncode == 0 else "FAILED"
            except TimeoutError:
                process.kill()
                await process.wait()
                result.update(status="TIMED_OUT", exit_code=124)
            streams = await asyncio.gather(*readers)
            result["stdout"], result["stderr"] = streams[0][0], streams[1][0]
            result["output_truncated"] = any(item[1] for item in streams)
            if check_profile in {"python_pytest", "python_collect"}:
                if REPORT_MARKER in result["stdout"]:
                    text, _, raw = result["stdout"].rpartition(REPORT_MARKER)
                    result["stdout"] = text
                    try:
                        parsed = json.loads(raw.strip())
                        if isinstance(parsed, dict) and parsed.get("exitcode") == result["exit_code"]:
                            result["report"] = parsed
                    except ValueError:
                        pass
            elif check_profile == "python_bandit":
                try:
                    raw = json.loads(result["stdout"])
                    result["report"] = {"results": [{key: item.get(key) for key in (
                        "test_id", "issue_severity", "issue_confidence", "filename", "line_number", "issue_text")}
                        for item in raw.get("results", [])[:100]], "errors": raw.get("errors", [])[:10],
                        "truncated": len(raw.get("results", [])) > 100}
                    result["stdout"] = f"Bandit reported {len(raw.get('results', []))} findings."
                except ValueError:
                    pass
        except OSError:
            result["stderr"] = "Container launch failed. Check Docker and the prebuilt check image."
        finally:
            if process and process.returncode is None:
                process.kill()
                await process.wait()
            for reader in readers:
                if not reader.done():
                    reader.cancel()
            if readers:
                await asyncio.gather(*readers, return_exceptions=True)
            await asyncio.shield(self._remove(name))
            result["duration_ms"] = int((monotonic() - started) * 1000)
        return result
