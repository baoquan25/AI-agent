from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="", tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    daytona_initialized: bool
    workspace_manager_initialized: bool
    filesystem_service_initialized: bool


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    daytona_initialized = request.app.state.daytona is not None
    workspace_manager_initialized = request.app.state.workspace_manager is not None
    filesystem_service_initialized = request.app.state.filesystem_service is not None
    status = (
        "ok"
        if daytona_initialized and workspace_manager_initialized and filesystem_service_initialized
        else "degraded"
    )
    return HealthResponse(
        status=status,
        service="sandbox",
        daytona_initialized=daytona_initialized,
        workspace_manager_initialized=workspace_manager_initialized,
        filesystem_service_initialized=filesystem_service_initialized,
    )
