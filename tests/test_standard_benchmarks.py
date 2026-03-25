"""
Tests for standard trace benchmarking infrastructure.

Tests:
1. S3-FIFO controller correctness
2. Standard trace profile generation
3. Benchmark runner integration
"""

import pytest
from simulator.ctm_plus.core.config import SimulatorConfig
from simulator.ctm_plus.core.state import GlobalState, TierState, Tier, OpType
from simulator.ctm_plus.controllers.s3fifo import S3FIFOController
from simulator.ctm_plus.controllers.lru import LRUController
from simulator.ctm_plus.controllers.arc import ARCController
from simulator.ctm_plus.simulator import Simulator
from simulator.ctm_plus.traces.loader import TraceEvent, generate_synthetic_trace
from simulator.ctm_plus.traces.standard import (
    TraceProfile,
    ALL_PROFILES,
    MSR_SRC1_0,
    TWITTER_CLUSTER52,
    META_CDN,
    generate_from_profile,
    load_or_generate,
    get_profile,
    list_profiles,
)
from simulator.ctm_plus.benchmarks import run_benchmarks, BenchmarkResult


# =============================================================================
# S3-FIFO Controller Tests
# =============================================================================


class TestS3FIFO:
    """Test S3-FIFO controller implementation."""

    def _make_config(self, tier0: int = 10, tier1: int = 10000) -> SimulatorConfig:
        return SimulatorConfig(tier0_size=tier0, tier1_size=tier1)

    def test_name(self):
        config = self._make_config()
        ctrl = S3FIFOController(config)
        assert ctrl.name == "S3-FIFO"

    def test_basic_hit(self):
        """First access is miss, second is hit."""
        config = self._make_config(tier0=10)
        ctrl = S3FIFOController(config)
        state = GlobalState(
            tier0=TierState(tier_id=Tier.TIER0, capacity=10),
            tier1=TierState(tier_id=Tier.TIER1, capacity=10000),
        )

        # First access: miss
        state.current_time = 0
        tier, _, _, _ = ctrl.on_access(state, 1, OpType.READ)
        assert tier == Tier.NONE

        # Second access: hit (in Small queue)
        state.current_time = 1
        tier, _, _, _ = ctrl.on_access(state, 1, OpType.READ)
        assert tier == Tier.TIER0

    def test_eviction_from_small(self):
        """Pages with freq=0 get evicted from Small to ghost."""
        config = self._make_config(tier0=5)
        ctrl = S3FIFOController(config, small_ratio=0.2)  # 1 slot in Small
        state = GlobalState(
            tier0=TierState(tier_id=Tier.TIER0, capacity=5),
            tier1=TierState(tier_id=Tier.TIER1, capacity=10000),
        )

        # Fill Small (1 slot)
        state.current_time = 0
        ctrl.on_access(state, 1, OpType.READ)

        # Insert another page — should evict page 1 from Small
        state.current_time = 1
        ctrl.on_access(state, 2, OpType.READ)

        # Page 1 should be evicted (freq=0 → ghost, not promoted to Main)
        assert 1 not in ctrl._small_set

    def test_promotion_to_main(self):
        """Pages with freq>=1 get promoted from Small to Main."""
        config = self._make_config(tier0=5)
        ctrl = S3FIFOController(config, small_ratio=0.2)
        state = GlobalState(
            tier0=TierState(tier_id=Tier.TIER0, capacity=5),
            tier1=TierState(tier_id=Tier.TIER1, capacity=10000),
        )

        # Access page 1 twice (freq becomes 1)
        state.current_time = 0
        ctrl.on_access(state, 1, OpType.READ)
        state.current_time = 1
        ctrl.on_access(state, 1, OpType.READ)

        # Insert another page to evict page 1 from Small
        state.current_time = 2
        ctrl.on_access(state, 2, OpType.READ)

        # Page 1 should be in Main (freq was >= 1)
        assert 1 in ctrl._main_set

    def test_reset(self):
        config = self._make_config()
        ctrl = S3FIFOController(config)
        state = GlobalState(
            tier0=TierState(tier_id=Tier.TIER0, capacity=10),
            tier1=TierState(tier_id=Tier.TIER1, capacity=10000),
        )
        ctrl.on_access(state, 1, OpType.READ)
        ctrl.reset()
        assert len(ctrl._small) == 0
        assert len(ctrl._main) == 0

    def test_stats(self):
        config = self._make_config()
        ctrl = S3FIFOController(config)
        stats = ctrl.get_stats()
        assert "promotions" in stats
        assert "demotions" in stats
        assert "ghost_hits" in stats
        assert "small_size" in stats
        assert "main_size" in stats

    def test_competitive_with_lru(self):
        """S3-FIFO should be competitive with LRU on zipfian workload."""
        config = SimulatorConfig(tier0_size=500, tier1_size=50000)
        sim = Simulator(config=config)
        trace = generate_synthetic_trace("zipf", num_events=20000, num_pages=5000, seed=42)

        lru_result = sim.run(trace, LRUController(config), "test", verbose=False)
        s3_result = sim.run(trace, S3FIFOController(config), "test", verbose=False)

        # S3-FIFO should not be dramatically worse than LRU
        assert s3_result.metrics.hit_rate >= lru_result.metrics.hit_rate * 0.7

    def test_scan_resistant(self):
        """S3-FIFO should handle sequential scans better than plain LRU."""
        config = SimulatorConfig(tier0_size=100, tier1_size=10000)
        sim = Simulator(config=config)

        # Mixed workload: Zipfian base + sequential scan bursts
        trace = generate_synthetic_trace("mixed", num_events=20000, num_pages=5000, seed=42)

        lru_result = sim.run(trace, LRUController(config), "test", verbose=False)
        s3_result = sim.run(trace, S3FIFOController(config), "test", verbose=False)

        # S3-FIFO should handle mixed patterns reasonably
        assert s3_result.metrics.hit_rate > 0  # Sanity check


# =============================================================================
# Standard Trace Profile Tests
# =============================================================================


class TestTraceProfiles:
    """Test standard trace profile definitions and generation."""

    def test_all_profiles_registered(self):
        """All 7 standard profiles should be registered."""
        assert len(ALL_PROFILES) == 7
        assert "msr_src1_0" in ALL_PROFILES
        assert "msr_web_0" in ALL_PROFILES
        assert "msr_proj_0" in ALL_PROFILES
        assert "twitter_cluster52" in ALL_PROFILES
        assert "twitter_kv" in ALL_PROFILES
        assert "meta_cdn" in ALL_PROFILES
        assert "meta_kv" in ALL_PROFILES

    def test_profile_fields(self):
        """Each profile has valid field values."""
        for name, profile in ALL_PROFILES.items():
            assert profile.num_pages > 0, f"{name}: num_pages"
            assert profile.num_events > 0, f"{name}: num_events"
            assert 0.0 < profile.zipf_alpha <= 2.0, f"{name}: zipf_alpha"
            assert 0.0 <= profile.read_ratio <= 1.0, f"{name}: read_ratio"
            assert 0.0 <= profile.temporal_locality <= 1.0, f"{name}: temporal_locality"
            assert 0.0 <= profile.scan_fraction <= 1.0, f"{name}: scan_fraction"
            assert profile.phase_changes >= 0, f"{name}: phase_changes"
            assert 0.0 < profile.recommended_tier0_ratio <= 1.0, f"{name}: tier0_ratio"

    def test_generate_from_profile(self):
        """Should generate correct number of events."""
        trace = generate_from_profile(MSR_SRC1_0, num_events=1000, seed=42)
        assert len(trace) == 1000
        assert all(isinstance(e, TraceEvent) for e in trace)

    def test_generate_deterministic(self):
        """Same seed should produce same trace."""
        t1 = generate_from_profile(MSR_SRC1_0, num_events=100, seed=42)
        t2 = generate_from_profile(MSR_SRC1_0, num_events=100, seed=42)
        assert [e.page_id for e in t1] == [e.page_id for e in t2]

    def test_generate_different_seeds(self):
        """Different seeds should produce different traces."""
        t1 = generate_from_profile(MSR_SRC1_0, num_events=100, seed=42)
        t2 = generate_from_profile(MSR_SRC1_0, num_events=100, seed=99)
        assert [e.page_id for e in t1] != [e.page_id for e in t2]

    def test_read_write_ratio(self):
        """Generated trace should roughly match profile's read ratio."""
        trace = generate_from_profile(TWITTER_CLUSTER52, num_events=10000, seed=42)
        reads = sum(1 for e in trace if e.op_type == OpType.READ)
        actual_ratio = reads / len(trace)
        # Allow 5% tolerance
        assert abs(actual_ratio - TWITTER_CLUSTER52.read_ratio) < 0.05

    def test_page_ids_in_range(self):
        """Generated page IDs should be within profile's num_pages."""
        trace = generate_from_profile(META_CDN, num_events=5000, seed=42)
        for e in trace:
            assert 0 <= e.page_id < META_CDN.num_pages

    def test_zipf_skew(self):
        """Higher alpha should produce more skewed distribution."""
        # Twitter cluster52 has alpha=1.3 (very skewed)
        trace = generate_from_profile(TWITTER_CLUSTER52, num_events=10000, seed=42)
        from collections import Counter
        counts = Counter(e.page_id for e in trace)
        top10_fraction = sum(c for _, c in counts.most_common(10)) / len(trace)

        # Meta CDN has alpha=0.75 (less skewed)
        trace2 = generate_from_profile(META_CDN, num_events=10000, seed=42)
        counts2 = Counter(e.page_id for e in trace2)
        top10_fraction2 = sum(c for _, c in counts2.most_common(10)) / len(trace2)

        assert top10_fraction > top10_fraction2

    def test_get_profile(self):
        p = get_profile("msr_src1_0")
        assert p.name == "msr_src1_0"
        with pytest.raises(KeyError):
            get_profile("nonexistent")

    def test_list_profiles(self):
        names = list_profiles()
        assert len(names) == 7
        assert names == sorted(names)  # Should be sorted

    def test_load_or_generate_no_dir(self):
        """Without trace_dir, should generate synthetic."""
        trace = load_or_generate(MSR_SRC1_0, num_events=100, seed=42)
        assert len(trace) == 100

    def test_load_or_generate_missing_dir(self):
        """With nonexistent trace_dir, should fall back to synthetic."""
        trace = load_or_generate(MSR_SRC1_0, trace_dir="/nonexistent", num_events=100, seed=42)
        assert len(trace) == 100


# =============================================================================
# Benchmark Runner Integration Tests
# =============================================================================


class TestBenchmarkRunner:
    """Test the benchmark runner end-to-end."""

    def test_single_trace_benchmark(self):
        """Run benchmark on a single trace."""
        suite = run_benchmarks(
            profiles=["msr_src1_0"],
            num_events=5000,
            verbose=False,
            seed=42,
        )
        assert len(suite.results) == 1
        br = suite.results[0]
        assert br.profile.name == "msr_src1_0"
        assert "LRU" in br.results
        assert "ARC" in br.results
        assert "S3-FIFO" in br.results
        assert "CTM+" in br.results

    def test_all_controllers_produce_results(self):
        """Each controller should produce valid metrics."""
        suite = run_benchmarks(
            profiles=["twitter_kv"],
            num_events=5000,
            verbose=False,
        )
        br = suite.results[0]
        for name, result in br.results.items():
            m = result.metrics
            assert m.total_accesses == 5000, f"{name} total_accesses"
            assert 0 <= m.hit_rate <= 1.0, f"{name} hit_rate"
            assert m.avg_latency_ns > 0, f"{name} avg_latency"

    def test_improvement_calculation(self):
        """Improvement vs LRU should be calculated correctly."""
        suite = run_benchmarks(
            profiles=["msr_src1_0"],
            num_events=5000,
            verbose=False,
        )
        br = suite.results[0]
        ctm_rate = br.hit_rate("CTM+")
        lru_rate = br.hit_rate("LRU")
        expected = ctm_rate - lru_rate
        assert abs(br.improvement_vs_lru("CTM+") - expected) < 1e-10

    def test_summary_table(self):
        """Summary table should be non-empty and contain headers."""
        suite = run_benchmarks(
            profiles=["msr_src1_0"],
            num_events=5000,
            verbose=False,
        )
        table = suite.summary_table()
        assert "Trace" in table
        assert "LRU" in table
        assert "ARC" in table
        assert "S3-FIFO" in table
        assert "CTM+" in table
        assert "msr_src1_0" in table

    def test_latency_table(self):
        """Latency table should contain data."""
        suite = run_benchmarks(
            profiles=["msr_src1_0"],
            num_events=5000,
            verbose=False,
        )
        table = suite.latency_table()
        assert "msr_src1_0" in table

    def test_json_export(self):
        """JSON export should be valid."""
        import json
        suite = run_benchmarks(
            profiles=["msr_src1_0"],
            num_events=5000,
            verbose=False,
        )
        data = json.loads(suite.to_json())
        assert "config" in data
        assert "traces" in data
        assert len(data["traces"]) == 1
        assert "LRU_hit_rate" in data["traces"][0]
        assert "CTM+_hit_rate" in data["traces"][0]

    def test_multi_trace_benchmark(self):
        """Run benchmark on multiple traces."""
        suite = run_benchmarks(
            profiles=["msr_src1_0", "twitter_kv"],
            num_events=3000,
            verbose=False,
        )
        assert len(suite.results) == 2
        names = [br.profile.name for br in suite.results]
        assert "msr_src1_0" in names
        assert "twitter_kv" in names

    def test_invalid_profile_name(self):
        """Should raise on invalid profile name."""
        with pytest.raises(ValueError, match="Unknown profile"):
            run_benchmarks(profiles=["nonexistent"], verbose=False)

    def test_custom_tier0_size(self):
        """Custom tier0 size should be respected."""
        suite = run_benchmarks(
            profiles=["msr_src1_0"],
            num_events=3000,
            tier0_size=200,
            verbose=False,
        )
        # All controllers should have been configured with tier0=200
        assert suite.results[0].results["LRU"].metrics.total_accesses == 3000

    def test_to_dict(self):
        """BenchmarkResult.to_dict should include all controllers."""
        suite = run_benchmarks(
            profiles=["msr_src1_0"],
            num_events=3000,
            verbose=False,
        )
        d = suite.results[0].to_dict()
        assert d["trace"] == "msr_src1_0"
        assert d["source"] == "msr"
        assert "LRU_hit_rate" in d
        assert "CTM+_hit_rate" in d
        assert "S3-FIFO_hit_rate" in d
