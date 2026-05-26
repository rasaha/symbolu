"""Phase 4B CPU integration tests for the three-cell pinning bench.

Verifies the orchestration in
``ctm_bench.scripts.bench_phase4_extended_pinning`` against the
internal dry-run mock vLLM module.

Acceptance gates exercised:

* All three cells execute against the dry-run mock.
* Comparison JSON includes all required pinning telemetry fields.
* Cell C produces populated extended_pinning_stats.
* AST gate: no Int4ProtectedAttentionImpl / kernel references.
* CLI --help lists the new pinning flags.
* CLI dry-run produces artifacts.
* Flag-OFF cells leave extended_pinning_stats empty.
* B-vs-C comparison block has the C-only enrichment fields.
"""

from __future__ import annotations

import ast
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


# ---------------------------------------------------------------- #
# End-to-end orchestration helper
# ---------------------------------------------------------------- #


def _run_bench(
    *,
    tmp_path: Path,
    cells: Sequence[str] = ("A", "B", "C"),
    shared_prefix_length: int = 32,
    n_shared_prefixes: int = 4,
    n_requests: int = 4,
    pin_max_budget_blocks: int = 1024,
    vllm_module_factory: Any = None,
) -> Dict[str, Any]:
    from ctm_bench.scripts.bench_phase4_extended_pinning import (
        make_dry_run_vllm_module_factory,
        run_three_cells,
    )

    factory = vllm_module_factory or make_dry_run_vllm_module_factory()
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            run_three_cells(
                model="dummy",
                shared_prefix_length=shared_prefix_length,
                n_shared_prefixes=n_shared_prefixes,
                unique_tail_choices=[16, 32],
                n_requests=n_requests,
                arrival_rate=20.0,
                arrival_alpha=2.0,
                max_wall_seconds=2.0,
                max_decode_tokens=2,
                gpu_memory_utilization=0.5,
                swap_space_gb=4,
                seed=42,
                sample_interval_seconds=0.05,
                pin_max_budget_blocks=pin_max_budget_blocks,
                vllm_module_factory=factory,
                cells_to_run=list(cells),
                output_dir=tmp_path,
            )
        )
    finally:
        loop.close()


# ---------------------------------------------------------------- #
# Three cells execute
# ---------------------------------------------------------------- #


def test_all_three_cells_execute(tmp_path: Path) -> None:
    comp = _run_bench(tmp_path=tmp_path)
    assert (tmp_path / "cell_A" / "streaming_summary.json").exists()
    assert (tmp_path / "cell_B" / "streaming_summary.json").exists()
    assert (tmp_path / "cell_C" / "streaming_summary.json").exists()
    assert (tmp_path / "comparison.json").exists()
    assert len(comp["cells"]) == 3


# ---------------------------------------------------------------- #
# Comparison JSON schema
# ---------------------------------------------------------------- #


def test_comparison_top_level_schema(tmp_path: Path) -> None:
    comp = _run_bench(tmp_path=tmp_path)
    expected = {"phase", "seed", "workload", "cells", "comparison", "warnings"}
    assert expected.issubset(set(comp.keys()))
    assert comp["phase"] == "4B"


def test_per_cell_schema_includes_pinning_telemetry(tmp_path: Path) -> None:
    """Every cell dict must expose the required pinning fields, even
    cells with pinning OFF (they report zeros, not missing keys)."""
    comp = _run_bench(tmp_path=tmp_path)
    required = {
        "pinned_blocks_total",
        "pinned_evictions_avoided",
        "forced_pin_evictions",
        "pin_budget_rejections",
        "pinned_memory_overhead_bytes",
        "evictor_path_taken",
        "extended_pinning_stats",
        # Plus the workload-shape fields:
        "n_requests_completed", "tokens_per_second",
        "ttft_p50_ms", "ttft_p99_ms",
        "e2e_p50_ms", "e2e_p99_ms",
        "config", "cell_name",
    }
    for cell_name, cell_dict in comp["cells"].items():
        missing = required - set(cell_dict.keys())
        assert not missing, f"{cell_name} missing: {missing}"


def test_cell_configs_match_phase4_design(tmp_path: Path) -> None:
    """A=prefix off+pinning off; B=prefix on+pinning off;
    C=prefix on+pinning on with pin_first_n_blocks set."""
    comp = _run_bench(tmp_path=tmp_path)
    a = comp["cells"]["A_prefix_off_pinning_off"]["config"]
    assert a["enable_prefix_caching"] is False
    assert a["extended_pinning"] is False
    b = comp["cells"]["B_prefix_on_pinning_off"]["config"]
    assert b["enable_prefix_caching"] is True
    assert b["extended_pinning"] is False
    c = comp["cells"]["C_prefix_on_pinning_on"]["config"]
    assert c["enable_prefix_caching"] is True
    assert c["extended_pinning"] is True
    assert c["pin_first_n_blocks"] > 0


# ---------------------------------------------------------------- #
# Cell C produces populated extended_pinning_stats
# ---------------------------------------------------------------- #


def test_cell_c_has_populated_extended_pinning_stats(
    tmp_path: Path,
) -> None:
    """Cell C runs with extended_pinning=True; the install fires
    and stats() reports the canonical dict."""
    comp = _run_bench(tmp_path=tmp_path)
    c = comp["cells"]["C_prefix_on_pinning_on"]
    stats = c["extended_pinning_stats"]
    assert isinstance(stats, dict)
    assert stats.get("enabled") is True
    expected_keys = {
        "enabled",
        "pinned_blocks_total",
        "pin_specs_count",
        "pinned_evictions_avoided",
        "pin_budget_rejections",
        "forced_pin_evictions",
        "pinned_memory_overhead_bytes",
        "per_spec_pinned_blocks",
        "evictor_path_taken",
    }
    missing = expected_keys - set(stats.keys())
    assert not missing, f"stats() missing keys: {missing}"
    # Allocate wrap fired → pinned_blocks_total > 0.
    assert c["pinned_blocks_total"] > 0
    # Evictor wrap resolved (V2 path) — dry-run mock provides
    # the V2 evictor shape.
    assert c["evictor_path_taken"] in (
        "v2_block_allocator.gpu_allocator.evictor",
        "v2_block_allocator._allocators[GPU].evictor",
    )


def test_cells_a_and_b_have_empty_extended_pinning_stats(
    tmp_path: Path,
) -> None:
    """Cells A and B don't install extended pinning; the stats
    dict is the empty default."""
    comp = _run_bench(tmp_path=tmp_path)
    a = comp["cells"]["A_prefix_off_pinning_off"]
    b = comp["cells"]["B_prefix_on_pinning_off"]
    assert a["extended_pinning_stats"] == {}
    assert b["extended_pinning_stats"] == {}
    # Top-level fields default to zero / 'n/a'.
    assert a["pinned_blocks_total"] == 0
    assert b["pinned_blocks_total"] == 0
    assert a["evictor_path_taken"] == "n/a"
    assert b["evictor_path_taken"] == "n/a"


def test_b_vs_c_comparison_has_c_only_enrichment(tmp_path: Path) -> None:
    """The B-vs-C block has the load-bearing performance ratios
    plus the C-only enrichment for the Phase 4D decision."""
    comp = _run_bench(tmp_path=tmp_path)
    bvc = comp["comparison"]["B_vs_C"]
    required = {
        "tokens_per_second_ratio",
        "ttft_p99_ratio", "ttft_p50_ratio",
        "e2e_p99_ratio", "e2e_p50_ratio",
        "completion_ratio",
        "c_pinned_evictions_avoided",
        "c_forced_pin_evictions",
        "c_pinned_blocks_total",
    }
    missing = required - set(bvc.keys())
    assert not missing, f"B_vs_C missing: {missing}"
    # Cell C pinned at least one block (allocate wrap fired).
    assert bvc["c_pinned_blocks_total"] > 0


def test_pin_first_n_blocks_cli_override(tmp_path: Path) -> None:
    """CLI flag --pin-first-n-blocks overrides cell C's compiled-in
    pin_first_n_blocks. Verifies the override plumbs through
    run_three_cells -> dataclasses.replace(cell, ...)."""
    from ctm_bench.scripts.bench_phase4_extended_pinning import (
        CELLS,
        make_dry_run_vllm_module_factory,
        run_three_cells,
    )
    factory = make_dry_run_vllm_module_factory()
    loop = asyncio.new_event_loop()
    try:
        comp = loop.run_until_complete(
            run_three_cells(
                model="dummy",
                shared_prefix_length=64,
                n_shared_prefixes=2,
                unique_tail_choices=[16],
                n_requests=2,
                arrival_rate=20.0,
                arrival_alpha=2.0,
                max_wall_seconds=1.0,
                max_decode_tokens=2,
                gpu_memory_utilization=0.5,
                swap_space_gb=4,
                seed=42,
                sample_interval_seconds=0.05,
                pin_max_budget_blocks=1024,
                vllm_module_factory=factory,
                cells_to_run=["C"],
                output_dir=tmp_path,
                pin_first_n_blocks_override=2,
            )
        )
    finally:
        loop.close()
    # Cell C's config reflects the override (NOT the default 4).
    c = comp["cells"]["C_prefix_on_pinning_on"]
    assert c["config"]["pin_first_n_blocks"] == 2
    # Workload block records the override for reproducibility.
    assert comp["workload"]["pin_first_n_blocks_override"] == 2


def test_pin_first_n_blocks_default_when_unset(tmp_path: Path) -> None:
    """Without the CLI override, cell C uses its compiled-in default."""
    from ctm_bench.scripts.bench_phase4_extended_pinning import CELLS
    comp = _run_bench(tmp_path=tmp_path)
    c = comp["cells"]["C_prefix_on_pinning_on"]
    assert c["config"]["pin_first_n_blocks"] == CELLS["C"].pin_first_n_blocks


def test_pin_budget_rejections_when_cap_low(tmp_path: Path) -> None:
    """Setting a tiny max_budget_blocks forces budget rejection
    after the first few admissions. Verifies the budget knob is
    plumbed through the bench."""
    comp = _run_bench(
        tmp_path=tmp_path, n_requests=6, pin_max_budget_blocks=2,
    )
    c = comp["cells"]["C_prefix_on_pinning_on"]
    # With pin_first_n_blocks=4 per request and a cap of 2, the
    # first request fills the cap; subsequent requests get
    # rejected. Total pinned blocks ≤ 2.
    assert c["pinned_blocks_total"] <= 2
    # And budget_rejections > 0 (later requests' pin attempts
    # were rejected).
    assert c["pin_budget_rejections"] > 0


# ---------------------------------------------------------------- #
# Subset cells
# ---------------------------------------------------------------- #


def test_subset_cells_b_c(tmp_path: Path) -> None:
    """Running only B+C produces an aggregate with just those cells."""
    comp = _run_bench(tmp_path=tmp_path, cells=("B", "C"))
    assert "A_prefix_off_pinning_off" not in comp["cells"]
    assert "B_prefix_on_pinning_off" in comp["cells"]
    assert "C_prefix_on_pinning_on" in comp["cells"]
    assert "B_vs_C" in comp["comparison"]


# ---------------------------------------------------------------- #
# Orthogonality — AST gate + runtime sys.modules check
# ---------------------------------------------------------------- #


def test_bench_source_does_not_reference_int4_protected() -> None:
    """AST-based gate: the bench script must not import or
    reference Int4ProtectedAttentionImpl, the vendored vllm-flash-
    attn fork, or other shipped int4_protected components."""
    script_path = Path(
        "/home/user/symbolu/CTM_plus/Bench/ctm_bench/scripts/"
        "bench_phase4_extended_pinning.py"
    )
    src = script_path.read_text()
    tree = ast.parse(src)
    forbidden = {
        "Int4ProtectedAttentionImpl",
        "Int4ProtectedLLM",
        "phase5b_backend_install",
        "phase5b_4c_paged_writer",
        "phase5b_streaming_quantizer",
        "vllm_flash_attn_int4",
        "int4_protected_k_cache",
        "int4_fused_attention_kernel",
        "int4_fused_attention_sketch",
    }
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for piece in node.module.split("."):
                    referenced.add(piece)
            for alias in node.names:
                referenced.add(alias.name)
                referenced.add(alias.name.split(".")[-1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for piece in alias.name.split("."):
                    referenced.add(piece)
    overlap = forbidden & referenced
    assert not overlap, (
        f"bench script references forbidden symbols {overlap}"
    )


def test_dry_run_does_not_load_int4_protected_modules(
    tmp_path: Path,
) -> None:
    before = set(sys.modules.keys())
    _run_bench(tmp_path=tmp_path)
    after = set(sys.modules.keys())
    new_modules = after - before
    forbidden_substrings = [
        "phase5b_backend_install",
        "phase5b_4c_paged_writer",
        "phase5b_streaming_quantizer",
        "int4_protected_k_cache",
        "int4_fused_attention_kernel",
        "int4_fused_attention_sketch",
    ]
    for mod in new_modules:
        for forbidden in forbidden_substrings:
            assert forbidden not in mod, (
                f"dry-run loaded a forbidden module: {mod!r} "
                f"(matched {forbidden!r})"
            )


# ---------------------------------------------------------------- #
# CLI entry point
# ---------------------------------------------------------------- #


def test_cli_help_lists_pinning_flags() -> None:
    result = subprocess.run(
        [
            sys.executable, "-m",
            "ctm_bench.scripts.bench_phase4_extended_pinning",
            "--help",
        ],
        cwd="/home/user/symbolu/CTM_plus/Bench",
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    for flag in (
        "--dry-run", "--cells",
        "--shared-prefix-length", "--n-shared-prefixes",
        "--pin-max-budget-blocks",
        "--output-dir",
    ):
        assert flag in result.stdout, f"missing flag: {flag}"


def test_run_streaming_cli_lists_pinning_flags() -> None:
    """run_streaming.py (the single-cell CLI) also exposes the
    pinning flags — verified via --help."""
    result = subprocess.run(
        [
            sys.executable, "-m",
            "ctm_bench.scripts.run_streaming",
            "--help",
        ],
        cwd="/home/user/symbolu/CTM_plus/Bench",
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    for flag in (
        "--extended-pinning",
        "--pin-first-n-blocks",
        "--pin-tokens-file",
        "--pin-max-budget-blocks",
    ):
        assert flag in result.stdout, f"missing flag: {flag}"


def test_cli_dry_run_writes_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "phase4b_cli_test"
    result = subprocess.run(
        [
            sys.executable, "-m",
            "ctm_bench.scripts.bench_phase4_extended_pinning",
            "--model", "dummy",
            "--shared-prefix-length", "16",
            "--n-shared-prefixes", "2",
            "--shared-prefix-unique-tail-choices", "8",
            "--n-requests", "2",
            "--max-wall-seconds", "1.0",
            "--max-decode-tokens", "2",
            "--output-dir", str(out),
            "--dry-run",
            "--log-level", "WARNING",
        ],
        cwd="/home/user/symbolu/CTM_plus/Bench",
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"dry-run failed: stdout={result.stdout!r}, "
        f"stderr={result.stderr!r}"
    )
    for cell in ("A", "B", "C"):
        assert (out / f"cell_{cell}" / "streaming_summary.json").exists()
    assert (out / "comparison.json").exists()
    comp = json.loads((out / "comparison.json").read_text())
    assert comp["phase"] == "4B"
    assert set(comp["cells"].keys()) == {
        "A_prefix_off_pinning_off",
        "B_prefix_on_pinning_off",
        "C_prefix_on_pinning_on",
    }


def test_cli_rejects_unknown_cell(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable, "-m",
            "ctm_bench.scripts.bench_phase4_extended_pinning",
            "--cells", "A,Z",
            "--output-dir", str(tmp_path),
            "--dry-run",
        ],
        cwd="/home/user/symbolu/CTM_plus/Bench",
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
