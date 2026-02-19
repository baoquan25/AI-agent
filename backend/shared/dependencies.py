# pyright: basic
# type: ignore

"""Shared FastAPI dependency injection helpers."""

import logging

from fastapi import HTTPException, Request, Header
from daytona import CreateSandboxFromSnapshotParams

logger = logging.getLogger(__name__)


def _create_sandbox(daytona_client, settings, user_id: str):
    """Create a new sandbox for a user."""
    params = CreateSandboxFromSnapshotParams(
        language=settings.LANGUAGE,
        auto_stop_interval=settings.AUTO_STOP_INTERVAL,
        snapshot=settings.SNAPSHOT_NAME,
    )
    return daytona_client.create(params)


def get_daytona(request: Request):
    daytona_client = request.app.state.daytona
    if daytona_client is None:
        raise HTTPException(status_code=503, detail="Daytona not initialized")
    return daytona_client


def get_workspace_manager(request: Request):
    """Dependency: get WorkspaceManager from app state."""
    wm = request.app.state.workspace_manager
    if wm is None:
        raise HTTPException(status_code=503, detail="Workspace manager not initialized")
    return wm


def make_get_sandbox(settings):
    """Factory: creates a get_sandbox dependency bound to a specific settings instance."""

    async def get_sandbox(
        request: Request,
        user_id: str = Header(default="default_user", alias="X-User-ID"),
    ):
        """
        Dependency: 1 user = 1 sandbox.
        Creates new sandbox if user doesn't have one yet.
        """
        daytona_client = get_daytona(request)

        async with request.app.state.user_lock:
            saved = request.app.state.user_sandboxes.get(user_id)

            if saved:
                return saved["sandbox"], saved["sandbox_id"]

            sandbox = _create_sandbox(daytona_client, settings, user_id)
            sandbox_id = sandbox.id

            request.app.state.user_sandboxes[user_id] = {
                "sandbox": sandbox,
                "sandbox_id": sandbox_id,
            }

            logger.info(f"Created sandbox: user_id={user_id} | sandbox_id={sandbox_id}")
            return sandbox, sandbox_id

    return get_sandbox
