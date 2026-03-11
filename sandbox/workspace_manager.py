from __future__ import annotations

import asyncio
import os
import time
import logging

logger = logging.getLogger(__name__)

_INIT_TTL = 60  # seconds — skip create_folder if workspace was confirmed recently


class WorkspaceManager:

    SDK_PATH = "workspace"

    def __init__(self, base_path: str = "/home/daytona/workspace"):
        self.base_path = base_path
        self._init_cache: dict[str, float] = {}

    def get_path(self, relative_path: str = "") -> str:
        """Resolve a relative path inside the workspace to an absolute path."""
        if relative_path:
            return f"{self.base_path}/{relative_path.lstrip('/')}"
        return self.base_path

    def wrap_code(self, code: str, file_path: str) -> str:
        """Wrap code to run in the directory of file_path (for /run with file_path)."""
        if not file_path:
            return code
        dir_part = os.path.dirname(file_path)
        if not dir_part:
            return code
        abs_dir = f"{self.base_path}/{dir_part}".replace("//", "/")
        return f"import os\nos.makedirs({repr(abs_dir)}, exist_ok=True)\nos.chdir({repr(abs_dir)})\n{code}"

    async def initialize(self, sandbox, force: bool = False) -> bool:
        """
        Ensure workspace directory exists. Idempotent (toolbox uses MkdirAll).
        Skips the API call if workspace was confirmed within the last _INIT_TTL seconds.
        Retries up to 3 times with backoff on any error.
        """
        sandbox_id = getattr(sandbox, "id", None)
        now = time.monotonic()

        if not force and sandbox_id and self._init_cache.get(sandbox_id, 0) + _INIT_TTL > now:
            return True

        last_error = None
        for attempt in range(1, 4):
            try:
                t0 = time.monotonic()
                await asyncio.to_thread(sandbox.fs.create_folder, self.SDK_PATH, "755")
                logger.info("wm.initialize sdk=%.0fms (attempt %d)", (time.monotonic()-t0)*1000, attempt)
                if sandbox_id:
                    self._init_cache[sandbox_id] = now
                    if len(self._init_cache) > 10_000:
                        cutoff = now - _INIT_TTL * 2
                        self._init_cache = {k: v for k, v in self._init_cache.items() if v > cutoff}
                return True
            except Exception as e:
                last_error = e
                if attempt < 3:
                    wait = attempt * 2
                    logger.warning(
                        "Workspace init attempt %s/3 failed: %s — retrying in %ss",
                        attempt, str(e)[:200], wait,
                    )
                    await asyncio.sleep(wait)

        logger.error(
            "Failed to initialize workspace: %s (sandbox=%s state=%s)",
            last_error, sandbox_id, getattr(sandbox, "state", "unknown"),
        )
        return False

    def invalidate(self, sandbox) -> None:
        """Invalidate TTL cache for this sandbox, forcing re-init on next request."""
        sandbox_id = getattr(sandbox, "id", None)
        if sandbox_id:
            self._init_cache.pop(sandbox_id, None)

    async def cleanup(self, sandbox) -> bool:
        """Delete the entire workspace (SDK path 'workspace')."""
        sandbox_id = getattr(sandbox, "id", None)
        try:
            await asyncio.to_thread(sandbox.fs.delete_file, self.SDK_PATH, recursive=True)
            self.invalidate(sandbox)
            return True
        except Exception as e:
            logger.error("Workspace cleanup failed: %s", e)
            return False
