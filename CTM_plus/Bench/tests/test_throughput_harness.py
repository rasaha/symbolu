"""CPU regression tests for ``ctm_bench.scripts.track_e_throughput``.

Pins:

* The dry-run path produces a valid JSON artefact with the expected
  schema (cells + aggregates + ratio block).
* The timing helpers handle CUDA-sync on CPU as a no-op (so the
  harness runs identically on the GPU pod and on this CPU dev pod
  for shape verification).
* The aggregator picks the best-of-trials value (matters: a single
  CUDA-launch jitter spike during a 5-trial sweep shouldn't lower
  the headline number).

These tests do NOT measure throughput — they verify the harness
shape. Real throughput numbers come from the GPU run that produces
``Bench/bench_out/track_e_audit_followups/int4_throughput_hf.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


pytest.importorskip("torch")
pytest.importorskip("transformers")


def test_dry_run_writes_expected_schema(tmp_path: Path):
    """The dry-run path produces JSON with: top-level model_id/dtype/
    device/config, a cells list, and an aggregates dict containing
    both per-cell summaries and an ``int4_vs_baseline`` ratio block.

    Pinning the schema here means the partner-shareable artefact
    surface stays stable as the timing internals evolve.
    """
    from ctm_bench.scripts import track_e_throughput as tp

    out = tmp_path / "throughput.json"
    rc = tp.main([
        "--dry-run",
        "--prefill-lengths", "32,64",
        "--decode-tokens", "4",
        "--trials", "2",
        "--warmup", "1",
        "--output", str(out),
    ])
    assert rc == 0
    assert out.exists()

    data = json.loads(out.read_text())
    assert "model_id" in data
    assert "config" in data
    assert data["config"]["quant"] == "int4-per-channel"
    assert data["config"]["asymmetric"] is True
    assert data["config"]["k_group_size"] == 32
    assert data["config"]["v_group_size"] == 32

    cells = data["cells"]
    # 2 caches × 2 prefill lengths × 2 trials = 8 cells.
    assert len(cells) == 8
    seen = {(c["cache_type"], c["prefill_tokens"], c["trial"]) for c in cells}
    assert ("baseline", 32, 0) in seen
    assert ("baseline", 64, 1) in seen
    assert ("int4-per-channel", 32, 0) in seen
    assert ("int4-per-channel", 64, 1) in seen
    for c in cells:
        assert c["prefill_ms"] >= 0.0
        assert c["decode_ms"] >= 0.0
        assert c["decode_tokens"] == 4

    aggs = data["aggregates"]
    assert "baseline@prefill=32" in aggs
    assert "int4-per-channel@prefill=64" in aggs
    assert "int4_vs_baseline" in aggs
    ratios = aggs["int4_vs_baseline"]
    assert "prefill=32" in ratios and "prefill=64" in ratios
    for plen in (32, 64):
        cell_ratio = ratios[f"prefill={plen}"]
        # Sign: INT4 is slower on CPU dry-run (ratio < 1.0). On GPU
        # with real kernels the sign can flip, but the schema is
        # the same.
        assert "int4_vs_baseline_decode_tps_ratio" in cell_ratio
        assert "int4_decode_overhead_pct" in cell_ratio


def test_aggregator_picks_best_of_trials():
    """The headline ``best_decode_tokens_per_sec`` must be max() across
    trials, not mean(). Means absorb a single jitter spike; bests
    expose the steady-state ceiling.
    """
    from ctm_bench.scripts.track_e_throughput import (
        ThroughputCell, _compute_aggregates,
    )

    # Two trials at the same (cache, prefill) — first slow (jitter),
    # second fast (steady state). Headline should pick the fast one.
    cells = [
        ThroughputCell(
            cache_type="baseline", prefill_tokens=128, decode_tokens=8,
            trial=0, prefill_ms=10.0, decode_ms=50.0,
            decode_tokens_per_sec=160.0, total_tokens_per_sec=2266.0,
        ),
        ThroughputCell(
            cache_type="baseline", prefill_tokens=128, decode_tokens=8,
            trial=1, prefill_ms=10.0, decode_ms=20.0,
            decode_tokens_per_sec=400.0, total_tokens_per_sec=4533.0,
        ),
    ]
    aggs = _compute_aggregates(cells)
    key = "baseline@prefill=128"
    assert aggs[key]["best_decode_tokens_per_sec"] == 400.0
    assert aggs[key]["median_decode_tokens_per_sec"] == pytest.approx(280.0)
    assert aggs[key]["n_trials"] == 2


def test_cuda_sync_is_noop_on_cpu():
    """``_cuda_sync`` must accept CPU devices (real and string-typed)
    without raising. Means the harness shape is identical whether
    we're on the GPU pod or on the CPU dev pod doing a dry-run.
    """
    import torch
    from ctm_bench.scripts.track_e_throughput import _cuda_sync

    # No-op paths.
    _cuda_sync(torch.device("cpu"))
    _cuda_sync("cpu")
    _cuda_sync(None)  # type: ignore[arg-type] — defensive against missing .type


def test_sink_size_threads_into_int4_config(tmp_path: Path):
    """The ``--sink-size`` flag must flow into the config artefact so
    the §20.2 sink-FP16 + body-INT4 sweep is reproducible from JSON
    alone. Other sweep dimensions: prefill_lengths, group sizes.
    """
    from ctm_bench.scripts import track_e_throughput as tp

    out = tmp_path / "throughput_sink.json"
    rc = tp.main([
        "--dry-run",
        "--prefill-lengths", "32",
        "--decode-tokens", "2",
        "--trials", "1",
        "--warmup", "1",
        "--sink-size", "4",
        "--output", str(out),
    ])
    assert rc == 0
    data = json.loads(out.read_text())
    assert data["config"]["sink_size"] == 4
    assert "sink_size=4" in data["config"]["scheme"]
