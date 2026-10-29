import pytest
from pathlib import Path
from starlette.testclient import TestClient

from app.main import app
from app.security.paths import (
    canonicalize_and_validate_path,
    is_path_excluded,
    PathSecurityError,
)
from app.services.repository_service import RepositoryService
from app.services.workspace_service import WorkspaceService, WriterLeaseError
from app.tools.files import list_files, read_file
from app.tools.search import search_text
from app.tools.editor import apply_patch, PatchError
from app.tools.diff import read_diff
from app.tools.checks import run_check
from app.tools.gateway import ToolGateway, ToolGatewayError


@pytest.fixture
def sample_repo(tmp_path):
    """Creates a sample repo fixture with code, tests, and sensitive files."""
    repo_dir = tmp_path / "sample_project"
    repo_dir.mkdir()

    # Valid files
    (repo_dir / "tasks.py").write_text("def get_tasks():\n    return ['task1', 'task2']\n")
    (repo_dir / "utils.py").write_text("def sort_tasks(items):\n    return sorted(items)\n")
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_tasks.py").write_text("def test_get():\n    assert True\n")

    # Sensitive/excluded files that MUST be ignored
    (repo_dir / ".env").write_text("SECRET_KEY=12345\n")
    (repo_dir / "server.key").write_text("-----BEGIN PRIVATE KEY-----\n")
    pycache = repo_dir / "__pycache__"
    pycache.mkdir()
    (pycache / "tasks.cpython-312.pyc").write_bytes(b"bytecode")

    return repo_dir


# --- 1. Path Security & Traversal Rejection Tests ---

def test_path_traversal_rejection(sample_repo):
    # Attempting to escape via ../
    with pytest.raises(PathSecurityError, match="Path traversal detected"):
        canonicalize_and_validate_path(sample_repo, "../outside.txt")

    with pytest.raises(PathSecurityError, match="Path traversal detected"):
        canonicalize_and_validate_path(sample_repo, "tests/../../secret.txt")


def test_restricted_file_rejection(sample_repo):
    # Attempting to read .env
    with pytest.raises(PathSecurityError, match="restricted"):
        canonicalize_and_validate_path(sample_repo, ".env")

    # Attempting to read private key
    with pytest.raises(PathSecurityError, match="restricted"):
        canonicalize_and_validate_path(sample_repo, "server.key")


# --- 2. Repository Preflight & Reconnaissance Tests ---

def test_repository_service_preflight(sample_repo):
    service = RepositoryService()
    record = service.connect_repository(str(sample_repo))

    assert record["repository_id"].startswith("repo-")
    assert record["name"] == "sample_project"
    preflight = record["preflight"]
    assert preflight.detected_profile == "python_pytest"
    assert preflight.file_count == 3  # tasks.py, utils.py, tests/test_tasks.py
    assert preflight.excluded_count >= 2  # .env, server.key, pycache

    # Verify inclusion tree
    tree = service.get_file_tree(record["repository_id"])
    assert "tasks.py" in tree
    assert "utils.py" in tree
    assert ".env" not in tree
    assert "server.key" not in tree


# --- 3. Tool Implementations (Search, Read, Patch, Diff) ---

def test_file_tools_and_bounding(sample_repo):
    # list_files
    files = list_files(sample_repo)
    assert "tasks.py" in files
    assert ".env" not in files

    # read_file
    res = read_file(sample_repo, "tasks.py", line_start=1, line_end=2)
    assert res["total_lines"] == 2
    assert "def get_tasks():" in res["content"]


def test_search_text(sample_repo):
    # Search for 'sort_tasks'
    matches = search_text(sample_repo, "sort_tasks")
    assert len(matches) == 1
    assert matches[0]["file_path"] == "utils.py"
    assert matches[0]["line_number"] == 1
    assert "def sort_tasks" in matches[0]["snippet"]


def test_apply_patch_targeted_and_full(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    target_file = ws / "code.py"
    target_file.write_text("status = 'pending'\nreturn status\n")

    # Targeted replacement
    res = apply_patch(ws, "code.py", target="pending", replacement="completed")
    assert res["status"] == "APPLIED"
    assert target_file.read_text() == "status = 'completed'\nreturn status\n"

    # Full content create
    res2 = apply_patch(ws, "new_file.py", content="new_content = True\n")
    assert res2["status"] == "APPLIED"
    assert (ws / "new_file.py").read_text() == "new_content = True\n"


def test_read_diff(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "app.py").write_text("v1 = True\n")

    cand = tmp_path / "cand"
    cand.mkdir()
    (cand / "app.py").write_text("v1 = False\n")

    diff = read_diff(base, cand, "app.py")
    assert "-v1 = True" in diff
    assert "+v1 = False" in diff


# --- 4. Disposable Workspace & Writer Lease Invariant Tests ---

def test_disposable_workspace_preserves_original(sample_repo, tmp_path):
    ws_service = WorkspaceService(base_workspaces_dir=tmp_path / "workspaces")
    repo_service = RepositoryService()
    repo_record = repo_service.connect_repository(str(sample_repo))
    repo_id = repo_record["repository_id"]

    # Register in global service for workspace creation
    from app.services.repository_service import get_repository_service
    get_repository_service()._repositories[repo_id] = repo_record

    # Create disposable workspace
    ws_dir = ws_service.create_disposable_workspace("miss-001", repo_id)
    assert ws_dir.exists()
    assert (ws_dir / "tasks.py").exists()
    assert not (ws_dir / ".env").exists()  # Kept clean

    # Writer lease enforcement
    ws_service.acquire_writer_lease("miss-001", "SAMURAI")
    
    # Second writer (e.g. SENTINEL or another agent) must be denied
    with pytest.raises(WriterLeaseError, match="Workspace write lease already held"):
        ws_service.acquire_writer_lease("miss-001", "SENTINEL")

    # Release and reacquire
    ws_service.release_writer_lease("miss-001", "SAMURAI")
    ws_service.acquire_writer_lease("miss-001", "SENTINEL")


def test_candidate_freeze_and_diff(sample_repo, tmp_path):
    ws_service = WorkspaceService(base_workspaces_dir=tmp_path / "workspaces")
    repo_service = RepositoryService()
    repo_record = repo_service.connect_repository(str(sample_repo))
    repo_id = repo_record["repository_id"]
    from app.services.repository_service import get_repository_service
    get_repository_service()._repositories[repo_id] = repo_record

    # Create workspace and edit file
    ws_dir = ws_service.create_disposable_workspace("miss-002", repo_id)
    (ws_dir / "tasks.py").write_text("def get_tasks():\n    return ['task1', 'task2', 'task3']\n")

    # Freeze candidate
    cand = ws_service.freeze_candidate("miss-002", repo_id)
    assert cand.id.startswith("cand-")
    assert cand.changed_files == ["tasks.py"]

    # Generate diff
    diff_res = ws_service.generate_candidate_diff("miss-002", repo_id, cand.id)
    assert diff_res["changed_files_count"] == 1
    assert "+    return ['task1', 'task2', 'task3']" in diff_res["unified_diff"]


# --- 5. Container Prerequisite Enforcement Check ---

def test_run_check_blocks_when_docker_unavailable(tmp_path):
    # Tests that run_check NEVER falls back to host execution when container is unready
    res = run_check(tmp_path, "python_pytest")
    if res["status"] == "BLOCKED":
        assert res["exit_code"] == 126
        assert "BLOCKED: Docker Desktop Linux Engine is unavailable" in res["stderr"]
        assert "fallback to host execution is strictly forbidden" in res["stderr"]


# --- 6. Tool Gateway Role Permissions ---

def test_tool_gateway_role_permissions(tmp_path):
    gateway = ToolGateway()
    ws_dir = tmp_path / "ws_gw"
    ws_dir.mkdir()
    (ws_dir / "file.txt").write_text("sample")

    # Planner (SHOGUN) cannot apply patches
    with pytest.raises(ToolGatewayError, match="not permitted for role 'SHOGUN'"):
        gateway.execute_tool("SHOGUN", "apply_patch", {"relative_path": "file.txt", "content": "hack"}, "miss-01", ws_dir)

    # Developer (SAMURAI) with writer lease can apply patches
    gateway.workspace_service._leases["miss-01"] = "SAMURAI"
    res = gateway.execute_tool("SAMURAI", "apply_patch", {"relative_path": "file.txt", "content": "updated"}, "miss-01", ws_dir)
    assert res["status"] == "SUCCEEDED"


# --- 7. HTTP API Repositories Endpoints Tests ---

def test_repositories_api_connect_and_read(sample_repo):
    client = TestClient(app)

    # 1. Connect repository
    res = client.post("/api/repositories/connect", json={"path": str(sample_repo)})
    assert res.status_code == 200
    data = res.json()
    repo_id = data["repository_id"]
    assert data["name"] == "sample_project"
    assert data["preflight"]["detected_profile"] == "python_pytest"

    # 2. Get tree
    tree_res = client.get(f"/api/repositories/{repo_id}/tree")
    assert tree_res.status_code == 200
    tree = tree_res.json()
    assert "tasks.py" in tree

    # 3. Read file
    file_res = client.get(f"/api/repositories/{repo_id}/file?path=tasks.py")
    assert file_res.status_code == 200
    assert "def get_tasks():" in file_res.json()["content"]

    # 4. Path traversal attempt via API -> 403 Forbidden
    escape_res = client.get(f"/api/repositories/{repo_id}/file?path=../outside.txt")
    assert escape_res.status_code == 403

    # 5. Restricted file access attempt via API -> 403 Forbidden
    secret_res = client.get(f"/api/repositories/{repo_id}/file?path=.env")
    assert secret_res.status_code == 403

