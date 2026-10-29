"""Synchronous compatibility entry point; Sentinel awaits ContainerExecutor directly."""

import asyncio
from pathlib import Path
from app.services.execution_service import ContainerExecutor


def is_docker_available() -> bool:
    return asyncio.run(ContainerExecutor().available())


def run_check(candidate_dir: Path, check_profile="python_pytest", test_selector=None):
    return asyncio.run(ContainerExecutor().run(candidate_dir, check_profile, test_selector))
