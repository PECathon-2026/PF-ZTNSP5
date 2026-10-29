from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from app.schemas.common import PreflightResult
from app.security.paths import PathSecurityError
from app.services.repository_service import get_repository_service
from app.services.workspace_service import get_workspace_service

router = APIRouter(tags=["Repositories"])


class ConnectRepositoryRequest(BaseModel):
    path: str = Field(..., description="Absolute or relative local directory path")


class RepositoryConnectResponse(BaseModel):
    repository_id: str
    name: str
    path: str
    fingerprint: str
    preflight: PreflightResult


class FileContentResponse(BaseModel):
    file_path: str
    content: str


@router.post(
    "/api/repositories/connect",
    response_model=RepositoryConnectResponse,
    status_code=status.HTTP_200_OK,
)
async def connect_repository(request: ConnectRepositoryRequest) -> RepositoryConnectResponse:
    """
    Registers and preflights a local folder.
    Builds the approved inclusion manifest and runs baseline environment checks.
    """
    repo_service = get_repository_service()
    try:
        record = repo_service.connect_repository(request.path)
        return RepositoryConnectResponse(
            repository_id=record["repository_id"],
            name=record["name"],
            path=record["path"],
            fingerprint=record["fingerprint"],
            preflight=record["preflight"],
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (NotADirectoryError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except PathSecurityError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/api/repositories/{repository_id}/tree", response_model=list[str])
async def get_repository_tree(repository_id: str) -> list[str]:
    """Returns the approved, bounded file tree for a registered repository."""
    repo_service = get_repository_service()
    try:
        return repo_service.get_file_tree(repository_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/api/repositories/{repository_id}/file", response_model=FileContentResponse)
async def read_repository_file(
    repository_id: str,
    path: str = Query(..., description="Relative file path within repository"),
) -> FileContentResponse:
    """Reads file text from baseline repository for the IDE code viewer."""
    repo_service = get_repository_service()
    try:
        content = repo_service.read_file_content(repository_id, path)
        return FileContentResponse(file_path=path, content=content)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PathSecurityError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))


@router.get("/api/missions/{mission_id}/candidates/{candidate_id}/diff")
async def get_candidate_diff(
    mission_id: str,
    candidate_id: str,
    repository_id: str = Query(..., description="Repository ID to diff against"),
):
    """Returns structured diff between original repository and frozen candidate snapshot."""
    ws_service = get_workspace_service()
    try:
        return ws_service.generate_candidate_diff(mission_id, repository_id, candidate_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/api/missions/{mission_id}/candidates/{candidate_id}/file", response_model=FileContentResponse)
async def read_candidate_file(
    mission_id: str,
    candidate_id: str,
    path: str = Query(..., description="Relative file path within candidate snapshot"),
) -> FileContentResponse:
    """Reads file text from a frozen candidate snapshot for the IDE code viewer."""
    ws_service = get_workspace_service()
    cand_dir = ws_service.get_candidate_dir(mission_id, candidate_id)
    if not cand_dir.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate snapshot not found.")

    from app.security.paths import canonicalize_and_validate_path
    try:
        validated_file = canonicalize_and_validate_path(cand_dir, path)
        if not validated_file.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File '{path}' not found in candidate.")
        content = validated_file.read_text(encoding="utf-8", errors="replace")
        return FileContentResponse(file_path=path, content=content)
    except PathSecurityError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

