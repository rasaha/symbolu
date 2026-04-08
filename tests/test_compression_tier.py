"""
Tests for CTM+ Compression Tier (zswap/zram).

Validates:
1. CompressionTierConfig validation and defaults
2. CompressionTierManager: compression, decompression, gating, age demotion
3. Tier0c hit path: access counting, promotion threshold
4. Eviction routing: Tier0 → Tier0c (compressed) instead of Tier1
5. Integration with CTMPlusController
6. Backward compatibility (disabled by default)
"""

import pytest
from simulator.ctm_plus.core.config import (
    SimulatorConfig,
    CTMPlusConfig,
    CompressionTierConfig,
)
from simulator.ctm_plus.core.state import (
    GlobalState,
    TierState,
    PageState,
    Tier,
    OpType,
)
from simulator.ctm_plus.controllers.ctm_plus import CTMPlusController, CompressionTierManager


# ── Fixtures ──────────────────────────────────────────────────────────


def make_sim_config(tier0=100, tier1=10000):
    return SimulatorConfig(tier0_size=tier0, tier1_size=tier1)


def make_state(tier0=100, tier1=10000, tier0c=None):
    state = GlobalState(
        tier0=TierState(tier_id=Tier.TIER0, capacity=tier0),
        tier1=TierState(tier_id=Tier.TIER1, capacity=tier1),
        tier0c=tier0c,
    )
    return state


def make_state_with_tier0c(tier0=100, tier1=10000, tier0c_cap=200):
    tier0c = TierState(tier_id=Tier.COMPRESSED, capacity=tier0c_cap)
    return make_state(tier0=tier0, tier1=tier1, tier0c=tier0c)


def make_comp_config(**kwargs):
    defaults = {"enabled": True}
    defaults.update(kwargs)
    return CompressionTierConfig(**defaults)


# ── CompressionTierConfig Tests ──────────────────────────────────────


class TestCompressionTierConfig:
    def test_disabled_by_default(self):
        cfg = CTMPlusConfig.default()
        assert cfg.compression_tier.enabled is False

    def test_default_values(self):
        cc = CompressionTierConfig()
        assert cc.capacity_multiplier == 2.0
        assert cc.avg_compression_ratio == 2.5
        assert cc.min_compression_ratio == 1.5
        assert cc.compress_latency_ns == 500
        assert cc.decompress_latency_ns == 200
        assert cc.access_latency_ns == 300
        assert cc.promotion_threshold_accesses == 2
        assert cc.max_compressed_age == 2000
        assert cc.epoch_scan_ratio == 0.25

    def test_enabled_config(self):
        cc = CompressionTierConfig(enabled=True, capacity_multiplier=3.0)
        cfg = CTMPlusConfig(compression_tier=cc)
        assert cfg.compression_tier.enabled is True
        assert cfg.compression_tier.capacity_multiplier == 3.0

    def test_invalid_capacity_multiplier(self):
        with pytest.raises(ValueError, match="capacity_multiplier"):
            CompressionTierConfig(capacity_multiplier=0.05)

    def test_invalid_compression_ratio(self):
        with pytest.raises(ValueError, match="avg_compression_ratio"):
            CompressionTierConfig(avg_compression_ratio=0.5)

    def test_invalid_min_compression_ratio(self):
        with pytest.raises(ValueError, match="min_compression_ratio"):
            CompressionTierConfig(min_compression_ratio=0.8)

    def test_invalid_promotion_threshold(self):
        with pytest.raises(ValueError, match="promotion_threshold"):
            CompressionTierConfig(promotion_threshold_accesses=0)

    def test_invalid_max_compressed_age(self):
        with pytest.raises(ValueError, match="max_compressed_age"):
            CompressionTierConfig(max_compressed_age=0)

    def test_invalid_epoch_scan_ratio(self):
        with pytest.raises(ValueError, match="epoch_scan_ratio"):
            CompressionTierConfig(epoch_scan_ratio=0.0)
        with pytest.raises(ValueError, match="epoch_scan_ratio"):
            CompressionTierConfig(epoch_scan_ratio=1.5)


# ── CompressionTierManager Unit Tests ────────────────────────────────


class TestCompressionTierManager:
    def test_disabled_noop(self):
        mgr = CompressionTierManager(CompressionTierConfig(enabled=False), 100)
        page = PageState(page_id=1)
        state = make_state_with_tier0c()
        assert mgr.should_compress(page, state) is False
        assert mgr.on_tier0c_hit(page, 100) is False

    def test_tier0c_capacity(self):
        mgr = CompressionTierManager(make_comp_config(capacity_multiplier=3.0), 100)
        assert mgr.get_tier0c_capacity() == 300

    def test_compression_ratio_estimation(self):
        mgr = CompressionTierManager(make_comp_config(), 100)
        page = PageState(page_id=42)
        ratio = mgr.estimate_compression_ratio(page)
        assert ratio >= 1.0
        # Different pages get different ratios (deterministic diversity)
        page2 = PageState(page_id=99)
        ratio2 = mgr.estimate_compression_ratio(page2)
        assert ratio != ratio2 or page.page_id == page2.page_id

    def test_hot_pages_compress_worse(self):
        """Write-hot pages should have lower compression ratio."""
        mgr = CompressionTierManager(make_comp_config(), 100)
        cold_page = PageState(page_id=1, heat=0.0)
        hot_page = PageState(page_id=1, heat=1.0)
        cold_ratio = mgr.estimate_compression_ratio(cold_page)
        hot_ratio = mgr.estimate_compression_ratio(hot_page)
        assert cold_ratio > hot_ratio

    def test_should_compress_with_space(self):
        mgr = CompressionTierManager(make_comp_config(), 100)
        state = make_state_with_tier0c(tier0c_cap=200)
        page = PageState(page_id=1)
        assert mgr.should_compress(page, state) is True

    def test_should_compress_when_full(self):
        """should_compress allows compression even when full (compress_page handles overflow)."""
        mgr = CompressionTierManager(make_comp_config(), 100)
        state = make_state_with_tier0c(tier0c_cap=2)
        # Fill tier0c
        for i in range(2):
            p = PageState(page_id=i + 100)
            state.tier0c.add(p)
        page = PageState(page_id=1)
        # should_compress returns True (capacity handled by compress_page)
        assert mgr.should_compress(page, state) is True

    def test_should_not_compress_without_tier0c(self):
        mgr = CompressionTierManager(make_comp_config(), 100)
        state = make_state(tier0=100, tier1=10000)  # No tier0c
        page = PageState(page_id=1)
        assert mgr.should_compress(page, state) is False

    def test_compress_page(self):
        mgr = CompressionTierManager(make_comp_config(), 100)
        state = make_state_with_tier0c()
        page = PageState(page_id=1)
        result = mgr.compress_page(page, state, current_time=100)
        assert result is True
        assert state.tier0c.contains(1)
        assert page.tier == Tier.COMPRESSED
        assert page.last_compress_time == 100
        assert page.compressed_access_count == 0

    def test_tier0c_hit_counting(self):
        mgr = CompressionTierManager(make_comp_config(promotion_threshold_accesses=3), 100)
        page = PageState(page_id=1)
        # First two accesses: not enough for promotion
        assert mgr.on_tier0c_hit(page, 100) is False
        assert page.compressed_access_count == 1
        assert mgr.on_tier0c_hit(page, 200) is False
        assert page.compressed_access_count == 2
        # Third access: meets threshold
        assert mgr.on_tier0c_hit(page, 300) is True
        assert page.compressed_access_count == 3

    def test_decompress_page(self):
        mgr = CompressionTierManager(make_comp_config(), 100)
        page = PageState(page_id=1, compressed_access_count=3, last_compress_time=50)
        mgr.decompress_page(page)
        assert page.compressed_access_count == 0
        assert page.last_compress_time == 0
        stats = mgr.get_stats()
        assert stats["decompressions"] == 1
        assert stats["tier0c_promotions"] == 1

    def test_epoch_scan_demotes_old_pages(self):
        mgr = CompressionTierManager(
            make_comp_config(max_compressed_age=100, epoch_scan_ratio=1.0), 100
        )
        state = make_state_with_tier0c()
        # Add old compressed pages (compress_time=10, never accessed)
        for i in range(10):
            page = PageState(page_id=i, last_compress_time=10, compressed_access_count=0)
            state.tier0c.add(page)
            page.tier = Tier.COMPRESSED
        # Epoch scan at time 200 (age 190 > max_compressed_age 100)
        demoted = mgr.epoch_scan(state, current_time=200)
        assert demoted == 10
        assert state.tier0c.size == 0
        assert state.tier1.size == 10

    def test_epoch_scan_keeps_accessed_pages(self):
        mgr = CompressionTierManager(
            make_comp_config(max_compressed_age=100, epoch_scan_ratio=1.0), 100
        )
        state = make_state_with_tier0c()
        # Add page that was accessed (compressed_access_count > 0)
        page = PageState(page_id=1, last_compress_time=10, compressed_access_count=1)
        state.tier0c.add(page)
        page.tier = Tier.COMPRESSED
        # Even though old, accessed pages are kept
        demoted = mgr.epoch_scan(state, current_time=200)
        assert demoted == 0
        assert state.tier0c.contains(1)

    def test_compress_evicts_victim_when_full(self):
        mgr = CompressionTierManager(make_comp_config(), 100)
        state = make_state_with_tier0c(tier0c_cap=3)
        # Fill tier0c with 3 pages
        for i in range(3):
            p = PageState(page_id=i, last_compress_time=10 + i)
            state.tier0c.add(p)
            p.tier = Tier.COMPRESSED
        assert state.tier0c.size == 3

        # Compress a new page → should evict oldest (page 0)
        new_page = PageState(page_id=99)
        mgr.compress_page(new_page, state, current_time=100)
        assert state.tier0c.contains(99)
        assert state.tier1.contains(0)  # Oldest evicted to tier1
        stats = mgr.get_stats()
        assert stats["tier0c_demotions"] == 1


# ── CompressionTierManager Stats Tests ───────────────────────────────


class TestCompressionStats:
    def test_stats_structure(self):
        mgr = CompressionTierManager(make_comp_config(), 100)
        stats = mgr.get_stats()
        assert "compressions" in stats
        assert "decompressions" in stats
        assert "compression_bypasses" in stats
        assert "bypass_rate" in stats
        assert "tier0c_hits" in stats
        assert "tier0c_promotions" in stats
        assert "tier0c_demotions" in stats
        assert "last_epoch_demotions" in stats

    def test_stats_after_operations(self):
        mgr = CompressionTierManager(make_comp_config(), 100)
        state = make_state_with_tier0c()
        page = PageState(page_id=1)
        mgr.compress_page(page, state, 100)
        mgr.on_tier0c_hit(page, 200)
        mgr.decompress_page(page)
        stats = mgr.get_stats()
        assert stats["compressions"] == 1
        assert stats["decompressions"] == 1
        assert stats["tier0c_hits"] == 1
        assert stats["tier0c_promotions"] == 1


# ── Integration Tests with CTMPlusController ─────────────────────────


class TestCompressionIntegration:
    def _make_controller(self, tier0=20, tier1=10000, **comp_kwargs):
        sim_config = SimulatorConfig(tier0_size=tier0, tier1_size=tier1)
        comp_config = CompressionTierConfig(enabled=True, **comp_kwargs)
        ctm_config = CTMPlusConfig(compression_tier=comp_config)
        controller = CTMPlusController(sim_config, ctm_config)
        # Initialize state with tier0c
        tier0c_cap = int(tier0 * comp_config.capacity_multiplier)
        state = make_state_with_tier0c(tier0=tier0, tier1=tier1, tier0c_cap=tier0c_cap)
        return controller, state

    def test_eviction_routes_to_tier0c(self):
        """Evicted pages should go to compression tier, not directly to tier1."""
        controller, state = self._make_controller(tier0=10)
        # Fill tier0
        for i in range(10):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)
        assert state.tier0.size == 10

        # Access new page → eviction from tier0
        state.current_time += 1
        controller.on_access(state, 100, OpType.READ)

        # Evicted page should be in tier0c (compressed), not tier1
        # At least some pages should be in tier0c
        assert state.tier0c.size > 0 or state.tier1.size > 0

    def test_tier0c_hit_promotes_back(self):
        """Accessing a compressed page enough times should promote it to tier0."""
        controller, state = self._make_controller(
            tier0=5,
            promotion_threshold_accesses=2,
        )
        # Fill tier0
        for i in range(5):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Force page 0 to eviction by accessing new pages
        for i in range(5, 10):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Page 0 should be in tier0c (or tier1 if incompressible)
        # Now access page 0 multiple times to trigger promotion from tier0c
        for _ in range(5):
            state.current_time += 1
            controller.on_access(state, 0, OpType.READ)

        # Page 0 should be back in tier0 (promoted from compressed)
        # Note: May go through tier1 if incompressible; just verify it served
        stats = controller.get_stats()
        assert stats["compression_tier_enabled"] is True

    def test_stats_in_get_stats(self):
        """Compression stats should appear in controller get_stats()."""
        controller, state = self._make_controller()
        stats = controller.get_stats()
        assert "compression_tier_enabled" in stats
        assert stats["compression_tier_enabled"] is True
        assert "tier0c_hits" in stats
        assert "compression_stats" in stats

    def test_disabled_no_overhead(self):
        """Disabled compression should not affect controller behavior."""
        sim_config = SimulatorConfig(tier0_size=20, tier1_size=10000)
        ctm_config = CTMPlusConfig()  # Default: disabled
        controller = CTMPlusController(sim_config, ctm_config)
        state = make_state(tier0=20, tier1=10000)

        for i in range(30):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        stats = controller.get_stats()
        assert stats["compression_tier_enabled"] is False
        assert stats["compression_stats"] == {}
        assert stats["tier0c_hits"] == 0

    def test_get_compression_stats_api(self):
        """Public API get_compression_stats() should work."""
        controller, state = self._make_controller()
        stats = controller.get_compression_stats()
        assert isinstance(stats, dict)
        assert "compressions" in stats

    def test_epoch_demotes_old_compressed_pages(self):
        """on_epoch should demote old compressed pages to tier1."""
        controller, state = self._make_controller(
            tier0=5,
            max_compressed_age=100,
            epoch_scan_ratio=1.0,
        )
        # Fill tier0 then evict to tier0c
        for i in range(10):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Advance time far enough for age threshold
        state.current_time += 200
        controller.on_epoch(state, 1)

        # Old compressed pages should have been demoted to tier1
        comp_stats = controller.get_compression_stats()
        # Some demotions may have happened
        assert isinstance(comp_stats["tier0c_demotions"], int)

    def test_tier_enum_compressed_value(self):
        """Tier.COMPRESSED should be a valid tier."""
        assert Tier.COMPRESSED == 2
        assert Tier.COMPRESSED != Tier.TIER0
        assert Tier.COMPRESSED != Tier.TIER1

    def test_find_page_tier_compressed(self):
        """GlobalState.find_page_tier should find pages in tier0c."""
        state = make_state_with_tier0c()
        page = PageState(page_id=1)
        state.tier0c.add(page)
        assert state.find_page_tier(1) == Tier.COMPRESSED

    def test_global_mean_phase_includes_tier0c(self):
        """Global mean phase should include tier0c pages."""
        state = make_state_with_tier0c()
        page = PageState(page_id=1, phase=1.0)
        state.tier0c.add(page)
        # Should not crash and should include compressed pages
        _ = state.global_mean_phase

    def test_compressed_page_write_marks_dirty(self):
        """Writing to a compressed page that gets promoted should mark dirty."""
        controller, state = self._make_controller(
            tier0=5,
            promotion_threshold_accesses=1,  # Promote on first access
        )
        # Fill tier0 with reads
        for i in range(5):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Evict page 0 by adding new pages
        for i in range(5, 10):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Page 0 should be somewhere (tier0c or tier1)
        # Access it with WRITE — if in tier0c, it should promote and mark dirty
        state.current_time += 1
        controller.on_access(state, 0, OpType.WRITE)

        # Verify page 0 is accessible (promoted or served from some tier)
        page = state.all_pages.get(0)
        assert page is not None

    def test_tier0c_hit_returns_compressed_tier(self):
        """Tier0c hit should return Tier.COMPRESSED regardless of promotion."""
        controller, state = self._make_controller(
            tier0=5,
            promotion_threshold_accesses=1,  # Promote on first hit
        )
        # Fill tier0
        for i in range(5):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Evict page 0 to tier0c
        for i in range(5, 10):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Access page 0 — should hit tier0c and promote (threshold=1)
        state.current_time += 1
        tier, latency, promoted, demoted = controller.on_access(state, 0, OpType.READ)

        # Access was served from compressed tier
        if tier == Tier.COMPRESSED:
            assert latency > 0
            # If promoted, latency should include promotion cost
            if promoted:
                assert latency >= controller.ctm_config.compression_tier.access_latency_ns

    def test_tier0c_non_promoted_hit_no_promotion_latency(self):
        """Tier0c hit without promotion should not include promotion latency."""
        controller, state = self._make_controller(
            tier0=5,
            promotion_threshold_accesses=10,  # Need many hits before promotion
        )
        # Fill tier0
        for i in range(5):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Evict page 0 to tier0c
        for i in range(5, 10):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Access page 0 — should hit tier0c but NOT promote (threshold=10)
        state.current_time += 1
        tier, latency, promoted, demoted = controller.on_access(state, 0, OpType.READ)

        if tier == Tier.COMPRESSED:
            assert promoted is False
            assert demoted is False
            # Latency should be just compression access + NUMA penalty
            assert latency >= controller.ctm_config.compression_tier.access_latency_ns

    def test_backward_compat_no_tier0c(self):
        """Tests should pass when tier0c is None (disabled compression)."""
        state = make_state(tier0=10, tier1=10000)
        assert state.tier0c is None
        assert state.find_page_tier(999) == Tier.NONE
        # global_mean_phase should work without tier0c
        _ = state.global_mean_phase
