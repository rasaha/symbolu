"""
Base controller interface for memory tier management.

All controllers (LRU, ARC, CTM+) implement this interface,
enabling fair comparison across different algorithms.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
from ..core.state import GlobalState, PageState, Tier, OpType
from ..core.config import SimulatorConfig


class BaseController(ABC):
    """
    Abstract base class for memory tier controllers.

    A controller decides:
    1. How to handle a memory access (which tier serves it)
    2. When to promote pages from tier1 to tier0
    3. When to demote pages from tier0 to tier1
    4. Which pages to evict when tiers are full
    """

    def __init__(self, config: SimulatorConfig):
        """
        Initialize controller.

        Args:
            config: Simulator configuration with tier sizes and latencies
        """
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this controller."""
        pass

    @abstractmethod
    def on_access(
        self,
        state: GlobalState,
        page_id: int,
        op_type: OpType,
        **kwargs,
    ) -> Tuple[Tier, int, bool, bool]:
        """
        Handle a memory access.

        This is the main entry point called by the simulator for each access.
        The controller must:
        1. Determine which tier serves the access (or if it's a miss)
        2. Update any internal state
        3. Decide whether to promote/demote pages

        Args:
            state: Global simulator state with all tiers and pages
            page_id: ID of the page being accessed
            op_type: Type of access (READ, WRITE, PREFETCH)
            **kwargs: Extended parameters (e.g., tenant_id, numa_node)
                consumed by advanced controllers, ignored by baselines.

        Returns:
            Tuple of:
            - tier: Which tier served the access (TIER0, TIER1, or NONE for miss)
            - latency_ns: Simulated latency for this access
            - promoted: Whether a promotion occurred
            - demoted: Whether a demotion occurred
        """
        pass

    def reset(self) -> None:
        """
        Reset controller state.

        Called before starting a new simulation run.
        Override in subclasses if controller has internal state.
        """
        pass

    def on_epoch(self, state: GlobalState, epoch: int) -> None:
        """
        Called at the end of each epoch (configurable number of accesses).

        Override in subclasses for periodic maintenance tasks like:
        - Updating coherence scores (slow path)
        - Adjusting parameters (SCC)
        - Collecting statistics

        Args:
            state: Global simulator state
            epoch: Current epoch number
        """
        pass

    def get_stats(self) -> dict:
        """
        Get controller-specific statistics.

        Override in subclasses to expose internal metrics.

        Returns:
            Dictionary of statistic name -> value
        """
        return {}

    def _compute_latency(
        self,
        tier: Tier,
        promoted: bool,
        demoted: bool,
    ) -> int:
        """
        Compute access latency based on tier and movement.

        Args:
            tier: Which tier served the access
            promoted: Whether a promotion occurred
            demoted: Whether a demotion occurred

        Returns:
            Total latency in nanoseconds
        """
        # Base latency from tier
        if tier == Tier.TIER0:
            latency = self.config.tier0_latency_ns
        elif tier == Tier.COMPRESSED:
            # Compressed DRAM: DRAM access + decompression overhead
            # Default to halfway between tier0 and tier1 if no config
            latency = self.config.tier0_latency_ns + 200  # ~300ns
        elif tier == Tier.TIER1:
            latency = self.config.tier1_latency_ns
        else:
            # Miss - assume we fetch from "backing store" at tier1 latency
            latency = self.config.tier1_latency_ns

        # Add movement costs
        if promoted:
            latency += self.config.promotion_latency_ns
        if demoted:
            latency += self.config.demotion_latency_ns

        return latency


class PassthroughController(BaseController):
    """
    Minimal controller that does nothing - all accesses go to tier1.

    Useful as a worst-case baseline.
    """

    @property
    def name(self) -> str:
        return "Passthrough"

    def on_access(
        self,
        state: GlobalState,
        page_id: int,
        op_type: OpType,
        **kwargs,
    ) -> Tuple[Tier, int, bool, bool]:
        # Get or create page
        page = state.get_or_create_page(page_id)
        page.update_on_access(state.current_time, op_type)

        # Always serve from tier1 (or miss if not present)
        if state.tier1.contains(page_id):
            state.tier1.touch(page_id)
            return (Tier.TIER1, self.config.tier1_latency_ns, False, False)
        else:
            # Add to tier1
            state.tier1.add(page)
            return (Tier.NONE, self.config.tier1_latency_ns, False, False)
