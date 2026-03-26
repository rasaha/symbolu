"""
S3-FIFO (Simple, Scalable, SOSP'23) baseline controller.

S3-FIFO uses three FIFO queues:
- Small (S): Admission filter (10% of cache)
- Main (M): Frequency-promoted pages (90% of cache)
- Ghost (G): Recently evicted from S (tracks frequency)

Only pages with freq >= 1 in S get promoted to M on eviction from S.
Pages evicted from M go to ghost or are discarded.

Reference: "FIFO Queues are All You Need for Cache Eviction"
           Yang et al., SOSP 2023
"""

from typing import Tuple
from collections import deque, defaultdict
from .base import BaseController
from ..core.state import GlobalState, Tier, OpType
from ..core.config import SimulatorConfig


class S3FIFOController(BaseController):
    """
    S3-FIFO tier controller.

    Simple, scalable, scan-resistant FIFO-based cache.
    Competitive with ARC and LRU-K with lower overhead.
    """

    def __init__(self, config: SimulatorConfig, small_ratio: float = 0.1):
        super().__init__(config)
        self._small_ratio = small_ratio
        self._reset_internal()

    def _reset_internal(self) -> None:
        c = self.config.tier0_size
        self._small_cap = max(1, int(c * self._small_ratio))
        self._main_cap = c - self._small_cap
        self._ghost_cap = c  # Ghost same size as cache

        # FIFO queues (deque: appendleft=enqueue, pop=dequeue)
        self._small: deque = deque()  # page_ids in FIFO order
        self._main: deque = deque()
        self._ghost: deque = deque()

        # Sets for O(1) membership test
        self._small_set: set = set()
        self._main_set: set = set()
        self._ghost_set: set = set()

        # Frequency counters (max 3, saturating)
        self._freq: defaultdict = defaultdict(int)

        # Stats
        self._promotions = 0
        self._demotions = 0
        self._ghost_hits = 0

    @property
    def name(self) -> str:
        return "S3-FIFO"

    def reset(self) -> None:
        self._reset_internal()

    def on_access(
        self,
        state: GlobalState,
        page_id: int,
        op_type: OpType,
        **kwargs,
    ) -> Tuple[Tier, int, bool, bool]:
        page = state.get_or_create_page(page_id)
        page.update_on_access(state.current_time, op_type)

        promoted = False
        demoted = False

        # Hit in Small queue
        if page_id in self._small_set:
            # Increment frequency (saturate at 3)
            self._freq[page_id] = min(3, self._freq[page_id] + 1)
            if state.tier0.contains(page_id):
                state.tier0.touch(page_id)
                state.tier0.record_hit()
            return (Tier.TIER0, self._compute_latency(Tier.TIER0, False, False), False, False)

        # Hit in Main queue
        if page_id in self._main_set:
            self._freq[page_id] = min(3, self._freq[page_id] + 1)
            if state.tier0.contains(page_id):
                state.tier0.touch(page_id)
                state.tier0.record_hit()
            return (Tier.TIER0, self._compute_latency(Tier.TIER0, False, False), False, False)

        # Miss — insert into Small queue
        # Check ghost hit first (indicates frequency)
        if page_id in self._ghost_set:
            self._ghost_hits += 1
            self._ghost_set.discard(page_id)
            # Remove from ghost deque (lazy — will skip missing entries on evict)
            self._freq[page_id] = min(3, self._freq[page_id] + 1)

        # Evict from Small if full
        while len(self._small) >= self._small_cap:
            demoted = self._evict_small(state) or demoted

        # Evict from Main if full
        while len(self._main) >= self._main_cap:
            demoted = self._evict_main(state) or demoted

        # Insert into Small
        self._small.appendleft(page_id)
        self._small_set.add(page_id)
        self._freq[page_id] = 0

        # Add to tier0
        if state.tier1.contains(page_id):
            state.tier1.remove(page_id)
            promoted = True
            self._promotions += 1

        evicted = state.tier0.add(page)
        if evicted is not None:
            state.tier1.add(evicted)
            demoted = True
            self._demotions += 1

        tier = Tier.TIER1 if promoted else Tier.NONE
        return (tier, self._compute_latency(tier, promoted, demoted), promoted, demoted)

    def _evict_small(self, state: GlobalState) -> bool:
        """Evict from Small queue. Promote to Main if freq > 0."""
        demoted = False
        while self._small:
            victim_id = self._small.pop()
            if victim_id not in self._small_set:
                continue  # Lazy deletion
            self._small_set.discard(victim_id)

            if self._freq.get(victim_id, 0) >= 1:
                # Promote to Main (has been re-accessed)
                self._main.appendleft(victim_id)
                self._main_set.add(victim_id)
            else:
                # Evict: add to ghost, demote from tier0
                self._add_to_ghost(victim_id)
                if state.tier0.contains(victim_id):
                    evicted_page = state.tier0.remove(victim_id)
                    if evicted_page:
                        state.tier1.add(evicted_page)
                        demoted = True
                        self._demotions += 1
                self._freq.pop(victim_id, None)
            return demoted
        return demoted

    def _evict_main(self, state: GlobalState) -> bool:
        """Evict from Main queue. Re-insert if freq > 0 (give second chance)."""
        demoted = False
        max_iters = len(self._main) + 1
        for _ in range(max_iters):
            if not self._main:
                break
            victim_id = self._main.pop()
            if victim_id not in self._main_set:
                continue

            if self._freq.get(victim_id, 0) > 0:
                # Second chance: decrement freq, re-insert
                self._freq[victim_id] = max(0, self._freq[victim_id] - 1)
                self._main.appendleft(victim_id)
            else:
                # Evict from Main
                self._main_set.discard(victim_id)
                if state.tier0.contains(victim_id):
                    evicted_page = state.tier0.remove(victim_id)
                    if evicted_page:
                        state.tier1.add(evicted_page)
                        demoted = True
                        self._demotions += 1
                self._freq.pop(victim_id, None)
                return demoted
        return demoted

    def _add_to_ghost(self, page_id: int) -> None:
        """Add to ghost queue, evicting oldest if full."""
        while len(self._ghost) >= self._ghost_cap:
            old = self._ghost.pop()
            self._ghost_set.discard(old)
        self._ghost.appendleft(page_id)
        self._ghost_set.add(page_id)

    def get_stats(self) -> dict:
        return {
            "promotions": self._promotions,
            "demotions": self._demotions,
            "ghost_hits": self._ghost_hits,
            "small_size": len(self._small),
            "main_size": len(self._main),
            "ghost_size": len(self._ghost),
        }
