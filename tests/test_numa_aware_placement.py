"""
Tests for CTM+ NUMA-Aware Placement.

Validates:
1. NUMA config and distance matrix
2. NUMAManager: affinity tracking, migration decisions, scoring
3. Per-page node assignment and occupancy tracking in TierState
4. Latency penalty for cross-node access
5. Victim selection prefers evicting remote pages
6. Migration moves pages closer to frequent accessor
7. Backward compatibility (disabled by default)
8. End-to-end integration via CTMPlusController
"""

import pytest
from simulator.ctm_plus.core.config import (
    SimulatorConfig,
    CTMPlusConfig,
    NUMAConfig,
)
from simulator.ctm_plus.core.state import (
    GlobalState,
    TierState,
    PageState,
    Tier,
    OpType,
)
from simulator.ctm_plus.controllers.ctm_plus import CTMPlusController, NUMAManager


# ── Fixtures ──────────────────────────────────────────────────────────


def make_state(tier0=100, tier1=10000):
    return GlobalState(
        tier0=TierState(tier_id=Tier.TIER0, capacity=tier0),
        tier1=TierState(tier_id=Tier.TIER1, capacity=tier1),
    )


def make_numa_config(**kwargs):
    defaults = {"enabled": True, "num_nodes": 2}
    defaults.update(kwargs)
    return NUMAConfig(**defaults)


# ── NUMAConfig Tests ──────────────────────────────────────────────────


class TestNUMAConfig:
    def test_disabled_by_default(self):
        cfg = CTMPlusConfig.default()
        assert cfg.numa.enabled is False

    def test_default_2_nodes(self):
        nc = NUMAConfig(enabled=True)
        assert nc.num_nodes == 2

    def test_distance_self_is_zero(self):
        nc = make_numa_config(num_nodes=4)
        for i in range(4):
            assert nc.get_distance(i, i) == 0.0

    def test_default_remote_distance(self):
        nc = make_numa_config(num_nodes=2)
        assert nc.get_distance(0, 1) == 1.0
        assert nc.get_distance(1, 0) == 1.0

    def test_custom_distance_matrix(self):
        # 3-node system with varying distances
        distances = (
            0.0, 0.5, 1.0,
            0.5, 0.0, 0.3,
            1.0, 0.3, 0.0,
        )
        nc = NUMAConfig(enabled=True, num_nodes=3, distances=distances)
        assert nc.get_distance(0, 1) == 0.5
        assert nc.get_distance(0, 2) == 1.0
        assert nc.get_distance(1, 2) == 0.3

    def test_distance_matrix_generation(self):
        nc = make_numa_config(num_nodes=3)
        matrix = nc.get_distance_matrix()
        assert len(matrix) == 3
        assert all(len(row) == 3 for row in matrix)
        # Diagonal should be 0
        for i in range(3):
            assert matrix[i][i] == 0.0
        # Off-diagonal should be 1.0 (default)
        assert matrix[0][1] == 1.0

    def test_invalid_num_nodes(self):
        with pytest.raises(ValueError):
            NUMAConfig(num_nodes=0)

    def test_invalid_distance_size(self):
        with pytest.raises(ValueError, match="distances must have"):
            NUMAConfig(enabled=True, num_nodes=2, distances=(0.0, 1.0))  # Need 4


# ── NUMAManager Unit Tests ────────────────────────────────────────────


class TestNUMAManager:
    def test_disabled_returns_zero(self):
        mgr = NUMAManager(NUMAConfig(enabled=False))
        page = PageState(page_id=1)
        assert mgr.compute_latency_penalty(0, 1) == 0
        assert mgr.get_victim_score_adjustment(page, 0) == 0.0

    def test_local_access_no_penalty(self):
        mgr = NUMAManager(make_numa_config(remote_penalty_ns=200))
        assert mgr.compute_latency_penalty(0, 0) == 0

    def test_remote_access_penalty(self):
        mgr = NUMAManager(make_numa_config(remote_penalty_ns=200))
        penalty = mgr.compute_latency_penalty(0, 1)
        assert penalty == 200  # distance=1.0, penalty=200*1.0

    def test_partial_distance_penalty(self):
        distances = (0.0, 0.5, 0.5, 0.0)
        mgr = NUMAManager(NUMAConfig(enabled=True, num_nodes=2, distances=distances, remote_penalty_ns=200))
        penalty = mgr.compute_latency_penalty(0, 1)
        assert penalty == 100  # distance=0.5, penalty=200*0.5

    def test_affinity_tracking(self):
        mgr = NUMAManager(make_numa_config())
        page = PageState(page_id=1, numa_node=0)

        # 5 accesses from node 0, 3 from node 1
        for _ in range(5):
            mgr.record_access(page, 0)
        for _ in range(3):
            mgr.record_access(page, 1)

        assert page.preferred_node == 0  # Node 0 has most accesses
        assert page.node_access_counts[0] == 5
        assert page.node_access_counts[1] == 3

    def test_preferred_node_switches(self):
        mgr = NUMAManager(make_numa_config())
        page = PageState(page_id=1, numa_node=0)

        # Initially accessed from node 0
        for _ in range(3):
            mgr.record_access(page, 0)
        assert page.preferred_node == 0

        # Then heavily accessed from node 1
        for _ in range(5):
            mgr.record_access(page, 1)
        assert page.preferred_node == 1

    def test_assign_node(self):
        mgr = NUMAManager(make_numa_config())
        page = PageState(page_id=1)
        mgr.assign_node(page, 1)
        assert page.numa_node == 1
        assert page.preferred_node == 1
        assert page.last_accessor_node == 1

    def test_migration_decision(self):
        """Page should be migrated when affinity threshold is met."""
        mgr = NUMAManager(make_numa_config(
            migration_threshold=0.6,
            migration_cooldown=5,
        ))
        page = PageState(page_id=1, numa_node=0)

        # 8 accesses from node 1, 2 from node 0 → 80% affinity to node 1
        for _ in range(2):
            mgr.record_access(page, 0)
        for _ in range(8):
            mgr.record_access(page, 1)

        assert page.preferred_node == 1
        assert page.numa_node == 0  # Still on node 0
        assert mgr.should_migrate(page, current_time=100) is True

    def test_migration_cooldown(self):
        mgr = NUMAManager(make_numa_config(migration_cooldown=50, migration_threshold=0.6))
        page = PageState(page_id=1, numa_node=0)

        # Strong affinity to node 1
        for _ in range(10):
            mgr.record_access(page, 1)

        # Migrate to node 1
        mgr.migrate_page(page, 1, current_time=100)
        assert page.numa_node == 1

        # Build affinity back to node 0 (need >60% of total)
        for _ in range(20):
            mgr.record_access(page, 0)
        # Now: node 0 has 20, node 1 has 10 → 66% affinity to node 0
        assert page.preferred_node == 0

        # Still within cooldown → blocked
        assert mgr.should_migrate(page, current_time=120) is False
        # Past cooldown → allowed
        assert mgr.should_migrate(page, current_time=151) is True

    def test_no_migration_when_local(self):
        mgr = NUMAManager(make_numa_config())
        page = PageState(page_id=1, numa_node=0, preferred_node=0)
        assert mgr.should_migrate(page, current_time=100) is False

    def test_victim_score_local_boost(self):
        """Pages on their preferred node get a protective boost."""
        mgr = NUMAManager(make_numa_config(local_preference_weight=0.2))
        page = PageState(page_id=1, numa_node=0, preferred_node=0)
        adj = mgr.get_victim_score_adjustment(page, accessor_node=0)
        assert adj > 0  # Protected

    def test_victim_score_remote_penalty(self):
        """Pages remote from their preferred node get penalized."""
        mgr = NUMAManager(make_numa_config(remote_eviction_penalty=0.2))
        page = PageState(page_id=1, numa_node=1, preferred_node=0)
        adj = mgr.get_victim_score_adjustment(page, accessor_node=0)
        assert adj < 0  # Easier to evict

    def test_metrics(self):
        mgr = NUMAManager(make_numa_config())
        page = PageState(page_id=1, numa_node=0)

        mgr.record_access(page, 0)  # Local
        mgr.record_access(page, 0)  # Local
        mgr.record_access(page, 1)  # Remote

        stats = mgr.get_stats()
        assert stats["per_node"][0]["local_hits"] == 2
        assert stats["per_node"][0]["remote_hits"] == 0
        assert stats["per_node"][1]["remote_hits"] == 1


# ── TierState NUMA Tracking Tests ────────────────────────────────────


class TestTierStateNUMATracking:
    def test_add_tracks_numa_node(self):
        tier = TierState(tier_id=Tier.TIER0, capacity=10)
        page = PageState(page_id=1, numa_node=0)
        tier.add(page)
        assert tier.get_numa_node_page_count(0) == 1
        assert tier.get_numa_node_page_count(1) == 0

    def test_remove_tracks_numa_node(self):
        tier = TierState(tier_id=Tier.TIER0, capacity=10)
        page = PageState(page_id=1, numa_node=0)
        tier.add(page)
        tier.remove(1)
        assert tier.get_numa_node_page_count(0) == 0

    def test_multi_node_occupancy(self):
        tier = TierState(tier_id=Tier.TIER0, capacity=10)
        for i in range(3):
            tier.add(PageState(page_id=i, numa_node=0))
        for i in range(3, 7):
            tier.add(PageState(page_id=i, numa_node=1))

        assert tier.get_numa_node_page_count(0) == 3
        assert tier.get_numa_node_page_count(1) == 4

    def test_eviction_updates_numa_count(self):
        tier = TierState(tier_id=Tier.TIER0, capacity=3)
        tier.add(PageState(page_id=1, numa_node=0))
        tier.add(PageState(page_id=2, numa_node=0))
        tier.add(PageState(page_id=3, numa_node=1))

        # Evict page_id=1 (node 0) by adding a new page
        evicted = tier.add(PageState(page_id=4, numa_node=1))
        assert evicted is not None
        assert evicted.numa_node == 0
        assert tier.get_numa_node_page_count(0) == 1  # Was 2, evicted 1
        assert tier.get_numa_node_page_count(1) == 2  # Was 1, added 1


# ── Integration Tests (CTMPlusController) ─────────────────────────────


class TestNUMAIntegration:
    def _make_controller(self, tier0=100, tier1=10000, **numa_kwargs):
        sim_config = SimulatorConfig(tier0_size=tier0, tier1_size=tier1)
        numa_config = NUMAConfig(enabled=True, **numa_kwargs)
        ctm_config = CTMPlusConfig(numa=numa_config)
        return CTMPlusController(sim_config, ctm_config), make_state(tier0=tier0, tier1=tier1)

    def test_numa_node_assigned_on_miss(self):
        """Pages get placed on the accessor's NUMA node."""
        ctrl, state = self._make_controller()

        ctrl.on_access(state, page_id=42, op_type=OpType.READ, numa_node=1)
        state.current_time += 1

        page = state.all_pages[42]
        assert page.numa_node == 1
        assert page.preferred_node == 1

    def test_backward_compat_no_numa_node(self):
        """Calling on_access without numa_node defaults to node 0."""
        ctrl, state = self._make_controller()
        ctrl.on_access(state, page_id=42, op_type=OpType.READ)
        state.current_time += 1

        page = state.all_pages[42]
        assert page.numa_node == 0

    def test_remote_access_higher_latency(self):
        """Accessing a page from a remote NUMA node should have higher latency."""
        ctrl, state = self._make_controller(
            tier0=50, remote_penalty_ns=200,
        )

        # Place page on node 0
        tier, lat_local, _, _ = ctrl.on_access(
            state, page_id=1, op_type=OpType.READ, numa_node=0
        )
        state.current_time += 1

        # Access same page from node 0 (local) — this is a tier0 hit
        _, lat_local, _, _ = ctrl.on_access(
            state, page_id=1, op_type=OpType.READ, numa_node=0
        )
        state.current_time += 1

        # Access same page from node 1 (remote) — tier0 hit + NUMA penalty
        _, lat_remote, _, _ = ctrl.on_access(
            state, page_id=1, op_type=OpType.READ, numa_node=1
        )
        state.current_time += 1

        assert lat_remote > lat_local, (
            f"Remote latency ({lat_remote}) should exceed local ({lat_local})"
        )

    def test_disabled_numa_no_overhead(self):
        """When NUMA is disabled, everything works normally."""
        sim_config = SimulatorConfig(tier0_size=50, tier1_size=10000)
        ctm_config = CTMPlusConfig()  # Default: numa disabled
        ctrl = CTMPlusController(sim_config, ctm_config)
        state = make_state(tier0=50, tier1=10000)

        for i in range(100):
            ctrl.on_access(state, page_id=i % 60, op_type=OpType.READ)
            state.current_time += 1

        stats = ctrl.get_stats()
        assert stats["numa_enabled"] is False
        assert stats["numa_stats"] == {}

    def test_numa_stats_in_controller(self):
        """Controller stats include NUMA metrics when enabled."""
        ctrl, state = self._make_controller()

        for i in range(20):
            ctrl.on_access(state, page_id=i, op_type=OpType.READ, numa_node=i % 2)
            state.current_time += 1

        stats = ctrl.get_stats()
        assert stats["numa_enabled"] is True
        assert "migrations" in stats["numa_stats"]
        assert "per_node" in stats["numa_stats"]
        assert 0 in stats["numa_stats"]["per_node"]
        assert 1 in stats["numa_stats"]["per_node"]

    def test_remote_pages_evicted_first(self):
        """
        Pages placed on the wrong NUMA node should be preferentially evicted.

        Fill tier0 with pages: half on node 0, half on node 1.
        Then access all from node 0 → node 1 pages become "remote".
        New page admission should evict node 1 pages first.
        """
        ctrl, state = self._make_controller(
            tier0=20, tier1=10000,
            local_preference_weight=0.3,
            remote_eviction_penalty=0.3,
        )

        # Fill tier0: pages 0-9 on node 0, pages 10-19 on node 1
        for i in range(10):
            ctrl.on_access(state, page_id=i, op_type=OpType.READ, numa_node=0)
            state.current_time += 1
        for i in range(10, 20):
            ctrl.on_access(state, page_id=i, op_type=OpType.READ, numa_node=1)
            state.current_time += 1

        # Warm up: access all pages from node 0 a few times so affinity is clear
        for _ in range(3):
            for i in range(20):
                ctrl.on_access(state, page_id=i, op_type=OpType.READ, numa_node=0)
                state.current_time += 1

        # Now add new pages from node 0, causing evictions
        for i in range(100, 115):
            ctrl.on_access(state, page_id=i, op_type=OpType.READ, numa_node=0)
            state.current_time += 1

        # Check: pages on node 0 should have survived better
        node0_count = state.tier0.get_numa_node_page_count(0)
        node1_count = state.tier0.get_numa_node_page_count(1)

        # Node 0 pages (local) should outnumber node 1 pages (remote)
        assert node0_count >= node1_count, (
            f"Node 0 ({node0_count}) should have >= pages than node 1 ({node1_count})"
        )

    def test_migration_on_tier0_hit(self):
        """Pages should migrate to their preferred node on repeated remote access."""
        ctrl, state = self._make_controller(
            tier0=50,
            migration_threshold=0.6,
            migration_cooldown=5,
        )

        # Place page on node 0
        ctrl.on_access(state, page_id=1, op_type=OpType.READ, numa_node=0)
        state.current_time += 1

        # Access from node 0 a couple of times
        for _ in range(2):
            ctrl.on_access(state, page_id=1, op_type=OpType.READ, numa_node=0)
            state.current_time += 1

        page = state.all_pages[1]
        assert page.numa_node == 0

        # Heavily access from node 1 (8 accesses to build affinity)
        for _ in range(8):
            ctrl.on_access(state, page_id=1, op_type=OpType.READ, numa_node=1)
            state.current_time += 1

        # Page should have migrated to node 1
        assert page.numa_node == 1, "Page should have migrated to node 1"

    def test_3_node_topology(self):
        """Test with a 3-node system with custom distances."""
        distances = (
            0.0, 0.5, 1.0,
            0.5, 0.0, 0.3,
            1.0, 0.3, 0.0,
        )
        ctrl, state = self._make_controller(
            tier0=50,
            num_nodes=3,
            distances=distances,
            remote_penalty_ns=200,
        )

        # Place page on node 0
        ctrl.on_access(state, page_id=1, op_type=OpType.READ, numa_node=0)
        state.current_time += 1

        # Access from node 1 (distance 0.5)
        _, lat_n1, _, _ = ctrl.on_access(
            state, page_id=1, op_type=OpType.READ, numa_node=1
        )
        state.current_time += 1

        # Access from node 2 (distance 1.0)
        _, lat_n2, _, _ = ctrl.on_access(
            state, page_id=1, op_type=OpType.READ, numa_node=2
        )
        state.current_time += 1

        # Node 2 access should be more expensive than node 1
        assert lat_n2 > lat_n1, (
            f"Node 2 latency ({lat_n2}) should exceed node 1 ({lat_n1})"
        )

    def test_numa_with_tenancy(self):
        """NUMA and multi-tenancy should work together without conflicts."""
        from simulator.ctm_plus.core.config import MultiTenancyConfig, TenantConfig, TenantPriority

        sim_config = SimulatorConfig(tier0_size=50, tier1_size=10000)
        ctm_config = CTMPlusConfig(
            numa=NUMAConfig(enabled=True, num_nodes=2),
            multi_tenancy=MultiTenancyConfig(enabled=True),
        )
        ctrl = CTMPlusController(sim_config, ctm_config)
        ctrl.register_tenant(TenantConfig(tenant_id="svc-a", priority=TenantPriority.HIGH))
        state = make_state(tier0=50, tier1=10000)

        # Mix of tenant + NUMA
        for i in range(30):
            ctrl.on_access(
                state, page_id=i, op_type=OpType.READ,
                tenant_id="svc-a", numa_node=i % 2,
            )
            state.current_time += 1

        stats = ctrl.get_stats()
        assert stats["numa_enabled"] is True
        assert stats["multi_tenancy_enabled"] is True
        assert "svc-a" in stats["tenant_stats"]
        assert stats["numa_stats"]["per_node"][0]["accesses"] > 0
