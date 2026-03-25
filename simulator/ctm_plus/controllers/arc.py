"""
ARC (Adaptive Replacement Cache) baseline controller.

ARC is a self-tuning cache that balances between:
- Recency (LRU-like behavior)
- Frequency (LFU-like behavior)

It maintains ghost lists to track recently evicted pages and
adaptively adjusts the balance between recency and frequency.

Reference: "ARC: A Self-Tuning, Low Overhead Replacement Cache"
           Megiddo & Modha, FAST 2003
"""

from typing import Tuple, Optional, Set
from collections import OrderedDict
from .base import BaseController
from ..core.state import GlobalState, PageState, Tier, OpType
from ..core.config import SimulatorConfig


class ARCController(BaseController):
    """
    ARC-based tier controller.

    Maintains four lists:
    - T1: Recent pages (seen once recently)
    - T2: Frequent pages (seen at least twice recently)
    - B1: Ghost list for T1 (recently evicted from T1)
    - B2: Ghost list for T2 (recently evicted from T2)

    The parameter p controls the target size of T1 (vs T2).
    p is adapted based on hits in ghost lists.
    """

    def __init__(self, config: SimulatorConfig):
        super().__init__(config)
        self._reset_internal()

    def _reset_internal(self) -> None:
        """Reset internal ARC state."""
        # T1: Pages seen once recently (recency)
        self._t1: OrderedDict = OrderedDict()
        # T2: Pages seen twice+ recently (frequency)
        self._t2: OrderedDict = OrderedDict()
        # B1: Ghost entries for recently evicted T1 pages
        self._b1: OrderedDict = OrderedDict()
        # B2: Ghost entries for recently evicted T2 pages
        self._b2: OrderedDict = OrderedDict()

        # Target size for T1 (adaptive)
        self._p: float = 0.0

        # Stats
        self._promotions = 0
        self._demotions = 0
        self._b1_hits = 0
        self._b2_hits = 0

    @property
    def name(self) -> str:
        return "ARC"

    @property
    def _c(self) -> int:
        """Cache capacity (tier0 size)."""
        return self.config.tier0_size

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

        # Case I: Page in T1 or T2 (cache hit)
        if page_id in self._t1:
            # Move from T1 to T2 (now frequent)
            del self._t1[page_id]
            self._t2[page_id] = True
            self._move_to_end(self._t2, page_id)

            if state.tier0.contains(page_id):
                state.tier0.touch(page_id)
                state.tier0.record_hit()
                return (Tier.TIER0, self._compute_latency(Tier.TIER0, False, False), False, False)

        if page_id in self._t2:
            # Already in T2, just touch
            self._move_to_end(self._t2, page_id)

            if state.tier0.contains(page_id):
                state.tier0.touch(page_id)
                state.tier0.record_hit()
                return (Tier.TIER0, self._compute_latency(Tier.TIER0, False, False), False, False)

        # Case II: Page in B1 (ghost hit - was recently evicted from T1)
        if page_id in self._b1:
            self._b1_hits += 1
            # Adapt: favor recency more
            delta = max(1.0, len(self._b2) / max(1, len(self._b1)))
            self._p = min(self._c, self._p + delta)

            # Remove from ghost list
            del self._b1[page_id]

            # Replace and add to T2
            demoted = self._replace(state, page_id, in_b2=False)
            self._t2[page_id] = True

            # Promote to tier0
            if state.tier1.contains(page_id):
                state.tier1.remove(page_id)
            evicted = state.tier0.add(page)
            promoted = True
            self._promotions += 1

            if evicted is not None:
                state.tier1.add(evicted)
                demoted = True
                self._demotions += 1

            return (Tier.TIER1, self._compute_latency(Tier.TIER1, promoted, demoted), promoted, demoted)

        # Case III: Page in B2 (ghost hit - was recently evicted from T2)
        if page_id in self._b2:
            self._b2_hits += 1
            # Adapt: favor frequency more
            delta = max(1.0, len(self._b1) / max(1, len(self._b2)))
            self._p = max(0, self._p - delta)

            # Remove from ghost list
            del self._b2[page_id]

            # Replace and add to T2
            demoted = self._replace(state, page_id, in_b2=True)
            self._t2[page_id] = True

            # Promote to tier0
            if state.tier1.contains(page_id):
                state.tier1.remove(page_id)
            evicted = state.tier0.add(page)
            promoted = True
            self._promotions += 1

            if evicted is not None:
                state.tier1.add(evicted)
                demoted = True
                self._demotions += 1

            return (Tier.TIER1, self._compute_latency(Tier.TIER1, promoted, demoted), promoted, demoted)

        # Case IV: Cache miss (not in T1, T2, B1, or B2)
        tier = Tier.NONE

        # Manage list sizes
        if len(self._t1) + len(self._b1) == self._c:
            if len(self._t1) < self._c:
                # Remove oldest from B1
                if self._b1:
                    oldest = next(iter(self._b1))
                    del self._b1[oldest]
                demoted = self._replace(state, page_id, in_b2=False)
            else:
                # T1 is full, evict from T1
                if self._t1:
                    oldest = next(iter(self._t1))
                    del self._t1[oldest]
                    if state.tier0.contains(oldest):
                        evicted_page = state.tier0.remove(oldest)
                        if evicted_page:
                            state.tier1.add(evicted_page)
                            demoted = True
                            self._demotions += 1
        elif len(self._t1) + len(self._t2) + len(self._b1) + len(self._b2) >= self._c:
            if len(self._t1) + len(self._t2) + len(self._b1) + len(self._b2) == 2 * self._c:
                # Remove oldest from B2
                if self._b2:
                    oldest = next(iter(self._b2))
                    del self._b2[oldest]
            demoted = self._replace(state, page_id, in_b2=False) or demoted

        # Add to T1
        self._t1[page_id] = True

        # Add to tier0 or tier1
        if not state.tier0.is_full:
            state.tier0.add(page)
        else:
            evicted = state.tier0.add(page)
            if evicted is not None:
                state.tier1.add(evicted)
                demoted = True
                self._demotions += 1
            promoted = True
            self._promotions += 1

        return (tier, self._compute_latency(tier, promoted, demoted), promoted, demoted)

    def _replace(self, state: GlobalState, page_id: int, in_b2: bool) -> bool:
        """
        Replace a page in the cache.

        Returns True if a demotion occurred.
        """
        demoted = False

        if self._t1 and (
            (in_b2 and len(self._t1) == int(self._p))
            or len(self._t1) > int(self._p)
        ):
            # Evict from T1, add to B1
            oldest = next(iter(self._t1))
            del self._t1[oldest]
            self._b1[oldest] = True

            # Demote from tier0
            if state.tier0.contains(oldest):
                evicted_page = state.tier0.remove(oldest)
                if evicted_page:
                    state.tier1.add(evicted_page)
                    demoted = True
                    self._demotions += 1
        elif self._t2:
            # Evict from T2, add to B2
            oldest = next(iter(self._t2))
            del self._t2[oldest]
            self._b2[oldest] = True

            # Demote from tier0
            if state.tier0.contains(oldest):
                evicted_page = state.tier0.remove(oldest)
                if evicted_page:
                    state.tier1.add(evicted_page)
                    demoted = True
                    self._demotions += 1

        return demoted

    def _move_to_end(self, d: OrderedDict, key: int) -> None:
        """Move key to end of ordered dict (MRU position)."""
        if key in d:
            d.move_to_end(key)

    def get_stats(self) -> dict:
        return {
            "promotions": self._promotions,
            "demotions": self._demotions,
            "p": self._p,
            "t1_size": len(self._t1),
            "t2_size": len(self._t2),
            "b1_size": len(self._b1),
            "b2_size": len(self._b2),
            "b1_hits": self._b1_hits,
            "b2_hits": self._b2_hits,
        }
