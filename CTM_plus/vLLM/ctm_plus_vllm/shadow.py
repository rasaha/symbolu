"""
Shadow / A-B testing infrastructure for CTM+ eviction policies.

Enables safe, zero-risk evaluation of new eviction policies in production
by running them in "shadow mode" alongside the live policy.  The shadow
policy sees the same access stream and makes its own decisions, but only
the live policy's decisions are executed.  Divergences are logged so
operators can measure the shadow's quality before promoting it to live.

Architecture::

    access ──┬──▶ live policy ──▶ EXECUTED decision
             │
             └──▶ shadow policy ──▶ LOGGED decision (not executed)
                                      │
                                      ▼
                                 ShadowMetrics
                                 (agreement rate, regret, divergences)

Usage::

    from ctm_plus_vllm.shadow import ShadowEvictionPolicy, ShadowMetrics

    live = CTMEvictionPolicy(config)
    shadow = CTMEvictionPolicy(aggressive_config)  # candidate
    shadow_policy = ShadowEvictionPolicy(live, shadow)

    # Drop-in replacement — same interface as CTMEvictionPolicy
    shadow_policy.set_capacity(1000)
    shadow_policy.on_block_access(block_id, sequence_id)

    # After a test window, inspect results
    report = shadow_policy.get_shadow_report()
    print(report)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .evictor import CTMEvictionPolicy

logger = logging.getLogger(__name__)


# =============================================================================
# Shadow Metrics
# =============================================================================

@dataclass
class DecisionDivergence:
    """Record of a single decision where live and shadow diverged."""
    timestamp: float
    decision_type: str       # "victim", "promote", "evict"
    live_choice: Optional[int]
    shadow_choice: Optional[int]
    # Populated later when we observe the outcome
    live_was_refaulted: bool = False
    shadow_was_refaulted: bool = False


class ShadowMetrics:
    """Tracks agreement rate, divergence details, and regret between policies.

    "Regret" = the shadow's victim was accessed again sooner than the live's
    victim (shadow made a better choice), or vice versa.  Measured via a
    refault window: if a block evicted by the live policy is accessed within
    N accesses, that's a live-regret event.  Same for shadow.
    """

    def __init__(self, refault_window: int = 2000):
        self.refault_window = refault_window

        # Decision counts
        self.total_decisions = 0
        self.agreements = 0        # Both chose same block
        self.divergences = 0       # Different choices

        # Per-decision-type tracking
        self.victim_decisions = 0
        self.victim_agreements = 0
        self.promote_decisions = 0
        self.promote_agreements = 0

        # Regret tracking
        self.live_regrets = 0      # Live evicted block was accessed soon after
        self.shadow_regrets = 0    # Shadow would have evicted block accessed soon
        self._live_evicted: deque = deque()    # (block_id, access_counter) tuples
        self._shadow_evicted: deque = deque()

        # Recent divergences (bounded ring buffer)
        self.recent_divergences: deque[DecisionDivergence] = deque(maxlen=1000)

        # Per-access-counter tracking for refault detection
        self._access_counter = 0

        self._lock = threading.Lock()

    def record_victim_decision(
        self,
        live_victim: Optional[int],
        shadow_victim: Optional[int],
    ) -> None:
        """Record a victim selection decision from both policies."""
        with self._lock:
            # Note: does NOT increment _access_counter.  Only check_refault
            # increments it, so the refault window is measured in accesses,
            # not in decisions (which is the correct unit).
            self.total_decisions += 1
            self.victim_decisions += 1

            if live_victim == shadow_victim:
                self.agreements += 1
                self.victim_agreements += 1
            else:
                self.divergences += 1
                div = DecisionDivergence(
                    timestamp=time.monotonic(),
                    decision_type="victim",
                    live_choice=live_victim,
                    shadow_choice=shadow_victim,
                )
                self.recent_divergences.append(div)

                # Track evicted blocks for regret detection
                if live_victim is not None:
                    self._live_evicted.append(
                        (live_victim, self._access_counter)
                    )
                if shadow_victim is not None:
                    self._shadow_evicted.append(
                        (shadow_victim, self._access_counter)
                    )

            # Prune old eviction records outside refault window
            self._prune_old_evictions()

    def record_promote_decision(
        self,
        live_promotes: bool,
        shadow_promotes: bool,
    ) -> None:
        """Record a promotion decision from both policies."""
        with self._lock:
            self.total_decisions += 1
            self.promote_decisions += 1

            if live_promotes == shadow_promotes:
                self.agreements += 1
                self.promote_agreements += 1
            else:
                self.divergences += 1
                self.recent_divergences.append(DecisionDivergence(
                    timestamp=time.monotonic(),
                    decision_type="promote",
                    live_choice=1 if live_promotes else 0,
                    shadow_choice=1 if shadow_promotes else 0,
                ))

    def check_refault(self, block_id: int) -> None:
        """Check if an accessed block was recently evicted by either policy."""
        with self._lock:
            self._access_counter += 1

            # Prune expired eviction records first
            self._prune_old_evictions()

            # Check live evictions for regret
            for evicted_id, evict_time in self._live_evicted:
                if evicted_id == block_id:
                    self.live_regrets += 1
                    break

            # Check shadow evictions for regret
            for evicted_id, evict_time in self._shadow_evicted:
                if evicted_id == block_id:
                    self.shadow_regrets += 1
                    break

    def _prune_old_evictions(self) -> None:
        """Remove eviction records outside the refault window."""
        cutoff = self._access_counter - self.refault_window
        while self._live_evicted and self._live_evicted[0][1] < cutoff:
            self._live_evicted.popleft()
        while self._shadow_evicted and self._shadow_evicted[0][1] < cutoff:
            self._shadow_evicted.popleft()

    @property
    def agreement_rate(self) -> float:
        return self.agreements / self.total_decisions if self.total_decisions > 0 else 0.0

    @property
    def victim_agreement_rate(self) -> float:
        return self.victim_agreements / self.victim_decisions if self.victim_decisions > 0 else 0.0

    @property
    def promote_agreement_rate(self) -> float:
        return self.promote_agreements / self.promote_decisions if self.promote_decisions > 0 else 0.0

    @property
    def live_regret_rate(self) -> float:
        """Fraction of live victim decisions that led to a refault."""
        return self.live_regrets / self.victim_decisions if self.victim_decisions > 0 else 0.0

    @property
    def shadow_regret_rate(self) -> float:
        return self.shadow_regrets / self.victim_decisions if self.victim_decisions > 0 else 0.0

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict suitable for logging/JSON."""
        return {
            "total_decisions": self.total_decisions,
            "agreements": self.agreements,
            "divergences": self.divergences,
            "agreement_rate": f"{self.agreement_rate:.2%}",
            "victim_decisions": self.victim_decisions,
            "victim_agreement_rate": f"{self.victim_agreement_rate:.2%}",
            "promote_decisions": self.promote_decisions,
            "promote_agreement_rate": f"{self.promote_agreement_rate:.2%}",
            "live_regrets": self.live_regrets,
            "shadow_regrets": self.shadow_regrets,
            "live_regret_rate": f"{self.live_regret_rate:.2%}",
            "shadow_regret_rate": f"{self.shadow_regret_rate:.2%}",
            "shadow_better": self.live_regrets > self.shadow_regrets,
            "recent_divergences": len(self.recent_divergences),
        }

    def reset(self) -> None:
        with self._lock:
            self.total_decisions = 0
            self.agreements = 0
            self.divergences = 0
            self.victim_decisions = 0
            self.victim_agreements = 0
            self.promote_decisions = 0
            self.promote_agreements = 0
            self.live_regrets = 0
            self.shadow_regrets = 0
            self._live_evicted.clear()
            self._shadow_evicted.clear()
            self.recent_divergences.clear()
            self._access_counter = 0


# =============================================================================
# ShadowEvictionPolicy — drop-in wrapper for the vLLM evictor
# =============================================================================

class ShadowEvictionPolicy:
    """Runs a shadow eviction policy alongside the live policy.

    The live policy's decisions are executed normally.  The shadow policy
    receives the same access stream and makes its own decisions which are
    only recorded, never executed.  This allows safe A/B comparison of a
    candidate policy in production.

    Implements the same public interface as CTMEvictionPolicy so it can
    be a drop-in replacement in CTMBlockSpaceManager.
    """

    def __init__(
        self,
        live: CTMEvictionPolicy,
        shadow: CTMEvictionPolicy,
        refault_window: int = 2000,
    ):
        self.live = live
        self.shadow = shadow
        self.metrics = ShadowMetrics(refault_window=refault_window)

        # Mirror live config to shadow where appropriate
        self.shadow.set_capacity(self.live.max_blocks)

    # ── Delegated interface (live executes, shadow observes) ──

    def on_block_access(
        self,
        block_id: int,
        sequence_id: Optional[int] = None,
    ) -> Tuple[bool, bool]:
        """Access a block.  Both policies see it; only live's result returned."""
        # Check for refault (block accessed after eviction)
        self.metrics.check_refault(block_id)

        # Live policy (executed)
        live_result = self.live.on_block_access(block_id, sequence_id)

        # Shadow policy (observed only — same access stream)
        shadow_result = self.shadow.on_block_access(block_id, sequence_id)

        # Record promotion divergence
        live_promotes, _ = live_result
        shadow_promotes, _ = shadow_result
        if live_promotes or shadow_promotes:
            self.metrics.record_promote_decision(live_promotes, shadow_promotes)

        return live_result  # Only live's decision is used

    def select_victim(self) -> Optional[int]:
        """Select victim.  Both policies choose; only live's choice executed."""
        live_victim = self.live.select_victim()
        shadow_victim = self.shadow.select_victim()

        self.metrics.record_victim_decision(live_victim, shadow_victim)

        return live_victim  # Only live's victim is evicted

    def evict_block(self, block_id: int) -> None:
        """Evict block from live policy only.

        The shadow maintains its own independent view of GPU occupancy.
        When the live evicts block X, the shadow does NOT mirror this —
        the shadow's state tracks what would happen if the shadow were
        running live, which means it only evicts what *it* decides to
        evict (via its own batch eviction in on_block_access).

        The shadow's cache state will drift from reality.  This is
        intentional: it measures "what would the shadow's hit rate be?"
        """
        self.live.evict_block(block_id)
        # Shadow does NOT mirror: it manages its own evictions.

    def promote_block(self, block_id: int) -> None:
        """Promote block in live policy only.

        Shadow manages its own promotions independently via on_block_access.
        """
        self.live.promote_block(block_id)
        # Shadow does NOT mirror: it manages its own promotions.

    def free_block(self, block_id: int) -> None:
        """Free block in both policies.

        When a sequence completes, blocks are genuinely freed in the
        real system.  Both policies must see this because the physical
        block is returned to the free pool.
        """
        self.live.free_block(block_id)
        self.shadow.free_block(block_id)

    def pin_block(self, block_id: int) -> None:
        self.live.pin_block(block_id)
        self.shadow.pin_block(block_id)

    def unpin_block(self, block_id: int) -> None:
        self.live.unpin_block(block_id)
        self.shadow.unpin_block(block_id)

    def set_capacity(self, max_blocks: int) -> None:
        self.live.set_capacity(max_blocks)
        self.shadow.set_capacity(max_blocks)

    def get_stats(self) -> Dict[str, Any]:
        """Return live stats augmented with shadow comparison."""
        live_stats = self.live.get_stats()
        live_stats["shadow"] = self.metrics.summary()
        live_stats["shadow_stats"] = self.shadow.get_stats()
        return live_stats

    def reset_stats(self) -> None:
        self.live.reset_stats()
        self.shadow.reset_stats()
        self.metrics.reset()

    def get_shadow_report(self) -> str:
        """Human-readable shadow comparison report."""
        s = self.metrics.summary()
        live_stats = self.live.get_stats()
        shadow_stats = self.shadow.get_stats()

        lines = [
            "=" * 60,
            "SHADOW MODE REPORT",
            "=" * 60,
            f"  Total decisions:       {s['total_decisions']:,}",
            f"  Agreement rate:        {s['agreement_rate']}",
            f"  Divergences:           {s['divergences']:,}",
            "",
            "  Victim Selection:",
            f"    Decisions:           {s['victim_decisions']:,}",
            f"    Agreement rate:      {s['victim_agreement_rate']}",
            "",
            "  Promotion:",
            f"    Decisions:           {s['promote_decisions']:,}",
            f"    Agreement rate:      {s['promote_agreement_rate']}",
            "",
            "  Regret Analysis (refault window):",
            f"    Live regrets:        {s['live_regrets']:,} ({s['live_regret_rate']})",
            f"    Shadow regrets:      {s['shadow_regrets']:,} ({s['shadow_regret_rate']})",
            f"    Shadow is better:    {s['shadow_better']}",
            "",
            "  Live Policy:",
            f"    Hit rate:            {live_stats['gpu_hit_rate']:.2%}",
            f"    GPU blocks:          {live_stats['gpu_blocks']}",
            "",
            "  Shadow Policy:",
            f"    Hit rate:            {shadow_stats['gpu_hit_rate']:.2%}",
            f"    GPU blocks:          {shadow_stats['gpu_blocks']}",
            "=" * 60,
        ]
        return "\n".join(lines)

    # ── Legacy alias for code that accesses _lock directly ──

    @property
    def _lock(self):
        return self.live._lock

    @property
    def _write_lock(self):
        return self.live._write_lock
