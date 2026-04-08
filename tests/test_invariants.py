"""
Tests for formal correctness invariants.

Validates:
1. All 12 invariants hold under normal controller operation (LRU, ARC, CTM+)
2. Planted violations are detected by the checker
3. Invariant checking works in the simulator run loop

Run: python -m pytest tests/test_invariants.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "simulator"))

import pytest

from ctm_plus.core.state import GlobalState, TierState, PageState, Tier, OpType
from ctm_plus.core.config import SimulatorConfig
from ctm_plus.core.invariants import (
    InvariantChecker,
    Violation,
    check_invariants,
    assert_invariants,
)
from ctm_plus.simulator import Simulator
from ctm_plus.traces.loader import TraceEvent
from ctm_plus.controllers.lru import LRUController
from ctm_plus.controllers.arc import ARCController
from ctm_plus.controllers.ctm_plus import CTMPlusController


def _make_state(t0=10, t1=100):
    return GlobalState(
        tier0=TierState(tier_id=Tier.TIER0, capacity=t0),
        tier1=TierState(tier_id=Tier.TIER1, capacity=t1),
    )


def _make_page(pid, tier=Tier.NONE, access_count=1):
    p = PageState(page_id=pid)
    p.tier = tier
    p.access_count = access_count
    p.last_access_time = pid  # Simple monotonic
    return p


# ============================================================================
# Clean state: all invariants should hold
# ============================================================================

class TestCleanState:
    def test_empty_state(self):
        state = _make_state()
        violations = check_invariants(state)
        assert not violations

    def test_state_with_pages(self):
        state = _make_state()
        for i in range(5):
            p = _make_page(i)
            state.all_pages[i] = p
            state.tier0.add(p)
        violations = check_invariants(state)
        assert not violations

    def test_pages_in_tier1(self):
        state = _make_state()
        for i in range(20):
            p = _make_page(i)
            state.all_pages[i] = p
            state.tier1.add(p)
        violations = check_invariants(state)
        assert not violations


# ============================================================================
# Planted violations: each invariant is tested individually
# ============================================================================

class TestPlantedViolations:
    def test_inv1_mutual_exclusivity(self):
        """Page in both tier0 and tier1."""
        state = _make_state()
        p = _make_page(42)
        state.all_pages[42] = p

        # Force page into both tiers (bypassing normal add)
        state.tier0.pages[42] = p
        state.tier0.access_order.append(42)
        p.tier = Tier.TIER0

        # Also put in tier1 (violation!)
        state.tier1.pages[42] = p
        state.tier1.access_order.append(42)

        violations = check_invariants(state)
        inv1 = [v for v in violations if v.invariant == "INV-1"]
        assert len(inv1) >= 1
        assert inv1[0].severity == "CRITICAL"

    def test_inv2_tier_field_mismatch(self):
        """Page in tier0 but page.tier says TIER1."""
        state = _make_state()
        p = _make_page(42)
        state.all_pages[42] = p
        state.tier0.pages[42] = p
        state.tier0.access_order.append(42)
        p.tier = Tier.TIER1  # Wrong!

        violations = check_invariants(state)
        inv2 = [v for v in violations if v.invariant == "INV-2"]
        assert len(inv2) >= 1
        assert inv2[0].severity == "CRITICAL"

    def test_inv3_capacity_exceeded(self):
        """More pages in tier than capacity allows."""
        state = _make_state(t0=3)
        for i in range(5):  # 5 pages in tier with capacity 3
            p = _make_page(i)
            state.all_pages[i] = p
            state.tier0.pages[i] = p
            state.tier0.access_order.append(i)
            p.tier = Tier.TIER0

        violations = check_invariants(state)
        inv3 = [v for v in violations if v.invariant == "INV-3"]
        assert len(inv3) >= 1
        assert inv3[0].severity == "CRITICAL"

    def test_inv4_access_order_ghost(self):
        """Page in access_order but not in pages dict."""
        state = _make_state()
        state.tier0.access_order.append(999)  # Ghost entry

        violations = check_invariants(state)
        inv4 = [v for v in violations if v.invariant == "INV-4"]
        assert len(inv4) >= 1

    def test_inv4_access_order_missing(self):
        """Page in pages dict but not in access_order."""
        state = _make_state()
        p = _make_page(42)
        state.all_pages[42] = p
        state.tier0.pages[42] = p
        p.tier = Tier.TIER0
        # Don't add to access_order

        violations = check_invariants(state)
        inv4 = [v for v in violations if v.invariant == "INV-4"]
        assert len(inv4) >= 1

    def test_inv6_hits_exceed_accesses(self):
        """Total hits > total accesses."""
        state = _make_state()
        state.tier0.total_hits = 100
        state.tier0.total_accesses = 50  # Less than hits!

        violations = check_invariants(state)
        inv6 = [v for v in violations if v.invariant == "INV-6"]
        assert len(inv6) >= 1

    def test_inv7_negative_access_count(self):
        """Negative access count."""
        state = _make_state()
        p = _make_page(42)
        p.access_count = -1
        state.all_pages[42] = p

        violations = check_invariants(state)
        inv7 = [v for v in violations if v.invariant == "INV-7"]
        assert len(inv7) >= 1

    def test_inv8_dirty_page_outside_tier0(self):
        """Dirty page in tier1."""
        state = _make_state()
        p = _make_page(42)
        p.dirty = True
        p.dirty_since = 100
        p.tier = Tier.TIER1
        state.all_pages[42] = p
        state.tier1.pages[42] = p
        state.tier1.access_order.append(42)

        violations = check_invariants(state)
        inv8 = [v for v in violations if v.invariant == "INV-8"]
        assert len(inv8) >= 1

    def test_inv11_page_not_in_all_pages(self):
        """Page in tier0 but not in all_pages registry."""
        state = _make_state()
        p = _make_page(42)
        p.tier = Tier.TIER0
        state.tier0.pages[42] = p
        state.tier0.access_order.append(42)
        # Don't add to all_pages!

        violations = check_invariants(state)
        inv11 = [v for v in violations if v.invariant == "INV-11"]
        assert len(inv11) >= 1
        assert inv11[0].severity == "CRITICAL"

    def test_inv12_orphan_page(self):
        """Page claims tier=TIER0 but isn't in tier0.pages."""
        state = _make_state()
        p = _make_page(42)
        p.tier = Tier.TIER0
        state.all_pages[42] = p
        # Don't add to tier0.pages!

        violations = check_invariants(state)
        inv12 = [v for v in violations if v.invariant == "INV-12"]
        assert len(inv12) >= 1
        assert inv12[0].severity == "CRITICAL"


# ============================================================================
# assert_invariants: severity filtering
# ============================================================================

class TestAssertInvariants:
    def test_clean_state_passes(self):
        state = _make_state()
        assert_invariants(state)  # Should not raise

    def test_critical_violation_raises(self):
        state = _make_state()
        p = _make_page(42)
        p.tier = Tier.TIER0
        state.all_pages[42] = p  # Orphan: claims TIER0 but not in tier0

        with pytest.raises(AssertionError, match="INV-12"):
            assert_invariants(state, context="test_critical")

    def test_warning_only_does_not_raise(self):
        """Warnings alone should not cause assertion failure."""
        state = _make_state()
        p = _make_page(42)
        p.visited = True
        p.tier = Tier.TIER1
        state.all_pages[42] = p
        state.tier1.pages[42] = p
        state.tier1.access_order.append(42)

        # This has a WARNING (INV-9: visited outside tier0) but no ERROR
        assert_invariants(state)  # Should not raise


# ============================================================================
# Simulation integration: invariants hold under real controllers
# ============================================================================

class TestSimulationInvariants:
    """Run real controllers with invariant checking enabled."""

    def _run_with_invariants(self, controller_cls, num_events=2000, check_every=100):
        config = SimulatorConfig(tier0_size=50, tier1_size=5000)
        controller = controller_cls(config)
        trace = [
            TraceEvent(timestamp=i, page_id=i % 200, op_type=OpType.READ)
            for i in range(num_events)
        ]
        sim = Simulator(config=config)
        result = sim.run(
            trace, controller, trace_name="invariant_test",
            verbose=False, check_invariants_every=check_every,
        )
        return result

    def test_lru_invariants_hold(self):
        """LRU controller should never violate invariants."""
        result = self._run_with_invariants(LRUController)
        assert result.metrics.total_accesses == 2000

    def test_arc_invariants_hold(self):
        """ARC controller should never violate invariants."""
        result = self._run_with_invariants(ARCController)
        assert result.metrics.total_accesses == 2000

    def test_ctm_plus_invariants_hold(self):
        """CTM+ controller should never violate invariants."""
        result = self._run_with_invariants(CTMPlusController)
        assert result.metrics.total_accesses == 2000

    def test_ctm_plus_heavy_eviction_invariants(self):
        """CTM+ with heavy eviction pressure (1% cache ratio)."""
        config = SimulatorConfig(tier0_size=20, tier1_size=2000)
        controller = CTMPlusController(config)
        trace = [
            TraceEvent(timestamp=i, page_id=i % 500, op_type=OpType.READ)
            for i in range(5000)
        ]
        sim = Simulator(config=config)
        # Check every 50 accesses for thorough coverage
        result = sim.run(
            trace, controller, trace_name="heavy_eviction",
            verbose=False, check_invariants_every=50,
        )
        assert result.metrics.total_accesses == 5000

    def test_ctm_plus_mixed_rw_invariants(self):
        """Mixed read/write workload."""
        config = SimulatorConfig(tier0_size=30, tier1_size=3000)
        controller = CTMPlusController(config)
        trace = []
        for i in range(3000):
            op = OpType.WRITE if i % 3 == 0 else OpType.READ
            trace.append(TraceEvent(timestamp=i, page_id=i % 300, op_type=op))

        sim = Simulator(config=config)
        result = sim.run(
            trace, controller, trace_name="mixed_rw",
            verbose=False, check_invariants_every=100,
        )
        assert result.metrics.total_accesses == 3000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
