# pyright: basic
# type: ignore

"""
FileCache — Production-ready cache with TTL and LRU eviction.

Extracted from routers/file_system.py to keep the router thin.
"""

import hashlib
import logging
import time
import threading
from collections import OrderedDict
from typing import Any, Optional
from dataclasses import dataclass

logger = logging.getLogger("daytona-api")


@dataclass
class CacheEntry:
    """Single cache entry with metadata."""
    etag: str
    modified: str
    timestamp: float

    def is_expired(self, ttl_seconds: float) -> bool:
        return time.time() - self.timestamp > ttl_seconds


class FileCache:
    """
    Production-ready file cache with TTL and LRU eviction.

    Features:
    - TTL: Entries automatically expire after ttl_seconds
    - Max Size: LRU eviction when cache exceeds max_size
    - Thread-safe: All operations are protected by a lock
    - Per-user isolation: Keys include user_id
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "expirations": 0}

    def get(self, key: str) -> Optional[CacheEntry]:
        with self._lock:
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

    def set(self, key: str, etag: str, modified: str) -> None:
        with self._lock:
            if key in self._cache:
                self._cache[key] = CacheEntry(etag=etag, modified=modified, timestamp=time.time())
                self._cache.move_to_end(key)
                return
            while len(self._cache) >= self.max_size:
                oldest_key, _ = self._cache.popitem(last=False)
                self._stats["evictions"] += 1
                logger.debug(f"Cache eviction: {oldest_key}")
            self._cache[key] = CacheEntry(etag=etag, modified=modified, timestamp=time.time())

    def invalidate(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    def invalidate_user(self, user_id: str) -> int:
        return self.invalidate_prefix(f"{user_id}:")

    def clear(self) -> int:
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def cleanup_expired(self) -> int:
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired(self.ttl_seconds)]
            for key in expired_keys:
                del self._cache[key]
                self._stats["expirations"] += 1
            return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
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
