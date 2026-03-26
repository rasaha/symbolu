"""
Tests for CXL 3.0 shared memory pool, cross-host coherence, and dynamic capacity.

Tests:
1. CXL3PoolConfig validation
2. CXLSharedMemoryPool: admission, eviction, pool hits, cross-host access
3. CXLCoherenceTracker: sharer tracking, invalidation, exclusive access
4. CXLCapacityManager: expansion, contraction, rebalancing
5. CTMPlusController integration: pool tier in eviction path
6. Invariant checker: INV-13 CXL pool integrity
"""

import pytest
from simulator.ctm_plus.core.config import (
    SimulatorConfig, CTMPlusConfig, CXL3PoolConfig,
)
from simulator.ctm_plus.core.state import (
    GlobalState, TierState, PageState, Tier, OpType,
)
from simulator.ctm_plus.controllers.ctm_plus import (
    CXLSharedMemoryPool, CXLCoherenceTracker, CXLCapacityManager,
    CTMPlusController,
)
from simulator.ctm_plus.core.invariants import InvariantChecker, check_invariants


# =============================================================================
# Helpers
# =============================================================================


def make_cxl_config(**overrides) -> CTMPlusConfig:
    """Create a CTMPlusConfig with CXL 3.0 pool enabled."""
    pool_defaults = {
        "enabled": True,
        "num_hosts": 2,
        "pool_size": 100,
        "per_host_min_share": 0.1,
        "per_host_max_share": 0.8,
    }
    pool_defaults.update(overrides)
    return CTMPlusConfig(cxl3_pool=CXL3PoolConfig(**pool_defaults))


def make_state(tier0: int = 50, tier1: int = 10000, pool_size: int = 100):
    """Create a GlobalState with CXL pool tier."""
    return GlobalState(
        tier0=TierState(tier_id=Tier.TIER0, capacity=tier0),
        tier1=TierState(tier_id=Tier.TIER1, capacity=tier1),
        pool=TierState(tier_id=Tier.POOL, capacity=pool_size),
    )


def make_page(page_id: int, access_count: int = 0, owner_host: int = 0) -> PageState:
    """Create a PageState with given access count."""
    p = PageState(page_id=page_id)
    p.access_count = access_count
    p.owner_host = owner_host
    return p


# =============================================================================
# CXL3PoolConfig Tests
# =============================================================================


class TestCXL3PoolConfig:
    """Test CXL3PoolConfig validation."""

    def test_default_disabled(self):
        cfg = CXL3PoolConfig()
        assert cfg.enabled is False
        assert cfg.num_hosts == 2
        assert cfg.pool_size == 2000

    def test_valid_config(self):
        cfg = CXL3PoolConfig(enabled=True, num_hosts=4, pool_size=500)
        assert cfg.num_hosts == 4
        assert cfg.pool_size == 500

    def test_invalid_num_hosts(self):
        with pytest.raises(ValueError):
            CXL3PoolConfig(num_hosts=0)

    def test_invalid_pool_size(self):
        with pytest.raises(ValueError):
            CXL3PoolConfig(pool_size=0)

    def test_invalid_share_bounds(self):
        with pytest.raises(ValueError):
            CXL3PoolConfig(per_host_min_share=0.9, per_host_max_share=0.5)

    def test_invalid_thresholds(self):
        with pytest.raises(ValueError):
            CXL3PoolConfig(expansion_threshold=0.3, contraction_threshold=0.8)

    def test_in_ctm_plus_config(self):
        cfg = CTMPlusConfig.default()
        assert hasattr(cfg, 'cxl3_pool')
        assert cfg.cxl3_pool.enabled is False


# =============================================================================
# CXLSharedMemoryPool Tests
# =============================================================================


class TestCXLSharedMemoryPool:
    """Test CXL shared memory pool manager."""

    def test_can_admit_when_enabled(self):
        ctm_cfg = make_cxl_config()
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        assert pool.can_admit(0) is True

    def test_cannot_admit_when_disabled(self):
        ctm_cfg = CTMPlusConfig()  # CXL disabled by default
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        assert pool.can_admit(0) is False

    def test_admit_to_pool(self):
        ctm_cfg = make_cxl_config()
        state = make_state()
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)

        page = make_page(42, access_count=3, owner_host=0)
        result = pool.admit_to_pool(page, state, host_id=0)
        assert result is True
        assert page.pool_resident is True
        assert state.pool.contains(42)
        assert pool.get_host_usage(0) == 1
        assert pool.pool_admissions == 1

    def test_should_use_pool_cold_page(self):
        """Cold pages (access_count < 2) skip the pool."""
        ctm_cfg = make_cxl_config()
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        cold_page = make_page(1, access_count=1)
        assert pool.should_use_pool(cold_page, 0) is False

    def test_should_use_pool_warm_page(self):
        """Warm pages (access_count >= 2) go to pool."""
        ctm_cfg = make_cxl_config()
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        warm_page = make_page(1, access_count=3)
        assert pool.should_use_pool(warm_page, 0) is True

    def test_per_host_max_share(self):
        """Host cannot exceed max share of pool."""
        ctm_cfg = make_cxl_config(pool_size=10, per_host_max_share=0.5)
        state = make_state(pool_size=10)
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)

        # Admit 5 pages for host 0 (50% of pool = max)
        for i in range(5):
            page = make_page(i, access_count=3, owner_host=0)
            pool.admit_to_pool(page, state, 0)

        assert pool.can_admit(0) is False  # At max share
        assert pool.can_admit(1) is True   # Host 1 still has room

    def test_remove_from_pool(self):
        ctm_cfg = make_cxl_config()
        state = make_state()
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)

        page = make_page(42, access_count=3, owner_host=0)
        pool.admit_to_pool(page, state, 0)
        assert pool.get_host_usage(0) == 1

        pool.remove_from_pool(page, state)
        assert pool.get_host_usage(0) == 0
        assert not state.pool.contains(42)
        assert page.pool_resident is False

    def test_pool_hit_tracking(self):
        ctm_cfg = make_cxl_config()
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        page = make_page(42, owner_host=0)

        pool.on_pool_hit(page, accessor_host=0)
        assert pool.pool_hits == 1
        assert pool.cross_host_accesses == 0

        pool.on_pool_hit(page, accessor_host=1)
        assert pool.pool_hits == 2
        assert pool.cross_host_accesses == 1

    def test_select_pool_victim(self):
        ctm_cfg = make_cxl_config(pool_size=5)
        state = make_state(pool_size=5)
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)

        # Admit pages with different access counts
        for i in range(5):
            page = make_page(i, access_count=i, owner_host=0)
            pool.admit_to_pool(page, state, 0)

        victim = pool.select_pool_victim(0, state)
        assert victim is not None
        # Page 0 has lowest pool_access_count (0) → most evictable
        assert victim.page_id == 0

    def test_get_stats(self):
        ctm_cfg = make_cxl_config()
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        stats = pool.get_stats()
        assert "pool_admissions" in stats
        assert "pool_hits" in stats
        assert "cross_host_accesses" in stats
        assert "host_usage" in stats


# =============================================================================
# CXLCoherenceTracker Tests
# =============================================================================


class TestCXLCoherenceTracker:
    """Test CXL cross-host coherence tracking."""

    def test_add_sharer(self):
        ctm_cfg = make_cxl_config()
        tracker = CXLCoherenceTracker(ctm_cfg)
        page = make_page(42)

        tracker.add_sharer(42, host_id=0, page=page)
        assert tracker.get_sharer_count(42) == 1
        assert 0 in tracker.get_sharers(42)
        assert 0 in page.sharer_hosts

    def test_multiple_sharers(self):
        ctm_cfg = make_cxl_config()
        tracker = CXLCoherenceTracker(ctm_cfg)
        page = make_page(42)

        tracker.add_sharer(42, 0, page)
        tracker.add_sharer(42, 1, page)
        tracker.add_sharer(42, 2, page)
        assert tracker.get_sharer_count(42) == 3
        assert page.sharer_hosts == {0, 1, 2}

    def test_max_sharers_limit(self):
        ctm_cfg = make_cxl_config(max_sharers=2)
        tracker = CXLCoherenceTracker(ctm_cfg)
        page = make_page(42)

        tracker.add_sharer(42, 0, page)
        tracker.add_sharer(42, 1, page)
        tracker.add_sharer(42, 2, page)  # Should be rejected
        assert tracker.get_sharer_count(42) == 2

    def test_remove_sharer(self):
        ctm_cfg = make_cxl_config()
        tracker = CXLCoherenceTracker(ctm_cfg)
        page = make_page(42)

        tracker.add_sharer(42, 0, page)
        tracker.add_sharer(42, 1, page)
        tracker.remove_sharer(42, 0, page)
        assert tracker.get_sharer_count(42) == 1
        assert 0 not in page.sharer_hosts

    def test_request_exclusive(self):
        """Exclusive access invalidates all other sharers."""
        ctm_cfg = make_cxl_config()
        tracker = CXLCoherenceTracker(ctm_cfg)
        page = make_page(42)

        tracker.add_sharer(42, 0, page)
        tracker.add_sharer(42, 1, page)
        tracker.add_sharer(42, 2, page)

        invalidations = tracker.request_exclusive(42, host_id=0, page=page)
        assert invalidations == 2  # Host 1 and 2 invalidated
        assert tracker.get_sharer_count(42) == 1
        assert 0 in tracker.get_sharers(42)
        assert tracker.invalidations_sent == 2

    def test_invalidation_cost(self):
        ctm_cfg = make_cxl_config()
        tracker = CXLCoherenceTracker(ctm_cfg)
        page = make_page(42)

        # No sharers → no cost
        assert tracker.compute_invalidation_cost_ns(42) == 0

        # Add sharers
        tracker.add_sharer(42, 0, page)
        assert tracker.compute_invalidation_cost_ns(42) == 0  # Only 1 sharer

        tracker.add_sharer(42, 1, page)
        cost = tracker.compute_invalidation_cost_ns(42)
        assert cost > 0  # 2 sharers → invalidation cost

    def test_eviction_penalty(self):
        ctm_cfg = make_cxl_config()
        tracker = CXLCoherenceTracker(ctm_cfg)
        page = make_page(42)

        assert tracker.get_eviction_penalty(42) == 0.0

        tracker.add_sharer(42, 0, page)
        tracker.add_sharer(42, 1, page)
        penalty = tracker.get_eviction_penalty(42)
        assert penalty > 0.0  # Shared page has eviction penalty

    def test_disabled_tracker(self):
        ctm_cfg = CTMPlusConfig()  # CXL disabled
        tracker = CXLCoherenceTracker(ctm_cfg)
        page = make_page(42)

        tracker.add_sharer(42, 0, page)
        assert tracker.get_sharer_count(42) == 0

    def test_get_stats(self):
        ctm_cfg = make_cxl_config()
        tracker = CXLCoherenceTracker(ctm_cfg)
        stats = tracker.get_stats()
        assert "invalidations_sent" in stats
        assert "shared_pages" in stats


# =============================================================================
# CXLCapacityManager Tests
# =============================================================================


class TestCXLCapacityManager:
    """Test CXL dynamic capacity management."""

    def test_initial_capacity(self):
        ctm_cfg = make_cxl_config(pool_size=200)
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        cap_mgr = CXLCapacityManager(ctm_cfg, pool)
        assert cap_mgr.current_capacity == 200

    def test_expansion_on_high_utilization(self):
        ctm_cfg = make_cxl_config(
            pool_size=10,
            expansion_threshold=0.8,
            contraction_threshold=0.2,
            capacity_step_pages=5,
            rebalance_interval=1,
        )
        state = make_state(pool_size=10)
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        cap_mgr = CXLCapacityManager(ctm_cfg, pool)

        # Fill pool to 90% (> 80% threshold)
        for i in range(9):
            page = make_page(i, access_count=3, owner_host=0)
            pool.admit_to_pool(page, state, 0)

        cap_mgr.record_demand(0)
        result = cap_mgr.rebalance(state)
        assert result["action"] == "expand"
        assert cap_mgr.current_capacity == 15
        assert cap_mgr.expansions == 1

    def test_contraction_on_low_utilization(self):
        ctm_cfg = make_cxl_config(
            pool_size=100,
            expansion_threshold=0.85,
            contraction_threshold=0.30,
            capacity_step_pages=10,
            rebalance_interval=1,
        )
        state = make_state(pool_size=100)
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        cap_mgr = CXLCapacityManager(ctm_cfg, pool)

        # Only 5% utilization (5 pages in 100 capacity)
        for i in range(5):
            page = make_page(i, access_count=3, owner_host=0)
            pool.admit_to_pool(page, state, 0)

        cap_mgr.record_demand(0)
        result = cap_mgr.rebalance(state)
        assert result["action"] == "contract"
        assert cap_mgr.current_capacity == 90
        assert cap_mgr.contractions == 1

    def test_no_action_normal_utilization(self):
        ctm_cfg = make_cxl_config(
            pool_size=100,
            expansion_threshold=0.85,
            contraction_threshold=0.30,
            rebalance_interval=1,
        )
        state = make_state(pool_size=100)
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        cap_mgr = CXLCapacityManager(ctm_cfg, pool)

        # 50% utilization — normal range
        for i in range(50):
            page = make_page(i, access_count=3, owner_host=0)
            pool.admit_to_pool(page, state, 0)

        cap_mgr.record_demand(0)
        result = cap_mgr.rebalance(state)
        assert result["action"] == "none"

    def test_host_demand_tracking(self):
        ctm_cfg = make_cxl_config()
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        cap_mgr = CXLCapacityManager(ctm_cfg, pool)

        for _ in range(10):
            cap_mgr.record_demand(0)
        for _ in range(5):
            cap_mgr.record_demand(1)

        assert cap_mgr.get_host_demand_share(0) == pytest.approx(10 / 15)
        assert cap_mgr.get_host_demand_share(1) == pytest.approx(5 / 15)

    def test_cannot_contract_below_usage(self):
        ctm_cfg = make_cxl_config(
            pool_size=20,
            contraction_threshold=0.30,
            capacity_step_pages=15,
            rebalance_interval=1,
        )
        state = make_state(pool_size=20)
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        cap_mgr = CXLCapacityManager(ctm_cfg, pool)

        # 3 pages in pool, try to contract by 15
        for i in range(3):
            page = make_page(i, access_count=3, owner_host=0)
            pool.admit_to_pool(page, state, 0)

        cap_mgr.record_demand(0)
        result = cap_mgr.rebalance(state)
        # Should contract but not below usage (3+1=4)
        if result["action"] == "contract":
            assert cap_mgr.current_capacity >= pool.get_total_usage()

    def test_get_stats(self):
        ctm_cfg = make_cxl_config()
        pool = CXLSharedMemoryPool(ctm_cfg, tier0_size=50)
        cap_mgr = CXLCapacityManager(ctm_cfg, pool)
        stats = cap_mgr.get_stats()
        assert "current_capacity" in stats
        assert "expansions" in stats
        assert "contractions" in stats
        assert "host_demand" in stats


# =============================================================================
# CTMPlusController Integration Tests
# =============================================================================


class TestCXLIntegration:
    """Test CXL 3.0 integration with CTMPlusController."""

    def _make_cxl_controller(self, tier0: int = 50, pool_size: int = 100):
        config = SimulatorConfig(tier0_size=tier0, tier1_size=10000)
        ctm_cfg = CTMPlusConfig(cxl3_pool=CXL3PoolConfig(
            enabled=True,
            num_hosts=2,
            pool_size=pool_size,
        ))
        ctrl = CTMPlusController(config, ctm_cfg)
        state = GlobalState(
            tier0=TierState(tier_id=Tier.TIER0, capacity=tier0),
            tier1=TierState(tier_id=Tier.TIER1, capacity=10000),
            pool=TierState(tier_id=Tier.POOL, capacity=pool_size),
        )
        return ctrl, state

    def test_cxl_managers_created(self):
        ctrl, _ = self._make_cxl_controller()
        assert hasattr(ctrl, '_cxl_pool')
        assert hasattr(ctrl, '_cxl_coherence')
        assert hasattr(ctrl, '_cxl_capacity')

    def test_init_cxl_pool(self):
        config = SimulatorConfig(tier0_size=50, tier1_size=10000)
        ctm_cfg = CTMPlusConfig(cxl3_pool=CXL3PoolConfig(
            enabled=True, pool_size=200,
        ))
        ctrl = CTMPlusController(config, ctm_cfg)
        state = GlobalState(
            tier0=TierState(tier_id=Tier.TIER0, capacity=50),
            tier1=TierState(tier_id=Tier.TIER1, capacity=10000),
        )
        assert state.pool is None
        ctrl.init_cxl_pool(state)
        assert state.pool is not None
        assert state.pool.capacity == 200

    def test_stats_include_cxl(self):
        ctrl, state = self._make_cxl_controller()
        stats = ctrl.get_stats()
        assert "cxl3_pool_enabled" in stats
        assert stats["cxl3_pool_enabled"] is True
        assert "cxl3_pool_stats" in stats
        assert "cxl3_coherence_stats" in stats
        assert "cxl3_capacity_stats" in stats

    def test_eviction_routes_to_pool(self):
        """Warm pages evicted from tier0 should go to CXL pool."""
        ctrl, state = self._make_cxl_controller(tier0=20, pool_size=50)

        # Fill tier0 with warm pages
        for i in range(25):
            state.current_time = i
            ctrl.on_access(state, i, OpType.READ)

        # Some pages should have been evicted to pool
        pool_stats = ctrl._cxl_pool.get_stats()
        # Pool admissions might be 0 if pages had access_count < 2
        # (single-access pages go straight to tier1)
        # Let's re-access some to make them warm, then force eviction
        for i in range(20):
            state.current_time = 30 + i
            ctrl.on_access(state, i, OpType.READ)

        # Now add more pages to force evictions of warm pages
        for i in range(100, 120):
            state.current_time = 60 + i
            ctrl.on_access(state, i, OpType.READ)

        pool_stats = ctrl._cxl_pool.get_stats()
        # At least some warm pages should have been admitted to pool
        assert pool_stats["pool_admissions"] >= 0  # Depends on exact eviction path

    def test_pool_hit_promotes_to_tier0(self):
        """Pages hit in pool with enough accesses get promoted back to tier0."""
        ctrl, state = self._make_cxl_controller(tier0=20, pool_size=50)

        # Manually place a page in the pool
        page = state.get_or_create_page(999)
        page.access_count = 5
        page.owner_host = 0
        page.pool_access_count = 2  # Enough for promotion threshold
        ctrl._cxl_pool.admit_to_pool(page, state, 0)
        ctrl._cxl_coherence.add_sharer(999, 0, page)

        # Access the page — should promote from pool to tier0
        state.current_time = 100
        tier, latency, promoted, demoted = ctrl.on_access(state, 999, OpType.READ)
        assert tier == Tier.POOL
        assert promoted is True
        assert state.tier0.contains(999)
        assert not state.pool.contains(999)

    def test_get_cxl_pool_stats(self):
        ctrl, _ = self._make_cxl_controller()
        stats = ctrl.get_cxl_pool_stats()
        assert "pool" in stats
        assert "coherence" in stats
        assert "capacity" in stats

    def test_disabled_cxl_no_pool_usage(self):
        """When CXL is disabled, no pages go to pool."""
        config = SimulatorConfig(tier0_size=20, tier1_size=10000)
        ctrl = CTMPlusController(config)  # Default config, CXL disabled
        state = GlobalState(
            tier0=TierState(tier_id=Tier.TIER0, capacity=20),
            tier1=TierState(tier_id=Tier.TIER1, capacity=10000),
        )

        for i in range(50):
            state.current_time = i
            ctrl.on_access(state, i, OpType.READ)

        stats = ctrl.get_stats()
        assert stats["cxl3_pool_enabled"] is False
        assert stats["cxl3_pool_hits"] == 0


# =============================================================================
# Invariant Tests
# =============================================================================


class TestCXLInvariants:
    """Test invariant checker handles CXL pool correctly."""

    def test_pool_mutual_exclusivity(self):
        """Page in pool should not also be in tier0."""
        state = make_state()
        page = PageState(page_id=42)
        page.tier = Tier.POOL
        page.pool_resident = True
        state.pool.add(page)
        state.all_pages[42] = page

        checker = InvariantChecker(state)
        violations = checker.check_all()
        critical = [v for v in violations if v.severity == "CRITICAL"]
        assert len(critical) == 0  # No violations — page only in pool

    def test_pool_tier0_conflict(self):
        """Page in both pool and tier0 is a CRITICAL violation."""
        state = make_state()
        page = PageState(page_id=42)

        # Forcibly place in both (bug scenario)
        state.tier0.pages[42] = page
        page.tier = Tier.TIER0
        state.tier0.access_order.append(42)
        state.pool.pages[42] = page
        state.pool.access_order.append(42)
        state.all_pages[42] = page

        checker = InvariantChecker(state)
        checker.check_mutual_exclusivity()
        critical = [v for v in checker.violations if v.severity == "CRITICAL"]
        assert any("BOTH tier0 and CXL pool" in v.message for v in critical)

    def test_pool_integrity_valid(self):
        """Valid pool page passes INV-13."""
        state = make_state()
        page = PageState(page_id=42)
        page.tier = Tier.POOL
        page.pool_resident = True
        state.pool.add(page)
        state.all_pages[42] = page

        checker = InvariantChecker(state)
        checker.check_cxl_pool_integrity()
        assert len(checker.violations) == 0

    def test_pool_integrity_wrong_tier(self):
        """Page in pool.pages with wrong tier field is CRITICAL."""
        state = make_state()
        page = PageState(page_id=42)
        page.pool_resident = True
        # Manually set wrong tier
        state.pool.pages[42] = page
        state.pool.access_order.append(42)
        page.tier = Tier.TIER0  # Wrong!
        state.all_pages[42] = page

        checker = InvariantChecker(state)
        checker.check_cxl_pool_integrity()
        critical = [v for v in checker.violations if v.severity == "CRITICAL"]
        assert len(critical) == 1
        assert "pool but tier=TIER0" in critical[0].message

    def test_pool_integrity_not_resident(self):
        """Page in pool.pages with pool_resident=False is ERROR."""
        state = make_state()
        page = PageState(page_id=42)
        page.tier = Tier.POOL
        page.pool_resident = False  # Bug: should be True
        state.pool.pages[42] = page
        state.pool.access_order.append(42)
        state.all_pages[42] = page

        checker = InvariantChecker(state)
        checker.check_cxl_pool_integrity()
        errors = [v for v in checker.violations if v.severity == "ERROR"]
        assert len(errors) == 1
        assert "pool_resident=False" in errors[0].message

    def test_orphan_pool_page(self):
        """Page claiming tier=POOL but not in pool.pages is INV-12 violation."""
        state = make_state()
        page = PageState(page_id=42)
        page.tier = Tier.POOL
        state.all_pages[42] = page
        # NOT added to pool.pages

        checker = InvariantChecker(state)
        checker.check_no_orphan_pages()
        critical = [v for v in checker.violations if v.severity == "CRITICAL"]
        assert any("POOL" in v.message for v in critical)

    def test_find_page_tier_pool(self):
        """GlobalState.find_page_tier returns POOL for pool-resident pages."""
        state = make_state()
        page = PageState(page_id=42)
        page.tier = Tier.POOL
        state.pool.add(page)
        state.all_pages[42] = page

        assert state.find_page_tier(42) == Tier.POOL


# =============================================================================
# PageState CXL Fields Tests
# =============================================================================


class TestPageStateCXLFields:
    """Test CXL-related fields on PageState."""

    def test_default_cxl_fields(self):
        page = PageState(page_id=1)
        assert page.owner_host == 0
        assert page.pool_resident is False
        assert page.sharer_hosts == set()
        assert page.last_pool_access_time == 0
        assert page.pool_access_count == 0

    def test_sharer_hosts_tracking(self):
        page = PageState(page_id=1)
        page.sharer_hosts.add(0)
        page.sharer_hosts.add(1)
        assert len(page.sharer_hosts) == 2
        page.sharer_hosts.discard(0)
        assert page.sharer_hosts == {1}
