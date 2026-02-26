# file_cache.py

import asyncio
import hashlib
import logging
import posixpath
import time
from collections import OrderedDict
from typing import Any, Optional
from dataclasses import dataclass

logger = logging.getLogger("daytona-api")


@dataclass
class CacheEntry:
    etag: str
    modified: str
    timestamp: float

    def is_expired(self, ttl_seconds: float) -> bool:
        return time.time() - self.timestamp > ttl_seconds


class FileCache:

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "expirations": 0}

    async def get(self, key: str) -> Optional[CacheEntry]:
        async with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None
            entry = self._cache[key]
            if entry.is_expired(self.ttl_seconds):
                del self._cache[key]
                self._stats["expirations"] += 1
                self._stats["misses"] += 1
                return None
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return entry

    async def set(self, key: str, etag: str, modified: str) -> None:
        async with self._lock:
            if key in self._cache:
                self._cache[key] = CacheEntry(etag=etag, modified=modified, timestamp=time.time())
                self._cache.move_to_end(key)
                return
            while len(self._cache) >= self.max_size:
                oldest_key, _ = self._cache.popitem(last=False)
                self._stats["evictions"] += 1
                logger.debug(f"Cache eviction: {oldest_key}")
            self._cache[key] = CacheEntry(etag=etag, modified=modified, timestamp=time.time())

    async def invalidate(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def invalidate_prefix(self, prefix: str) -> int:
        async with self._lock:
            prefix_slash = prefix if prefix.endswith("/") else prefix + "/"
            prefix_colon = prefix + ":"
            keys_to_delete = [
                k for k in self._cache.keys()
                if k == prefix
                or k.startswith(prefix_slash)
                or k.startswith(prefix_colon)
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    async def invalidate_user(self, user_id: str) -> int:
        return await self.invalidate_prefix(f"{user_id}:")

    async def invalidate_by_path(self, rel_path: str) -> int:
        """Invalidate all entries matching a relative path and its descendants, across all users.

        Used by the file watcher: when a directory (e.g. src) is modified/deleted,
        we must invalidate both user1:src and user1:src/a.py, user2:src/b.py, etc.
        Key format is "{user_id}:{path}"; we match exact path or path + "/" prefix.
        """
        if not rel_path:
            return 0
        rel_path = posixpath.normpath(rel_path.replace("\\", "/")).strip("/")
        if rel_path in ("", "."):
            return 0

        async with self._lock:
            keys_to_delete = []
            for k in self._cache:
                # key format: "{user_id}:{path}"
                _, sep, cached_path = k.partition(":")
                if not sep:
                    continue
                if cached_path == rel_path or cached_path.startswith(rel_path + "/"):
                    keys_to_delete.append(k)
            for key in keys_to_delete:
                del self._cache[key]
            if keys_to_delete:
                logger.debug(
                    "File watcher invalidated %d cache entries for path: %s",
                    len(keys_to_delete), rel_path,
                )
            return len(keys_to_delete)

    async def clear(self) -> int:
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    async def cleanup_expired(self) -> int:
        async with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired(self.ttl_seconds)]
            for key in expired_keys:
                del self._cache[key]
                self._stats["expirations"] += 1
            return len(expired_keys)

    async def get_stats(self) -> dict[str, Any]:
        async with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate_percent": round(hit_rate, 2),
                "evictions": self._stats["evictions"],
                "expirations": self._stats["expirations"],
            }

    def __len__(self) -> int:
        return len(self._cache)


# ── Helper functions ────────────────────────────────────────────────

def generate_etag_from_metadata(modified: str, size: int) -> str:
    raw = f"{modified}-{size}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def get_cache_key(user_id: str, path: str) -> str:
    """Return a normalized cache key so that equivalent paths always map to the same key."""
    if path:
        # Normalize slashes and collapse . / .. segments defensively,
        # even if the caller has already validated the path.
        path = posixpath.normpath(path.replace("\\", "/")).strip("/")
        if path == ".":
            path = ""
    return f"{user_id}:{path}"


def normalize_etag(etag: Optional[str]) -> Optional[str]:
    if not etag:
        return None
    etag = etag.strip()
    if "," in etag:
        etag = etag.split(",")[0].strip()
    if etag.startswith("W/"):
        etag = etag[2:]
    if etag.startswith('"') and etag.endswith('"'):
        etag = etag[1:-1]
    return etag if etag else None


def clamp_ttl(ttl_remaining: float) -> int:
    return max(0, int(ttl_remaining))
