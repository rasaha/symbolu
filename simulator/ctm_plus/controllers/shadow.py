"""
Shadow controller for offline A/B testing in the simulator.

Wraps a live controller and a shadow controller, replaying the same trace
through both.  The live controller's decisions drive the actual tier state;
the shadow controller runs on a *separate copy* of the state and its
decisions are only logged.

This enables measuring what *would* have happened under a different policy
without affecting the live simulation.

Usage::

    from ctm_plus.controllers.shadow import ShadowController
    from ctm_plus.controllers.lru import LRUController
    from ctm_plus.controllers.ctm_plus import CTMPlusController

    config = SimulatorConfig(tier0_size=1000, tier1_size=100000)
    live = LRUController(config)
    shadow = CTMPlusController(config)

    controller = ShadowController(config, live, shadow)
    result = sim.run(trace, controller, trace_name="ab_test")

    # Inspect divergences
    report = controller.get_shadow_report()
    print(report)
"""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseController
from ..core.state import GlobalState, TierState, Tier, OpType
from ..core.config import SimulatorConfig


@dataclass
class VictimDivergence:
    """Records a single victim-selection divergence."""
    access_num: int
    page_id: int
    live_tier: Tier
    shadow_tier: Tier
    live_promoted: bool
    shadow_promoted: bool
    live_demoted: bool
    shadow_demoted: bool


class ShadowState:
    """Maintains a separate copy of tier state for the shadow controller.

    The shadow state is independent of the live state: the shadow
    controller can promote/demote pages differently.  Both start from
    the same initial empty state.
    """

    def __init__(self, config: SimulatorConfig):
        self.state = GlobalState(
            tier0=TierState(tier_id=Tier.TIER0, capacity=config.tier0_size),
            tier1=TierState(tier_id=Tier.TIER1, capacity=config.tier1_size),
        )

    def sync_time(self, current_time: int) -> None:
        self.state.current_time = current_time


class ShadowMetrics:
    """Tracks decision divergences between live and shadow controllers."""

    def __init__(self):
        self.total_accesses = 0

        # Tier-hit divergences
        self.tier_agreements = 0
        self.tier_divergences = 0

        # Promote/demote divergences
        self.promote_agreements = 0
        self.promote_divergences = 0
        self.demote_agreements = 0
        self.demote_divergences = 0

        # Hit-rate tracking
        self.live_tier0_hits = 0
        self.shadow_tier0_hits = 0

        # Regret: shadow would have served from tier0 but live didn't
        self.shadow_better_count = 0
        # Live served from tier0 but shadow wouldn't have
        self.live_better_count = 0

        # Recent divergences
        self.recent_divergences: deque[VictimDivergence] = deque(maxlen=1000)

    def record(
        self,
        access_num: int,
        page_id: int,
        live_tier: Tier,
        shadow_tier: Tier,
        live_promoted: bool,
        shadow_promoted: bool,
        live_demoted: bool,
        shadow_demoted: bool,
    ) -> None:
        self.total_accesses += 1

        # Tier agreement
        if live_tier == shadow_tier:
            self.tier_agreements += 1
        else:
            self.tier_divergences += 1
            self.recent_divergences.append(VictimDivergence(
                access_num=access_num,
                page_id=page_id,
                live_tier=live_tier,
                shadow_tier=shadow_tier,
                live_promoted=live_promoted,
                shadow_promoted=shadow_promoted,
                live_demoted=live_demoted,
                shadow_demoted=shadow_demoted,
            ))

        # Promote agreement
        if live_promoted == shadow_promoted:
            self.promote_agreements += 1
        else:
            self.promote_divergences += 1

        # Demote agreement
        if live_demoted == shadow_demoted:
            self.demote_agreements += 1
        else:
            self.demote_divergences += 1

        # Tier0 hit tracking
        if live_tier == Tier.TIER0:
            self.live_tier0_hits += 1
        if shadow_tier == Tier.TIER0:
            self.shadow_tier0_hits += 1

        # Shadow-better: shadow had tier0 hit, live didn't
        if shadow_tier == Tier.TIER0 and live_tier != Tier.TIER0:
            self.shadow_better_count += 1
        elif live_tier == Tier.TIER0 and shadow_tier != Tier.TIER0:
            self.live_better_count += 1

    @property
    def tier_agreement_rate(self) -> float:
        return self.tier_agreements / self.total_accesses if self.total_accesses > 0 else 0.0

    @property
    def live_hit_rate(self) -> float:
        return self.live_tier0_hits / self.total_accesses if self.total_accesses > 0 else 0.0

    @property
    def shadow_hit_rate(self) -> float:
        return self.shadow_tier0_hits / self.total_accesses if self.total_accesses > 0 else 0.0

    def summary(self) -> Dict[str, Any]:
        t = self.total_accesses or 1
        return {
            "total_accesses": self.total_accesses,
            "tier_agreement_rate": f"{self.tier_agreement_rate:.2%}",
            "tier_divergences": self.tier_divergences,
            "promote_divergences": self.promote_divergences,
            "demote_divergences": self.demote_divergences,
            "live_hit_rate": f"{self.live_hit_rate:.2%}",
            "shadow_hit_rate": f"{self.shadow_hit_rate:.2%}",
            "hit_rate_delta": f"{self.shadow_hit_rate - self.live_hit_rate:+.2%}",
            "shadow_better_count": self.shadow_better_count,
            "live_better_count": self.live_better_count,
            "shadow_is_better": self.shadow_tier0_hits > self.live_tier0_hits,
        }


class ShadowController(BaseController):
    """Wraps two controllers for A/B shadow testing.

    The live controller drives the real simulation state.
    The shadow controller runs on a separate state copy.
    Both see every access; divergences are recorded.

    The simulator sees this as a single controller (it implements
    BaseController) and only the live controller's decisions affect
    the real state.
    """

    def __init__(
        self,
        config: SimulatorConfig,
        live: BaseController,
        shadow: BaseController,
    ):
        super().__init__(config)
        self.live = live
        self.shadow = shadow
        self._shadow_state = ShadowState(config)
        self.shadow_metrics = ShadowMetrics()
        self._access_num = 0

    @property
    def name(self) -> str:
        return f"{self.live.name}[shadow:{self.shadow.name}]"

    def reset(self) -> None:
        self.live.reset()
        self.shadow.reset()
        self._shadow_state = ShadowState(self.config)
        self.shadow_metrics = ShadowMetrics()
        self._access_num = 0

    def on_access(
        self,
        state: GlobalState,
        page_id: int,
        op_type: OpType,
        **kwargs,
    ) -> Tuple[Tier, int, bool, bool]:
        """Process access through both live and shadow controllers."""
        self._access_num += 1

        # Sync shadow time
        self._shadow_state.sync_time(state.current_time)

        # Live controller (drives real state)
        live_tier, live_latency, live_promoted, live_demoted = (
            self.live.on_access(state, page_id, op_type, **kwargs)
        )

        # Shadow controller (independent state)
        shadow_tier, _, shadow_promoted, shadow_demoted = (
            self.shadow.on_access(
                self._shadow_state.state, page_id, op_type, **kwargs
            )
        )

        # Record divergence
        self.shadow_metrics.record(
            access_num=self._access_num,
            page_id=page_id,
            live_tier=live_tier,
            shadow_tier=shadow_tier,
            live_promoted=live_promoted,
            shadow_promoted=shadow_promoted,
            live_demoted=live_demoted,
            shadow_demoted=shadow_demoted,
        )

        # Return live's decisions (shadow is observation-only)
        return live_tier, live_latency, live_promoted, live_demoted

    def on_epoch(self, state: GlobalState, epoch: int) -> None:
        self.live.on_epoch(state, epoch)
        self._shadow_state.sync_time(state.current_time)
        self.shadow.on_epoch(self._shadow_state.state, epoch)

    def get_stats(self) -> dict:
        live_stats = self.live.get_stats()
        live_stats["shadow"] = self.shadow_metrics.summary()
        live_stats["shadow_controller_stats"] = self.shadow.get_stats()
        return live_stats

    def get_shadow_report(self) -> str:
        """Human-readable A/B comparison report."""
        s = self.shadow_metrics.summary()
        lines = [
            "=" * 60,
            f"SHADOW A/B REPORT: {self.live.name} vs {self.shadow.name}",
            "=" * 60,
            f"  Total accesses:        {s['total_accesses']:,}",
            f"  Tier agreement rate:   {s['tier_agreement_rate']}",
            f"  Tier divergences:      {s['tier_divergences']:,}",
            f"  Promote divergences:   {s['promote_divergences']:,}",
            f"  Demote divergences:    {s['demote_divergences']:,}",
            "",
            "  Hit Rates:",
            f"    Live ({self.live.name}):  {s['live_hit_rate']}",
            f"    Shadow ({self.shadow.name}): {s['shadow_hit_rate']}",
            f"    Delta:               {s['hit_rate_delta']}",
            "",
            "  Per-Access Comparison:",
            f"    Shadow better:       {s['shadow_better_count']:,} accesses",
            f"    Live better:         {s['live_better_count']:,} accesses",
            f"    Shadow is better:    {s['shadow_is_better']}",
            "=" * 60,
        ]
        return "\n".join(lines)
