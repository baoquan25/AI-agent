# file_watcher.py
#
# API-driven file change notification — no local disk watching.
#
# How it works:
#   - File mutations (write/create/delete/rename) in routers/file_system.py
#     call emit_change() directly after they succeed.
#   - emit_change() feeds the EventBroadcaster which coalesces, throttles,
#     invalidates cache in batch, and pushes events to WS /fs/watch clients.
#
# This avoids watchdog (a local-disk watcher) which is useless when the
# actual files live on a remote Daytona sandbox (accessed via SDK).

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from services.event_broadcaster import broadcaster as _default_broadcaster, ChangeType

logger = logging.getLogger("daytona-api")


class WorkspaceCacheWatcher:
    """Thin adapter that wires the FileCache batch-invalidation callback
    into the EventBroadcaster so cache entries are cleared whenever the
    broadcaster flushes a coalesced batch of file-change events.

    File changes are injected externally via emit_change() — called by
    the API mutation endpoints (write / create / delete / rename).
    There is no background thread and no local filesystem watching.
    """

    def __init__(self, cache, workspace_path: str = "", broadcaster=None) -> None:
        self._cache = cache
        self._broadcaster = broadcaster or _default_broadcaster
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> bool:
        self._loop = loop
        self._broadcaster.set_loop(loop)
        self._broadcaster.set_cache_invalidator(self._invalidate_batch)
        logger.info("File change broadcaster ready (API-driven, no disk watcher).")
        return True

    async def _invalidate_batch(self, paths: set[str]) -> None:
        """Called by broadcaster after coalescing — one cache scan per flush."""
        if self._cache is not None and paths:
            await self._cache.invalidate_by_paths(paths)

    def stop(self) -> None:
        pass  # nothing to stop — no background thread


def emit_change(path: str, change: str, loop: asyncio.AbstractEventLoop) -> None:
    """Emit a file change event from an API mutation endpoint.

    Called after write / create / delete / rename succeeds.
    The event is forwarded to EventBroadcaster which coalesces,
    throttles, invalidates cache, and pushes to WS clients.

    Args:
        path:   relative path inside the workspace (e.g. "src/foo.py")
        change: "added" | "updated" | "deleted"
        loop:   the running asyncio event loop
    """
    try:
        ct = ChangeType(change)
    except ValueError:
        ct = ChangeType.UPDATED
    _default_broadcaster.emit_threadsafe(path, ct, loop)
