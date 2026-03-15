import asyncio
import logging
import time

from fastapi import HTTPException, Request, Header
from daytona import CreateSandboxFromSnapshotParams
from daytona_api_client import SandboxState

from config import settings

logger = logging.getLogger(__name__)

_LABEL_KEY = "user-id"
_STARTING_STATES: frozenset = frozenset({SandboxState.STARTING})
_USABLE_STATES: frozenset = frozenset({SandboxState.STARTED})

# ── Sandbox cache ────────────────────────────────────────────────────
# Cache sandbox objects per user_id to avoid calling find_one on every
# single HTTP request.  Each entry expires after _SANDBOX_CACHE_TTL seconds.

_SANDBOX_CACHE_TTL = 300  # 5 minutes
_sandbox_cache: dict[str, tuple[object, float]] = {}
_sandbox_cache_lock = asyncio.Lock()


def _ensure_sandbox_started(sandbox, timeout: float = 60) -> bool:
    """Wait for sandbox to reach STARTED if still starting. Returns True if ready."""
    state = getattr(sandbox, "state", None)
    if state in _USABLE_STATES:
        return True
    if state in _STARTING_STATES:
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
        language=settings.LANGUAGE,
        auto_stop_interval=settings.AUTO_STOP_INTERVAL,
        snapshot=settings.SNAPSHOT_NAME,
        labels={"user-id": user_id},
    )
    return daytona_client.create(params)


def _find_existing_sandbox(daytona_client, user_id: str):
    """Find sandbox by label; if STARTING, wait for STARTED. Returns None if not found or not usable."""
    try:
        sandbox = daytona_client.find_one(labels={_LABEL_KEY: user_id})
        state = getattr(sandbox, "state", None)

        if state in _USABLE_STATES:
            return sandbox
        if state in _STARTING_STATES:
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

    # ── Check cache first ─────────────────────────────────────────────
    # Do NOT call wm.initialize here — filesystem_service methods already
    # call it internally, and it has its own TTL cache.  Calling it here
    # adds a redundant SDK round-trip on every request.
    now = time.monotonic()
    async with _sandbox_cache_lock:
        cached = _sandbox_cache.get(user_id)
        if cached:
            sandbox, ts = cached
            if now - ts < _SANDBOX_CACHE_TTL:
                state = getattr(sandbox, "state", None)
                if state in _USABLE_STATES:
                    return sandbox, sandbox.id
                else:
                    _sandbox_cache.pop(user_id, None)

    # ── Cache miss — resolve via SDK ──────────────────────────────────
    t0 = time.monotonic()
    sandbox = await asyncio.to_thread(_find_existing_sandbox, daytona_client, user_id)
    t1 = time.monotonic()
    if not sandbox:
        try:
            sandbox = await asyncio.to_thread(_create_sandbox, daytona_client, user_id)
        except Exception as e:
            logger.warning("Create failed for %s (%s), retrying find_one", user_id, e)
            sandbox = await asyncio.to_thread(_find_existing_sandbox, daytona_client, user_id)
            if not sandbox:
                raise RuntimeError(f"Failed to get or create sandbox: {e}") from e
    t2 = time.monotonic()
    logger.info(
        "resolve_sandbox MISS user=%s find=%.0fms create=%.0fms",
        user_id, (t1-t0)*1000, (t2-t1)*1000,
    )

    wm = getattr(app_state, "workspace_manager", None)
    if wm:
        await wm.initialize(sandbox)

    # ── Store in cache ────────────────────────────────────────────────
    async with _sandbox_cache_lock:
        _sandbox_cache[user_id] = (sandbox, time.monotonic())
        # Prune if cache grows too large
        if len(_sandbox_cache) > 10_000:
            cutoff = time.monotonic() - _SANDBOX_CACHE_TTL
            expired = [k for k, (_, ts) in _sandbox_cache.items() if ts < cutoff]
            for k in expired:
                _sandbox_cache.pop(k, None)

    return sandbox, sandbox.id


def invalidate_sandbox_cache(user_id: str) -> None:
    """Remove a user's sandbox from the cache (e.g. after stop/delete)."""
    _sandbox_cache.pop(user_id, None)


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
    """HTTP dependency: resolve sandbox per request.
    Uses in-memory cache to avoid calling find_one on every request."""
    try:
        return await resolve_sandbox(request.app.state, user_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


def get_filesystem_service(request: Request):
    svc = request.app.state.filesystem_service
    if svc is None:
        raise HTTPException(status_code=503, detail="Filesystem service not initialized")
    return svc
