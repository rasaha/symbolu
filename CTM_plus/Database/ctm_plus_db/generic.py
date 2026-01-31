"""
CTM+ Generic Key-Value Cache.

Provides a simple, generic interface for any key-value storage system.
"""

import time
import threading
from typing import Dict, List, Optional, Any, Tuple, Generic, TypeVar, Callable
from dataclasses import dataclass

from .buffer_pool import CTMBufferPool, PageType
from .config import CTMDBConfig

K = TypeVar('K')
V = TypeVar('V')


@dataclass
class CacheEntry(Generic[V]):
    """Generic cache entry."""
    value: V
    size_bytes: int
    created_at: float
    last_access: float
    access_count: int = 0
    metadata: Optional[Dict[str, Any]] = None


class GenericKVCache(Generic[K, V]):
    """
    Generic key-value cache with CTM+ eviction.

    A flexible cache interface that can be adapted to any storage system.
    Supports:
    - Size-aware eviction
    - Custom serialization
    - Metadata tracking
    - Event callbacks
    """

    def __init__(
        self,
        max_entries: int = 10000,
        max_memory_bytes: Optional[int] = None,
        config: Optional[CTMDBConfig] = None,
        size_fn: Optional[Callable[[V], int]] = None,
    ):
        """
        Initialize cache.

        Args:
            max_entries: Maximum number of entries.
            max_memory_bytes: Optional memory limit (entries evicted when exceeded).
            config: CTM+ configuration.
            size_fn: Function to compute value size in bytes.
        """
        self.max_entries = max_entries
        self.max_memory = max_memory_bytes
        self.config = config or CTMDBConfig()
        self.size_fn = size_fn or (lambda v: 1)

        self._pool = CTMBufferPool(
            pool_size_pages=max_entries,
            page_size_bytes=1,
            config=self.config,
        )

        self._entries: Dict[K, CacheEntry[V]] = {}
        self._key_to_id: Dict[K, int] = {}
        self._id_to_key: Dict[int, K] = {}
        self._next_id = 0
        self._memory_used = 0
        self._lock = threading.RLock()

        # Callbacks
        self.on_evict: Optional[Callable[[K, V], None]] = None
        self.on_miss: Optional[Callable[[K], Optional[V]]] = None  # Loader

    def _get_id(self, key: K) -> int:
        """Get internal ID for key."""
        if key not in self._key_to_id:
            self._key_to_id[key] = self._next_id
            self._id_to_key[self._next_id] = key
            self._next_id += 1
        return self._key_to_id[key]

    def get(
        self,
        key: K,
        default: Optional[V] = None,
        load_on_miss: bool = True,
    ) -> Optional[V]:
        """
        Get value for key.

        Args:
            key: Cache key.
            default: Default value if not found.
            load_on_miss: Whether to call on_miss loader if not found.

        Returns:
            Cached value or default.
        """
        with self._lock:
            if key in self._entries:
                entry = self._entries[key]
                entry.last_access = time.monotonic()
                entry.access_count += 1

                # Record access in pool
                key_id = self._get_id(key)
                self._pool.access(key_id, is_write=False)

                return entry.value

            # Miss - try loader
            if load_on_miss and self.on_miss:
                value = self.on_miss(key)
                if value is not None:
                    self.put(key, value)
                    return value

            return default

    def put(
        self,
        key: K,
        value: V,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[K]:
        """
        Put value in cache.

        Args:
            key: Cache key.
            value: Value to cache.
            metadata: Optional metadata to store with entry.

        Returns:
            Evicted key if eviction occurred.
        """
        with self._lock:
            value_size = self.size_fn(value)
            evicted_key = None

            # Handle update vs insert
            if key in self._entries:
                old_entry = self._entries[key]
                self._memory_used -= old_entry.size_bytes
            else:
                # Check limits
                while len(self._entries) >= self.max_entries:
                    evicted_key = self._evict_one()
                    if evicted_key is None:
                        break

            # Check memory limit
            if self.max_memory:
                while self._memory_used + value_size > self.max_memory:
                    evicted = self._evict_one()
                    if evicted is None:
                        break
                    if evicted_key is None:
                        evicted_key = evicted

            # Store entry
            now = time.monotonic()
            entry = CacheEntry(
                value=value,
                size_bytes=value_size,
                created_at=now,
                last_access=now,
                access_count=1,
                metadata=metadata,
            )
            self._entries[key] = entry
            self._memory_used += value_size

            # Record access
            key_id = self._get_id(key)
            self._pool.access(key_id, is_write=True)

            return evicted_key

    def _evict_one(self) -> Optional[K]:
        """Evict one entry."""
        victim_id = self._pool.select_victim()
        if victim_id is None or victim_id not in self._id_to_key:
            return None

        victim_key = self._id_to_key[victim_id]
        entry = self._entries.get(victim_key)

        # Callback
        if self.on_evict and entry:
            self.on_evict(victim_key, entry.value)

        # Clean up
        if victim_key in self._entries:
            self._memory_used -= self._entries[victim_key].size_bytes
            del self._entries[victim_key]
        if victim_key in self._key_to_id:
            del self._key_to_id[victim_key]
        if victim_id in self._id_to_key:
            del self._id_to_key[victim_id]

        self._pool.buffer_pages.discard(victim_id)
        if victim_id in self._pool.pages:
            del self._pool.pages[victim_id]

        return victim_key

    def delete(self, key: K) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key not in self._entries:
                return False

            entry = self._entries[key]
            self._memory_used -= entry.size_bytes

            key_id = self._key_to_id.get(key)
            if key_id is not None:
                self._pool.buffer_pages.discard(key_id)
                if key_id in self._pool.pages:
                    del self._pool.pages[key_id]
                del self._id_to_key[key_id]
                del self._key_to_id[key]

            del self._entries[key]
            return True

    def contains(self, key: K) -> bool:
        """Check if key exists."""
        return key in self._entries

    def get_metadata(self, key: K) -> Optional[Dict[str, Any]]:
        """Get metadata for key."""
        with self._lock:
            if key in self._entries:
                return self._entries[key].metadata
            return None

    def set_metadata(self, key: K, metadata: Dict[str, Any]) -> bool:
        """Set metadata for key."""
        with self._lock:
            if key in self._entries:
                self._entries[key].metadata = metadata
                return True
            return False

    def get_many(self, keys: List[K]) -> Dict[K, V]:
        """Get multiple values."""
        result = {}
        for key in keys:
            value = self.get(key, load_on_miss=False)
            if value is not None:
                result[key] = value
        return result

    def put_many(self, items: Dict[K, V]) -> None:
        """Put multiple values."""
        for key, value in items.items():
            self.put(key, value)

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._entries.clear()
            self._key_to_id.clear()
            self._id_to_key.clear()
            self._pool.buffer_pages.clear()
            self._pool.pages.clear()
            self._memory_used = 0

    def keys(self) -> List[K]:
        """Get all keys."""
        with self._lock:
            return list(self._entries.keys())

    def size(self) -> int:
        """Get current size."""
        return len(self._entries)

    def memory_used(self) -> int:
        """Get memory used in bytes."""
        return self._memory_used

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pool_stats = self._pool.get_stats()
        return {
            "size": len(self._entries),
            "max_entries": self.max_entries,
            "memory_used": self._memory_used,
            "max_memory": self.max_memory,
            **pool_stats,
        }


class WriteBackCache(GenericKVCache[K, V]):
    """
    Write-back cache with deferred persistence.

    Accumulates writes and flushes to storage periodically.
    """

    def __init__(
        self,
        max_entries: int = 10000,
        max_memory_bytes: Optional[int] = None,
        config: Optional[CTMDBConfig] = None,
        size_fn: Optional[Callable[[V], int]] = None,
        flush_fn: Optional[Callable[[Dict[K, V]], None]] = None,
        flush_interval: float = 60.0,
    ):
        super().__init__(max_entries, max_memory_bytes, config, size_fn)
        self.flush_fn = flush_fn
        self.flush_interval = flush_interval
        self._dirty_keys: set = set()
        self._last_flush = time.monotonic()

    def put(
        self,
        key: K,
        value: V,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[K]:
        evicted = super().put(key, value, metadata)
        self._dirty_keys.add(key)

        # Check if flush needed
        if time.monotonic() - self._last_flush >= self.flush_interval:
            self.flush()

        return evicted

    def flush(self) -> int:
        """Flush dirty entries to storage."""
        with self._lock:
            if not self._dirty_keys or not self.flush_fn:
                return 0

            to_flush = {
                k: self._entries[k].value
                for k in self._dirty_keys
                if k in self._entries
            }

            if to_flush:
                self.flush_fn(to_flush)

            count = len(to_flush)
            self._dirty_keys.clear()
            self._last_flush = time.monotonic()
            return count

    def get_dirty_count(self) -> int:
        """Get number of dirty entries."""
        return len(self._dirty_keys)
