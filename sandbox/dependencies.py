# pyright: basic
# type: ignore

"""Sandbox FastAPI dependencies — Daytona client, sandbox lookup, workspace, filesystem service."""

import asyncio
import logging

from fastapi import HTTPException, Request, Header
from daytona import CreateSandboxFromSnapshotParams

from config import LANGUAGE, AUTO_STOP_INTERVAL, SNAPSHOT_NAME

logger = logging.getLogger(__name__)

_LABEL_KEY = "app-user-id"


def _create_sandbox(daytona_client, user_id: str):
    """Create a new sandbox for a user, labeled with user_id for lookup."""
    params = CreateSandboxFromSnapshotParams(
        language=LANGUAGE,
        auto_stop_interval=AUTO_STOP_INTERVAL,
        snapshot=SNAPSHOT_NAME,
        labels={_LABEL_KEY: user_id},
    )
    return daytona_client.create(params)


def _find_existing_sandbox(daytona_client, user_id: str):
    """Find an existing running sandbox for user_id via Daytona labels."""
    try:
        from daytona_api_client import SandboxState
        sandbox = daytona_client.find_one(labels={_LABEL_KEY: user_id})
        state = getattr(sandbox, "state", None)
        logger.info(f"Found sandbox for {user_id}: id={sandbox.id}, state={state}")
        if state and state not in (SandboxState.STARTED, SandboxState.STARTING):
            logger.info(f"Sandbox {sandbox.id} not usable (state={state}), skipping")
            return None
        return sandbox
    except Exception as e:
        logger.info(f"No existing sandbox found for {user_id}: {e}")
        return None


def get_daytona(request: Request):
    daytona_client = request.app.state.daytona
    if daytona_client is None:
        raise HTTPException(status_code=503, detail="Daytona not initialized")
    return daytona_client


def get_workspace_manager(request: Request):
    wm = request.app.state.workspace_manager
    if wm is None:
        raise HTTPException(status_code=503, detail="Workspace manager not initialized")
    return wm


async def _get_user_lock(app_state, user_id: str) -> asyncio.Lock:
    """Get or create per-user lock. Uses a registry lock to avoid race on dict write."""
    async with app_state.lock_registry_lock:
        if user_id not in app_state.user_locks:
            app_state.user_locks[user_id] = asyncio.Lock()
        return app_state.user_locks[user_id]


async def resolve_sandbox(app_state, user_id: str):
    """Find or create sandbox for user_id. User A no longer blocks User B."""
    daytona_client = app_state.daytona
    if not daytona_client:
        raise RuntimeError("Daytona not initialized")

    user_lock = await _get_user_lock(app_state, user_id)
    async with user_lock:
        saved = app_state.user_sandboxes.get(user_id)
        if saved:
            sandbox = saved["sandbox"]
        else:
            sandbox = _find_existing_sandbox(daytona_client, user_id)
            if not sandbox:
                sandbox = _create_sandbox(daytona_client, user_id)
                logger.info(f"Created new sandbox: user_id={user_id} | sandbox_id={sandbox.id}")
            app_state.user_sandboxes[user_id] = {
                "sandbox": sandbox,
                "sandbox_id": sandbox.id,
            }

    wm = app_state.workspace_manager
    if wm:
        await wm.initialize(sandbox)
    return sandbox, sandbox.id


async def get_sandbox(
    request: Request,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
):
    """HTTP dependency: 1 user = 1 sandbox."""
    try:
        return await resolve_sandbox(request.app.state, user_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


def get_filesystem_service(request: Request):
    svc = request.app.state.filesystem_service
    if svc is None:
        raise HTTPException(status_code=503, detail="Filesystem service not initialized")
    return svc
