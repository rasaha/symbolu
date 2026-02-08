"""
CTM+ Integration for Database Systems.

Provides intelligent buffer pool management for database systems
including PostgreSQL, MySQL, Redis, and generic key-value stores.

Usage:
    from ctm_plus_db import CTMBufferPool, CTMDBConfig

    # Create buffer pool with CTM+
    pool = CTMBufferPool(
        pool_size_pages=10000,
        page_size_bytes=8192,
    )

    # Access pages
    pool.access(page_id=12345, is_write=False)

    # Get eviction victim
    victim = pool.select_victim()
"""

from .buffer_pool import CTMBufferPool
from .page_cache import CTMPageCache
from .config import CTMDBConfig
from .postgres import PostgresCTMExtension
from .redis_cache import RedisCTMCache
from .generic import GenericKVCache

__version__ = "0.1.0"
__all__ = [
    "CTMBufferPool",
    "CTMPageCache",
    "CTMDBConfig",
    "PostgresCTMExtension",
    "RedisCTMCache",
    "GenericKVCache",
]
