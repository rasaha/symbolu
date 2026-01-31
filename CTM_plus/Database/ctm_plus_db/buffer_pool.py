"""
CTM+ Buffer Pool Manager for Database Systems.

Implements smart page eviction for database buffer pools using:
- O(k) sampled scoring for victim selection
- ARC-style shadow tiers with adaptive p
- Page type awareness (index vs heap vs dirty)
- Sequential access prefetching
"""

import random
import time
import threading
from collections import deque, OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from enum import Enum

from .config import CTMDBConfig


class PageType(Enum):
    HEAP = "heap"       # Regular data page
    INDEX = "index"     # Index/B-tree page
    TOAST = "toast"     # Large object storage
    FSM = "fsm"         # Free space map
    VM = "vm"           # Visibility map
    TEMP = "temp"       # Temporary table


@dataclass
class PageState:
    """Per-page state for CTM+ tracking."""
    page_id: int
    page_type: PageType = PageType.HEAP
    is_dirty: bool = False
    is_pinned: bool = False
    pin_count: int = 0
    last_access_time: float = 0.0
    access_count: int = 0
    reuse_score: float = 0.0
    sequential_count: int = 0  # Count of sequential accesses
    last_accessor_id: Optional[int] = None  # Transaction/connection ID

    def update_access(self, current_time: float) -> None:
        self.access_count += 1
        self.last_access_time = current_time


@dataclass
class ShadowEntry:
    """Entry in shadow tier (ghost cache)."""
    page_id: int
    evict_time: float
    was_dirty: bool
    page_type: PageType


class AccessPatternTracker:
    """Tracks page access patterns for prefetching and correlation."""

    def __init__(self, window_size: int = 32):
        self.window_size = window_size
        self.access_history: deque = deque(maxlen=window_size * 10)
        self.transitions: Dict[int, Dict[int, int]] = {}
        self.last_page: Optional[int] = None
        self.sequential_runs: Dict[int, int] = {}  # page_id -> sequential count

    def record_access(self, page_id: int) -> Tuple[bool, int]:
        """
        Record page access.

        Returns:
            (is_sequential, run_length): Whether this is a sequential access
            and the current run length.
        """
        self.access_history.append(page_id)

        is_sequential = False
        run_length = 1

        if self.last_page is not None:
            # Check if sequential (adjacent page IDs)
            if abs(page_id - self.last_page) == 1:
                is_sequential = True
                run_length = self.sequential_runs.get(self.last_page, 1) + 1
                self.sequential_runs[page_id] = run_length
            else:
                self.sequential_runs[page_id] = 1

            # Record transition
            if self.last_page != page_id:
                if self.last_page not in self.transitions:
                    self.transitions[self.last_page] = {}
                self.transitions[self.last_page][page_id] = (
                    self.transitions[self.last_page].get(page_id, 0) + 1
                )

        self.last_page = page_id
        return is_sequential, run_length

    def predict_next(self, page_id: int, k: int = 8) -> List[int]:
        """Predict next k pages likely to be accessed."""
        predictions = []

        # Sequential prediction
        for i in range(1, k + 1):
            predictions.append(page_id + i)

        # Transition-based prediction
        if page_id in self.transitions:
            successors = self.transitions[page_id]
            sorted_successors = sorted(
                successors.items(), key=lambda x: -x[1]
            )[:k]
            for pred_id, _ in sorted_successors:
                if pred_id not in predictions:
                    predictions.append(pred_id)

        return predictions[:k]

    def get_correlation_score(self, page_id: int, buffer_pages: Set[int]) -> float:
        """Get score based on correlation with buffered pages."""
        if page_id not in self.transitions:
            return 0.0

        neighbors = self.transitions.get(page_id, {})
        if not neighbors:
            return 0.0

        total = sum(neighbors.values())
        buffered_weight = sum(
            count for pid, count in neighbors.items() if pid in buffer_pages
        )
        return buffered_weight / total if total > 0 else 0.0


class DualShadowTier:
    """ARC-style dual shadow tiers for adaptive buffer management."""

    def __init__(self, max_size: int = 2048):
        self.max_size = max_size
        self.b1: OrderedDict[int, ShadowEntry] = OrderedDict()  # Recent evictions
        self.b2: OrderedDict[int, ShadowEntry] = OrderedDict()  # Frequent evictions
        self.p: float = 0.5  # Adaptive partition parameter

    def record_eviction(
        self,
        page_id: int,
        was_dirty: bool,
        page_type: PageType,
        current_time: float,
        from_recent: bool = True,
    ) -> None:
        """Record eviction to appropriate shadow tier."""
        entry = ShadowEntry(page_id, current_time, was_dirty, page_type)

        target = self.b1 if from_recent else self.b2
        if len(target) >= self.max_size:
            target.popitem(last=False)
        target[page_id] = entry

    def check_and_adapt(self, page_id: int, learning_rate: float) -> Optional[str]:
        """Check if page is in shadow tier and adapt p."""
        if page_id in self.b1:
            # Hit in B1: increase p (favor recency)
            delta = learning_rate * (
                1.0 if len(self.b2) == 0 else len(self.b1) / len(self.b2)
            )
            self.p = min(1.0, self.p + delta)
            del self.b1[page_id]
            return "b1"
        elif page_id in self.b2:
            # Hit in B2: decrease p (favor frequency)
            delta = learning_rate * (
                1.0 if len(self.b1) == 0 else len(self.b2) / len(self.b1)
            )
            self.p = max(0.0, self.p - delta)
            del self.b2[page_id]
            return "b2"
        return None


class CTMBufferPool:
    """
    CTM+ Buffer Pool Manager for database systems.

    Provides intelligent page eviction that outperforms LRU
    on typical database workloads.
    """

    def __init__(
        self,
        pool_size_pages: int,
        page_size_bytes: int = 8192,
        config: Optional[CTMDBConfig] = None,
    ):
        """
        Initialize buffer pool.

        Args:
            pool_size_pages: Maximum pages in buffer pool.
            page_size_bytes: Size of each page in bytes.
            config: CTM+ configuration.
        """
        self.config = config or CTMDBConfig()
        self.pool_size = pool_size_pages
        self.page_size = page_size_bytes

        self.pages: Dict[int, PageState] = {}
        self.buffer_pages: Set[int] = set()

        self.pattern_tracker = AccessPatternTracker(self.config.neighbor_window)
        self.shadow_tier = DualShadowTier(self.config.shadow_size)
        self.shadow_tier.p = self.config.initial_p

        self.access_counter = 0
        self._lock = threading.RLock()

        # Prefetch queue
        self.prefetch_queue: deque = deque()

        # Callbacks
        self.on_evict: Optional[Callable[[int, bool], None]] = None  # page_id, is_dirty
        self.on_prefetch: Optional[Callable[[int], None]] = None

        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "dirty_evictions": 0,
            "prefetches": 0,
            "smart_selections": 0,
        }

    def access(
        self,
        page_id: int,
        is_write: bool = False,
        page_type: PageType = PageType.HEAP,
        accessor_id: Optional[int] = None,
    ) -> Tuple[bool, List[int]]:
        """
        Access a page.

        Args:
            page_id: Page identifier.
            is_write: Whether this is a write access.
            page_type: Type of page being accessed.
            accessor_id: Transaction or connection ID.

        Returns:
            (is_hit, prefetch_list): Whether page was in buffer,
            and list of pages to prefetch.
        """
        with self._lock:
            current_time = time.monotonic()
            self.access_counter += 1

            # Track pattern
            is_sequential, seq_length = self.pattern_tracker.record_access(page_id)

            # Check shadow tier for adaptation
            self.shadow_tier.check_and_adapt(
                page_id, self.config.adaptive_p_learning_rate
            )

            is_hit = page_id in self.buffer_pages
            prefetch_list = []

            if is_hit:
                # Buffer hit
                self.stats["hits"] += 1
                page = self.pages[page_id]
                page.update_access(current_time)
                if is_write:
                    page.is_dirty = True
                page.sequential_count = seq_length
                page.last_accessor_id = accessor_id

            else:
                # Buffer miss
                self.stats["misses"] += 1

                # Make space if needed
                if len(self.buffer_pages) >= self.pool_size:
                    self._evict_page()

                # Add page to buffer
                page = PageState(
                    page_id=page_id,
                    page_type=page_type,
                    is_dirty=is_write,
                    last_access_time=current_time,
                    access_count=1,
                    sequential_count=seq_length,
                    last_accessor_id=accessor_id,
                )
                self.pages[page_id] = page
                self.buffer_pages.add(page_id)

            # Handle prefetching
            if self.config.prefetch_enabled and is_sequential:
                if seq_length >= self.config.sequential_threshold:
                    prefetch_list = self._get_prefetch_pages(page_id)

            return is_hit, prefetch_list

    def _get_prefetch_pages(self, page_id: int) -> List[int]:
        """Get pages to prefetch based on current access."""
        predictions = self.pattern_tracker.predict_next(
            page_id, self.config.prefetch_distance
        )

        to_prefetch = []
        for pred_id in predictions:
            if pred_id not in self.buffer_pages and pred_id not in self.prefetch_queue:
                to_prefetch.append(pred_id)
                self.prefetch_queue.append(pred_id)
                self.stats["prefetches"] += 1

                if self.on_prefetch:
                    self.on_prefetch(pred_id)

        return to_prefetch

    def select_victim(self) -> Optional[int]:
        """
        Select victim page for eviction.

        Returns:
            Page ID to evict, or None if buffer is empty.
        """
        with self._lock:
            if not self.buffer_pages:
                return None

            if not self.config.enable_smart_victim:
                return self._select_lru_victim()

            self.stats["smart_selections"] += 1
            return self._select_smart_victim()

    def _select_lru_victim(self) -> Optional[int]:
        """Select victim using simple LRU."""
        oldest_time = float('inf')
        victim = None

        for page_id in self.buffer_pages:
            page = self.pages[page_id]
            if page.is_pinned or page.pin_count > 0:
                continue
            if page.last_access_time < oldest_time:
                oldest_time = page.last_access_time
                victim = page_id

        return victim

    def _select_smart_victim(self) -> Optional[int]:
        """Select victim using CTM+ scoring."""
        candidates = [
            pid for pid in self.buffer_pages
            if not self.pages[pid].is_pinned and self.pages[pid].pin_count == 0
        ]

        if not candidates:
            return None

        n = len(candidates)
        sample_size = min(self.config.victim_sample_size, n)
        if sample_size < n:
            sampled = random.sample(candidates, sample_size)
        else:
            sampled = candidates

        # Always include LRU as baseline
        lru_victim = self._select_lru_victim()
        if lru_victim and lru_victim not in sampled:
            sampled.append(lru_victim)

        # Compute time range
        times = [self.pages[pid].last_access_time for pid in sampled]
        min_time = min(times)
        max_time = max(times)
        time_range = max_time - min_time if max_time > min_time else 1.0

        # Score candidates
        best_victim = None
        best_score = float('inf')
        adaptive_p = self.shadow_tier.p

        for page_id in sampled:
            score = self._compute_victim_score(
                page_id, min_time, time_range, adaptive_p
            )
            if score < best_score:
                best_score = score
                best_victim = page_id

        return best_victim or lru_victim

    def _compute_victim_score(
        self,
        page_id: int,
        min_time: float,
        time_range: float,
        adaptive_p: float,
    ) -> float:
        """Compute victim score (lower = evict first)."""
        page = self.pages[page_id]

        # Recency [0, 1]
        recency = (page.last_access_time - min_time) / time_range

        # Frequency
        frequency = min(page.access_count * 0.1, 1.0)

        # Reuse score from transitions
        reuse = page.reuse_score

        # Correlation with other buffered pages
        correlation = self.pattern_tracker.get_correlation_score(
            page_id, self.buffer_pages
        )

        # Page type bonus/penalty
        page_type_score = 0.0
        if page.page_type == PageType.INDEX:
            page_type_score = self.config.index_page_bonus
        elif page.is_dirty:
            page_type_score = self.config.dirty_page_penalty

        # Weighted score
        score = (
            self.config.weight_recency * recency +
            self.config.weight_frequency * frequency +
            self.config.weight_reuse * reuse +
            self.config.weight_correlation * correlation +
            self.config.weight_page_type * page_type_score
        )

        # Partition penalty based on adaptive p
        if adaptive_p > 0.5 and frequency < 0.3:
            score -= 0.10 * (adaptive_p - 0.5) * 2.0
        elif adaptive_p < 0.5 and recency < 0.3:
            score -= 0.10 * (0.5 - adaptive_p) * 2.0

        return score

    def _evict_page(self) -> Optional[int]:
        """Evict a page from buffer."""
        victim_id = self.select_victim()
        if victim_id is None:
            return None

        page = self.pages[victim_id]

        # Record in shadow tier
        self.shadow_tier.record_eviction(
            victim_id,
            was_dirty=page.is_dirty,
            page_type=page.page_type,
            current_time=time.monotonic(),
            from_recent=(page.access_count <= 2),
        )

        # Update stats
        self.stats["evictions"] += 1
        if page.is_dirty:
            self.stats["dirty_evictions"] += 1

        # Callback
        if self.on_evict:
            self.on_evict(victim_id, page.is_dirty)

        # Remove from buffer
        self.buffer_pages.remove(victim_id)
        del self.pages[victim_id]

        return victim_id

    def pin_page(self, page_id: int) -> bool:
        """Pin page to prevent eviction."""
        with self._lock:
            if page_id in self.pages:
                self.pages[page_id].pin_count += 1
                return True
            return False

    def unpin_page(self, page_id: int) -> bool:
        """Unpin page to allow eviction."""
        with self._lock:
            if page_id in self.pages:
                self.pages[page_id].pin_count = max(0, self.pages[page_id].pin_count - 1)
                return True
            return False

    def mark_dirty(self, page_id: int) -> bool:
        """Mark page as dirty."""
        with self._lock:
            if page_id in self.pages:
                self.pages[page_id].is_dirty = True
                return True
            return False

    def mark_clean(self, page_id: int) -> bool:
        """Mark page as clean (after write-back)."""
        with self._lock:
            if page_id in self.pages:
                self.pages[page_id].is_dirty = False
                return True
            return False

    def get_dirty_pages(self) -> List[int]:
        """Get list of dirty page IDs."""
        with self._lock:
            return [pid for pid, page in self.pages.items() if page.is_dirty]

    def get_dirty_ratio(self) -> float:
        """Get ratio of dirty pages."""
        with self._lock:
            if not self.pages:
                return 0.0
            dirty_count = sum(1 for page in self.pages.values() if page.is_dirty)
            return dirty_count / len(self.pages)

    def should_flush(self) -> bool:
        """Check if buffer should be flushed based on dirty ratio."""
        return self.get_dirty_ratio() >= self.config.lazy_write_threshold

    def get_stats(self) -> Dict[str, Any]:
        """Get buffer pool statistics."""
        with self._lock:
            total = self.stats["hits"] + self.stats["misses"]
            return {
                **self.stats,
                "total_accesses": total,
                "hit_rate": self.stats["hits"] / total if total > 0 else 0.0,
                "adaptive_p": self.shadow_tier.p,
                "buffer_pages": len(self.buffer_pages),
                "pool_size": self.pool_size,
                "utilization": len(self.buffer_pages) / self.pool_size,
                "dirty_ratio": self.get_dirty_ratio(),
            }

    def reset_stats(self) -> None:
        """Reset statistics."""
        with self._lock:
            for key in self.stats:
                self.stats[key] = 0
