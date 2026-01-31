"""
CTM+ PostgreSQL Integration.

Provides CTM+ buffer pool management hooks for PostgreSQL.
Can be used as a reference for C extension development.
"""

import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .buffer_pool import CTMBufferPool, PageType
from .config import CTMDBConfig


class PostgresRelationType(Enum):
    """PostgreSQL relation types."""
    TABLE = "r"
    INDEX = "i"
    SEQUENCE = "S"
    TOAST = "t"
    VIEW = "v"
    MATERIALIZED = "m"


@dataclass
class PostgresBufferTag:
    """
    PostgreSQL buffer tag identifying a page.

    Equivalent to BufferTag in PostgreSQL's buf_internals.h
    """
    rel_file_node: int  # RelFileNode (database/tablespace/relation)
    fork_number: int    # 0=main, 1=fsm, 2=vm
    block_number: int   # Block number within fork

    def __hash__(self) -> int:
        return hash((self.rel_file_node, self.fork_number, self.block_number))

    def __eq__(self, other) -> bool:
        if not isinstance(other, PostgresBufferTag):
            return False
        return (
            self.rel_file_node == other.rel_file_node and
            self.fork_number == other.fork_number and
            self.block_number == other.block_number
        )


class PostgresCTMExtension:
    """
    CTM+ extension for PostgreSQL buffer manager.

    This class provides the interface that would be called from
    a PostgreSQL C extension to make eviction decisions.

    Usage (conceptual C integration):
        // In bufmgr.c
        static CTMBufferPool* ctm_pool = NULL;

        void ctm_init(int shared_buffers) {
            // Call Python or use C port of CTM+
            ctm_pool = ctm_buffer_pool_new(shared_buffers);
        }

        BufferDesc* ctm_strategy_get_victim() {
            int victim_id = ctm_select_victim(ctm_pool);
            return GetBufferDescriptor(victim_id);
        }
    """

    def __init__(
        self,
        shared_buffers: int,
        block_size: int = 8192,
        config: Optional[CTMDBConfig] = None,
    ):
        """
        Initialize PostgreSQL CTM+ extension.

        Args:
            shared_buffers: Number of shared buffer pages.
            block_size: PostgreSQL block size (default 8KB).
            config: CTM+ configuration.
        """
        self.config = config or CTMDBConfig.for_postgres()
        self.block_size = block_size

        self._pool = CTMBufferPool(
            pool_size_pages=shared_buffers,
            page_size_bytes=block_size,
            config=self.config,
        )

        # Map buffer tags to internal IDs
        self._tag_to_id: Dict[PostgresBufferTag, int] = {}
        self._id_to_tag: Dict[int, PostgresBufferTag] = {}
        self._next_id = 0

        # Relation type cache
        self._rel_types: Dict[int, PostgresRelationType] = {}

        self._lock = threading.RLock()

    def _get_page_id(self, tag: PostgresBufferTag) -> int:
        """Get internal page ID for buffer tag."""
        if tag not in self._tag_to_id:
            self._tag_to_id[tag] = self._next_id
            self._id_to_tag[self._next_id] = tag
            self._next_id += 1
        return self._tag_to_id[tag]

    def _get_page_type(self, tag: PostgresBufferTag) -> PageType:
        """Determine page type from buffer tag."""
        # Check relation type
        rel_type = self._rel_types.get(tag.rel_file_node)
        if rel_type == PostgresRelationType.INDEX:
            return PageType.INDEX
        elif rel_type == PostgresRelationType.TOAST:
            return PageType.TOAST

        # Check fork type
        if tag.fork_number == 1:
            return PageType.FSM
        elif tag.fork_number == 2:
            return PageType.VM

        return PageType.HEAP

    def register_relation(
        self,
        rel_file_node: int,
        rel_type: PostgresRelationType,
    ) -> None:
        """Register relation type for better eviction decisions."""
        with self._lock:
            self._rel_types[rel_file_node] = rel_type

    def read_buffer(
        self,
        tag: PostgresBufferTag,
        backend_id: Optional[int] = None,
    ) -> Tuple[bool, List[PostgresBufferTag]]:
        """
        Called when PostgreSQL reads a buffer.

        Args:
            tag: Buffer tag being read.
            backend_id: Backend process ID.

        Returns:
            (is_hit, prefetch_tags): Whether buffer was in pool,
            and list of buffers to prefetch.
        """
        with self._lock:
            page_id = self._get_page_id(tag)
            page_type = self._get_page_type(tag)

            is_hit, prefetch_ids = self._pool.access(
                page_id,
                is_write=False,
                page_type=page_type,
                accessor_id=backend_id,
            )

            # Convert prefetch IDs back to tags
            prefetch_tags = []
            for pid in prefetch_ids:
                if pid in self._id_to_tag:
                    prefetch_tags.append(self._id_to_tag[pid])
                else:
                    # Sequential prefetch - create new tag
                    next_tag = PostgresBufferTag(
                        rel_file_node=tag.rel_file_node,
                        fork_number=tag.fork_number,
                        block_number=tag.block_number + (pid - page_id),
                    )
                    prefetch_tags.append(next_tag)

            return is_hit, prefetch_tags

    def write_buffer(
        self,
        tag: PostgresBufferTag,
        backend_id: Optional[int] = None,
    ) -> None:
        """Called when PostgreSQL writes to a buffer."""
        with self._lock:
            page_id = self._get_page_id(tag)
            page_type = self._get_page_type(tag)

            self._pool.access(
                page_id,
                is_write=True,
                page_type=page_type,
                accessor_id=backend_id,
            )

    def mark_dirty(self, tag: PostgresBufferTag) -> None:
        """Mark buffer as dirty."""
        with self._lock:
            page_id = self._get_page_id(tag)
            self._pool.mark_dirty(page_id)

    def mark_clean(self, tag: PostgresBufferTag) -> None:
        """Mark buffer as clean after checkpoint/sync."""
        with self._lock:
            page_id = self._get_page_id(tag)
            self._pool.mark_clean(page_id)

    def pin_buffer(self, tag: PostgresBufferTag) -> bool:
        """Pin buffer (increment refcount)."""
        with self._lock:
            page_id = self._get_page_id(tag)
            return self._pool.pin_page(page_id)

    def unpin_buffer(self, tag: PostgresBufferTag) -> bool:
        """Unpin buffer (decrement refcount)."""
        with self._lock:
            page_id = self._get_page_id(tag)
            return self._pool.unpin_page(page_id)

    def get_victim(self) -> Optional[PostgresBufferTag]:
        """
        Get victim buffer for eviction.

        This is the main integration point - called by PostgreSQL's
        StrategyGetBuffer when it needs to evict a page.
        """
        with self._lock:
            victim_id = self._pool.select_victim()
            if victim_id is None:
                return None
            return self._id_to_tag.get(victim_id)

    def should_checkpoint(self) -> bool:
        """Check if checkpoint should be triggered based on dirty ratio."""
        return self._pool.should_flush()

    def get_dirty_buffers(self) -> List[PostgresBufferTag]:
        """Get all dirty buffer tags for checkpoint."""
        with self._lock:
            dirty_ids = self._pool.get_dirty_pages()
            return [
                self._id_to_tag[pid]
                for pid in dirty_ids
                if pid in self._id_to_tag
            ]

    def get_stats(self) -> Dict[str, Any]:
        """Get buffer pool statistics."""
        pool_stats = self._pool.get_stats()
        return {
            **pool_stats,
            "block_size": self.block_size,
            "registered_relations": len(self._rel_types),
        }

    def get_buffer_stats_sql(self) -> str:
        """Generate SQL-like stats output."""
        stats = self.get_stats()
        return f"""
        CTM+ Buffer Pool Statistics
        ===========================
        Hit Rate:        {stats['hit_rate']:.2%}
        Buffer Hits:     {stats['hits']:,}
        Buffer Misses:   {stats['misses']:,}
        Evictions:       {stats['evictions']:,}
        Dirty Evictions: {stats['dirty_evictions']:,}
        Prefetches:      {stats['prefetches']:,}
        Adaptive p:      {stats['adaptive_p']:.3f}
        Buffer Usage:    {stats['buffer_pages']:,} / {stats['pool_size']:,} ({stats['utilization']:.1%})
        Dirty Ratio:     {stats['dirty_ratio']:.1%}
        """


def generate_c_header() -> str:
    """
    Generate C header for PostgreSQL extension.

    This is a reference implementation showing how the C extension
    would interface with CTM+.
    """
    return '''
/*
 * ctm_plus_pg.h - CTM+ PostgreSQL Extension Header
 *
 * This header provides the interface for integrating CTM+
 * with PostgreSQL's buffer manager.
 */

#ifndef CTM_PLUS_PG_H
#define CTM_PLUS_PG_H

#include "postgres.h"
#include "storage/buf_internals.h"

/* CTM+ Configuration */
typedef struct CTMConfig {
    int32 victim_sample_size;
    float8 promotion_threshold;
    bool enable_smart_victim;
    int32 shadow_size;
    float8 dirty_page_penalty;
    float8 index_page_bonus;
} CTMConfig;

/* Initialize CTM+ buffer manager */
extern void ctm_init(int shared_buffers, CTMConfig *config);

/* Shutdown CTM+ */
extern void ctm_shutdown(void);

/* Called on buffer access */
extern void ctm_on_access(BufferTag *tag, bool is_write);

/* Select victim for eviction */
extern Buffer ctm_select_victim(void);

/* Pin/unpin buffer */
extern void ctm_pin_buffer(Buffer buf);
extern void ctm_unpin_buffer(Buffer buf);

/* Mark buffer dirty/clean */
extern void ctm_mark_dirty(Buffer buf);
extern void ctm_mark_clean(Buffer buf);

/* Get statistics */
extern void ctm_get_stats(int64 *hits, int64 *misses,
                          int64 *evictions, float8 *hit_rate);

/* GUC variables */
extern int ctm_victim_sample_size;
extern double ctm_promotion_threshold;
extern bool ctm_enable_smart_victim;

#endif /* CTM_PLUS_PG_H */
'''
