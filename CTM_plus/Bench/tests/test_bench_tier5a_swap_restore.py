"""Phase TIER5A.1 CPU tests for the swap-restore bench harness.

Covers ``bench_tier5a_swap_restore``:

* build_bench_spec produces 2-cell or 3-cell specs depending on
  ``g4_smoke_enabled``.
* Cell A has gpu_memory_utilization=base, no pressure prompts.
* Cell B has gpu_memory_utilization=pressure, n_pressure_requests > 0.
* Cell C (G4 smoke) has all three install flags True + prefix
  caching forced ON.
* Dry-run renderer produces non-empty deterministic output.
* CLI --dry-run path doesn't import vLLM.
* CLI --help / argparse accepts the documented flags.
* compute_g2_verdict returns pass/fail correctly.
* compute_g3_verdict requires both telemetry signals.
* compute_g4_verdict requires all three install layers present.
* compute_g5_g6_verdicts read the three-track GateReport correctly.
* execute_bench_on_engine raises NotImplementedError at TIER5A.1.
* BenchReport.overall_passed enforces the right gate set.

No torch, no vllm, no GPU.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Dict

import pytest

from ctm_bench.scripts.bench_tier5a_swap_restore import (
    BenchReport,
    BenchSpec,
    CellConfig,
    GateVerdict,
    build_bench_spec,
    compute_g2_verdict,
    compute_g3_verdict,
    compute_g4_verdict,
    compute_g5_g6_verdicts,
    execute_bench_on_engine,
    main,
    render_dry_run,
)


# ---------------------------------------------------------------- #
# build_bench_spec
# ---------------------------------------------------------------- #


def test_build_bench_spec_default_two_cells():
    spec = build_bench_spec(
        model="qwen-7b-test", seed=42,
        output_dir=Path("/tmp/tier5a_test"),
    )
    assert len(spec.cells) == 2
    assert spec.cells[0].cell_name == "cell_A_no_pressure"
    assert spec.cells[1].cell_name == "cell_B_pressure"
    assert spec.cells[0].n_pressure_requests == 0
    assert spec.cells[1].n_pressure_requests > 0
    assert spec.cells[0].preemption_mode == "swap"
    assert spec.cells[1].preemption_mode == "swap"


def test_build_bench_spec_with_g4_smoke_three_cells():
    spec = build_bench_spec(
        model="qwen-7b-test", seed=42,
        output_dir=Path("/tmp/tier5a_test"),
        g4_smoke_enabled=True, g4_pin_first_n_blocks=8,
    )
    assert len(spec.cells) == 3
    cell_c = spec.cells[2]
    assert cell_c.cell_name == "cell_C_g4_composition"
    assert cell_c.install_extended_pinning is True
    assert cell_c.install_cache_aware_measurement_only is True
    assert cell_c.install_prefix_hit_probe is True
    # Prefix caching is forced ON for cell C because both
    # extended_pinning and cache_aware_install require it.
    assert cell_c.enable_prefix_caching is True
    assert cell_c.pin_first_n_blocks == 8


def test_build_bench_spec_pressure_gpu_mem_util_is_tighter():
    spec = build_bench_spec(
        model="m", seed=0, output_dir=Path("/tmp/x"),
        base_gpu_mem_util=0.5, pressure_gpu_mem_util=0.20,
    )
    assert spec.cells[0].gpu_memory_utilization == 0.5
    assert spec.cells[1].gpu_memory_utilization == 0.20


# ---------------------------------------------------------------- #
# Dry-run renderer
# ---------------------------------------------------------------- #


def test_dry_run_renderer_contains_each_cell_name():
    spec = build_bench_spec(
        model="qwen-7b-test", seed=42,
        output_dir=Path("/tmp/x"),
        g4_smoke_enabled=True,
    )
    out = render_dry_run(spec)
    assert "cell_A_no_pressure" in out
    assert "cell_B_pressure" in out
    assert "cell_C_g4_composition" in out
    assert "Acceptance gates" in out
    assert "G1" in out and "G2" in out and "G5" in out


def test_dry_run_renderer_omits_cell_c_when_g4_smoke_off():
    spec = build_bench_spec(
        model="m", seed=0, output_dir=Path("/tmp/x"),
        g4_smoke_enabled=False,
    )
    out = render_dry_run(spec)
    assert "cell_A_no_pressure" in out
    assert "cell_B_pressure" in out
    assert "cell_C_g4_composition" not in out


def test_cli_dry_run_path(monkeypatch, tmp_path):
    """--dry-run should print the rendered spec + exit 0 without
    touching vLLM."""
    monkeypatch.chdir(tmp_path)
    captured = io.StringIO()
    with redirect_stdout(captured):
        rc = main([
            "--model", "qwen-7b-test",
            "--seed", "7",
            "--output-dir", str(tmp_path / "out"),
            "--dry-run",
        ])
    assert rc == 0
    out = captured.getvalue()
    assert "qwen-7b-test" in out
    assert "cell_A_no_pressure" in out


# ---------------------------------------------------------------- #
# Per-gate verdict computers
# ---------------------------------------------------------------- #


def test_compute_g2_verdict_passes_when_swap_out_positive():
    v = compute_g2_verdict(cell_b_swap_out_blocks=128)
    assert v.gate_id == "G2"
    assert v.passed is True
    assert v.evidence["swap_out_blocks"] == 128


def test_compute_g2_verdict_fails_when_swap_out_zero():
    v = compute_g2_verdict(cell_b_swap_out_blocks=0)
    assert v.passed is False


def test_compute_g3_verdict_requires_both_signals():
    # Pool nonzero but latency missing.
    v = compute_g3_verdict(
        cpu_swap_pool_used_blocks_peak=100,
        swap_in_latency_p50_ms=0.0,
        swap_in_latency_call_count=0,
        cpu_swap_pool_total_blocks=4096,
    )
    assert v.passed is False

    # Latency nonzero but pool unread.
    v = compute_g3_verdict(
        cpu_swap_pool_used_blocks_peak=0,
        swap_in_latency_p50_ms=2.5,
        swap_in_latency_call_count=5,
        cpu_swap_pool_total_blocks=4096,
    )
    assert v.passed is False

    # Both present.
    v = compute_g3_verdict(
        cpu_swap_pool_used_blocks_peak=100,
        swap_in_latency_p50_ms=2.5,
        swap_in_latency_call_count=5,
        cpu_swap_pool_total_blocks=4096,
    )
    assert v.passed is True


def test_compute_g4_verdict_requires_all_install_layers():
    # Missing one layer.
    v = compute_g4_verdict(
        composition_cell_completed=True,
        composition_cell_completed_requests=200,
        composition_install_layer_status={
            "extended_pinning": "ok",
            "cache_aware_measurement_only": "ok",
            # missing prefix_hit_probe
        },
    )
    assert v.passed is False
    assert "prefix_hit_probe" in v.evidence["install_layer_status"].keys() or \
        v.evidence["composition_cell_completed"] is True

    # All present.
    v = compute_g4_verdict(
        composition_cell_completed=True,
        composition_cell_completed_requests=200,
        composition_install_layer_status={
            "extended_pinning": "ok",
            "cache_aware_measurement_only": "ok",
            "prefix_hit_probe": "ok",
        },
    )
    assert v.passed is True


def test_compute_g4_verdict_fails_when_cell_did_not_complete():
    v = compute_g4_verdict(
        composition_cell_completed=False,
        composition_cell_completed_requests=0,
        composition_install_layer_status={
            "extended_pinning": "ok",
            "cache_aware_measurement_only": "ok",
            "prefix_hit_probe": "ok",
        },
    )
    assert v.passed is False


def test_compute_g3_verdict_passes_when_call_count_positive_even_if_p50_zero():
    """TIER5A.3 fixup (audit A3): G3 gates on call_count > 0, NOT
    on p50_ms > 0.0. A legitimately-fast swap or coarse perf_counter
    resolution can record dt_ms = 0.0 on every event — that's a
    probe that fired, not a probe that didn't.
    """
    v = compute_g3_verdict(
        cpu_swap_pool_used_blocks_peak=10,
        swap_in_latency_p50_ms=0.0,          # all events rounded to zero
        swap_in_latency_call_count=4,        # but the probe fired 4x
        cpu_swap_pool_total_blocks=4096,
    )
    assert v.passed is True, (
        "G3 must pass when call_count > 0 and pool > 0, even if "
        "interpolated p50_ms is 0.0; p50 is supporting evidence only"
    )
    # p50 still in evidence for inspection.
    assert v.evidence["swap_in_latency_p50_ms"] == 0.0
    assert "evidence only" in v.summary


def test_compute_g3_verdict_fails_when_call_count_zero():
    """The other side of the fixup: call_count == 0 is the probe-
    never-fired signal; G3 must fail there even if p50 looks
    plausible (which it can't, since latencies_ms is empty)."""
    v = compute_g3_verdict(
        cpu_swap_pool_used_blocks_peak=10,
        swap_in_latency_p50_ms=0.0,
        swap_in_latency_call_count=0,
        cpu_swap_pool_total_blocks=4096,
    )
    assert v.passed is False


def test_compute_g4_verdict_fails_when_layer_present_but_disabled_string():
    """TIER5A.3 fixup (audit A2): a layer whose status value is the
    string 'False' (the shape the smoke test emits via
    str(stats().get('enabled'))) is NOT enabled. G4 must fail, not
    treat the layer as 'present and therefore OK'.
    """
    v = compute_g4_verdict(
        composition_cell_completed=True,
        composition_cell_completed_requests=200,
        composition_install_layer_status={
            "extended_pinning": "True",
            "cache_aware_measurement_only": "False",   # disabled stub
            "prefix_hit_probe": "True",
        },
    )
    assert v.passed is False, (
        "G4 must fail when a layer reports str(False) — half-"
        "installed composition was the silent green path the audit "
        "caught"
    )
    assert "cache_aware_measurement_only" in v.evidence["layers_not_enabled"]


def test_compute_g4_verdict_fails_when_layer_stats_dict_has_enabled_false():
    """Same audit-A2 fixup, but with the layer value being the full
    stats() dict (the runner-side shape). The dict's enabled=False
    must surface as 'not_enabled'."""
    v = compute_g4_verdict(
        composition_cell_completed=True,
        composition_cell_completed_requests=200,
        composition_install_layer_status={
            "extended_pinning": {"enabled": True, "n_pinned": 5},
            "cache_aware_measurement_only": {"enabled": False},
            "prefix_hit_probe": {"installed": True},
        },
    )
    assert v.passed is False
    assert "cache_aware_measurement_only" in v.evidence["layers_not_enabled"]


def test_compute_g4_verdict_passes_when_layer_stats_dict_has_enabled_true():
    """The 'all good' shape: stats dicts carrying enabled=True OR
    installed=True (prefix_hit_probe uses installed) pass G4."""
    v = compute_g4_verdict(
        composition_cell_completed=True,
        composition_cell_completed_requests=200,
        composition_install_layer_status={
            "extended_pinning": {"enabled": True, "n_pinned": 5},
            "cache_aware_measurement_only": {"enabled": True},
            "prefix_hit_probe": {"installed": True, "path_taken": "..."},
        },
    )
    assert v.passed is True
    assert v.evidence["layers_not_enabled"] == []


def test_compute_g4_verdict_accepts_raw_bool_layer_status():
    """Raw bool values also work — covers the legacy / direct test
    fixture pattern."""
    v = compute_g4_verdict(
        composition_cell_completed=True,
        composition_cell_completed_requests=200,
        composition_install_layer_status={
            "extended_pinning": True,
            "cache_aware_measurement_only": False,
            "prefix_hit_probe": True,
        },
    )
    assert v.passed is False
    assert "cache_aware_measurement_only" in v.evidence["layers_not_enabled"]


def test_compute_g5_g6_verdicts_aggregate_three_track_g5():
    """G5 passes iff all three sub-tracks pass. G6 is its own."""
    gate_report = {
        "g5a_fingerprint_passed": True,
        "g5b_ast_passed": True,
        "g5c_sha_passed": True,
        "g6_passed": True,
        "g5a_violations": {},
        "g5b_violations": {},
        "g5c_violations": {},
        "g6_violations": {},
        "fingerprint_baseline_path": "/x/fingerprint.json",
        "int4_sha_baseline_path": "/x/int4.json",
        "cuda_sha_baseline_path": "/x/cuda.json",
    }
    g5, g6 = compute_g5_g6_verdicts(gate_report_dict=gate_report)
    assert g5.gate_id == "G5"
    assert g5.passed is True
    assert g6.gate_id == "G6"
    assert g6.passed is True

    # If any sub-track fails, G5 fails.
    gate_report["g5b_ast_passed"] = False
    g5, _ = compute_g5_g6_verdicts(gate_report_dict=gate_report)
    assert g5.passed is False


def test_compute_g5_g6_verdicts_g6_independent_of_g5():
    gate_report = {
        "g5a_fingerprint_passed": False,
        "g5b_ast_passed": False,
        "g5c_sha_passed": False,
        "g6_passed": True,
        "g5a_violations": {"x": {"status": "modified"}},
        "g5b_violations": {"y": ["Int4ProtectedAttentionImpl"]},
        "g5c_violations": {"z": {"status": "modified"}},
        "g6_violations": {},
        "fingerprint_baseline_path": "",
        "int4_sha_baseline_path": "",
        "cuda_sha_baseline_path": "",
    }
    g5, g6 = compute_g5_g6_verdicts(gate_report_dict=gate_report)
    assert g5.passed is False
    assert g6.passed is True


# ---------------------------------------------------------------- #
# BenchReport.overall_passed
# ---------------------------------------------------------------- #


def _green_verdict(gid: str) -> GateVerdict:
    return GateVerdict(gate_id=gid, passed=True, summary="ok")


def _red_verdict(gid: str) -> GateVerdict:
    return GateVerdict(gate_id=gid, passed=False, summary="not ok")


def _empty_spec(g4: bool = False) -> BenchSpec:
    return build_bench_spec(
        model="m", seed=0,
        output_dir=Path("/tmp/x"),
        g4_smoke_enabled=g4,
    )


def test_overall_passed_requires_all_load_bearing_gates():
    """G1, G2, G3, G5, G6 are always required. G4 is required iff
    g4_smoke_enabled."""
    spec = _empty_spec(g4=False)
    rpt = BenchReport(
        spec=spec,
        gate_verdicts={
            "G1": _green_verdict("G1"),
            "G2": _green_verdict("G2"),
            "G3": _green_verdict("G3"),
            "G5": _green_verdict("G5"),
            "G6": _green_verdict("G6"),
        },
        cell_records={}, pre_run_orthogonality={},
        post_run_orthogonality={}, g1_result={},
        timestamp_unix=0.0, dry_run=False,
    )
    assert rpt.overall_passed() is True


def test_overall_passed_red_when_any_required_gate_red():
    spec = _empty_spec(g4=False)
    for fail_gate in ("G1", "G2", "G3", "G5", "G6"):
        verdicts = {
            g: _green_verdict(g)
            for g in ("G1", "G2", "G3", "G5", "G6")
        }
        verdicts[fail_gate] = _red_verdict(fail_gate)
        rpt = BenchReport(
            spec=spec, gate_verdicts=verdicts,
            cell_records={}, pre_run_orthogonality={},
            post_run_orthogonality={}, g1_result={},
            timestamp_unix=0.0, dry_run=False,
        )
        assert rpt.overall_passed() is False, (
            f"expected red verdict when {fail_gate} failed"
        )


def test_overall_passed_requires_g4_when_smoke_enabled():
    spec = _empty_spec(g4=True)
    # G1..G6 green BUT G4 missing.
    rpt = BenchReport(
        spec=spec,
        gate_verdicts={
            "G1": _green_verdict("G1"),
            "G2": _green_verdict("G2"),
            "G3": _green_verdict("G3"),
            "G5": _green_verdict("G5"),
            "G6": _green_verdict("G6"),
        },
        cell_records={}, pre_run_orthogonality={},
        post_run_orthogonality={}, g1_result={},
        timestamp_unix=0.0, dry_run=False,
    )
    assert rpt.overall_passed() is False

    # Now with G4 green.
    rpt.gate_verdicts["G4"] = _green_verdict("G4")
    assert rpt.overall_passed() is True


def test_overall_passed_ignores_g4_when_smoke_disabled():
    spec = _empty_spec(g4=False)
    rpt = BenchReport(
        spec=spec,
        gate_verdicts={
            "G1": _green_verdict("G1"),
            "G2": _green_verdict("G2"),
            "G3": _green_verdict("G3"),
            "G4": _red_verdict("G4"),       # red but irrelevant
            "G5": _green_verdict("G5"),
            "G6": _green_verdict("G6"),
        },
        cell_records={}, pre_run_orthogonality={},
        post_run_orthogonality={}, g1_result={},
        timestamp_unix=0.0, dry_run=False,
    )
    assert rpt.overall_passed() is True


def test_report_to_dict_is_jsonable():
    spec = _empty_spec(g4=False)
    rpt = BenchReport(
        spec=spec,
        gate_verdicts={"G2": _green_verdict("G2")},
        cell_records={"cell_A_no_pressure": {"swap_out_blocks": 0}},
        pre_run_orthogonality={"passed": True},
        post_run_orthogonality={"passed": True},
        g1_result={"verdict": "green"},
        timestamp_unix=1700000000.0, dry_run=False,
    )
    d = rpt.to_dict()
    # Must serialise without errors.
    text = json.dumps(d)
    parsed = json.loads(text)
    assert parsed["spec"]["model"] == "m"
    assert "cell_A_no_pressure" in parsed["cell_records"]
    assert parsed["overall_passed"] is False    # only G2 in verdicts


# ---------------------------------------------------------------- #
# execute_bench_on_engine — TIER5A.1 raises NotImplementedError
# ---------------------------------------------------------------- #


def test_execute_bench_on_engine_raises_at_tier5a_1():
    spec = _empty_spec(g4=False)
    with pytest.raises(NotImplementedError) as exc_info:
        execute_bench_on_engine(
            spec=spec,
            pre_orthogonality={"passed": True},
            skip_post_orthogonality=False,
        )
    assert "TIER5A.3" in str(exc_info.value)
