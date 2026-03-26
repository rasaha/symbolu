"""
LRU (Least Recently Used) baseline controller.

This is the standard baseline for cache/tier management:
- Promote on access (if room in tier0)
- Evict LRU page when tier is full
- No intelligence beyond recency

This provides the baseline to beat for CTM+.
"""

from typing import Tuple
from .base import BaseController
from ..core.state import GlobalState, Tier, OpType
from ..core.config import SimulatorConfig


class LRUController(BaseController):
    """
    LRU-based tier controller.

    Policy:
    - If page is in tier0: hit, update LRU position
    - If page is in tier1: promote to tier0 (evict LRU from tier0 if full)
    - If page is not in any tier: add to tier0 (or tier1 if tier0 full)
    """

    def __init__(self, config: SimulatorConfig, promote_on_first_access: bool = True):
        """
        Initialize LRU controller.

        Args:
            config: Simulator configuration
            promote_on_first_access: If True, new pages go to tier0; if False, tier1
        """
        super().__init__(config)
        self.promote_on_first_access = promote_on_first_access
        self._promotions = 0
        self._demotions = 0

    @property
    def name(self) -> str:
        return "LRU"

    def reset(self) -> None:
        self._promotions = 0
        self._demotions = 0

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

        # Case 1: Page is in tier0 (fast tier hit)
        if state.tier0.contains(page_id):
            state.tier0.touch(page_id)
            state.tier0.record_hit()
            latency = self._compute_latency(Tier.TIER0, False, False)
            return (Tier.TIER0, latency, False, False)

        # Case 2: Page is in tier1 (slow tier hit, consider promotion)
        if state.tier1.contains(page_id):
            state.tier1.touch(page_id)

            # Promote to tier0
            state.tier1.remove(page_id)
            evicted = state.tier0.add(page)
            promoted = True
            self._promotions += 1
            state.tier0.total_promotions += 1

            # Handle eviction (demote to tier1)
            if evicted is not None:
                state.tier1.add(evicted)
                demoted = True
                self._demotions += 1
                state.tier1.total_demotions += 1

            page.last_promotion_time = state.current_time
            latency = self._compute_latency(Tier.TIER1, promoted, demoted)
            return (Tier.TIER1, latency, promoted, demoted)

        # Case 3: Page is not in any tier (miss)
        if self.promote_on_first_access and not state.tier0.is_full:
            # Add directly to tier0
            state.tier0.add(page)
            latency = self._compute_latency(Tier.NONE, False, False)
            return (Tier.NONE, latency, False, False)
        elif self.promote_on_first_access:
            # tier0 is full, add to tier0 and evict to tier1
            evicted = state.tier0.add(page)
            if evicted is not None:
                state.tier1.add(evicted)
                demoted = True
                self._demotions += 1
            latency = self._compute_latency(Tier.NONE, False, demoted)
            return (Tier.NONE, latency, False, demoted)
        else:
            # Add to tier1 first
            state.tier1.add(page)
            latency = self._compute_latency(Tier.NONE, False, False)
            return (Tier.NONE, latency, False, False)

    def get_stats(self) -> dict:
        return {
            "promotions": self._promotions,
            "demotions": self._demotions,
        }


class LRU2Controller(BaseController):
    """
    LRU-2 variant: Only promote on second access.

    This reduces thrashing for scan workloads by requiring
    a page to be accessed twice before promotion.
    """

    def __init__(self, config: SimulatorConfig):
        super().__init__(config)
        self._access_counts: dict = {}
        self._promotions = 0
        self._demotions = 0

    @property
    def name(self) -> str:
        return "LRU-2"

    def reset(self) -> None:
        self._access_counts = {}
        self._promotions = 0
        self._demotions = 0

    def on_access(
        self,
        state: GlobalState,
        page_id: int,
        op_type: OpType,
        **kwargs,
    ) -> Tuple[Tier, int, bool, bool]:
        page = state.get_or_create_page(page_id)
        page.update_on_access(state.current_time, op_type)

        # Track access count
        self._access_counts[page_id] = self._access_counts.get(page_id, 0) + 1
        access_count = self._access_counts[page_id]

        promoted = False
        demoted = False

        # Case 1: Page is in tier0
        if state.tier0.contains(page_id):
            state.tier0.touch(page_id)
            state.tier0.record_hit()
            return (Tier.TIER0, self._compute_latency(Tier.TIER0, False, False), False, False)

        # Case 2: Page is in tier1
        if state.tier1.contains(page_id):
            state.tier1.touch(page_id)

            # Only promote on 2nd+ access
            if access_count >= 2:
                state.tier1.remove(page_id)
                evicted = state.tier0.add(page)
                promoted = True
                self._promotions += 1

                if evicted is not None:
                    state.tier1.add(evicted)
                    demoted = True
                    self._demotions += 1

            latency = self._compute_latency(Tier.TIER1, promoted, demoted)
            return (Tier.TIER1, latency, promoted, demoted)

        # Case 3: Miss - add to tier1
        state.tier1.add(page)
        return (Tier.NONE, self._compute_latency(Tier.NONE, False, False), False, False)

    def get_stats(self) -> dict:
        return {
            "promotions": self._promotions,
            "demotions": self._demotions,
            "tracked_pages": len(self._access_counts),
        }
