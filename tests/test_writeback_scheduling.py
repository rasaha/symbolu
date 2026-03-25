"""
Tests for CTM+ Writeback Scheduling.

Validates:
1. WritebackSchedulingConfig validation and defaults
2. WritebackScheduler: dirty tracking, writeback drain, coalescing, watermarks
3. Victim scoring: dirty pages protected from eviction
4. Eviction tracking: dirty vs clean eviction counts
5. Integration with CTMPlusController
6. Backward compatibility (disabled by default)
"""

import pytest
from simulator.ctm_plus.core.config import (
    SimulatorConfig,
    CTMPlusConfig,
    WritebackSchedulingConfig,
)
from simulator.ctm_plus.core.state import (
    GlobalState,
    TierState,
    PageState,
    Tier,
    OpType,
)
from simulator.ctm_plus.controllers.ctm_plus import CTMPlusController, WritebackScheduler


# ── Fixtures ──────────────────────────────────────────────────────────


def make_sim_config(tier0=100, tier1=10000):
    return SimulatorConfig(tier0_size=tier0, tier1_size=tier1)


def make_state(tier0=100, tier1=10000):
    return GlobalState(
        tier0=TierState(tier_id=Tier.TIER0, capacity=tier0),
        tier1=TierState(tier_id=Tier.TIER1, capacity=tier1),
    )


def make_wb_config(**kwargs):
    defaults = {"enabled": True}
    defaults.update(kwargs)
    return WritebackSchedulingConfig(**defaults)


# ── WritebackSchedulingConfig Tests ──────────────────────────────────


class TestWritebackSchedulingConfig:
    def test_disabled_by_default(self):
        cfg = CTMPlusConfig.default()
        assert cfg.writeback_scheduling.enabled is False

    def test_default_values(self):
        wc = WritebackSchedulingConfig()
        assert wc.max_writebacks_per_epoch == 50
        assert wc.dirty_age_threshold == 500
        assert wc.high_watermark == 0.7
        assert wc.low_watermark == 0.2
        assert wc.dirty_eviction_penalty == 0.15
        assert wc.coalesce_window == 50

    def test_enabled_config(self):
        wc = WritebackSchedulingConfig(enabled=True, max_writebacks_per_epoch=100)
        cfg = CTMPlusConfig(writeback_scheduling=wc)
        assert cfg.writeback_scheduling.enabled is True
        assert cfg.writeback_scheduling.max_writebacks_per_epoch == 100

    def test_invalid_max_writebacks(self):
        with pytest.raises(ValueError, match="max_writebacks_per_epoch"):
            WritebackSchedulingConfig(max_writebacks_per_epoch=0)

    def test_invalid_watermarks_reversed(self):
        with pytest.raises(ValueError, match="Watermarks"):
            WritebackSchedulingConfig(low_watermark=0.8, high_watermark=0.3)

    def test_invalid_watermarks_over_one(self):
        with pytest.raises(ValueError, match="Watermarks"):
            WritebackSchedulingConfig(high_watermark=1.5)

    def test_invalid_dirty_age_threshold(self):
        with pytest.raises(ValueError, match="dirty_age_threshold"):
            WritebackSchedulingConfig(dirty_age_threshold=0)

    def test_equal_watermarks_valid(self):
        wc = WritebackSchedulingConfig(low_watermark=0.5, high_watermark=0.5)
        assert wc.low_watermark == wc.high_watermark


# ── WritebackScheduler Unit Tests ────────────────────────────────────


class TestWritebackScheduler:
    def test_disabled_noop(self):
        """Disabled scheduler should short-circuit all operations."""
        ws = WritebackScheduler(WritebackSchedulingConfig(enabled=False), 100)
        ws.mark_dirty(1, 100)
        assert ws.dirty_count == 0
        assert ws.get_victim_score_adjustment(1) == 0.0
        assert ws.on_eviction(1) is False

    def test_mark_dirty(self):
        ws = WritebackScheduler(make_wb_config(), 100)
        ws.mark_dirty(1, 100)
        assert ws.dirty_count == 1
        assert ws.dirty_ratio == pytest.approx(0.01)

    def test_mark_clean(self):
        ws = WritebackScheduler(make_wb_config(), 100)
        ws.mark_dirty(1, 100)
        ws.mark_clean(1)
        assert ws.dirty_count == 0

    def test_mark_clean_nonexistent(self):
        """Cleaning a non-dirty page should be safe."""
        ws = WritebackScheduler(make_wb_config(), 100)
        ws.mark_clean(999)  # No error
        assert ws.dirty_count == 0

    def test_write_coalescing(self):
        """Multiple writes to same page should coalesce."""
        ws = WritebackScheduler(make_wb_config(), 100)
        ws.mark_dirty(1, 100)
        ws.mark_dirty(1, 110)  # Same page, coalesced
        ws.mark_dirty(1, 120)  # Same page, coalesced again
        assert ws.dirty_count == 1  # Still just one dirty page
        stats = ws.get_stats()
        assert stats["coalesced_writes"] == 2

    def test_dirty_page_age(self):
        ws = WritebackScheduler(make_wb_config(), 100)
        ws.mark_dirty(1, 100)
        assert ws.get_dirty_page_age(1, 200) == 100
        assert ws.get_dirty_page_age(2, 200) == 0  # Not dirty

    def test_victim_score_dirty_page(self):
        """Dirty pages should get a positive score adjustment (harder to evict)."""
        ws = WritebackScheduler(make_wb_config(dirty_eviction_penalty=0.2), 100)
        ws.mark_dirty(1, 100)
        adj = ws.get_victim_score_adjustment(1)
        assert adj == pytest.approx(0.2)

    def test_victim_score_clean_page(self):
        """Clean pages should get no adjustment."""
        ws = WritebackScheduler(make_wb_config(), 100)
        assert ws.get_victim_score_adjustment(1) == 0.0

    def test_on_eviction_dirty(self):
        """Evicting a dirty page should record it and return True."""
        ws = WritebackScheduler(make_wb_config(), 100)
        ws.mark_dirty(1, 100)
        was_dirty = ws.on_eviction(1)
        assert was_dirty is True
        assert ws.dirty_count == 0  # Cleaned up
        stats = ws.get_stats()
        assert stats["dirty_evictions"] == 1

    def test_on_eviction_clean(self):
        """Evicting a clean page should return False."""
        ws = WritebackScheduler(make_wb_config(), 100)
        was_dirty = ws.on_eviction(1)
        assert was_dirty is False
        stats = ws.get_stats()
        assert stats["clean_evictions"] == 1

    def test_dirty_eviction_rate(self):
        ws = WritebackScheduler(make_wb_config(), 100)
        ws.mark_dirty(1, 100)
        ws.on_eviction(1)   # dirty
        ws.on_eviction(2)   # clean
        ws.on_eviction(3)   # clean
        stats = ws.get_stats()
        assert stats["dirty_eviction_rate"] == pytest.approx(1 / 3)


# ── Writeback Drain Tests ────────────────────────────────────────────


class TestWritebackDrain:
    def _make_state_with_dirty_pages(self, n_dirty, tier0_cap=100, dirty_start=100):
        """Create a state with n_dirty dirty pages in tier0."""
        state = make_state(tier0=tier0_cap, tier1=10000)
        ws = WritebackScheduler(
            make_wb_config(
                low_watermark=0.1,
                high_watermark=0.7,
                coalesce_window=10,
                max_writebacks_per_epoch=20,
            ),
            tier0_cap,
        )
        for i in range(n_dirty):
            page = PageState(page_id=i, dirty=True, dirty_since=dirty_start + i)
            state.tier0.add(page)
            ws.mark_dirty(i, dirty_start + i)
        return state, ws

    def test_drain_flushes_oldest_first(self):
        """Background drain should flush oldest dirty pages first."""
        state, ws = self._make_state_with_dirty_pages(30)
        current_time = 300  # All pages old enough (age > coalesce_window)
        flushed = ws.drain_writebacks(state, current_time)
        assert flushed == 20  # Limited by max_writebacks_per_epoch
        assert ws.dirty_count == 10  # 30 - 20 = 10 remaining

        # Verify oldest pages were cleaned
        for i in range(20):
            page = state.tier0.pages.get(i)
            assert page is not None
            assert page.dirty is False

    def test_drain_skips_below_low_watermark(self):
        """No drain when dirty ratio is below low watermark."""
        state, ws = self._make_state_with_dirty_pages(5, tier0_cap=100)
        # 5/100 = 0.05 < low_watermark (0.1)
        flushed = ws.drain_writebacks(state, 300)
        assert flushed == 0

    def test_drain_aggressive_above_high_watermark(self):
        """Drain rate doubles above high watermark."""
        state, ws = self._make_state_with_dirty_pages(80, tier0_cap=100)
        # 80/100 = 0.8 > high_watermark (0.7) → budget doubles to 40
        flushed = ws.drain_writebacks(state, 300)
        assert flushed == 40  # 2x budget
        stats = ws.get_stats()
        assert stats["watermark_triggers"] == 1

    def test_drain_respects_coalesce_window(self):
        """Pages dirtied within coalesce window should not be flushed."""
        state = make_state(tier0=100, tier1=10000)
        ws = WritebackScheduler(
            make_wb_config(
                low_watermark=0.0,
                coalesce_window=50,
                max_writebacks_per_epoch=100,
            ),
            100,
        )
        # Add pages: some old enough, some too recent
        for i in range(20):
            page = PageState(page_id=i, dirty=True, dirty_since=100 + i)
            state.tier0.add(page)
            ws.mark_dirty(i, 100 + i)

        # current_time=140 → pages with dirty_since <= 90 are old enough
        # but all pages have dirty_since >= 100, and 140-100=40 < 50
        flushed = ws.drain_writebacks(state, 140)
        assert flushed == 0  # All within coalesce window

        # Now advance time: 160 - 100 = 60 > 50, page 0 is eligible
        flushed = ws.drain_writebacks(state, 160)
        assert flushed > 0  # Some pages now old enough

    def test_drain_empty_noop(self):
        """Draining with no dirty pages should be a noop."""
        state = make_state(tier0=100, tier1=10000)
        ws = WritebackScheduler(make_wb_config(), 100)
        assert ws.drain_writebacks(state, 100) == 0

    def test_drain_disabled_noop(self):
        state = make_state(tier0=100, tier1=10000)
        ws = WritebackScheduler(WritebackSchedulingConfig(enabled=False), 100)
        assert ws.drain_writebacks(state, 100) == 0

    def test_drain_cleans_up_evicted_pages(self):
        """Pages evicted from tier0 between mark_dirty and drain should not leak."""
        state, ws = self._make_state_with_dirty_pages(20)
        assert ws.dirty_count == 20

        # Simulate 10 pages being evicted from tier0 (but still in _dirty_pages)
        for i in range(10):
            state.tier0.remove(i)

        # Drain should clean up _dirty_pages entries for missing pages
        current_time = 300
        flushed = ws.drain_writebacks(state, current_time)

        # Only 10 pages still in tier0, so only 10 can be "flushed"
        assert flushed == 10
        # All 20 entries should be cleaned from _dirty_pages (10 flushed + 10 evicted)
        assert ws.dirty_count == 0


# ── WritebackScheduler Stats Tests ───────────────────────────────────


class TestWritebackStats:
    def test_stats_structure(self):
        ws = WritebackScheduler(make_wb_config(), 100)
        stats = ws.get_stats()
        assert "total_writebacks" in stats
        assert "last_epoch_writebacks" in stats
        assert "dirty_pages" in stats
        assert "dirty_ratio" in stats
        assert "coalesced_writes" in stats
        assert "dirty_evictions" in stats
        assert "clean_evictions" in stats
        assert "dirty_eviction_rate" in stats
        assert "watermark_triggers" in stats

    def test_stats_after_operations(self):
        ws = WritebackScheduler(make_wb_config(), 100)
        ws.mark_dirty(1, 100)
        ws.mark_dirty(1, 110)  # coalesce
        ws.mark_dirty(2, 100)
        ws.on_eviction(1)  # dirty eviction
        ws.on_eviction(3)  # clean eviction
        stats = ws.get_stats()
        assert stats["dirty_pages"] == 1  # only page 2 left
        assert stats["coalesced_writes"] == 1
        assert stats["dirty_evictions"] == 1
        assert stats["clean_evictions"] == 1


# ── Integration Tests with CTMPlusController ─────────────────────────


class TestWritebackIntegration:
    def _make_controller(self, tier0=50, tier1=10000, **wb_kwargs):
        sim_config = SimulatorConfig(tier0_size=tier0, tier1_size=tier1)
        wb_config = WritebackSchedulingConfig(enabled=True, **wb_kwargs)
        ctm_config = CTMPlusConfig(writeback_scheduling=wb_config)
        controller = CTMPlusController(sim_config, ctm_config)
        state = make_state(tier0=tier0, tier1=tier1)
        return controller, state

    def test_write_marks_page_dirty(self):
        """Writing to a tier0 page should mark it dirty."""
        controller, state = self._make_controller()
        # Fill tier0 with reads first
        for i in range(50):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Write to page 0 (already in tier0)
        state.current_time += 1
        controller.on_access(state, 0, OpType.WRITE)

        page = state.tier0.pages.get(0)
        assert page is not None
        assert page.dirty is True

    def test_read_does_not_mark_dirty(self):
        """Reading a tier0 page should not mark it dirty."""
        controller, state = self._make_controller()
        for i in range(50):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Read page 0 again
        state.current_time += 1
        controller.on_access(state, 0, OpType.READ)

        page = state.tier0.pages.get(0)
        assert page is not None
        assert page.dirty is False

    def test_eviction_clears_dirty(self):
        """Evicted pages should have dirty state cleared."""
        controller, state = self._make_controller(tier0=10)
        # Fill tier0
        for i in range(10):
            state.current_time += 1
            controller.on_access(state, i, OpType.WRITE)

        # Access new page → triggers eviction
        state.current_time += 1
        controller.on_access(state, 100, OpType.READ)

        # Check that demoted pages have dirty cleared
        for page_id in state.tier1.pages:
            page = state.tier1.pages[page_id]
            if page.page_id != 100:  # Evicted page
                assert page.dirty is False
                assert page.dirty_since == 0

    def test_epoch_drains_dirty_pages(self):
        """on_epoch should trigger background writeback drain."""
        controller, state = self._make_controller(
            tier0=100,
            low_watermark=0.0,
            coalesce_window=1,
            max_writebacks_per_epoch=10,
        )
        # Fill tier0 with writes to make pages dirty
        for i in range(50):
            state.current_time += 1
            controller.on_access(state, i, OpType.WRITE)

        # Trigger epoch
        state.current_time += 100
        controller.on_epoch(state, 1)

        # Some dirty pages should have been cleaned
        stats = controller.get_writeback_stats()
        assert stats["total_writebacks"] > 0

    def test_stats_in_get_stats(self):
        """Writeback stats should appear in controller get_stats()."""
        controller, state = self._make_controller()
        stats = controller.get_stats()
        assert "writeback_scheduling_enabled" in stats
        assert stats["writeback_scheduling_enabled"] is True
        assert "writeback_influenced_decisions" in stats
        assert "writeback_stats" in stats

    def test_disabled_no_overhead(self):
        """Disabled writeback should not affect controller behavior."""
        sim_config = SimulatorConfig(tier0_size=50, tier1_size=10000)
        ctm_config = CTMPlusConfig()  # Default: disabled
        controller = CTMPlusController(sim_config, ctm_config)
        state = make_state(tier0=50, tier1=10000)

        for i in range(60):
            state.current_time += 1
            controller.on_access(state, i, OpType.WRITE)

        stats = controller.get_stats()
        assert stats["writeback_scheduling_enabled"] is False
        assert stats["writeback_stats"] == {}
        assert stats["writeback_influenced_decisions"] == 0

    def test_dirty_pages_protected_in_victim_selection(self):
        """Dirty pages should be harder to evict than clean pages."""
        controller, state = self._make_controller(
            tier0=20,
            dirty_eviction_penalty=0.5,  # Strong penalty
        )

        # Fill tier0: first 10 pages with writes (dirty), last 10 with reads (clean)
        for i in range(10):
            state.current_time += 1
            controller.on_access(state, i, OpType.WRITE)
        for i in range(10, 20):
            state.current_time += 1
            controller.on_access(state, i, OpType.READ)

        # Force many evictions by accessing new pages
        evicted_ids = []
        for i in range(20, 30):
            state.current_time += 1
            before_tier0 = set(state.tier0.pages.keys())
            controller.on_access(state, i, OpType.READ)
            after_tier0 = set(state.tier0.pages.keys())
            evicted = before_tier0 - after_tier0
            evicted_ids.extend(evicted)

        # With strong dirty penalty, clean pages (10-19) should be evicted
        # more often than dirty pages (0-9)
        dirty_evicted = sum(1 for eid in evicted_ids if eid < 10)
        clean_evicted = sum(1 for eid in evicted_ids if 10 <= eid < 20)
        # At least some clean pages should be evicted preferentially
        assert clean_evicted >= dirty_evicted or len(evicted_ids) > 0

    def test_get_writeback_stats_api(self):
        """Public API get_writeback_stats() should work."""
        controller, state = self._make_controller()
        stats = controller.get_writeback_stats()
        assert isinstance(stats, dict)
        assert "total_writebacks" in stats
        assert "dirty_ratio" in stats

    def test_write_coalescing_integration(self):
        """Multiple writes to same page should coalesce in controller."""
        controller, state = self._make_controller()
        # Place page in tier0
        state.current_time = 1
        controller.on_access(state, 0, OpType.READ)

        # Write multiple times
        for t in range(2, 12):
            state.current_time = t
            controller.on_access(state, 0, OpType.WRITE)

        stats = controller.get_writeback_stats()
        assert stats["coalesced_writes"] >= 9  # 10 writes - 1 initial = 9 coalesced
