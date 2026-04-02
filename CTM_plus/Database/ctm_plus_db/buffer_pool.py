"""
Adaptive eviction policy with sampled multi-signal scoring.

This is a Python eviction policy for research and benchmarking.
It does NOT implement a real database buffer pool or storage system.
It makes eviction decisions only — it does not manage memory, I/O, or pages.

Algorithm:
    Sampled ARC variant with 4-signal weighted scoring.
    On eviction, sample k candidates and score them by:
      1. Recency  — normalized time since last access
      2. Frequency — saturated access count
      3. Correlation — transition affinity with buffered pages
      4. Page type — bonus for index pages, penalty for dirty pages
    ARC-style dual ghost caches (B1/B2) adapt the recency/frequency balance.

Not thread-safe. Callers must synchronize externally if needed.
"""

import random
import time
from collections import deque, OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from enum import Enum

from .config import EvictionConfig


class PageType(Enum):
    HEAP = "heap"
    INDEX = "index"
    TEMP = "temp"


@dataclass
class PageState:
    """Per-page metadata tracked by the eviction policy."""
    page_id: int
    page_type: PageType = PageType.HEAP
    is_dirty: bool = False
    pin_count: int = 0
    last_access_time: float = 0.0
    access_count: int = 0
    sequential_count: int = 0


@dataclass
class ShadowEntry:
    """Ghost cache entry — records metadata of evicted pages."""
    page_id: int
    evict_time: float
    was_dirty: bool
    page_type: PageType


class AccessPatternTracker:
    """
    Tracks page access patterns for sequential detection and correlation scoring.

    The transitions dict is bounded to max_tracked_pages entries.
    When full, the oldest entries are evicted via FIFO (OrderedDict).
    """

    def __init__(self, window_size: int = 32, max_tracked_pages: int = 8192):
        self.window_size = window_size
        self.max_tracked_pages = max_tracked_pages
        self.transitions: OrderedDict[int, Dict[int, int]] = OrderedDict()
        self.last_page: Optional[int] = None
        self._sequential_run: int = 0

    def record_access(self, page_id: int) -> Tuple[bool, int]:
        """
        Record page access. Returns (is_sequential, run_length).
        """
        is_sequential = False

        if self.last_page is not None and abs(page_id - self.last_page) == 1:
            is_sequential = True
            self._sequential_run += 1
        else:
            self._sequential_run = 1

        # Record transition (bounded)
        if self.last_page is not None and self.last_page != page_id:
            if self.last_page not in self.transitions:
                # Evict oldest if at capacity
                if len(self.transitions) >= self.max_tracked_pages:
                    self.transitions.popitem(last=False)
                self.transitions[self.last_page] = {}
            neighbors = self.transitions[self.last_page]
            neighbors[page_id] = neighbors.get(page_id, 0) + 1
            # Cap neighbor count per page to prevent unbounded inner dicts
            if len(neighbors) > self.window_size:
                # Remove least-frequent neighbor
                min_key = min(neighbors, key=neighbors.get)
                del neighbors[min_key]

        self.last_page = page_id
        return is_sequential, self._sequential_run

    def predict_next(self, page_id: int, k: int = 8) -> List[int]:
        """Predict next k pages likely to be accessed (sequential + transition)."""
        predictions = list(range(page_id + 1, page_id + k + 1))

        if page_id in self.transitions:
            successors = sorted(
                self.transitions[page_id].items(), key=lambda x: -x[1]
            )[:k]
            for pred_id, _ in successors:
                if pred_id not in predictions:
                    predictions.append(pred_id)

        return predictions[:k]

    def get_correlation_score(self, page_id: int, buffer_pages: Set[int]) -> float:
        """Score based on transition affinity with currently buffered pages."""
        neighbors = self.transitions.get(page_id)
        if not neighbors:
            return 0.0

        total = sum(neighbors.values())
        buffered_weight = sum(
            count for pid, count in neighbors.items() if pid in buffer_pages
        )
        return buffered_weight / total if total > 0 else 0.0


class DualShadowTier:
    """ARC-style dual ghost caches for adaptive recency/frequency balance."""

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
        entry = ShadowEntry(page_id, current_time, was_dirty, page_type)
        target = self.b1 if from_recent else self.b2
        if len(target) >= self.max_size:
            target.popitem(last=False)
        target[page_id] = entry

    def check_and_adapt(self, page_id: int, learning_rate: float) -> Optional[str]:
        """If page is in a ghost cache, adapt p and return which one."""
        if page_id in self.b1:
            delta = learning_rate * (
                1.0 if len(self.b2) == 0 else len(self.b1) / len(self.b2)
            )
            self.p = min(1.0, self.p + delta)
            del self.b1[page_id]
            return "b1"
        elif page_id in self.b2:
            delta = learning_rate * (
                1.0 if len(self.b1) == 0 else len(self.b2) / len(self.b1)
            )
            self.p = max(0.0, self.p - delta)
            del self.b2[page_id]
            return "b2"
        return None


class AdaptiveEvictionPolicy:
    """
    Sampled multi-signal eviction policy with ARC-style adaptation.

    This is a research/benchmarking tool. It tracks page metadata and makes
    eviction decisions. It does not manage actual page memory or I/O.

    Victim selection: sample k candidates, score by weighted signals,
    evict lowest scorer. ARC ghost caches adapt recency/frequency balance.

    Not thread-safe. Callers must synchronize externally.
    """

    EVICTION_BATCH_SIZE = 64
    EVICTION_THRESHOLD = 0.95
    MAINTENANCE_INTERVAL = 1000
    K_CANDIDATES = 32

    def __init__(
        self,
        capacity: int,
        config: Optional[EvictionConfig] = None,
    ):
        """
        Args:
            capacity: Maximum number of pages tracked.
            config: Scoring weights and behavior config.
        """
        self.config = config or EvictionConfig()
        self.capacity = capacity

        self.pages: Dict[int, PageState] = {}
        self.pinned_pages: Set[int] = set()

        self.pattern_tracker = AccessPatternTracker(
            window_size=self.config.neighbor_window,
            max_tracked_pages=min(capacity * 2, 16384),
        )
        self.shadow_tier = DualShadowTier(self.config.shadow_size)
        self.shadow_tier.p = self.config.initial_p

        self._access_counter = 0

        # Stratified candidate pools (rebuilt periodically)
        self._lru_candidates: List[int] = []
        self._lfu_candidates: List[int] = []
        self._clean_candidates: List[int] = []

        # Callbacks
        self.on_evict: Optional[Callable[[int, bool], None]] = None
        self.on_prefetch: Optional[Callable[[int], None]] = None

        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "dirty_evictions": 0,
            "prefetches": 0,
        }

    def access(
        self,
        page_id: int,
        is_write: bool = False,
        page_type: PageType = PageType.HEAP,
    ) -> Tuple[bool, List[int]]:
        """
        Record a page access. Evicts if over capacity.

        Returns:
            (is_hit, prefetch_list)
        """
        current_time = time.monotonic()
        self._access_counter += 1

        is_sequential, seq_length = self.pattern_tracker.record_access(page_id)
        self.shadow_tier.check_and_adapt(page_id, self.config.adaptive_p_learning_rate)

        is_hit = page_id in self.pages
        prefetch_list: List[int] = []

        if is_hit:
            self.stats["hits"] += 1
            page = self.pages[page_id]
            page.access_count += 1
            page.last_access_time = current_time
            if is_write:
                page.is_dirty = True
            page.sequential_count = seq_length
        else:
            self.stats["misses"] += 1

            # Batch eviction at threshold
            if len(self.pages) >= int(self.capacity * self.EVICTION_THRESHOLD):
                self._batch_evict()

            # Single eviction fallback
            while len(self.pages) >= self.capacity:
                self._evict_one()

            self.pages[page_id] = PageState(
                page_id=page_id,
                page_type=page_type,
                is_dirty=is_write,
                last_access_time=current_time,
                access_count=1,
                sequential_count=seq_length,
            )

        # Prefetch hints
        if self.config.prefetch_enabled and is_sequential:
            if seq_length >= self.config.sequential_threshold:
                prefetch_list = self._get_prefetch_hints(page_id)

        # Periodic maintenance (rebuild candidate pools)
        if self._access_counter % self.MAINTENANCE_INTERVAL == 0:
            self._rebuild_candidate_pools()

        return is_hit, prefetch_list

    def select_victim(self) -> Optional[int]:
        """Select a page to evict. Returns page_id or None."""
        if not self.pages:
            return None
        if not self.config.enable_smart_victim:
            return self._select_lru_victim()
        return self._select_scored_victim()

    def pin(self, page_id: int) -> bool:
        if page_id in self.pages:
            self.pages[page_id].pin_count += 1
            self.pinned_pages.add(page_id)
            return True
        return False

    def unpin(self, page_id: int) -> bool:
        if page_id in self.pages:
            self.pages[page_id].pin_count = max(0, self.pages[page_id].pin_count - 1)
            if self.pages[page_id].pin_count == 0:
                self.pinned_pages.discard(page_id)
            return True
        return False

    def mark_dirty(self, page_id: int) -> bool:
        if page_id in self.pages:
            self.pages[page_id].is_dirty = True
            return True
        return False

    def mark_clean(self, page_id: int) -> bool:
        if page_id in self.pages:
            self.pages[page_id].is_dirty = False
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        total = self.stats["hits"] + self.stats["misses"]
        return {
            **self.stats,
            "total_accesses": total,
            "hit_rate": self.stats["hits"] / total if total > 0 else 0.0,
            "adaptive_p": self.shadow_tier.p,
            "current_pages": len(self.pages),
            "capacity": self.capacity,
            "utilization": len(self.pages) / self.capacity if self.capacity > 0 else 0.0,
            "pinned_pages": len(self.pinned_pages),
        }

    def reset_stats(self) -> None:
        for key in self.stats:
            self.stats[key] = 0

    # ---- Internal ----

    def _batch_evict(self) -> List[int]:
        """Evict a batch of pages using sampled scoring."""
        # Gather candidates from stratified pools + random sample
        pool_candidates: Set[int] = set()
        k = self.K_CANDIDATES
        per_pool = max(1, k // 3)

        for pool in [self._lru_candidates, self._lfu_candidates, self._clean_candidates]:
            for pid in pool[:per_pool]:
                if pid in self.pages and pid not in self.pinned_pages:
                    pool_candidates.add(pid)

        # Random sample to fill remaining
        unpinned = [p for p in self.pages if p not in self.pinned_pages]
        if len(unpinned) > k:
            for pid in random.sample(unpinned, k):
                pool_candidates.add(pid)
        else:
            pool_candidates.update(unpinned)

        # Score and sort
        scored = self._score_batch(list(pool_candidates))
        scored.sort(key=lambda x: x[1])

        evicted = []
        for pid, _ in scored[:self.EVICTION_BATCH_SIZE]:
            if pid in self.pages:
                self._do_evict(pid)
                evicted.append(pid)
        return evicted

    def _evict_one(self) -> Optional[int]:
        """Evict a single page via select_victim."""
        victim_id = self.select_victim()
        if victim_id is None:
            return None
        self._do_evict(victim_id)
        return victim_id

    def _do_evict(self, page_id: int) -> None:
        """Remove a page and record in ghost cache."""
        page = self.pages[page_id]

        self.shadow_tier.record_eviction(
            page_id,
            was_dirty=page.is_dirty,
            page_type=page.page_type,
            current_time=time.monotonic(),
            from_recent=(page.access_count <= 2),
        )

        self.stats["evictions"] += 1
        if page.is_dirty:
            self.stats["dirty_evictions"] += 1

        if self.on_evict:
            self.on_evict(page_id, page.is_dirty)

        self.pinned_pages.discard(page_id)
        del self.pages[page_id]

    def _select_lru_victim(self) -> Optional[int]:
        """O(n) LRU fallback — scans all pages."""
        oldest_time = float('inf')
        victim = None
        for page_id, page in self.pages.items():
            if page.pin_count > 0:
                continue
            if page.last_access_time < oldest_time:
                oldest_time = page.last_access_time
                victim = page_id
        return victim

    def _select_scored_victim(self) -> Optional[int]:
        """Sample k unpinned pages, score them, return lowest."""
        unpinned = [p for p in self.pages if p not in self.pinned_pages]
        if not unpinned:
            return None

        sample_size = min(self.config.victim_sample_size, len(unpinned))
        sampled = random.sample(unpinned, sample_size) if sample_size < len(unpinned) else unpinned

        scored = self._score_batch(sampled)
        if not scored:
            return None

        return min(scored, key=lambda x: x[1])[0]

    def _score_batch(self, candidates: List[int]) -> List[Tuple[int, float]]:
        """Score multiple candidates. O(k)."""
        if not candidates:
            return []

        times = [self.pages[pid].last_access_time for pid in candidates if pid in self.pages]
        if not times:
            return []

        min_time = min(times)
        max_time = max(times)
        time_range = max(max_time - min_time, 0.001)
        adaptive_p = self.shadow_tier.p
        current_pages = set(self.pages.keys())

        scored = []
        for page_id in candidates:
            if page_id not in self.pages:
                continue
            page = self.pages[page_id]

            # Signal 1: Recency [0, 1]
            recency = (page.last_access_time - min_time) / time_range

            # Signal 2: Frequency [0, 1]
            frequency = min(page.access_count * 0.1, 1.0)

            # Signal 3: Correlation with buffered pages
            correlation = self.pattern_tracker.get_correlation_score(
                page_id, current_pages
            )

            # Signal 4: Page type bonus/penalty
            page_type_score = 0.0
            if page.page_type == PageType.INDEX:
                page_type_score = self.config.index_page_bonus
            elif page.is_dirty:
                page_type_score = self.config.dirty_page_penalty

            score = (
                self.config.weight_recency * recency +
                self.config.weight_frequency * frequency +
                self.config.weight_correlation * correlation +
                self.config.weight_page_type * page_type_score
            )

            # ARC adaptive penalty
            if adaptive_p > 0.5 and frequency < 0.3:
                score -= 0.10 * (adaptive_p - 0.5) * 2.0
            elif adaptive_p < 0.5 and recency < 0.3:
                score -= 0.10 * (0.5 - adaptive_p) * 2.0

            scored.append((page_id, score))

        return scored

    def _rebuild_candidate_pools(self) -> None:
        """
        Rebuild stratified candidate pools. O(n) but runs infrequently
        (every MAINTENANCE_INTERVAL accesses).

        Uses partial sort (heapq.nsmallest) instead of full sort for efficiency,
        but for simplicity with bounded k we just sort — k << n.
        """
        unpinned = [p for p in self.pages if p not in self.pinned_pages]
        if not unpinned:
            self._lru_candidates = []
            self._lfu_candidates = []
            self._clean_candidates = []
            return

        k = self.K_CANDIDATES

        # Oldest by access time
        self._lru_candidates = sorted(
            unpinned, key=lambda p: self.pages[p].last_access_time
        )[:k]

        # Lowest frequency
        self._lfu_candidates = sorted(
            unpinned, key=lambda p: self.pages[p].access_count
        )[:k]

        # Clean pages, oldest first
        clean = [p for p in unpinned if not self.pages[p].is_dirty]
        self._clean_candidates = sorted(
            clean, key=lambda p: self.pages[p].last_access_time
        )[:k]

    def _get_prefetch_hints(self, page_id: int) -> List[int]:
        """Return page IDs that should be prefetched."""
        predictions = self.pattern_tracker.predict_next(
            page_id, self.config.prefetch_distance
        )
        hints = [p for p in predictions if p not in self.pages]

        self.stats["prefetches"] += len(hints)
        if self.on_prefetch:
            for pid in hints:
                self.on_prefetch(pid)

        return hints
