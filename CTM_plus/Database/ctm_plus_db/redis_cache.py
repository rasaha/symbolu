"""
CTM+ Redis-style Cache.

Provides a Redis-compatible interface with CTM+ eviction.
Can be used as a local cache or as a Redis module reference.
"""

import time
import threading
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from dataclasses import dataclass
from enum import Enum

from .buffer_pool import CTMBufferPool, PageType
from .config import CTMDBConfig


class RedisDataType(Enum):
    STRING = "string"
    LIST = "list"
    SET = "set"
    ZSET = "zset"
    HASH = "hash"


@dataclass
class RedisEntry:
    """Redis-style cache entry."""
    key: str
    value: Any
    data_type: RedisDataType
    created_at: float
    expires_at: Optional[float] = None
    access_count: int = 0


class RedisCTMCache:
    """
    Redis-compatible cache with CTM+ eviction.

    Implements common Redis commands with intelligent memory management.
    """

    def __init__(
        self,
        maxmemory: int,  # Maximum memory in bytes
        avg_entry_size: int = 256,  # Estimated average entry size
        config: Optional[CTMDBConfig] = None,
    ):
        """
        Initialize Redis-style cache.

        Args:
            maxmemory: Maximum memory limit in bytes.
            avg_entry_size: Estimated average entry size for capacity calculation.
            config: CTM+ configuration.
        """
        self.maxmemory = maxmemory
        self.avg_entry_size = avg_entry_size
        self.config = config or CTMDBConfig.for_redis()

        # Calculate max entries
        max_entries = maxmemory // avg_entry_size

        self._pool = CTMBufferPool(
            pool_size_pages=max_entries,
            page_size_bytes=avg_entry_size,
            config=self.config,
        )

        # Storage
        self._data: Dict[str, RedisEntry] = {}
        self._key_to_id: Dict[str, int] = {}
        self._id_to_key: Dict[int, str] = {}
        self._next_id = 0
        self._memory_used = 0

        self._lock = threading.RLock()

        # Stats
        self._commands_processed = 0

    def _get_key_id(self, key: str) -> int:
        """Get internal ID for key."""
        if key not in self._key_to_id:
            self._key_to_id[key] = self._next_id
            self._id_to_key[self._next_id] = key
            self._next_id += 1
        return self._key_to_id[key]

    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of value."""
        if isinstance(value, str):
            return len(value.encode('utf-8'))
        elif isinstance(value, bytes):
            return len(value)
        elif isinstance(value, (int, float)):
            return 8
        elif isinstance(value, (list, set)):
            return sum(self._estimate_size(v) for v in value) + 64
        elif isinstance(value, dict):
            return sum(
                self._estimate_size(k) + self._estimate_size(v)
                for k, v in value.items()
            ) + 64
        return self.avg_entry_size

    def _check_memory(self, new_size: int) -> None:
        """Evict entries if memory limit exceeded."""
        while self._memory_used + new_size > self.maxmemory:
            victim_id = self._pool.select_victim()
            if victim_id is None:
                break

            if victim_id in self._id_to_key:
                victim_key = self._id_to_key[victim_id]
                self._delete_internal(victim_key)

    def _delete_internal(self, key: str) -> bool:
        """Internal delete without recording command."""
        if key not in self._data:
            return False

        entry = self._data[key]
        entry_size = self._estimate_size(entry.value)
        self._memory_used -= entry_size

        key_id = self._key_to_id.get(key)
        if key_id is not None:
            self._pool.buffer_pages.discard(key_id)
            if key_id in self._pool.pages:
                del self._pool.pages[key_id]
            del self._id_to_key[key_id]
            del self._key_to_id[key]

        del self._data[key]
        return True

    # ========== String Commands ==========

    def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,  # Expire seconds
        px: Optional[int] = None,  # Expire milliseconds
        nx: bool = False,  # Only set if not exists
        xx: bool = False,  # Only set if exists
    ) -> Optional[str]:
        """SET command."""
        with self._lock:
            self._commands_processed += 1

            if nx and key in self._data:
                return None
            if xx and key not in self._data:
                return None

            # Calculate expiry
            expires_at = None
            if ex is not None:
                expires_at = time.monotonic() + ex
            elif px is not None:
                expires_at = time.monotonic() + px / 1000.0

            # Check memory and evict if needed
            value_size = self._estimate_size(value)
            if key in self._data:
                old_size = self._estimate_size(self._data[key].value)
                self._memory_used -= old_size
            self._check_memory(value_size)

            # Store
            entry = RedisEntry(
                key=key,
                value=value,
                data_type=RedisDataType.STRING,
                created_at=time.monotonic(),
                expires_at=expires_at,
            )
            self._data[key] = entry
            self._memory_used += value_size

            # Record access
            key_id = self._get_key_id(key)
            self._pool.access(key_id, is_write=True)

            return "OK"

    def get(self, key: str) -> Optional[str]:
        """GET command."""
        with self._lock:
            self._commands_processed += 1

            if key not in self._data:
                return None

            entry = self._data[key]

            # Check expiry
            if entry.expires_at and time.monotonic() > entry.expires_at:
                self._delete_internal(key)
                return None

            if entry.data_type != RedisDataType.STRING:
                raise TypeError("WRONGTYPE Operation against a key holding the wrong kind of value")

            # Record access
            key_id = self._get_key_id(key)
            self._pool.access(key_id, is_write=False)
            entry.access_count += 1

            return entry.value

    def incr(self, key: str) -> int:
        """INCR command."""
        with self._lock:
            value = self.get(key)
            if value is None:
                value = "0"
            new_value = int(value) + 1
            self.set(key, str(new_value))
            return new_value

    def decr(self, key: str) -> int:
        """DECR command."""
        with self._lock:
            value = self.get(key)
            if value is None:
                value = "0"
            new_value = int(value) - 1
            self.set(key, str(new_value))
            return new_value

    # ========== Hash Commands ==========

    def hset(self, key: str, field: str, value: str) -> int:
        """HSET command."""
        with self._lock:
            self._commands_processed += 1

            is_new = False
            if key not in self._data:
                entry = RedisEntry(
                    key=key,
                    value={},
                    data_type=RedisDataType.HASH,
                    created_at=time.monotonic(),
                )
                self._data[key] = entry
                is_new = True

            entry = self._data[key]
            if entry.data_type != RedisDataType.HASH:
                raise TypeError("WRONGTYPE")

            field_is_new = field not in entry.value
            entry.value[field] = value

            key_id = self._get_key_id(key)
            self._pool.access(key_id, is_write=True)

            return 1 if field_is_new else 0

    def hget(self, key: str, field: str) -> Optional[str]:
        """HGET command."""
        with self._lock:
            self._commands_processed += 1

            if key not in self._data:
                return None

            entry = self._data[key]
            if entry.data_type != RedisDataType.HASH:
                raise TypeError("WRONGTYPE")

            key_id = self._get_key_id(key)
            self._pool.access(key_id, is_write=False)

            return entry.value.get(field)

    def hgetall(self, key: str) -> Dict[str, str]:
        """HGETALL command."""
        with self._lock:
            self._commands_processed += 1

            if key not in self._data:
                return {}

            entry = self._data[key]
            if entry.data_type != RedisDataType.HASH:
                raise TypeError("WRONGTYPE")

            key_id = self._get_key_id(key)
            self._pool.access(key_id, is_write=False)

            return dict(entry.value)

    # ========== List Commands ==========

    def lpush(self, key: str, *values: str) -> int:
        """LPUSH command."""
        with self._lock:
            self._commands_processed += 1

            if key not in self._data:
                entry = RedisEntry(
                    key=key,
                    value=[],
                    data_type=RedisDataType.LIST,
                    created_at=time.monotonic(),
                )
                self._data[key] = entry

            entry = self._data[key]
            if entry.data_type != RedisDataType.LIST:
                raise TypeError("WRONGTYPE")

            for v in values:
                entry.value.insert(0, v)

            key_id = self._get_key_id(key)
            self._pool.access(key_id, is_write=True)

            return len(entry.value)

    def rpush(self, key: str, *values: str) -> int:
        """RPUSH command."""
        with self._lock:
            self._commands_processed += 1

            if key not in self._data:
                entry = RedisEntry(
                    key=key,
                    value=[],
                    data_type=RedisDataType.LIST,
                    created_at=time.monotonic(),
                )
                self._data[key] = entry

            entry = self._data[key]
            if entry.data_type != RedisDataType.LIST:
                raise TypeError("WRONGTYPE")

            entry.value.extend(values)

            key_id = self._get_key_id(key)
            self._pool.access(key_id, is_write=True)

            return len(entry.value)

    def lrange(self, key: str, start: int, stop: int) -> List[str]:
        """LRANGE command."""
        with self._lock:
            self._commands_processed += 1

            if key not in self._data:
                return []

            entry = self._data[key]
            if entry.data_type != RedisDataType.LIST:
                raise TypeError("WRONGTYPE")

            key_id = self._get_key_id(key)
            self._pool.access(key_id, is_write=False)

            # Handle negative indices
            length = len(entry.value)
            if start < 0:
                start = max(0, length + start)
            if stop < 0:
                stop = length + stop

            return entry.value[start:stop + 1]

    # ========== Key Commands ==========

    def delete(self, *keys: str) -> int:
        """DEL command."""
        with self._lock:
            self._commands_processed += 1
            count = 0
            for key in keys:
                if self._delete_internal(key):
                    count += 1
            return count

    def exists(self, *keys: str) -> int:
        """EXISTS command."""
        with self._lock:
            self._commands_processed += 1
            return sum(1 for key in keys if key in self._data)

    def expire(self, key: str, seconds: int) -> int:
        """EXPIRE command."""
        with self._lock:
            self._commands_processed += 1

            if key not in self._data:
                return 0

            self._data[key].expires_at = time.monotonic() + seconds
            return 1

    def ttl(self, key: str) -> int:
        """TTL command."""
        with self._lock:
            self._commands_processed += 1

            if key not in self._data:
                return -2

            entry = self._data[key]
            if entry.expires_at is None:
                return -1

            remaining = entry.expires_at - time.monotonic()
            if remaining <= 0:
                self._delete_internal(key)
                return -2

            return int(remaining)

    def keys(self, pattern: str = "*") -> List[str]:
        """KEYS command (simplified - exact match or *)."""
        with self._lock:
            self._commands_processed += 1

            if pattern == "*":
                return list(self._data.keys())
            return [k for k in self._data.keys() if k == pattern]

    def dbsize(self) -> int:
        """DBSIZE command."""
        with self._lock:
            return len(self._data)

    def flushdb(self) -> str:
        """FLUSHDB command."""
        with self._lock:
            self._data.clear()
            self._key_to_id.clear()
            self._id_to_key.clear()
            self._pool.buffer_pages.clear()
            self._pool.pages.clear()
            self._memory_used = 0
            return "OK"

    # ========== Info Commands ==========

    def info(self, section: str = "all") -> Dict[str, Any]:
        """INFO command."""
        pool_stats = self._pool.get_stats()

        return {
            "server": {
                "ctm_version": "1.0.0",
            },
            "clients": {
                "connected_clients": 1,
            },
            "memory": {
                "used_memory": self._memory_used,
                "maxmemory": self.maxmemory,
                "mem_fragmentation_ratio": 1.0,
            },
            "stats": {
                "total_connections_received": 1,
                "total_commands_processed": self._commands_processed,
                "keyspace_hits": pool_stats["hits"],
                "keyspace_misses": pool_stats["misses"],
            },
            "ctm_plus": {
                "hit_rate": pool_stats["hit_rate"],
                "evictions": pool_stats["evictions"],
                "adaptive_p": pool_stats["adaptive_p"],
                "smart_selections": pool_stats["smart_selections"],
            },
            "keyspace": {
                "db0": {
                    "keys": len(self._data),
                }
            },
        }
