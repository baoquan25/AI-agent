import asyncio
import logging

from fastapi import HTTPException, Request, Header
from daytona import CreateSandboxFromSnapshotParams

from config import LANGUAGE, AUTO_STOP_INTERVAL, SNAPSHOT_NAME

logger = logging.getLogger(__name__)

_LABEL_KEY = "app-user-id"

_STARTING_STATES = None
_USABLE_STATES = None


def _get_sandbox_states():
    global _STARTING_STATES, _USABLE_STATES
    if _STARTING_STATES is None:
        from daytona_api_client import SandboxState
        _STARTING_STATES = {SandboxState.STARTING}
        _USABLE_STATES = {SandboxState.STARTED}
    return _STARTING_STATES, _USABLE_STATES


def _ensure_sandbox_started(sandbox, timeout: float = 60) -> bool:
    """Wait for sandbox to reach STARTED if still starting. Returns True if ready."""
    _, usable = _get_sandbox_states()
    starting, _ = _get_sandbox_states()
    state = getattr(sandbox, "state", None)
    if state in usable:
        return True
    if state in starting:
        try:
            sandbox.wait_for_sandbox_start(timeout=timeout)
            return True
        except Exception as e:
            logger.error("Sandbox %s failed to start: %s", sandbox.id, e)
            return False
    return False


def _create_sandbox(daytona_client, user_id: str):
    """Create a new sandbox for user_id. SDK create() waits for start internally."""
    params = CreateSandboxFromSnapshotParams(
        language=LANGUAGE,
        auto_stop_interval=AUTO_STOP_INTERVAL,
        snapshot=SNAPSHOT_NAME,
        labels={_LABEL_KEY: user_id},
    )
    return daytona_client.create(params)


def _find_existing_sandbox(daytona_client, user_id: str):
    """Find sandbox by label; if STARTING, wait for STARTED. Returns None if not found or not usable."""
    try:
        starting, usable = _get_sandbox_states()
        sandbox = daytona_client.find_one(labels={_LABEL_KEY: user_id})
        state = getattr(sandbox, "state", None)

        if state in usable:
            return sandbox
        if state in starting:
            if _ensure_sandbox_started(sandbox):
                return sandbox
            logger.warning("Sandbox %s did not reach STARTED in time", sandbox.id)
            return None
        return None
    except Exception as e:
        return None


async def resolve_sandbox(app_state, user_id: str):
    daytona_client = app_state.daytona
    if not daytona_client:
        raise RuntimeError("Daytona not initialized")

    sandbox = await asyncio.to_thread(_find_existing_sandbox, daytona_client, user_id)
    if not sandbox:
        try:
            sandbox = await asyncio.to_thread(_create_sandbox, daytona_client, user_id)
        except Exception as e:
            logger.warning("Create failed for %s (%s), retrying find_one", user_id, e)
            sandbox = await asyncio.to_thread(_find_existing_sandbox, daytona_client, user_id)
            if not sandbox:
                raise RuntimeError(f"Failed to get or create sandbox: {e}") from e

    wm = getattr(app_state, "workspace_manager", None)
    if wm:
        await wm.initialize(sandbox)
    return sandbox, sandbox.id


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


async def get_sandbox(
    request: Request,
    user_id: str = Header(default="default_user", alias="X-User-ID"),
):
    """HTTP dependency: resolve sandbox per request (stateless)."""
    try:
        return await resolve_sandbox(request.app.state, user_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


def get_filesystem_service(request: Request):
    svc = request.app.state.filesystem_service
    if svc is None:
        raise HTTPException(status_code=503, detail="Filesystem service not initialized")
    return svc
