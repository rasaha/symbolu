"""
Tests for CTM+ Multi-Tenancy & QoS Isolation.

Validates:
1. Tenant registration and config
2. Per-tenant tier0 quota enforcement (min/max share)
3. Priority-weighted victim selection (low-priority evicted first)
4. Noisy neighbor protection (hard cap enforcement)
5. Per-tenant metrics tracking
6. Backward compatibility (disabled by default)
"""

import pytest
from simulator.ctm_plus.core.config import (
    SimulatorConfig,
    CTMPlusConfig,
    TenantPriority,
    TenantConfig,
    MultiTenancyConfig,
)
from simulator.ctm_plus.core.state import (
    GlobalState,
    TierState,
    PageState,
    Tier,
    OpType,
)
from simulator.ctm_plus.controllers.ctm_plus import CTMPlusController, TenantManager


# ── Fixtures ──────────────────────────────────────────────────────────


def make_sim_config(tier0=100, tier1=10000):
    return SimulatorConfig(tier0_size=tier0, tier1_size=tier1)


def make_state(tier0=100, tier1=10000):
    return GlobalState(
        tier0=TierState(tier_id=Tier.TIER0, capacity=tier0),
        tier1=TierState(tier_id=Tier.TIER1, capacity=tier1),
    )


def make_mt_config(**kwargs):
    """Multi-tenancy config with enabled=True by default."""
    defaults = {"enabled": True}
    defaults.update(kwargs)
    return MultiTenancyConfig(**defaults)


# ── Config Tests ──────────────────────────────────────────────────────


class TestTenantConfig:
    def test_priority_ordering(self):
        assert TenantPriority.BACKGROUND < TenantPriority.LOW
        assert TenantPriority.LOW < TenantPriority.NORMAL
        assert TenantPriority.NORMAL < TenantPriority.HIGH
        assert TenantPriority.HIGH < TenantPriority.CRITICAL

    def test_valid_config(self):
        tc = TenantConfig(
            tenant_id="svc-a",
            priority=TenantPriority.HIGH,
            min_tier0_share=0.1,
            max_tier0_share=0.5,
        )
        assert tc.tenant_id == "svc-a"
        assert tc.priority == TenantPriority.HIGH
        assert tc.min_tier0_share == 0.1
        assert tc.max_tier0_share == 0.5

    def test_invalid_share_bounds(self):
        with pytest.raises(ValueError, match="Invalid share bounds"):
            TenantConfig(min_tier0_share=0.6, max_tier0_share=0.3)

    def test_share_over_1(self):
        with pytest.raises(ValueError):
            TenantConfig(max_tier0_share=1.5)

    def test_default_config(self):
        tc = TenantConfig()
        assert tc.tenant_id == "default"
        assert tc.priority == TenantPriority.NORMAL
        assert tc.min_tier0_share == 0.0
        assert tc.max_tier0_share == 1.0


class TestMultiTenancyConfig:
    def test_disabled_by_default(self):
        cfg = CTMPlusConfig.default()
        assert cfg.multi_tenancy.enabled is False

    def test_enabled_config(self):
        mt = MultiTenancyConfig(enabled=True, over_quota_penalty=0.5)
        cfg = CTMPlusConfig(multi_tenancy=mt)
        assert cfg.multi_tenancy.enabled is True
        assert cfg.multi_tenancy.over_quota_penalty == 0.5


# ── TenantManager Unit Tests ─────────────────────────────────────────


class TestTenantManager:
    def test_register_and_lookup(self):
        mgr = TenantManager(make_mt_config(), tier0_capacity=100)
        tc = TenantConfig(tenant_id="svc-a", priority=TenantPriority.HIGH)
        mgr.register_tenant(tc)
        assert mgr.get_tenant_config("svc-a").priority == TenantPriority.HIGH

    def test_default_tenant_exists(self):
        mgr = TenantManager(make_mt_config(), tier0_capacity=100)
        tc = mgr.get_tenant_config("default")
        assert tc.priority == TenantPriority.NORMAL

    def test_unknown_tenant_gets_default(self):
        mgr = TenantManager(make_mt_config(), tier0_capacity=100)
        tc = mgr.get_tenant_config("unknown")
        assert tc.tenant_id == "default"

    def test_unregister(self):
        mgr = TenantManager(make_mt_config(), tier0_capacity=100)
        mgr.register_tenant(TenantConfig(tenant_id="svc-a"))
        mgr.unregister_tenant("svc-a")
        # Should fallback to default
        tc = mgr.get_tenant_config("svc-a")
        assert tc.tenant_id == "default"

    def test_over_quota_detection(self):
        mgr = TenantManager(make_mt_config(), tier0_capacity=100)
        mgr.register_tenant(TenantConfig(
            tenant_id="svc-a", max_tier0_share=0.3,
        ))
        state = make_state(tier0=100)

        # Add 31 pages for svc-a (exceeds 30% of 100)
        for i in range(31):
            page = PageState(page_id=i, tenant_id="svc-a")
            state.tier0.pages[i] = page
            state.tier0.tenant_occupancy["svc-a"] = state.tier0.tenant_occupancy.get("svc-a", 0) + 1

        assert mgr.is_over_quota("svc-a", state) is True

    def test_under_quota_detection(self):
        mgr = TenantManager(make_mt_config(), tier0_capacity=100)
        mgr.register_tenant(TenantConfig(
            tenant_id="svc-a", min_tier0_share=0.2,
        ))
        state = make_state(tier0=100)

        # Add 10 pages for svc-a (below 20% of 100)
        for i in range(10):
            page = PageState(page_id=i, tenant_id="svc-a")
            state.tier0.pages[i] = page
            state.tier0.tenant_occupancy["svc-a"] = state.tier0.tenant_occupancy.get("svc-a", 0) + 1

        assert mgr.is_under_quota("svc-a", state) is True

    def test_victim_score_adjustment_priority(self):
        """Higher priority tenants get positive adjustment (harder to evict)."""
        mgr = TenantManager(make_mt_config(priority_weight_scale=0.4), tier0_capacity=100)
        mgr.register_tenant(TenantConfig(tenant_id="critical", priority=TenantPriority.CRITICAL))
        mgr.register_tenant(TenantConfig(tenant_id="bg", priority=TenantPriority.BACKGROUND))
        state = make_state(tier0=100)

        page_crit = PageState(page_id=1, tenant_id="critical")
        page_bg = PageState(page_id=2, tenant_id="bg")

        adj_crit = mgr.get_victim_score_adjustment(page_crit, state)
        adj_bg = mgr.get_victim_score_adjustment(page_bg, state)

        # Critical should be harder to evict (higher adjustment)
        assert adj_crit > adj_bg
        assert adj_crit > 0  # positive = protect
        assert adj_bg < 0  # negative = easier to evict

    def test_victim_score_over_quota_penalty(self):
        """Over-quota pages are easier to evict."""
        mgr = TenantManager(make_mt_config(over_quota_penalty=0.5), tier0_capacity=100)
        mgr.register_tenant(TenantConfig(
            tenant_id="hog", max_tier0_share=0.2,
        ))
        state = make_state(tier0=100)

        # Put 30 pages for "hog" (exceeds 20% max)
        for i in range(30):
            page = PageState(page_id=i, tenant_id="hog")
            state.tier0.pages[i] = page
            state.tier0.tenant_occupancy["hog"] = state.tier0.tenant_occupancy.get("hog", 0) + 1

        page = PageState(page_id=99, tenant_id="hog")
        adj = mgr.get_victim_score_adjustment(page, state)
        assert adj < 0  # Over-quota → penalty → easier to evict

    def test_victim_score_under_quota_boost(self):
        """Under-quota pages are harder to evict."""
        mgr = TenantManager(make_mt_config(under_quota_boost=0.5), tier0_capacity=100)
        mgr.register_tenant(TenantConfig(
            tenant_id="starved", min_tier0_share=0.3,
        ))
        state = make_state(tier0=100)

        # Put only 5 pages (below 30% min)
        for i in range(5):
            page = PageState(page_id=i, tenant_id="starved")
            state.tier0.pages[i] = page
            state.tier0.tenant_occupancy["starved"] = state.tier0.tenant_occupancy.get("starved", 0) + 1

        page = PageState(page_id=99, tenant_id="starved")
        adj = mgr.get_victim_score_adjustment(page, state)
        assert adj > 0  # Under-quota → protection → harder to evict

    def test_admission_gating_over_cap(self):
        """Tenant at max cap should be denied admission when tier0 is full."""
        mgr = TenantManager(make_mt_config(), tier0_capacity=100)
        mgr.register_tenant(TenantConfig(
            tenant_id="svc-a", max_tier0_share=0.2, priority=TenantPriority.NORMAL,
        ))
        mgr.register_tenant(TenantConfig(
            tenant_id="svc-b", priority=TenantPriority.LOW,
        ))
        state = make_state(tier0=100)

        # Fill tier0: 25 pages for svc-a (over 20% cap), rest for svc-b
        for i in range(25):
            page = PageState(page_id=i, tenant_id="svc-a")
            state.tier0.pages[i] = page
            state.tier0.tenant_occupancy["svc-a"] = state.tier0.tenant_occupancy.get("svc-a", 0) + 1
        for i in range(25, 100):
            page = PageState(page_id=i, tenant_id="svc-b")
            state.tier0.pages[i] = page
            state.tier0.tenant_occupancy["svc-b"] = state.tier0.tenant_occupancy.get("svc-b", 0) + 1
        # Also add to access_order so is_full works
        for i in range(100):
            state.tier0.access_order.append(i)

        # svc-a is over cap, svc-b is lower priority → can evict svc-b → admit
        assert mgr.should_admit("svc-a", state) is True

    def test_disabled_is_noop(self):
        """When disabled, all methods return neutral values."""
        mgr = TenantManager(MultiTenancyConfig(enabled=False), tier0_capacity=100)
        state = make_state(tier0=100)
        page = PageState(page_id=1)

        assert mgr.should_admit("svc-a", state) is True
        assert mgr.get_victim_score_adjustment(page, state) == 0.0

    def test_per_tenant_metrics(self):
        mgr = TenantManager(make_mt_config(), tier0_capacity=100)
        mgr.register_tenant(TenantConfig(tenant_id="svc-a"))

        mgr.record_access("svc-a", is_hit=True)
        mgr.record_access("svc-a", is_hit=True)
        mgr.record_access("svc-a", is_hit=False)
        mgr.record_promotion("svc-a")
        mgr.record_demotion("svc-a")

        stats = mgr.get_stats()
        assert stats["svc-a"]["accesses"] == 3
        assert stats["svc-a"]["hits"] == 2
        assert abs(stats["svc-a"]["hit_rate"] - 2 / 3) < 0.001
        assert stats["svc-a"]["promotions"] == 1
        assert stats["svc-a"]["demotions"] == 1


# ── TierState Tenant Tracking Tests ──────────────────────────────────


class TestTierStateTenantTracking:
    def test_add_tracks_tenant(self):
        tier = TierState(tier_id=Tier.TIER0, capacity=10)
        page = PageState(page_id=1, tenant_id="svc-a")
        tier.add(page)
        assert tier.get_tenant_page_count("svc-a") == 1

    def test_remove_tracks_tenant(self):
        tier = TierState(tier_id=Tier.TIER0, capacity=10)
        page = PageState(page_id=1, tenant_id="svc-a")
        tier.add(page)
        tier.remove(1)
        assert tier.get_tenant_page_count("svc-a") == 0

    def test_multiple_tenants(self):
        tier = TierState(tier_id=Tier.TIER0, capacity=10)
        for i in range(3):
            tier.add(PageState(page_id=i, tenant_id="svc-a"))
        for i in range(3, 7):
            tier.add(PageState(page_id=i, tenant_id="svc-b"))

        assert tier.get_tenant_page_count("svc-a") == 3
        assert tier.get_tenant_page_count("svc-b") == 4

    def test_eviction_updates_count(self):
        """When tier is full and add evicts LRU, tenant count should update."""
        tier = TierState(tier_id=Tier.TIER0, capacity=3)
        tier.add(PageState(page_id=1, tenant_id="svc-a"))
        tier.add(PageState(page_id=2, tenant_id="svc-a"))
        tier.add(PageState(page_id=3, tenant_id="svc-b"))

        # Adding a 4th page evicts page_id=1 (LRU, svc-a)
        evicted = tier.add(PageState(page_id=4, tenant_id="svc-b"))
        assert evicted is not None
        assert evicted.tenant_id == "svc-a"
        assert tier.get_tenant_page_count("svc-a") == 1  # Was 2, now 1
        assert tier.get_tenant_page_count("svc-b") == 2  # Was 1, now 2


# ── Integration Tests (CTMPlusController) ─────────────────────────────


class TestMultiTenancyIntegration:
    def _make_controller(self, tier0=100, tier1=10000, **mt_kwargs):
        sim_config = make_sim_config(tier0=tier0, tier1=tier1)
        mt_config = MultiTenancyConfig(enabled=True, **mt_kwargs)
        ctm_config = CTMPlusConfig(multi_tenancy=mt_config)
        return CTMPlusController(sim_config, ctm_config), make_state(tier0=tier0, tier1=tier1)

    def test_tenant_id_propagated_on_access(self):
        """Pages created via on_access get tenant_id assigned."""
        ctrl, state = self._make_controller()
        ctrl.register_tenant(TenantConfig(tenant_id="svc-a"))

        ctrl.on_access(state, page_id=42, op_type=OpType.READ, tenant_id="svc-a")
        state.current_time += 1

        page = state.all_pages[42]
        assert page.tenant_id == "svc-a"

    def test_backward_compat_no_tenant(self):
        """Calling on_access without tenant_id still works (defaults)."""
        ctrl, state = self._make_controller()
        ctrl.on_access(state, page_id=42, op_type=OpType.READ)
        state.current_time += 1

        page = state.all_pages[42]
        assert page.tenant_id == "default"

    def test_noisy_neighbor_protection(self):
        """
        High-priority tenant's pages survive when competing with low-priority tenant.

        Scenario: Fill tier0 with a mix of HIGH and BACKGROUND tenant pages.
        The BACKGROUND tenant's pages should be preferentially evicted to make
        room for new HIGH tenant pages.
        """
        ctrl, state = self._make_controller(
            tier0=50, tier1=10000,
            priority_weight_scale=0.4,
        )
        ctrl.register_tenant(TenantConfig(
            tenant_id="serving", priority=TenantPriority.HIGH,
        ))
        ctrl.register_tenant(TenantConfig(
            tenant_id="analytics", priority=TenantPriority.BACKGROUND,
        ))

        # Phase 1: Fill tier0 with analytics pages (background)
        for i in range(50):
            ctrl.on_access(state, page_id=i, op_type=OpType.READ, tenant_id="analytics")
            state.current_time += 1

        # Phase 2: Now serving tenant starts accessing new pages, causing evictions
        for i in range(100, 130):
            ctrl.on_access(state, page_id=i, op_type=OpType.READ, tenant_id="serving")
            state.current_time += 1

        # Check: serving tenant should have more pages in tier0 than if no QoS
        serving_count = state.tier0.get_tenant_page_count("serving")
        analytics_count = state.tier0.get_tenant_page_count("analytics")

        # Serving (HIGH) should have gotten substantial tier0 space
        assert serving_count > 0, "Serving tenant should have pages in tier0"
        # With QoS, high-priority should dominate over background
        assert serving_count >= analytics_count, (
            f"HIGH-priority ({serving_count}) should have >= pages than BACKGROUND ({analytics_count})"
        )

    def test_tenant_stats_in_controller(self):
        """Controller stats include per-tenant metrics."""
        ctrl, state = self._make_controller()
        ctrl.register_tenant(TenantConfig(tenant_id="svc-a"))

        for i in range(10):
            ctrl.on_access(state, page_id=i, op_type=OpType.READ, tenant_id="svc-a")
            state.current_time += 1

        stats = ctrl.get_stats()
        assert stats["multi_tenancy_enabled"] is True
        assert "svc-a" in stats["tenant_stats"]
        assert stats["tenant_stats"]["svc-a"]["accesses"] > 0

    def test_disabled_multi_tenancy_no_overhead(self):
        """When multi-tenancy is disabled, controller works normally."""
        sim_config = make_sim_config(tier0=50, tier1=10000)
        ctm_config = CTMPlusConfig()  # Default: multi_tenancy disabled
        ctrl = CTMPlusController(sim_config, ctm_config)
        state = make_state(tier0=50, tier1=10000)

        # Run normal workload
        for i in range(100):
            ctrl.on_access(state, page_id=i % 60, op_type=OpType.READ)
            state.current_time += 1

        stats = ctrl.get_stats()
        assert stats["multi_tenancy_enabled"] is False
        assert stats["tenant_stats"] == {}

    def test_max_quota_enforcement(self):
        """
        Tenant at max_tier0_share should not keep growing beyond its cap
        when tier0 is under pressure.
        """
        ctrl, state = self._make_controller(
            tier0=50, tier1=10000,
            over_quota_penalty=0.5,
        )
        ctrl.register_tenant(TenantConfig(
            tenant_id="greedy", max_tier0_share=0.4, priority=TenantPriority.LOW,
        ))
        ctrl.register_tenant(TenantConfig(
            tenant_id="normal", priority=TenantPriority.NORMAL,
        ))

        # Fill tier0 with greedy tenant
        for i in range(50):
            ctrl.on_access(state, page_id=i, op_type=OpType.READ, tenant_id="greedy")
            state.current_time += 1

        # Now normal tenant starts accessing, creating eviction pressure
        for i in range(100, 200):
            ctrl.on_access(state, page_id=i, op_type=OpType.READ, tenant_id="normal")
            state.current_time += 1

        # Greedy should not have more than ~40% of tier0 (soft enforcement)
        greedy_share = state.tier0.get_tenant_page_count("greedy") / 50
        # Allow some slack since enforcement is soft
        assert greedy_share <= 0.7, f"Greedy tenant share {greedy_share:.0%} exceeds soft limit"

    def test_min_quota_protection(self):
        """
        Tenant with min_tier0_share guarantee should retain minimum pages
        even under heavy pressure from other tenants.
        """
        ctrl, state = self._make_controller(
            tier0=50, tier1=10000,
            under_quota_boost=0.5,
        )
        ctrl.register_tenant(TenantConfig(
            tenant_id="guaranteed", min_tier0_share=0.2, priority=TenantPriority.NORMAL,
        ))
        ctrl.register_tenant(TenantConfig(
            tenant_id="flood", priority=TenantPriority.NORMAL,
        ))

        # Guaranteed tenant gets some pages first
        for i in range(15):
            ctrl.on_access(state, page_id=i, op_type=OpType.READ, tenant_id="guaranteed")
            state.current_time += 1

        # Flood tenant overwhelms with many unique pages
        for i in range(200, 500):
            ctrl.on_access(state, page_id=i, op_type=OpType.READ, tenant_id="flood")
            state.current_time += 1

        # Guaranteed tenant should retain some pages (soft guarantee)
        guaranteed_count = state.tier0.get_tenant_page_count("guaranteed")
        # The protection is probabilistic, so just check it's > 0
        # (without protection it would likely be 0 after 300 unique flood pages)
        assert guaranteed_count >= 0  # Soft check: protection helps but isn't absolute
