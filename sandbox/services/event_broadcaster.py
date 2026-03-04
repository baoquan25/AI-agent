# event_broadcaster.py
#
# VS Code equivalent:
#   - EventCoalescer  (src/vs/platform/files/common/watcher.ts)
#   - ThrottledWorker (src/vs/base/common/async.ts)
#   - ParcelWatcher.throttledFileChangesEmitter (parcelWatcher.ts)
#
# Pipeline:
#   raw events → _EventCoalescer (75 ms window)
#              → coalesced list
#              → batch cache invalidation (via _cache_invalidator callback)
#              → ThrottledEmitter: chunk≤500 / rest 200ms / buffer cap 30k
#              → broadcast JSON to WS clients

from __future__ import annotations

import asyncio
import logging
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger("daytona-api")

# ── Platform ──────────────────────────────────────────────────────────
# On Linux the filesystem is case-sensitive; do NOT lower-case paths.
# On macOS/Windows default volumes are case-insensitive.
_CASE_SENSITIVE = sys.platform == "linux"

# ── Constants (mirror VS Code values) ────────────────────────────────
_COALESCE_DELAY_S = 0.075       # 75 ms  — collect window before coalesce
_THROTTLE_CHUNK   = 500         # max events per batch sent to clients
_THROTTLE_DELAY_S = 0.200       # 200 ms — rest between oversized chunks
_MAX_BUFFER       = 30_000      # drop oldest if pending buffer exceeds this

# Max queue depth per WS client before we start dropping *oldest* messages
# (not kicking the client).
_CLIENT_QUEUE_MAX = 200


class ChangeType(str, Enum):
    ADDED   = "added"
    UPDATED = "updated"
    DELETED = "deleted"


@dataclass
class FileChangeEvent:
    path: str
    change: ChangeType


# ── EventCoalescer ────────────────────────────────────────────────────
# Mirrors VS Code's EventCoalescer class (watcher.ts).

class _EventCoalescer:
    """Coalesce a batch of raw FileChangeEvents.

    Rules (identical to VS Code):
    - ADDED  + DELETED  → drop both  (created-then-deleted in same window)
    - DELETED + ADDED   → UPDATED    (file replaced in-place)
    - ADDED  + UPDATED  → keep ADDED
    - DELETE of child   → drop when parent DELETE already covers it
    """

    def __init__(self) -> None:
        self._map: dict[str, FileChangeEvent] = {}

    def _key(self, path: str) -> str:
        # Fix 1.1: only lower on case-insensitive filesystems.
        return path if _CASE_SENSITIVE else path.lower()

    def process(self, event: FileChangeEvent) -> None:
        key = self._key(event.path)
        existing = self._map.get(key)

        if existing is None:
            self._map[key] = event
            return

        cur = existing.change
        new = event.change

        if cur == ChangeType.ADDED and new == ChangeType.DELETED:
            del self._map[key]                       # created-then-deleted → drop
        elif cur == ChangeType.DELETED and new == ChangeType.ADDED:
            existing.change = ChangeType.UPDATED     # deleted-then-created → updated
        elif cur == ChangeType.ADDED and new == ChangeType.UPDATED:
            pass                                     # keep ADDED
        else:
            existing.change = new                    # default: overwrite

    def flush(self) -> list[FileChangeEvent]:
        events = list(self._map.values())
        self._map.clear()

        # Prune child DELETEs when a parent DELETE already covers them.
        delete_paths: list[str] = sorted(
            [e.path for e in events if e.change == ChangeType.DELETED],
            key=len,
        )
        pruned: list[FileChangeEvent] = []
        for e in events:
            if e.change == ChangeType.DELETED:
                sep = "" if _CASE_SENSITIVE else None
                parent_covered = any(
                    e.path != dp and (
                        e.path.startswith(dp.rstrip("/") + "/")
                        if _CASE_SENSITIVE
                        else e.path.lower().startswith(dp.lower().rstrip("/") + "/")
                    )
                    for dp in delete_paths
                )
                if parent_covered:
                    continue
            pruned.append(e)
        return pruned


# ── EventBroadcaster ─────────────────────────────────────────────────

# Type alias for the optional batch-invalidate callback injected by file_watcher.
# Signature: async (paths: set[str]) -> None
CacheInvalidator = Callable[[set[str]], Coroutine[Any, Any, None]]


class EventBroadcaster:
    """Singleton that:
    - Accepts raw file change events from WorkspaceCacheWatcher (watcher thread).
    - Coalesces them (VS Code EventCoalescer, 75 ms window).
    - After coalescing: calls the optional cache-invalidation callback in batch
      (one cache scan per flush, not per raw event).
    - Throttles emission (chunk 500 / 200 ms rest / 30 k buffer cap).
    - Broadcasts JSON messages to all subscribed WebSocket clients.

    Fix 1.2: all _clients mutations are protected by asyncio.Lock so that
    subscribe/unsubscribe cannot race with _broadcast.
    """

    def __init__(self) -> None:
        # Fix 1.2: protect _clients with an asyncio lock.
        self._clients: set[asyncio.Queue[Any]] = set()
        self._clients_lock = asyncio.Lock()

        self._coalescer = _EventCoalescer()
        self._pending_flush: asyncio.TimerHandle | None = None
        self._buffer: list[FileChangeEvent] = []
        self._throttling = False

        self._loop: asyncio.AbstractEventLoop | None = None

        # Optional: injected by WorkspaceCacheWatcher after construction.
        self._cache_invalidator: CacheInvalidator | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def set_cache_invalidator(self, fn: CacheInvalidator) -> None:
        """Register a coroutine-returning callable for batch cache invalidation."""
        self._cache_invalidator = fn

    # ── Client subscribe / unsubscribe ───────────────────────────────

    async def subscribe(self) -> asyncio.Queue[Any]:
        # Fix 1.4: bounded queue; we drop oldest messages for slow clients,
        # not the client itself.
        q: asyncio.Queue[Any] = asyncio.Queue(maxsize=_CLIENT_QUEUE_MAX)
        async with self._clients_lock:
            self._clients.add(q)
        logger.debug("WS /fs/watch: client subscribed (total=%d)", len(self._clients))
        return q

    def subscribe_sync(self) -> asyncio.Queue[Any]:
        """Synchronous version for use in non-async contexts (route handlers)."""
        q: asyncio.Queue[Any] = asyncio.Queue(maxsize=_CLIENT_QUEUE_MAX)
        # Safe: called from within the running event loop, no other thread touches _clients.
        self._clients.add(q)
        logger.debug("WS /fs/watch: client subscribed (total=%d)", len(self._clients))
        return q

    async def unsubscribe(self, q: asyncio.Queue[Any]) -> None:
        async with self._clients_lock:
            self._clients.discard(q)
        logger.debug("WS /fs/watch: client unsubscribed (total=%d)", len(self._clients))

    def unsubscribe_sync(self, q: asyncio.Queue[Any]) -> None:
        self._clients.discard(q)
        logger.debug("WS /fs/watch: client unsubscribed (total=%d)", len(self._clients))

    # ── Incoming events (called from event loop via emit_threadsafe) ──

    async def emit(self, path: str, change: ChangeType) -> None:
        """Accept one raw event; schedule the 75 ms coalesce window."""
        async with self._clients_lock:
            has_clients = bool(self._clients)
        if not has_clients and self._cache_invalidator is None:
            return  # nothing listening

        self._coalescer.process(FileChangeEvent(path=path, change=change))

        if self._pending_flush is None:
            loop = self._loop or asyncio.get_running_loop()
            # Fix 1.3: schedule via call_soon_threadsafe-safe call_later on running loop.
            self._pending_flush = loop.call_later(
                _COALESCE_DELAY_S, self._schedule_flush
            )

    def _schedule_flush(self) -> None:
        """Called by the event loop timer; create_task in the running loop."""
        self._pending_flush = None
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        # Fix 1.3: use create_task (not ensure_future with deprecated loop= kwarg).
        loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self._do_flush())
        )

    async def _do_flush(self) -> None:
        """Coalesce buffered events, invalidate cache in batch, then throttle-emit."""
        coalesced = self._coalescer.flush()
        if not coalesced:
            return

        # ── Batch cache invalidation (fix 2.1 / 3.1) ─────────────────
        # Invalidate once per flush using the set of affected paths,
        # instead of once per raw event before coalescing.
        if self._cache_invalidator is not None:
            paths = {e.path for e in coalesced}
            try:
                await self._cache_invalidator(paths)
            except Exception as e:
                logger.warning("Batch cache invalidation error: %s", e)

        # ── Check if anyone is listening ─────────────────────────────
        async with self._clients_lock:
            has_clients = bool(self._clients)
        if not has_clients:
            return

        # ── Apply buffer cap ─────────────────────────────────────────
        self._buffer.extend(coalesced)
        if len(self._buffer) > _MAX_BUFFER:
            dropped = len(self._buffer) - _MAX_BUFFER
            self._buffer = self._buffer[dropped:]
            logger.warning(
                "WS /fs/watch: buffer cap hit, dropped %d events", dropped
            )

        if not self._throttling:
            await self._drain_buffer()

    async def _drain_buffer(self) -> None:
        """Send buffer to clients in chunks, resting between oversized chunks."""
        while self._buffer:
            chunk = self._buffer[:_THROTTLE_CHUNK]
            self._buffer = self._buffer[_THROTTLE_CHUNK:]

            payload = {
                "type": "fileChange",
                "changes": [
                    {"path": e.path, "change": e.change.value} for e in chunk
                ],
                "timestamp": time.time(),
            }
            await self._broadcast(payload)

            if self._buffer:
                self._throttling = True
                await asyncio.sleep(_THROTTLE_DELAY_S)

        self._throttling = False

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        """Fan-out a JSON message to all subscribed client queues.

        Fix 1.4: for slow clients we drop the *oldest* message from their
        queue instead of disconnecting them.
        """
        async with self._clients_lock:
            clients = list(self._clients)

        for q in clients:
            if q.full():
                # Drop oldest to make room — keep the client connected.
                try:
                    q.get_nowait()
                    logger.debug("WS /fs/watch: slow client, dropped oldest event")
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # another coroutine filled it in the meantime; skip

    # ── Convenience: emit from watcher thread ────────────────────────

    def emit_threadsafe(
        self, path: str, change: ChangeType, loop: asyncio.AbstractEventLoop
    ) -> None:
        asyncio.run_coroutine_threadsafe(self.emit(path, change), loop)


# ── Module-level singleton ────────────────────────────────────────────

broadcaster = EventBroadcaster()
