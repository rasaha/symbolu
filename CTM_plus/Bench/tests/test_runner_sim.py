"""End-to-end smoke + behaviour tests for the Mode A runner."""

from __future__ import annotations

import math

import pytest

from ctm_bench.metrics import RunResult, markdown_table, summarize
from ctm_bench.runner_sim import (
    DEFAULT_HBM_OVERSUBSCRIPTION,
    _tier_0_capacity_blocks_for,
    run_sim,
)
from ctm_bench.tier_model import HBM_DDR_NVME_2025
from ctm_bench.workload import AccessPattern, WorkloadSpec


def _smoke_spec(pattern: AccessPattern) -> WorkloadSpec:
    return WorkloadSpec(
        name=f"smoke_{pattern.value}",
        pattern=pattern,
        n_concurrent_seqs=2,
        context_length_tokens=128,
        duration_decode_tokens=16,
        block_size_tokens=16,
        seed=11,
    )


def test_tier_0_capacity_rejects_invalid_oversubscription():
    spec = _smoke_spec(AccessPattern.RAG)
    with pytest.raises(ValueError, match="oversubscription"):
        _tier_0_capacity_blocks_for(spec, 0.0)
    with pytest.raises(ValueError, match="oversubscription"):
        _tier_0_capacity_blocks_for(spec, 1.5)


def test_tier_0_capacity_returns_at_least_eight_blocks():
    spec = WorkloadSpec(
        name="tiny",
        pattern=AccessPattern.RAG,
        n_concurrent_seqs=1,
        context_length_tokens=16,
        duration_decode_tokens=1,
        block_size_tokens=16,
    )
    capacity = _tier_0_capacity_blocks_for(spec, 0.1)
    assert capacity >= 8


def test_run_sim_lru_returns_runresult_with_consistent_counters():
    spec = _smoke_spec(AccessPattern.AGENTIC)
    result = run_sim(
        spec,
        "lru",
        HBM_DDR_NVME_2025,
        tier_config_name="hbm_ddr_nvme",
        block_bytes=4096,
        hbm_oversubscription=0.5,
    )
    assert isinstance(result, RunResult)
    assert result.workload_name == spec.name
    assert result.policy_name == "lru"
    assert 0.0 <= result.hbm_hit_rate <= 1.0
    # At least one access happened.
    assert sum(result.accesses_served.values()) > 0
    # The RunResult should round-trip cleanly through to_dict.
    d = result.to_dict()
    assert d["policy_name"] == "lru"


def test_run_sim_fifo_runs_to_completion():
    spec = _smoke_spec(AccessPattern.RAG)
    result = run_sim(
        spec,
        "fifo",
        HBM_DDR_NVME_2025,
        block_bytes=4096,
        hbm_oversubscription=0.5,
    )
    assert result.wall_clock_seconds >= 0.0
    assert result.n_decode_tokens > 0


def test_run_sim_clustered_agentic_workload():
    spec = _smoke_spec(AccessPattern.AGENTIC_CLUSTERED)
    result = run_sim(
        spec,
        "lru",
        HBM_DDR_NVME_2025,
        block_bytes=4096,
        hbm_oversubscription=0.5,
    )
    assert result.n_decode_tokens > 0
    assert sum(result.accesses_served.values()) > 0


def test_run_sim_chat_workload():
    spec = _smoke_spec(AccessPattern.CHAT)
    result = run_sim(
        spec,
        "lru",
        HBM_DDR_NVME_2025,
        block_bytes=4096,
        hbm_oversubscription=0.5,
    )
    # Sink protection: HBM hit rate on chat should be reasonably
    # high since sink + recent blocks are re-read every step.
    assert result.hbm_hit_rate > 0.3


def test_summarize_zero_baseline_yields_none_not_inf():
    """When LRU baseline has no slow-tier reads, the reduction
    percentage is undefined. We must emit None (not ±inf) so
    the JSON output stays well-formed under allow_nan=False."""
    from ctm_bench.metrics import RunResult, summarize, to_json

    base = RunResult(
        workload_name="w",
        policy_name="lru",
        tier_config_name="x",
        n_decode_tokens=10,
        bytes_read={},
        bytes_written={},
        accesses_served={},
        cumulative_latency_ns={},
        evictions_to_tier={},
        hbm_hit_rate=1.0,
        slow_tier_bytes_per_decode_token=0.0,
        avg_access_latency_ns=200.0,
        wall_clock_seconds=0.01,
        seed=42,
    )
    other = RunResult(
        workload_name="w",
        policy_name="ctm_plus",
        tier_config_name="x",
        n_decode_tokens=10,
        bytes_read={},
        bytes_written={},
        accesses_served={},
        cumulative_latency_ns={},
        evictions_to_tier={},
        hbm_hit_rate=0.99,
        slow_tier_bytes_per_decode_token=1024.0,
        avg_access_latency_ns=300.0,
        wall_clock_seconds=0.01,
        seed=42,
    )
    summary = summarize([base, other])
    assert summary["pairs"][0]["reduction_pct_vs_lru"] is None
    # JSON serialisation must not raise on the None value.
    blob = to_json(summary)
    assert "null" in blob


def test_summarize_includes_pairs_when_lru_baseline_present():
    spec = _smoke_spec(AccessPattern.AGENTIC)
    a = run_sim(
        spec,
        "lru",
        HBM_DDR_NVME_2025,
        block_bytes=4096,
        hbm_oversubscription=0.5,
    )
    b = run_sim(
        spec,
        "fifo",
        HBM_DDR_NVME_2025,
        block_bytes=4096,
        hbm_oversubscription=0.5,
    )
    summary = summarize([a, b])
    assert "cells" in summary
    assert "pairs" in summary
    assert len(summary["cells"]) == 2
    assert len(summary["pairs"]) == 1
    pair = summary["pairs"][0]
    assert pair["baseline"] == "lru"
    assert pair["policy"] == "fifo"
    assert math.isfinite(pair["reduction_pct_vs_lru"])


def test_summarize_handles_no_lru_baseline():
    spec = _smoke_spec(AccessPattern.RAG)
    only_fifo = run_sim(
        spec,
        "fifo",
        HBM_DDR_NVME_2025,
        block_bytes=4096,
        hbm_oversubscription=0.5,
    )
    summary = summarize([only_fifo])
    assert summary["pairs"] == []


def test_markdown_table_renders_a_row_per_result():
    spec = _smoke_spec(AccessPattern.CHAT)
    a = run_sim(
        spec,
        "lru",
        HBM_DDR_NVME_2025,
        block_bytes=4096,
        hbm_oversubscription=0.5,
    )
    b = run_sim(
        spec,
        "fifo",
        HBM_DDR_NVME_2025,
        block_bytes=4096,
        hbm_oversubscription=0.5,
    )
    table = markdown_table([a, b])
    assert "Workload" in table
    assert spec.name in table
    assert "lru" in table
    assert "fifo" in table


def test_markdown_table_handles_empty_results():
    assert markdown_table([]).strip() == "| (no results) |"
