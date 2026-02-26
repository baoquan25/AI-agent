# file_watcher.py

import asyncio
import logging
import os
import posixpath
import threading
import time
from typing import Optional

logger = logging.getLogger("daytona-api")

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False


# ── Internal event handler ───────────────────────────────────────────

class _CacheInvalidationHandler:
    """Receives watchdog callbacks and schedules async cache invalidations."""

    _DEDUP_WINDOW: float = 0.10  # seconds — ignore duplicate events within this window

    def __init__(self, cache, workspace_path: str, loop: asyncio.AbstractEventLoop) -> None:
        self._cache = cache
        self._workspace_path = os.path.realpath(workspace_path)
        self._loop = loop
        self._last_seen: dict[str, float] = {}
        self._dedup_lock = threading.Lock()

    # ── Helpers ──────────────────────────────────────────────────────

    def _to_rel(self, abs_path: str) -> str:
        try:
            return posixpath.normpath(
                os.path.relpath(abs_path, self._workspace_path).replace("\\", "/")
            ).strip("/")
        except ValueError:
            return abs_path

    def _deduplicate(self, rel_path: str) -> bool:
        """Return True if this event should be processed (not a duplicate)."""
        now = time.monotonic()
        with self._dedup_lock:
            if now - self._last_seen.get(rel_path, 0.0) < self._DEDUP_WINDOW:
                return False
            self._last_seen[rel_path] = now
            return True

    def _submit(self, rel_path: str) -> None:
        if not rel_path or rel_path == ".":
            return
        if not self._deduplicate(rel_path):
            return
        fut = asyncio.run_coroutine_threadsafe(
            self._cache.invalidate_by_path(rel_path),
            self._loop,
        )

        def _done(f):
            try:
                f.result()
            except Exception as e:
                logger.debug("watcher invalidate failed for %s: %s", rel_path, e)

        fut.add_done_callback(_done)

    # ── Watchdog event callbacks ──────────────────────────────────────

    def on_modified(self, event) -> None:
        if not event.is_directory:
            self._submit(self._to_rel(event.src_path))

    def on_created(self, event) -> None:
        self._submit(self._to_rel(event.src_path))
        # Also invalidate the parent so a stale dir-listing cache gets dropped.
        parent = self._to_rel(os.path.dirname(event.src_path))
        if parent:
            self._submit(parent)

    def on_deleted(self, event) -> None:
        self._submit(self._to_rel(event.src_path))
        parent = self._to_rel(os.path.dirname(event.src_path))
        if parent:
            self._submit(parent)

    def on_moved(self, event) -> None:
        self._submit(self._to_rel(event.src_path))
        self._submit(self._to_rel(event.dest_path))
        for path in (event.src_path, event.dest_path):
            parent = self._to_rel(os.path.dirname(path))
            if parent:
                self._submit(parent)


# ── Thin watchdog adapter ────────────────────────────────────────────

if _WATCHDOG_AVAILABLE:
    class _WatchdogAdapter(FileSystemEventHandler):
        def __init__(self, delegate: _CacheInvalidationHandler) -> None:
            super().__init__()
            self._d = delegate

        def on_modified(self, event) -> None: self._d.on_modified(event)
        def on_created(self, event) -> None:  self._d.on_created(event)
        def on_deleted(self, event) -> None:  self._d.on_deleted(event)
        def on_moved(self, event) -> None:    self._d.on_moved(event)


# ── Public API ───────────────────────────────────────────────────────

class WorkspaceCacheWatcher:
    """Watches *workspace_path* for OS-level file changes and invalidates the
    provided ``FileCache`` automatically.

    Usage (inside the FastAPI lifespan)::

        watcher = WorkspaceCacheWatcher(cache, "/home/daytona/workspace")
        loop = asyncio.get_event_loop()
        watcher.start(loop)
        ...
        watcher.stop()
    """

    def __init__(self, cache, workspace_path: str) -> None:
        self._cache = cache
        self._workspace_path = workspace_path
        self._observer: Optional["Observer"] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> bool:
        """Start the background observer thread.  Returns True on success."""
        if not _WATCHDOG_AVAILABLE:
            return False
        if not os.path.isdir(self._workspace_path):
            logger.warning(
                "File watcher disabled: workspace path does not exist yet: %s",
                self._workspace_path,
            )
            return False

        delegate = _CacheInvalidationHandler(self._cache, self._workspace_path, loop)
        handler = _WatchdogAdapter(delegate)
        self._observer = Observer()
        self._observer.schedule(handler, self._workspace_path, recursive=True)
        self._observer.start()
        return True

    def stop(self) -> None:
        """Stop the background observer thread (blocks up to 5 s for join)."""
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=5)
        self._observer = None
