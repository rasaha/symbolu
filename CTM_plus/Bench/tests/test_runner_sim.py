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


def test_decode_token_count_matches_workload_duration():
    """Audit Finding #3 regression-pin: ``n_decode_tokens`` in
    RunResult must equal ``n_concurrent_seqs * duration_decode_tokens``.
    The pre-fix heuristic over-counted by ~2x."""
    spec = WorkloadSpec(
        name="count_check",
        pattern=AccessPattern.RAG,
        n_concurrent_seqs=2,
        context_length_tokens=512,
        duration_decode_tokens=16,
        block_size_tokens=16,
        seed=42,
    )
    result = run_sim(
        spec,
        "lru",
        HBM_DDR_NVME_2025,
        block_bytes=4096,
        hbm_oversubscription=0.5,
    )
    expected = spec.n_concurrent_seqs * spec.duration_decode_tokens
    assert result.n_decode_tokens == expected


def test_runner_uses_public_residency_methods():
    """Audit Finding #10 regression-pin: the runner must call
    the public TieredCache methods, not reach into ``_residency``.
    Tokenise the runner source to skip comments + docstrings so
    explanatory text mentioning ``_residency`` does not falsely
    fail the check."""
    import inspect
    import io
    import token
    import tokenize

    from ctm_bench import runner_sim

    src = inspect.getsource(runner_sim.run_sim)
    code_tokens = []
    for tok in tokenize.tokenize(io.BytesIO(src.encode()).readline):
        if tok.type in (token.COMMENT, token.STRING):
            continue
        code_tokens.append(tok.string)
    code_only = " ".join(code_tokens)
    assert "_residency" not in code_only, (
        "runner_sim.run_sim still references TieredCache._residency; "
        "use cache.is_resident_in_tier_0() / cache.tier_0_resident_ids()"
    )


def test_runresult_counter_source_defaults_empty_and_serialises():
    """Mode A produces RunResults with no counter_source; the
    field defaults to empty string and serialises through
    to_dict() for downstream JSON output. This is the
    regression-pin for the counter_source field added so a
    reader of vllm_summary.json can tell whether all-zero
    counters mean "API mismatch", "no swaps", or "real-data"."""
    from ctm_bench.metrics import RunResult

    # Mode A construction (no counter_source supplied).
    r = RunResult(
        workload_name="x",
        policy_name="lru",
        tier_config_name="hbm_ddr_nvme",
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
    assert r.counter_source == ""
    assert r.to_dict()["counter_source"] == ""

    # Mode B construction (counter_source set).
    r_b = RunResult(
        workload_name="x",
        policy_name="lru",
        tier_config_name="vllm_real",
        n_decode_tokens=100,
        bytes_read={"DDR": 1024},
        bytes_written={},
        accesses_served={},
        cumulative_latency_ns={},
        evictions_to_tier={},
        hbm_hit_rate=0.95,
        slow_tier_bytes_per_decode_token=10.24,
        avg_access_latency_ns=300.0,
        wall_clock_seconds=5.0,
        seed=42,
        counter_source="vllm_0_7_block_allocator_swaps",
    )
    assert r_b.to_dict()["counter_source"] == "vllm_0_7_block_allocator_swaps"


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
