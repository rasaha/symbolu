"""
CTM+ Page Cache for application-level caching.

A simpler interface for general-purpose page/block caching.
"""

import time
import threading
from typing import Dict, List, Optional, Any, Tuple, Generic, TypeVar
from collections import OrderedDict

from .config import CTMDBConfig
from .buffer_pool import CTMBufferPool, PageType

K = TypeVar('K')
V = TypeVar('V')


class CTMPageCache(Generic[K, V]):
    """
    Generic page cache with CTM+ eviction.

    A simple key-value cache interface backed by CTM+ buffer pool.
    """

    def __init__(
        self,
        max_size: int,
        config: Optional[CTMDBConfig] = None,
    ):
        """
        Initialize cache.

        Args:
            max_size: Maximum number of entries.
            config: CTM+ configuration.
        """
        self.max_size = max_size
        self.config = config or CTMDBConfig()

        # Use buffer pool for eviction decisions
        self._pool = CTMBufferPool(
            pool_size_pages=max_size,
            page_size_bytes=1,  # Size doesn't matter for logic
            config=self.config,
        )

        # Actual data storage
        self._data: Dict[K, V] = {}
        self._key_to_id: Dict[K, int] = {}
        self._id_to_key: Dict[int, K] = {}
        self._next_id = 0
        self._lock = threading.RLock()

    def _get_id(self, key: K) -> int:
        """Get or create numeric ID for key."""
        if key not in self._key_to_id:
            self._key_to_id[key] = self._next_id
            self._id_to_key[self._next_id] = key
            self._next_id += 1
        return self._key_to_id[key]

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """Get value for key."""
        with self._lock:
            if key not in self._data:
                return default

            # Record access
            page_id = self._get_id(key)
            self._pool.access(page_id, is_write=False)

            return self._data[key]

    def put(self, key: K, value: V) -> Optional[K]:
        """
        Put key-value pair in cache.

        Returns:
            Evicted key if eviction occurred, None otherwise.
        """
        with self._lock:
            page_id = self._get_id(key)
            evicted_key = None

            if key not in self._data:
                # New entry - may need eviction
                if len(self._data) >= self.max_size:
                    evicted_key = self._evict_one()

            # Record access and store
            self._pool.access(page_id, is_write=True)
            self._data[key] = value

            return evicted_key

    def _evict_one(self) -> Optional[K]:
        """Evict one entry."""
        victim_id = self._pool.select_victim()
        if victim_id is None:
            return None

        if victim_id not in self._id_to_key:
            return None

        victim_key = self._id_to_key[victim_id]

        # Remove from all structures
        if victim_key in self._data:
            del self._data[victim_key]
        if victim_key in self._key_to_id:
            del self._key_to_id[victim_key]
        if victim_id in self._id_to_key:
            del self._id_to_key[victim_id]

        # Remove from pool
        self._pool.buffer_pages.discard(victim_id)
        if victim_id in self._pool.pages:
            del self._pool.pages[victim_id]

        return victim_key

    def delete(self, key: K) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key not in self._data:
                return False

            page_id = self._key_to_id[key]

            del self._data[key]
            del self._key_to_id[key]
            del self._id_to_key[page_id]

            self._pool.buffer_pages.discard(page_id)
            if page_id in self._pool.pages:
                del self._pool.pages[page_id]

            return True

    def contains(self, key: K) -> bool:
        """Check if key is in cache."""
        return key in self._data

    def size(self) -> int:
        """Get current cache size."""
        return len(self._data)

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._data.clear()
            self._key_to_id.clear()
            self._id_to_key.clear()
            self._pool.buffer_pages.clear()
            self._pool.pages.clear()

    def keys(self) -> List[K]:
        """Get all keys."""
        with self._lock:
            return list(self._data.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pool_stats = self._pool.get_stats()
        return {
            "size": len(self._data),
            "max_size": self.max_size,
            "utilization": len(self._data) / self.max_size if self.max_size > 0 else 0,
            **pool_stats,
        }


class TTLCache(CTMPageCache[K, V]):
    """
    CTM+ cache with TTL (time-to-live) support.
    """

    def __init__(
        self,
        max_size: int,
        default_ttl_seconds: float = 300.0,
        config: Optional[CTMDBConfig] = None,
    ):
        super().__init__(max_size, config)
        self.default_ttl = default_ttl_seconds
        self._expiry: Dict[K, float] = {}

    def put(
        self,
        key: K,
        value: V,
        ttl_seconds: Optional[float] = None,
    ) -> Optional[K]:
        """Put with optional TTL override."""
        evicted = super().put(key, value)

        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        self._expiry[key] = time.monotonic() + ttl

        return evicted

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """Get with expiry check."""
        with self._lock:
            if key in self._expiry:
                if time.monotonic() > self._expiry[key]:
                    # Expired
                    self.delete(key)
                    return default

            return super().get(key, default)

    def delete(self, key: K) -> bool:
        """Delete with expiry cleanup."""
        if key in self._expiry:
            del self._expiry[key]
        return super().delete(key)

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with self._lock:
            now = time.monotonic()
            expired = [k for k, exp in self._expiry.items() if now > exp]
            for key in expired:
                self.delete(key)
            return len(expired)


class LRUCache(Generic[K, V]):
    """
    Simple LRU cache for comparison with CTM+.
    """

    def __init__(self, max_size: int):
        self.max_size = max_size
        self._cache: OrderedDict[K, V] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return default

    def put(self, key: K, value: V) -> Optional[K]:
        with self._lock:
            evicted = None
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self.max_size:
                    evicted, _ = self._cache.popitem(last=False)
            self._cache[key] = value
            return evicted

    def get_stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "size": len(self._cache),
            "max_size": self.max_size,
        }
