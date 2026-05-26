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


def test_execute_bench_on_engine_raises_runtime_error_when_vllm_missing():
    """TIER5A.3: ``execute_bench_on_engine`` requires vLLM on the
    runtime path. Absent vllm import, it raises ``RuntimeError`` with
    a clear operator-facing message (NOT the old NotImplementedError
    from TIER5A.1's stub).
    """
    spec = _empty_spec(g4=False)
    # If vllm IS importable (unlikely on a CPU test runner), this
    # test should skip rather than try to run a real engine.
    try:
        import vllm  # noqa: F401
        pytest.skip(
            "vllm is importable on this runner; the missing-vllm "
            "guard is not reachable here. The downstream GPU-pod "
            "tests cover the wired path."
        )
    except ImportError:
        pass

    with pytest.raises(RuntimeError) as exc_info:
        execute_bench_on_engine(
            spec=spec,
            pre_orthogonality={"passed": True},
            skip_post_orthogonality=False,
        )
    msg = str(exc_info.value)
    assert "vLLM" in msg or "vllm" in msg
    assert "TIER5A.3" in msg


# ---------------------------------------------------------------- #
# TIER5A.3 wiring — verifier prompt generation + cell→driver mapping
# helpers. Pure-Python; testable without vLLM.
# ---------------------------------------------------------------- #


def test_generate_verifier_prompt_token_ids_is_deterministic():
    """Same seed + length → exactly the same prompt. Required so
    cell A and cell B submit the bit-identical input that G1
    compares output against."""
    from ctm_bench.scripts.bench_tier5a_swap_restore import (
        _generate_verifier_prompt_token_ids,
    )

    p1 = _generate_verifier_prompt_token_ids(seed=42, length=96)
    p2 = _generate_verifier_prompt_token_ids(seed=42, length=96)
    assert p1 == p2
    # Different seed → different prompt (with high probability).
    p3 = _generate_verifier_prompt_token_ids(seed=43, length=96)
    assert p1 != p3
    # Length matches.
    assert len(p1) == 96
    # All IDs are in the safe range.
    for tid in p1:
        assert 100 <= tid < 50000


def test_driver_kwargs_for_cell_maps_install_flags_and_swap_telemetry():
    """The cell→driver mapping must set swap_telemetry=True for ALL
    TIER5A cells (always-on telemetry surface), and toggle the
    composition layers per the cell's install_* attributes."""
    from ctm_bench.scripts.bench_tier5a_swap_restore import (
        _driver_kwargs_for_cell, build_bench_spec,
    )

    spec = build_bench_spec(
        model="qwen-7b-test", seed=7,
        output_dir=Path("/tmp/tier5a_test"),
        g4_smoke_enabled=True, g4_pin_first_n_blocks=3,
    )
    cells = {c.cell_name: c for c in spec.cells}
    verifier_prompt = [1, 2, 3, 4]

    # Cell A — all composition flags OFF.
    kw_a = _driver_kwargs_for_cell(
        spec=spec, cell=cells["cell_A_no_pressure"],
        verifier_prompt=verifier_prompt,
    )
    assert kw_a["swap_telemetry"] is True
    assert kw_a["collect_native_prefix_hits"] is False
    assert kw_a["extended_pinning"] is False
    assert kw_a["cache_aware_measurement_only"] is False
    assert kw_a["pin_first_n_blocks"] == 0
    assert kw_a["verifier_prompt_token_ids"] == verifier_prompt
    assert kw_a["preemption_mode"] == "swap"
    assert kw_a["model"] == "qwen-7b-test"
    assert kw_a["seed"] == 7

    # Cell B — pressure but no composition flags.
    kw_b = _driver_kwargs_for_cell(
        spec=spec, cell=cells["cell_B_pressure"],
        verifier_prompt=verifier_prompt,
    )
    assert kw_b["swap_telemetry"] is True
    assert kw_b["collect_native_prefix_hits"] is False

    # Cell C — composition smoke, all install flags ON.
    kw_c = _driver_kwargs_for_cell(
        spec=spec, cell=cells["cell_C_g4_composition"],
        verifier_prompt=verifier_prompt,
    )
    assert kw_c["swap_telemetry"] is True
    assert kw_c["collect_native_prefix_hits"] is True
    assert kw_c["extended_pinning"] is True
    assert kw_c["cache_aware_measurement_only"] is True
    assert kw_c["pin_first_n_blocks"] == 3
    assert kw_c["enable_prefix_caching"] is True


def test_cell_result_to_verifier_record_extracts_g1_relevant_fields():
    """Conversion from StreamingRunCellResult → VerifierCellRecord
    must carry the bit-identity-relevant fields: verifier output,
    swap counters, telemetry, completed flag."""
    from ctm_bench.scripts.bench_tier5a_swap_restore import (
        _cell_result_to_verifier_record, build_bench_spec,
    )
    from ctm_bench.runner_vllm_streaming import StreamingRunCellResult

    spec = build_bench_spec(
        model="x", seed=0, output_dir=Path("/tmp"),
    )
    cell_b = spec.cells[1]
    cell_result = StreamingRunCellResult(
        workload_name=cell_b.cell_name, policy_name="lru", seed=0,
        n_requests_admitted=10, n_requests_completed=10,
        n_decode_tokens=100, wall_clock_seconds=5.0,
        swap_in_blocks=12, swap_out_blocks=24, preemption_events=2,
        cpu_swap_pool_used_blocks_peak=8,
        cpu_swap_pool_total_blocks=1024,
        swap_in_latency_call_count=2,
        verifier_output_token_ids=(11, 22, 33),
        verifier_request_completed=True,
    )
    record = _cell_result_to_verifier_record(
        cell=cell_b,
        verifier_prompt=(1, 2, 3),
        cell_result=cell_result,
    )
    assert record.cell_name == "cell_B_pressure"
    assert record.prompt_token_ids == (1, 2, 3)
    assert record.output_token_ids == (11, 22, 33)
    assert record.swap_out_blocks_total == 24
    assert record.swap_in_blocks_total == 12
    assert record.preemption_events_total == 2
    assert record.cpu_swap_pool_peak_used_blocks == 8
    assert record.cpu_swap_pool_total_blocks == 1024
    assert record.completed is True


def test_cell_result_to_verifier_record_when_verifier_did_not_complete():
    """Incomplete verifier (e.g. wall budget exhausted before its
    final token) maps to completed=False on the record. compute_g1
    _verdict then routes to INVALID."""
    from ctm_bench.scripts.bench_tier5a_swap_restore import (
        _cell_result_to_verifier_record, build_bench_spec,
    )
    from ctm_bench.runner_vllm_streaming import StreamingRunCellResult

    spec = build_bench_spec(
        model="x", seed=0, output_dir=Path("/tmp"),
    )
    cell_b = spec.cells[1]
    cell_result = StreamingRunCellResult(
        workload_name=cell_b.cell_name, policy_name="lru", seed=0,
        n_requests_admitted=10, n_requests_completed=9,
        n_decode_tokens=100, wall_clock_seconds=300.0,
        swap_in_blocks=0, swap_out_blocks=12, preemption_events=1,
        verifier_output_token_ids=(7, 8),  # partial output
        verifier_request_completed=False,
    )
    record = _cell_result_to_verifier_record(
        cell=cell_b,
        verifier_prompt=(1, 2, 3),
        cell_result=cell_result,
    )
    assert record.completed is False
    assert record.output_token_ids == (7, 8)


def test_execute_bench_on_engine_end_to_end_with_monkeypatched_vllm(monkeypatch):
    """End-to-end orchestration test using monkey-patched vLLM and
    AsyncEngineDriver. Drives cell A + cell B + cell C through
    execute_bench_on_engine and asserts the assembled BenchReport
    surfaces all six gates with the expected pass/fail wiring.

    The monkey-patched driver returns synthetic
    StreamingRunCellResult per cell:
      * cell A: verifier output (10, 20, 30); no swap; completed.
      * cell B: SAME verifier output (10, 20, 30); swap_out > 0;
        non-zero telemetry; completed.
      * cell C: SAME verifier output; non-zero telemetry; all three
        install layers report enabled.

    With this setup, all six gates pass. Tests the wiring + verdict
    assembly without needing a real GPU.
    """
    import sys
    import types
    import asyncio

    # Provide a sentinel ``vllm`` module so the import inside
    # execute_bench_on_engine succeeds.
    fake_vllm = types.ModuleType("vllm")
    monkeypatch.setitem(sys.modules, "vllm", fake_vllm)

    # Capture driver constructions per cell so we can return the
    # right synthetic result for each.
    driver_calls: list = []

    from ctm_bench.runner_vllm_streaming import StreamingRunCellResult

    def _result_for_cell(workload_name: str) -> StreamingRunCellResult:
        # The verifier output is IDENTICAL across cells — this is
        # the bit-identity contract the G1 verdict checks.
        common_verifier_output = (10, 20, 30, 40)
        if workload_name == "cell_A_no_pressure":
            return StreamingRunCellResult(
                workload_name=workload_name, policy_name="lru",
                seed=42,
                n_requests_admitted=1, n_requests_completed=1,
                n_decode_tokens=4, wall_clock_seconds=0.1,
                swap_in_blocks=0, swap_out_blocks=0,
                preemption_events=0,
                verifier_output_token_ids=common_verifier_output,
                verifier_request_completed=True,
            )
        if workload_name == "cell_B_pressure":
            return StreamingRunCellResult(
                workload_name=workload_name, policy_name="lru",
                seed=42,
                n_requests_admitted=51, n_requests_completed=51,
                n_decode_tokens=2048, wall_clock_seconds=5.0,
                swap_in_blocks=80, swap_out_blocks=120,
                preemption_events=3,
                cpu_swap_pool_used_blocks_peak=120,
                cpu_swap_pool_total_blocks=1024,
                swap_in_latency_call_count=3,
                swap_in_latency_p50_ms=2.5,
                verifier_output_token_ids=common_verifier_output,
                verifier_request_completed=True,
            )
        # cell_C_g4_composition
        return StreamingRunCellResult(
            workload_name=workload_name, policy_name="lru",
            seed=42,
            n_requests_admitted=51, n_requests_completed=51,
            n_decode_tokens=2048, wall_clock_seconds=5.0,
            swap_in_blocks=60, swap_out_blocks=100,
            preemption_events=2,
            cpu_swap_pool_used_blocks_peak=90,
            cpu_swap_pool_total_blocks=1024,
            swap_in_latency_call_count=2,
            swap_in_latency_p50_ms=2.0,
            verifier_output_token_ids=common_verifier_output,
            verifier_request_completed=True,
            extended_pinning_stats={"enabled": True, "n_pinned": 8},
            cache_aware_scheduler_stats={"enabled": True},
            native_prefix_hit_stats={"installed": True},
        )

    # Fake AsyncEngineDriver: records init args + run() returns the
    # synthetic per-cell result keyed by workload_name.
    class FakeDriver:
        def __init__(self, **kwargs):
            driver_calls.append(kwargs)

        async def run(self, *, workload_name, **kwargs):
            return _result_for_cell(workload_name)

    from ctm_bench import runner_vllm_streaming
    monkeypatch.setattr(
        runner_vllm_streaming, "AsyncEngineDriver", FakeDriver,
    )

    # Pre-run orthogonality report (synthetic GREEN).
    pre_orth = {
        "g5a_fingerprint_passed": True,
        "g5b_ast_passed": True,
        "g5c_sha_passed": True,
        "g6_passed": True,
        "g5a_violations": {},
        "g5b_violations": {},
        "g5c_violations": {},
        "g6_violations": {},
    }

    # Patch verify_orthogonality so the post-run check also returns
    # a GREEN report (matches the pre-run).
    from ctm_bench.scripts import tier5a_orthogonality_gate
    from ctm_bench.scripts.tier5a_orthogonality_gate import GateReport

    fake_post_report = GateReport(
        passed=True,
        summary="all green",
        g5a_fingerprint_passed=True,
        g5b_ast_passed=True,
        g5c_sha_passed=True,
        g6_passed=True,
        g5a_violations={},
        g5b_violations={},
        g5c_violations={},
        g6_violations={},
        fingerprint_baseline_path="/tmp/fp",
        int4_sha_baseline_path="/tmp/i4",
        cuda_sha_baseline_path="/tmp/cu",
        fingerprint_baseline_missing=False,
        int4_sha_baseline_missing=False,
        cuda_sha_baseline_missing=False,
    )
    monkeypatch.setattr(
        tier5a_orthogonality_gate, "verify_orthogonality",
        lambda: fake_post_report,
    )

    # Build a spec with cell A + B + C (g4_smoke).
    spec = build_bench_spec(
        model="qwen-7b-test", seed=42,
        output_dir=Path("/tmp/tier5a_e2e_test"),
        g4_smoke_enabled=True,
        g4_pin_first_n_blocks=4,
        # Tight pressure so the synthetic data looks realistic.
        n_pressure_requests=50,
    )

    report = execute_bench_on_engine(
        spec=spec,
        pre_orthogonality=pre_orth,
        skip_post_orthogonality=False,
        max_wall_seconds_per_cell=10.0,
    )

    # Sanity: 3 drivers constructed (one per cell).
    assert len(driver_calls) == 3
    for call in driver_calls:
        assert call["swap_telemetry"] is True
        assert call["preemption_mode"] == "swap"

    # All six gates assembled.
    assert set(report.gate_verdicts.keys()) >= {
        "G1", "G2", "G3", "G4", "G5", "G6",
    }

    # G1 GREEN (cell A == cell B verifier output, AND cell B
    # had swap_out_blocks > 0).
    assert report.gate_verdicts["G1"].passed is True, (
        f"G1 should be GREEN; got "
        f"{report.gate_verdicts['G1'].summary}"
    )
    assert report.g1_result["bit_identical"] is True

    # G2 PASS (swap_out_blocks=120).
    assert report.gate_verdicts["G2"].passed is True

    # G3 PASS (peak=120, call_count=3).
    assert report.gate_verdicts["G3"].passed is True

    # G4 PASS (all three install layers enabled).
    assert report.gate_verdicts["G4"].passed is True

    # G5 + G6 PASS (orthogonality green).
    assert report.gate_verdicts["G5"].passed is True
    assert report.gate_verdicts["G6"].passed is True

    # Overall verdict is GREEN.
    assert report.overall_passed() is True

    # The cell records are serialised in the report.
    assert "cell_A_no_pressure" in report.cell_records
    assert "cell_B_pressure" in report.cell_records
    assert "cell_C_g4_composition" in report.cell_records


def test_execute_bench_on_engine_red_g1_when_outputs_differ(monkeypatch):
    """When cell A and cell B produce DIFFERENT verifier outputs,
    G1 is RED and overall_passed is False — even if G2/G3/G4/G5/G6
    all pass.
    """
    import sys
    import types

    fake_vllm = types.ModuleType("vllm")
    monkeypatch.setitem(sys.modules, "vllm", fake_vllm)

    from ctm_bench.runner_vllm_streaming import StreamingRunCellResult
    from ctm_bench import runner_vllm_streaming

    def _result_for_cell(workload_name: str) -> StreamingRunCellResult:
        if workload_name == "cell_A_no_pressure":
            output = (1, 2, 3, 4)
        elif workload_name == "cell_B_pressure":
            output = (1, 2, 999, 4)   # divergence at index 2
        else:
            output = (1, 2, 3, 4)
        return StreamingRunCellResult(
            workload_name=workload_name, policy_name="lru", seed=42,
            n_requests_admitted=10, n_requests_completed=10,
            n_decode_tokens=40, wall_clock_seconds=1.0,
            swap_in_blocks=10, swap_out_blocks=20,
            preemption_events=1,
            cpu_swap_pool_used_blocks_peak=5,
            cpu_swap_pool_total_blocks=100,
            swap_in_latency_call_count=1,
            verifier_output_token_ids=output,
            verifier_request_completed=True,
        )

    class FakeDriver:
        def __init__(self, **kwargs):
            pass

        async def run(self, *, workload_name, **kwargs):
            return _result_for_cell(workload_name)

    monkeypatch.setattr(
        runner_vllm_streaming, "AsyncEngineDriver", FakeDriver,
    )

    pre_orth = {
        "g5a_fingerprint_passed": True, "g5b_ast_passed": True,
        "g5c_sha_passed": True, "g6_passed": True,
        "g5a_violations": {}, "g5b_violations": {},
        "g5c_violations": {}, "g6_violations": {},
    }

    from ctm_bench.scripts import tier5a_orthogonality_gate
    from ctm_bench.scripts.tier5a_orthogonality_gate import GateReport
    monkeypatch.setattr(
        tier5a_orthogonality_gate, "verify_orthogonality",
        lambda: GateReport(
            passed=True, summary="ok",
            g5a_fingerprint_passed=True, g5b_ast_passed=True,
            g5c_sha_passed=True, g6_passed=True,
            g5a_violations={}, g5b_violations={},
            g5c_violations={}, g6_violations={},
            fingerprint_baseline_path="", int4_sha_baseline_path="",
            cuda_sha_baseline_path="",
            fingerprint_baseline_missing=False,
            int4_sha_baseline_missing=False,
            cuda_sha_baseline_missing=False,
        ),
    )

    spec = build_bench_spec(
        model="x", seed=42,
        output_dir=Path("/tmp/tier5a_red"),
    )
    report = execute_bench_on_engine(
        spec=spec, pre_orthogonality=pre_orth,
        skip_post_orthogonality=False,
        max_wall_seconds_per_cell=10.0,
    )
    assert report.gate_verdicts["G1"].passed is False
    assert report.g1_result["verdict"] == "red"
    assert report.g1_result["divergence_index"] == 2
    assert report.overall_passed() is False


def test_compute_g5_g6_verdicts_g6_surfaces_g6a_and_g6b_separately():
    """TIER5A.3 audit B2 fix: the bench verdict for G6 must surface
    g6a (in-tree CUDA defensive) AND g6b (load-bearing forked-wheel
    SHA) state distinctly. When g6b can't verify (vllm not
    importable or baseline not frozen), G6 reports FAIL with the
    specific sub-track that failed."""
    # Case 1: G6a passes, G6b passes — both green. G6.passed=True.
    gate_report = {
        "g5a_fingerprint_passed": True, "g5b_ast_passed": True,
        "g5c_sha_passed": True, "g6_passed": True,
        "g6a_passed": True, "g6b_passed": True,
        "g6b_vllm_importable": True,
        "vllm_flash_attn_wheel_baseline_missing": False,
        "g6_violations": {}, "g6b_violations": {},
        "g5a_violations": {}, "g5b_violations": {},
        "g5c_violations": {},
    }
    g5, g6 = compute_g5_g6_verdicts(gate_report_dict=gate_report)
    assert g6.passed is True
    assert "G6a=GREEN" in g6.summary
    assert "G6b=GREEN" in g6.summary
    assert g6.evidence["g6a_passed"] is True
    assert g6.evidence["g6b_passed"] is True

    # Case 2: G6a passes, G6b fails (vllm not importable) — overall
    # FAIL with a clear message.
    gate_report = {
        "g5a_fingerprint_passed": True, "g5b_ast_passed": True,
        "g5c_sha_passed": True, "g6_passed": False,
        "g6a_passed": True, "g6b_passed": False,
        "g6b_vllm_importable": False,
        "vllm_flash_attn_wheel_baseline_missing": True,
        "g6_violations": {}, "g6b_violations": {},
        "g5a_violations": {}, "g5b_violations": {},
        "g5c_violations": {},
    }
    _, g6 = compute_g5_g6_verdicts(gate_report_dict=gate_report)
    assert g6.passed is False, (
        "audit B2 fix: G6 must be False when G6b can't verify, "
        "even though G6a passes"
    )
    assert "G6a=GREEN" in g6.summary
    assert "not importable" in g6.summary

    # Case 3: G6a passes, G6b fails (baseline not frozen) — overall
    # FAIL with the freeze-procedure hint.
    gate_report["g6b_vllm_importable"] = True
    gate_report["vllm_flash_attn_wheel_baseline_missing"] = True
    _, g6 = compute_g5_g6_verdicts(gate_report_dict=gate_report)
    assert g6.passed is False
    assert "baseline NOT FROZEN" in g6.summary or "not frozen" in g6.summary.lower()

    # Case 4: G6a fails (in-tree CUDA modified) — G6 FAIL regardless
    # of G6b state.
    gate_report = {
        "g5a_fingerprint_passed": True, "g5b_ast_passed": True,
        "g5c_sha_passed": True, "g6_passed": False,
        "g6a_passed": False, "g6b_passed": True,
        "g6b_vllm_importable": True,
        "vllm_flash_attn_wheel_baseline_missing": False,
        "g6_violations": {"CUDA/kernel.cu": {"status": "modified"}},
        "g6b_violations": {}, "g5a_violations": {},
        "g5b_violations": {}, "g5c_violations": {},
    }
    _, g6 = compute_g5_g6_verdicts(gate_report_dict=gate_report)
    assert g6.passed is False
    assert "G6a=FAIL" in g6.summary
    assert g6.evidence["g6a_violations"] == {
        "CUDA/kernel.cu": {"status": "modified"},
    }


def test_execute_bench_on_engine_invalid_g1_when_cell_failed(monkeypatch):
    """If a cell's driver run raises, the cell's record marks
    completed=False; G1 routes to INVALID with the operator-facing
    error preserved in the verdict evidence."""
    import sys
    import types

    fake_vllm = types.ModuleType("vllm")
    monkeypatch.setitem(sys.modules, "vllm", fake_vllm)

    from ctm_bench import runner_vllm_streaming

    class CrashingDriver:
        def __init__(self, **kwargs):
            self.workload = None

        async def run(self, *, workload_name, **kwargs):
            self.workload = workload_name
            # cell A is fine; cell B crashes mid-run.
            if workload_name == "cell_B_pressure":
                raise RuntimeError("simulated engine OOM mid-cell")
            from ctm_bench.runner_vllm_streaming import (
                StreamingRunCellResult,
            )
            return StreamingRunCellResult(
                workload_name=workload_name, policy_name="lru",
                seed=42,
                n_requests_admitted=1, n_requests_completed=1,
                n_decode_tokens=4, wall_clock_seconds=0.1,
                swap_in_blocks=0, swap_out_blocks=0,
                preemption_events=0,
                verifier_output_token_ids=(1, 2, 3, 4),
                verifier_request_completed=True,
            )

    monkeypatch.setattr(
        runner_vllm_streaming, "AsyncEngineDriver", CrashingDriver,
    )

    spec = build_bench_spec(
        model="x", seed=42,
        output_dir=Path("/tmp/tier5a_invalid"),
    )
    pre_orth = {
        "g5a_fingerprint_passed": True, "g5b_ast_passed": True,
        "g5c_sha_passed": True, "g6_passed": True,
        "g5a_violations": {}, "g5b_violations": {},
        "g5c_violations": {}, "g6_violations": {},
    }
    report = execute_bench_on_engine(
        spec=spec, pre_orthogonality=pre_orth,
        skip_post_orthogonality=True,   # skip the post-run check
        max_wall_seconds_per_cell=10.0,
    )
    # G1 INVALID because cell B failed.
    assert report.gate_verdicts["G1"].passed is False
    assert report.g1_result["verdict"] == "invalid"
    # Cell B record is marked failed.
    assert report.cell_records["cell_B_pressure"]["error"]
    assert "simulated engine OOM" in (
        report.cell_records["cell_B_pressure"]["error"]
    )
    assert report.overall_passed() is False
