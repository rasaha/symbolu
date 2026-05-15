"""CPU regression tests for the §20.2 sink-FP16 sweep harness +
composer.

Pins:

* `sink_fp16_sweep.py` dry-run produces a JSON with the §20.2.v1
  schema (model_id, int4_config, rows per sink, deltas vs FP16).
* The composer maps the per-sink deltas to GREEN/YELLOW/RED at the
  pre-decided thresholds (≥ -0.3pt → GREEN; ≥ -0.5pt → YELLOW;
  < -0.5pt → RED).
* The composer's `_find_best_sink` excludes sink=0 (the control)
  so the verdict reflects the best ACHIEVABLE non-zero sink, not
  the baseline being measured against.
* Handles partial input — sweep with no MMLU produces a sane
  "measurement missing" verdict.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


pytest.importorskip("torch")
pytest.importorskip("transformers")


def test_sink_sweep_dry_run_writes_v1_schema(tmp_path: Path):
    """End-to-end dry-run: produces a JSON with the §20.2.v1 schema:
    schema_version, model_id, int4_config (sweep is held FIXED at the
    §18.3 ship config), sink_values, rows (one per sink × cache type),
    deltas (vs FP16).
    """
    from ctm_bench.scripts import sink_fp16_sweep as sweep

    out = tmp_path / "sweep.json"
    rc = sweep.main([
        "--dry-run",
        "--sink-values", "0,4,16",
        "--eval", "perplexity,mmlu",
        "--output", str(out),
    ])
    assert rc == 0
    data = json.loads(out.read_text())
    assert data["schema_version"] == "§20.2.v1"
    assert data["int4_config"]["k_group_size"] == 32
    assert data["int4_config"]["v_group_size"] == 32
    assert data["int4_config"]["asymmetric"] is True
    assert data["int4_config"]["bits"] == 4
    assert data["sink_values"] == [0, 4, 16]

    rows = data["rows"]
    # 1 baseline row + 3 int4 rows (one per sink_value).
    int4_rows = [r for r in rows if r["cache_type"] == "int4-per-channel"]
    assert {r["sink_size"] for r in int4_rows} == {0, 4, 16}

    deltas = data["deltas"]
    assert "per_sink" in deltas
    assert "per_sink_vs_fp16" in deltas
    assert "sink=0" in deltas["per_sink_vs_fp16"]
    assert "sink=4" in deltas["per_sink_vs_fp16"]


def test_compose_inconclusive_when_within_noise_band(tmp_path: Path):
    """A realistic 1000-question sweep where the per-sink MMLU deltas
    (-0.90 / -0.20 / -0.30 pt) span only 0.70pt — well inside the 2σ
    binomial noise band (±4.10pt at 1000q). The composer must NOT
    stamp GREEN on this; the honest verdict is INCONCLUSIVE.

    This is the actual §20.2 GPU-run situation: at 1000 questions the
    sink configurations are statistically indistinguishable, so a
    GREEN ("algorithm axis closed") verdict would overclaim. The
    composer's noise gate (`_sweep_is_noise_dominated`) catches it.
    """
    from ctm_bench.scripts import compose_sink_fp16_summary as comp

    sweep_data = {
        "schema_version": "§20.2.v1",
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "int4_config": {
            "k_group_size": 32, "v_group_size": 32, "asymmetric": True,
            "bits": 4,
            "scheme": "K=per-channel INT4, V=per-token INT4, asymmetric, k_group=32, v_group=32",
        },
        "sink_values": [0, 4, 16],
        "rows": [
            {"sink_size": 0, "cache_type": "baseline",
             "perplexity": 3.7155, "mmlu_accuracy": 0.7020,
             "mmlu_correct": 702, "mmlu_total": 1000},
            {"sink_size": 0, "cache_type": "int4-per-channel",
             "perplexity": 3.8036, "mmlu_accuracy": 0.6930,
             "mmlu_correct": 693, "mmlu_total": 1000},
            {"sink_size": 4, "cache_type": "int4-per-channel",
             "perplexity": 3.7300, "mmlu_accuracy": 0.7000,
             "mmlu_correct": 700, "mmlu_total": 1000},
            {"sink_size": 16, "cache_type": "int4-per-channel",
             "perplexity": 3.7320, "mmlu_accuracy": 0.6990,
             "mmlu_correct": 699, "mmlu_total": 1000},
        ],
        "deltas": {
            "anchor": "sink=0 int4",
            "baseline_fp16_mmlu_accuracy": 0.7020,
            "baseline_fp16_perplexity": 3.7155,
            "sink0_mmlu_accuracy": 0.6930,
            "sink0_perplexity": 3.8036,
            "per_sink_vs_fp16": {
                "sink=0": {"mmlu_delta_pt": -0.90, "perplexity_ratio": 1.0237},
                "sink=4": {"mmlu_delta_pt": -0.20, "perplexity_ratio": 1.0039},
                "sink=16": {"mmlu_delta_pt": -0.30, "perplexity_ratio": 1.0044},
            },
        },
    }
    in_path = tmp_path / "sweep.json"
    out_path = tmp_path / "summary.json"
    in_path.write_text(json.dumps(sweep_data))

    rc = comp.main([
        "--input", str(in_path), "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    assert summary["schema_version"] == "§20.2.v1"
    # best_non_zero_sink is still computed (sink=4 at -0.20pt) — the
    # noise gate doesn't change the arithmetic, only the verdict.
    assert summary["best_non_zero_sink"]["sink_size"] == 4
    # The verdict must be INCONCLUSIVE, NOT GREEN.
    assert "INCONCLUSIVE" in summary["verdict"]
    assert "GREEN" not in summary["verdict"]


def test_sweep_noise_gate_flags_small_spread_at_1000q():
    """`_sweep_is_noise_dominated`: a 1000q sweep whose per-sink MMLU
    deltas span < the 2σ band (~4.1pt) is noise-dominated."""
    from ctm_bench.scripts.compose_sink_fp16_summary import (
        _sweep_is_noise_dominated,
    )
    sweep = {
        "rows": [{"mmlu_total": 1000}],
        "deltas": {"per_sink_vs_fp16": {
            "sink=0": {"mmlu_delta_pt": -0.90},
            "sink=4": {"mmlu_delta_pt": -1.30},
            "sink=16": {"mmlu_delta_pt": 0.0},
            "sink=64": {"mmlu_delta_pt": -0.30},
        }},
    }
    noise, reason = _sweep_is_noise_dominated(sweep)
    assert noise is True
    assert "noise band" in reason
    # The §20.2 GPU run is non-monotonic (sink=4 worse than sink=0) —
    # the reason should call that out as corroborating evidence.
    assert "non-monotonic" in reason


def test_sweep_noise_gate_passes_large_resolved_spread():
    """A spread exceeding the 2σ band → NOT noise-dominated; the
    GREEN/YELLOW/RED verdict path is reachable."""
    from ctm_bench.scripts.compose_sink_fp16_summary import (
        _sweep_is_noise_dominated,
    )
    sweep = {
        "rows": [{"mmlu_total": 1000}],
        "deltas": {"per_sink_vs_fp16": {
            "sink=0": {"mmlu_delta_pt": -6.0},
            "sink=16": {"mmlu_delta_pt": 0.0},
        }},
    }
    noise, reason = _sweep_is_noise_dominated(sweep)
    assert noise is False
    assert "resolved" in reason


def test_sweep_noise_gate_skips_when_no_mmlu_data():
    """No MMLU rows / no question count → the gate cannot assess
    noise and returns False (the band-mapping verdict then applies)."""
    from ctm_bench.scripts.compose_sink_fp16_summary import (
        _sweep_is_noise_dominated,
    )
    noise, reason = _sweep_is_noise_dominated({"rows": [], "deltas": {}})
    assert noise is False
    assert "insufficient" in reason


def test_compose_yellow_band_at_minus_0p4(tmp_path: Path):
    """Best sink at -0.40pt → YELLOW (between -0.5 and -0.3)."""
    from ctm_bench.scripts import compose_sink_fp16_summary as comp

    sweep_data = {
        "schema_version": "§20.2.v1",
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "int4_config": {"scheme": "test"},
        "sink_values": [0, 4],
        "rows": [],
        "deltas": {
            "per_sink_vs_fp16": {
                "sink=0": {"mmlu_delta_pt": -0.90},
                "sink=4": {"mmlu_delta_pt": -0.40},
            },
            "baseline_fp16_mmlu_accuracy": 0.7020,
            "baseline_fp16_perplexity": 3.7155,
        },
    }
    in_path = tmp_path / "sweep.json"
    out_path = tmp_path / "summary.json"
    in_path.write_text(json.dumps(sweep_data))
    rc = comp.main([
        "--input", str(in_path), "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    assert "YELLOW" in summary["verdict"]
    assert summary["best_non_zero_sink"]["sink_size"] == 4


def test_compose_red_band_when_sink_fp16_doesnt_help(tmp_path: Path):
    """Best sink at -0.70pt → RED (sink-FP16 hypothesis falsified)."""
    from ctm_bench.scripts import compose_sink_fp16_summary as comp

    sweep_data = {
        "schema_version": "§20.2.v1",
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "int4_config": {"scheme": "test"},
        "sink_values": [0, 4],
        "rows": [],
        "deltas": {
            "per_sink_vs_fp16": {
                "sink=0": {"mmlu_delta_pt": -0.90},
                "sink=4": {"mmlu_delta_pt": -0.70},
            },
            "baseline_fp16_mmlu_accuracy": 0.7020,
            "baseline_fp16_perplexity": 3.7155,
        },
    }
    in_path = tmp_path / "sweep.json"
    out_path = tmp_path / "summary.json"
    in_path.write_text(json.dumps(sweep_data))
    rc = comp.main([
        "--input", str(in_path), "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    assert "RED" in summary["verdict"]


def test_compose_decision_tree_boundaries():
    """Pin the GREEN / YELLOW / RED thresholds at -0.3 / -0.5 pt.
    These match the runbook §5i / PHASE4_GPU_FINDINGS §20.2 contract."""
    from ctm_bench.scripts.compose_sink_fp16_summary import (
        _verdict_best_sink, GREEN_THRESHOLD_PT, YELLOW_THRESHOLD_PT,
    )

    assert GREEN_THRESHOLD_PT == -0.3
    assert YELLOW_THRESHOLD_PT == -0.5

    assert "GREEN" in _verdict_best_sink(-0.30)
    assert "GREEN" in _verdict_best_sink(-0.10)
    assert "GREEN" in _verdict_best_sink(0.0)
    assert "YELLOW" in _verdict_best_sink(-0.31)
    assert "YELLOW" in _verdict_best_sink(-0.50)
    assert "RED" in _verdict_best_sink(-0.51)
    assert "RED" in _verdict_best_sink(-1.0)


def test_compose_find_best_sink_excludes_zero():
    """`_find_best_sink` must exclude sink=0 (the control measurement)
    so the verdict reflects what's ACHIEVABLE, not the baseline.

    If sink=0 has a smaller absolute delta than all non-zero sinks,
    the function should still return the best NON-zero sink.
    """
    from ctm_bench.scripts.compose_sink_fp16_summary import _find_best_sink

    # Pathological case: sink=0 has 0.0 delta but other sinks made
    # things worse. The function should return the best of the others
    # (here, sink=4 with -0.5), not sink=0.
    deltas = {
        "sink=0": {"mmlu_delta_pt": 0.0},
        "sink=4": {"mmlu_delta_pt": -0.5},
        "sink=16": {"mmlu_delta_pt": -1.0},
    }
    sink, delta = _find_best_sink(deltas)
    assert sink == 4
    assert delta == pytest.approx(-0.5)

    # Normal case: sink=4 helps the most.
    deltas2 = {
        "sink=0": {"mmlu_delta_pt": -0.9},
        "sink=4": {"mmlu_delta_pt": -0.2},
        "sink=16": {"mmlu_delta_pt": -0.3},
        "sink=64": {"mmlu_delta_pt": -0.5},
    }
    sink, delta = _find_best_sink(deltas2)
    assert sink == 4
    assert delta == pytest.approx(-0.2)


def test_compose_verdict_uses_measured_control_not_hardcoded():
    """M2 fix: the verdict text must reference the ACTUAL measured
    sink=0 control delta, not hardcode `−0.9pt`. If the GPU run
    produces a different control (e.g., −1.1pt or −0.7pt due to
    statistical noise on a different question subset), the verdict
    should reflect that number.
    """
    from ctm_bench.scripts.compose_sink_fp16_summary import _verdict_best_sink

    # GREEN case with control = -0.75pt (different from the
    # historical -0.9pt).
    v = _verdict_best_sink(-0.20, sink0_mmlu_delta_pt=-0.75)
    assert "-0.75" in v or "−0.75" in v, (
        f"verdict text must include the measured control -0.75 pt; "
        f"got: {v!r}"
    )
    # YELLOW case with control = -1.10pt.
    v = _verdict_best_sink(-0.40, sink0_mmlu_delta_pt=-1.10)
    assert "-1.10" in v or "−1.10" in v
    # RED case with control = -0.85pt.
    v = _verdict_best_sink(-0.60, sink0_mmlu_delta_pt=-0.85)
    assert "-0.85" in v or "−0.85" in v

    # When control is None (composer called against a partial sweep
    # without sink=0), fall back to the historical reference language.
    v = _verdict_best_sink(-0.20, sink0_mmlu_delta_pt=None)
    assert "§19.4" in v or "−0.9pt" in v or "-0.9pt" in v


def test_compose_handles_missing_mmlu_gracefully(tmp_path: Path):
    """If the sweep ran without MMLU (only perplexity), composer should
    return verdict="MEASUREMENT MISSING" rather than crash."""
    from ctm_bench.scripts import compose_sink_fp16_summary as comp

    sweep_data = {
        "schema_version": "§20.2.v1",
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "int4_config": {"scheme": "test"},
        "sink_values": [0, 4],
        "rows": [
            {"sink_size": 0, "cache_type": "int4-per-channel",
             "perplexity": 3.80},
            {"sink_size": 4, "cache_type": "int4-per-channel",
             "perplexity": 3.73},
        ],
        "deltas": {
            "per_sink_vs_fp16": {},
            "baseline_fp16_perplexity": 3.71,
        },
    }
    in_path = tmp_path / "sweep.json"
    out_path = tmp_path / "summary.json"
    in_path.write_text(json.dumps(sweep_data))
    rc = comp.main([
        "--input", str(in_path), "--json-output", str(out_path),
    ])
    assert rc == 0
    summary = json.loads(out_path.read_text())
    assert "MEASUREMENT MISSING" in summary["verdict"]
