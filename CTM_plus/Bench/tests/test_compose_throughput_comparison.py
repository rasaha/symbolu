"""CPU regression tests for
``ctm_bench.scripts.compose_throughput_comparison``.

Pins:

* Renders markdown for the 4-cell comparison when all cells present.
* Renders ``MEASUREMENT MISSING`` markers cleanly when one or more
  cells are absent — never emits fake numbers.
* Computes the B/A and D/C ratios correctly.
* Maps ratios to the correct decision-tree band (GREEN/YELLOW/RED for
  the D/C axis; the three-band runbook contract).
* The optional `--json-output` writes a single merged JSON with the
  ratios + verdicts pre-computed.

The composer is the operator's last step before pasting numbers into
PHASE4_GPU_FINDINGS §20.1; tests pin that surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_vllm_cell(path: Path, *, tps: float, n_completed: int = 5,
                     swap_out: int = 0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "tokens_per_second": tps,
        "n_requests_completed": n_completed,
        "n_requests_admitted": n_completed,
        "n_decode_tokens": 1024,
        "swap_out_blocks": swap_out,
        "wall_clock_seconds": 60.0,
        "workload_name": "chat_32k",
        "policy_name": "lru",
    }))


def _write_hf_cell(path: Path, *, baseline_tps: float, int4_tps: float,
                   prefill: int = 2048):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "config": {
            "quant": "int4-per-channel",
            "k_group_size": 32, "v_group_size": 32,
            "asymmetric": True, "bits": 4, "sink_size": 0,
        },
        "aggregates": {
            f"baseline@prefill={prefill}": {
                "best_decode_tokens_per_sec": baseline_tps,
                "median_decode_tokens_per_sec": baseline_tps * 0.95,
                "median_prefill_ms": 100.0,
                "n_trials": 5,
            },
            f"int4-per-channel@prefill={prefill}": {
                "best_decode_tokens_per_sec": int4_tps,
                "median_decode_tokens_per_sec": int4_tps * 0.95,
                "median_prefill_ms": 120.0,
                "n_trials": 5,
            },
            "int4_vs_baseline": {
                f"prefill={prefill}": {
                    "int4_vs_baseline_decode_tps_ratio": int4_tps / baseline_tps,
                    "int4_vs_baseline_total_tps_ratio": int4_tps / baseline_tps,
                    "int4_decode_overhead_pct": (
                        (baseline_tps - int4_tps) / baseline_tps * 100.0
                    ),
                },
            },
        },
    }))


def test_compose_with_all_cells_present(tmp_path: Path, capsys):
    """Happy path — all four cells present. Markdown renders both
    tables, all four tps numbers, and computed ratios. No
    `MEASUREMENT MISSING` markers."""
    from ctm_bench.scripts import compose_throughput_comparison as comp

    a = tmp_path / "vllm_fp16" / "streaming_summary.json"
    b = tmp_path / "vllm_fp8" / "streaming_summary.json"
    cd = tmp_path / "hf_int4.json"
    _write_vllm_cell(a, tps=85.0)
    _write_vllm_cell(b, tps=84.0)   # B/A ≈ 0.988 → near-zero overhead
    _write_hf_cell(cd, baseline_tps=35.0, int4_tps=30.0)  # D/C ≈ 0.857 → GREEN
    rc = comp.main([
        "--cell-a", str(a), "--cell-b", str(b),
        "--cell-cd", str(cd), "--prefill-length", "2048",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "85.00" in out
    assert "84.00" in out
    assert "35.00" in out
    assert "30.00" in out
    assert "0.988" in out or "0.989" in out  # B/A
    assert "0.857" in out or "0.858" in out  # D/C
    assert "MEASUREMENT MISSING" not in out
    assert "GREEN" in out  # D/C ≥ 0.80


def test_compose_missing_vllm_cells_marks_missing(tmp_path: Path, capsys):
    """Most realistic partial state: HF run finishes first, vLLM cells
    not yet. The composer must render the HF numbers, mark vLLM as
    `MEASUREMENT MISSING`, and NOT crash."""
    from ctm_bench.scripts import compose_throughput_comparison as comp

    cd = tmp_path / "hf_int4.json"
    _write_hf_cell(cd, baseline_tps=35.0, int4_tps=20.0)  # D/C ≈ 0.571 → YELLOW
    rc = comp.main([
        "--cell-a", str(tmp_path / "missing_a.json"),
        "--cell-b", str(tmp_path / "missing_b.json"),
        "--cell-cd", str(cd), "--prefill-length", "2048",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "MEASUREMENT MISSING" in out
    assert "35.00" in out
    assert "20.00" in out
    assert "YELLOW" in out  # 0.5 ≤ D/C < 0.80


def test_compose_red_band_when_int4_much_slower(tmp_path: Path, capsys):
    """D/C < 0.5 → RED band. Verifies the runbook's three-band
    contract triggers correctly."""
    from ctm_bench.scripts import compose_throughput_comparison as comp

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    cd = tmp_path / "cd.json"
    _write_vllm_cell(a, tps=85.0)
    _write_vllm_cell(b, tps=84.0)
    _write_hf_cell(cd, baseline_tps=35.0, int4_tps=10.0)  # D/C ≈ 0.286 → RED
    rc = comp.main([
        "--cell-a", str(a), "--cell-b", str(b),
        "--cell-cd", str(cd), "--prefill-length", "2048",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "RED" in out
    assert "Marlin" in out  # the RED-band verdict mentions Marlin


def test_compose_writes_merged_json(tmp_path: Path, capsys):
    """`--json-output` produces a single merged file with the four
    cells, ratios, and verdicts. Schema version pinned for partner-
    shareable archive stability."""
    from ctm_bench.scripts import compose_throughput_comparison as comp

    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    cd = tmp_path / "cd.json"
    out_json = tmp_path / "summary.json"
    _write_vllm_cell(a, tps=85.0)
    _write_vllm_cell(b, tps=82.0)
    _write_hf_cell(cd, baseline_tps=35.0, int4_tps=28.0)
    rc = comp.main([
        "--cell-a", str(a), "--cell-b", str(b),
        "--cell-cd", str(cd), "--prefill-length", "2048",
        "--json-output", str(out_json),
    ])
    assert rc == 0
    data = json.loads(out_json.read_text())
    assert data["schema_version"] == "§20.1.v1"
    assert data["cells"]["A_vllm_fp16"]["tokens_per_second"] == 85.0
    assert data["cells"]["D_hf_int4"]["tokens_per_second"] == 28.0
    assert data["ratios"]["B_over_A"] == pytest.approx(82.0 / 85.0)
    assert data["ratios"]["D_over_C"] == pytest.approx(28.0 / 35.0)
    assert data["ratios"]["D_over_A"] == pytest.approx(28.0 / 85.0)
    # Verdicts are strings populated from the ratios.
    assert "GREEN" in data["verdicts"]["int4_route_b_algorithm_cost"]
    assert "FP8" in data["verdicts"]["fp8_overhead"]


def test_compose_handles_unparseable_input_without_crash(tmp_path: Path, capsys):
    """A corrupt JSON file shouldn't crash the composer; it should mark
    that cell with a `note` and continue.
    """
    from ctm_bench.scripts import compose_throughput_comparison as comp

    a = tmp_path / "a.json"
    a.write_text("{ not valid json")
    rc = comp.main([
        "--cell-a", str(a),
        "--cell-b", str(tmp_path / "missing_b.json"),
        "--cell-cd", str(tmp_path / "missing_cd.json"),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "MEASUREMENT MISSING" in out
    assert "failed to parse" in out


def test_compose_decision_tree_boundary_at_0p80(tmp_path: Path, capsys):
    """The GREEN/YELLOW boundary is D/C >= 0.80. Verify both sides."""
    from ctm_bench.scripts.compose_throughput_comparison import (
        _verdict_d_over_c,
    )

    assert "GREEN" in _verdict_d_over_c(0.80)
    assert "GREEN" in _verdict_d_over_c(0.95)
    assert "YELLOW" in _verdict_d_over_c(0.79)
    assert "YELLOW" in _verdict_d_over_c(0.50)
    assert "RED" in _verdict_d_over_c(0.49)
    assert "RED" in _verdict_d_over_c(0.10)
