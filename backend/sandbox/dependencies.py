# pyright: basic
# type: ignore

"""Sandbox-specific FastAPI dependencies."""

from fastapi import HTTPException, Request

from config import settings
from shared.dependencies import get_daytona, get_workspace_manager, make_get_sandbox

get_sandbox = make_get_sandbox(settings)


def get_fs_agent(request: Request):
    """Dependency: get FilesystemService from app state."""
    fs_agent = request.app.state.fs_agent
    if fs_agent is None:
        raise HTTPException(status_code=503, detail="Filesystem service not initialized")
    return fs_agent
