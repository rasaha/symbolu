"""Phase 3B CPU tests for the three-cell bench driver.

Verifies the orchestration in
``ctm_bench.scripts.bench_phase3_cache_aware`` against the
internal dry-run mock vLLM module. Gates Phase 3C GPU spend on
the orchestration being correct.

Acceptance gates exercised:

* All three cells (A, B, C) execute against the dry-run mock.
* The comparison JSON schema matches the Phase 3B spec.
* No Int4ProtectedAttentionImpl or kernel paths are loaded (grep
  + sys.modules check).
* Failure-handling: when the prefix-hit probe lands on
  ``no_known_path``, the bench emits a warning instead of
  crashing, and the cell's realized_hit_tokens_total stays at 0.
* Subset-cell selection (``--cells B,C``) only runs the named
  cells.
* The CLI ``--help`` lists the new script.

No torch, no vllm, no GPU.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


# ---------------------------------------------------------------- #
# End-to-end orchestration via the script's public functions.
# ---------------------------------------------------------------- #


def _run_bench(
    *,
    tmp_path: Path,
    cells: Sequence[str] = ("A", "B", "C"),
    shared_prefix_length: int = 32,
    n_shared_prefixes: int = 4,
    n_requests: int = 4,
    vllm_module_factory: Any = None,
) -> Dict[str, Any]:
    """Run the dry-run orchestration end-to-end via the script's
    ``run_three_cells`` function. Returns the comparison dict."""
    from ctm_bench.scripts.bench_phase3_cache_aware import (
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
                vllm_module_factory=factory,
                cells_to_run=list(cells),
                output_dir=tmp_path,
            )
        )
    finally:
        loop.close()


def test_all_three_cells_execute(tmp_path: Path) -> None:
    """All three cells produce a streaming_summary.json + the
    aggregate comparison.json is emitted."""
    comp = _run_bench(tmp_path=tmp_path)
    # Three cell dirs exist.
    assert (tmp_path / "cell_A" / "streaming_summary.json").exists()
    assert (tmp_path / "cell_B" / "streaming_summary.json").exists()
    assert (tmp_path / "cell_C" / "streaming_summary.json").exists()
    # comparison.json exists.
    assert (tmp_path / "comparison.json").exists()
    # Three cells in the aggregate.
    assert len(comp["cells"]) == 3


def test_comparison_json_top_level_schema(tmp_path: Path) -> None:
    """The comparison JSON has the documented top-level keys."""
    comp = _run_bench(tmp_path=tmp_path)
    expected_top = {"phase", "seed", "workload", "cells", "comparison", "warnings"}
    assert expected_top.issubset(set(comp.keys())), (
        expected_top - set(comp.keys())
    )
    assert comp["phase"] == "3B"
    assert comp["seed"] == 42
    assert isinstance(comp["warnings"], list)


def test_per_cell_schema_covers_user_spec(tmp_path: Path) -> None:
    """Every cell's per-cell dict has every field the user listed
    in the Phase 3B requirements."""
    comp = _run_bench(tmp_path=tmp_path)
    required_per_cell = {
        # User's explicit Phase 3B spec:
        "realized_hit_tokens_total",
        "prediction_accuracy",
        "reordered_count",
        "starvation_overrides",
        "tokens_per_second",
        "n_requests_completed",
        "ttft_p50_ms",
        "ttft_p99_ms",
        "e2e_p50_ms",
        "e2e_p99_ms",
        "prefix_hit_probe_path_taken",
        # Plus the supporting fields:
        "cell_name",
        "config",
        "n_requests_admitted",
        "n_decode_tokens",
        "wall_clock_seconds",
        "prompt_builder_name",
        "cache_aware_extra",
    }
    for cell_name, cell_dict in comp["cells"].items():
        missing = required_per_cell - set(cell_dict.keys())
        assert not missing, f"{cell_name} missing: {missing}"


def test_cell_configs_match_spec(tmp_path: Path) -> None:
    """Cells A/B/C carry the canonical {enable_prefix_caching,
    cache_aware_scheduling} pair the user specified.

    * A: prefix OFF, cache-aware OFF
    * B: prefix ON,  cache-aware OFF
    * C: prefix ON,  cache-aware ON
    """
    comp = _run_bench(tmp_path=tmp_path)
    a = comp["cells"]["A_prefix_off_cache_aware_off"]["config"]
    assert a == {
        "enable_prefix_caching": False, "cache_aware_scheduling": False,
    }
    b = comp["cells"]["B_prefix_on_cache_aware_off"]["config"]
    assert b == {
        "enable_prefix_caching": True, "cache_aware_scheduling": False,
    }
    c = comp["cells"]["C_prefix_on_cache_aware_on"]["config"]
    assert c == {
        "enable_prefix_caching": True, "cache_aware_scheduling": True,
    }


def test_b_vs_c_comparison_block_populated(tmp_path: Path) -> None:
    """The B-vs-C comparison block is populated when both cells ran."""
    comp = _run_bench(tmp_path=tmp_path)
    bvc = comp["comparison"]["B_vs_C"]
    required = {
        "realized_hit_tokens_ratio",
        "realized_hit_tokens_delta",
        "tokens_per_second_ratio",
        "ttft_p99_ratio",
        "ttft_p50_ratio",
        "e2e_p99_ratio",
        "e2e_p50_ratio",
        "completion_ratio",
    }
    missing = required - set(bvc.keys())
    assert not missing, f"B_vs_C missing: {missing}"


def test_cell_a_has_no_realized_hits_in_dry_run(tmp_path: Path) -> None:
    """Cell A has prefix caching OFF in the engine + the dry-run mock
    exposes the non-caching allocator (no _cached_blocks). The probe
    lands on no_known_path; realized_hit_tokens_total stays at 0."""
    comp = _run_bench(tmp_path=tmp_path)
    a = comp["cells"]["A_prefix_off_cache_aware_off"]
    assert a["prefix_hit_probe_path_taken"] == "no_known_path"
    assert a["realized_hit_tokens_total"] == 0


def test_cell_b_probe_lands_on_cached_blocks_derived(tmp_path: Path) -> None:
    """Cell B has prefix caching ON; the dry-run mock exposes
    _cached_blocks but no native counter, so the probe lands on the
    cached_blocks_derived fallback path."""
    comp = _run_bench(tmp_path=tmp_path)
    b = comp["cells"]["B_prefix_on_cache_aware_off"]
    assert b["prefix_hit_probe_path_taken"] == "cached_blocks_derived"


def test_cell_c_cache_aware_extra_present(tmp_path: Path) -> None:
    """Cell C's cache_aware_extra block is populated (non-None)
    since the cache-aware install fired. Cells A and B have
    cache_aware_extra == None."""
    comp = _run_bench(tmp_path=tmp_path)
    assert comp["cells"]["A_prefix_off_cache_aware_off"]["cache_aware_extra"] is None
    assert comp["cells"]["B_prefix_on_cache_aware_off"]["cache_aware_extra"] is None
    cae = comp["cells"]["C_prefix_on_cache_aware_on"]["cache_aware_extra"]
    assert cae is not None
    # Tree inserts > 0 confirms allocate hook is firing in cell C.
    assert cae["tree_inserts"] > 0


def test_subset_cells_selection(tmp_path: Path) -> None:
    """Running only B+C produces an aggregate with just those cells."""
    comp = _run_bench(tmp_path=tmp_path, cells=("B", "C"))
    assert "A_prefix_off_cache_aware_off" not in comp["cells"]
    assert "B_prefix_on_cache_aware_off" in comp["cells"]
    assert "C_prefix_on_cache_aware_on" in comp["cells"]
    # B vs C still works.
    assert "B_vs_C" in comp["comparison"]


# ---------------------------------------------------------------- #
# Orthogonality: no Int4ProtectedAttentionImpl / kernel paths touched
# ---------------------------------------------------------------- #


def test_bench_source_does_not_reference_int4_protected() -> None:
    """AST-based gate: the bench script's executable code must not
    reference Int4ProtectedAttentionImpl, the vendored vllm-flash-attn
    fork, or other shipped int4_protected components. Walks the
    parsed module to avoid false positives from docstring mentions
    (this test's own discipline-rule list is in the script's
    docstring, which is fine — but a string-grep would flag it)."""
    import ast

    script_path = Path(
        "/home/user/symbolu/CTM_plus/Bench/ctm_bench/scripts/"
        "bench_phase3_cache_aware.py"
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
        f"bench script's AST references forbidden symbols {overlap} — "
        "Phase 3 must not touch the int4_protected stack."
    )


def test_dry_run_does_not_load_int4_protected_modules(
    tmp_path: Path,
) -> None:
    """Runtime gate: after a full dry-run, none of the int4_protected
    backend modules appear in sys.modules. This guarantees the bench
    script doesn't accidentally import them via a transitive path."""
    # Snapshot the state BEFORE the dry-run so we can detect
    # net-new imports (some int4 modules may be pre-loaded by
    # other tests in the same pytest session).
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
# Failure handling — probe lands on no_known_path
# ---------------------------------------------------------------- #


def test_warning_emitted_when_probe_lacks_path(tmp_path: Path) -> None:
    """When a cell has prefix caching ON but the probe can't find a
    measurement path, the comparison JSON should emit a warning
    flagging the issue (instead of silently reporting 0 hits)."""
    from ctm_bench.scripts.bench_phase3_cache_aware import (
        _DryRunVLLM,
        _DryRunNonCachingAllocator,
        CellConfig,
        run_three_cells,
    )

    # Custom factory: even when cell.config has
    # enable_prefix_caching=True, return a mock whose GPU allocator
    # is _DryRunNonCachingAllocator (no _cached_blocks, no native
    # counter). Simulates a hypothetical real-vLLM version where
    # the probe paths all fail.
    def _factory_with_broken_probe(*, cell: CellConfig) -> _DryRunVLLM:
        vllm_module = _DryRunVLLM()
        # The mock's AsyncLLMEngine reads enable_prefix_caching from
        # the engine args. We can't override mid-flight, so we
        # monkey-patch the factory's from_engine_args to always
        # construct a non-caching allocator regardless of args.
        from ctm_bench.scripts.bench_phase3_cache_aware import (
            _DryRunAsyncEngine,
        )

        original_factory = vllm_module._factory.from_engine_args

        def _broken_from_engine_args(args: Any) -> Any:
            engine = original_factory(args)
            # Force the GPU allocator to the no-counter variant.
            engine.engine.scheduler[0].block_manager.\
                block_allocator.gpu_allocator = (
                    _DryRunNonCachingAllocator()
                )
            return engine

        vllm_module._factory.from_engine_args = _broken_from_engine_args
        vllm_module.AsyncLLMEngine = vllm_module._factory
        return vllm_module

    loop = asyncio.new_event_loop()
    try:
        comp = loop.run_until_complete(
            run_three_cells(
                model="dummy",
                shared_prefix_length=16,
                n_shared_prefixes=2,
                unique_tail_choices=[8],
                n_requests=2,
                arrival_rate=10.0,
                arrival_alpha=2.0,
                max_wall_seconds=1.0,
                max_decode_tokens=2,
                gpu_memory_utilization=0.5,
                swap_space_gb=4,
                seed=42,
                sample_interval_seconds=0.05,
                vllm_module_factory=_factory_with_broken_probe,
                cells_to_run=["B", "C"],
                output_dir=tmp_path,
            )
        )
    finally:
        loop.close()

    # Both B and C should land on no_known_path because we forced
    # the non-caching allocator.
    for cell_name in (
        "B_prefix_on_cache_aware_off",
        "C_prefix_on_cache_aware_on",
    ):
        cell = comp["cells"][cell_name]
        assert cell["prefix_hit_probe_path_taken"] == "no_known_path", (
            cell_name, cell["prefix_hit_probe_path_taken"]
        )
        assert cell["realized_hit_tokens_total"] == 0

    # Warnings list contains entries for both cells.
    warning_text = "\n".join(comp["warnings"])
    assert "B_prefix_on_cache_aware_off" in warning_text
    assert "C_prefix_on_cache_aware_on" in warning_text
    assert "no_known_path" in warning_text


def test_warning_emitted_when_cell_a_unexpectedly_reports_hits(
    tmp_path: Path,
) -> None:
    """If cell A's probe somehow reports hits despite prefix caching
    being OFF, the bench emits a warning (catches state-leak bugs
    in mocks + future vLLM versions that change probe behavior)."""
    # Construct cell metrics dicts directly and feed them through
    # build_comparison to test the warning logic in isolation.
    from ctm_bench.scripts.bench_phase3_cache_aware import (
        CELLS, build_comparison,
    )

    cell_a = {
        "cell_name": CELLS["A"].name,
        "config": {
            "enable_prefix_caching": False, "cache_aware_scheduling": False,
        },
        "realized_hit_tokens_total": 64,  # unexpected!
        "prefix_hit_probe_path_taken": "native_counter",
        "n_requests_completed": 4,
        "tokens_per_second": 10.0,
        "ttft_p50_ms": 1.0, "ttft_p99_ms": 2.0,
        "e2e_p50_ms": 5.0, "e2e_p99_ms": 10.0,
    }
    cells = {CELLS["A"].name: cell_a}
    comp = build_comparison(cells=cells, workload={}, seed=0)
    warning_text = "\n".join(comp["warnings"])
    assert "prefix caching is OFF" in warning_text
    assert CELLS["A"].name in warning_text


# ---------------------------------------------------------------- #
# CLI entry point
# ---------------------------------------------------------------- #


def test_cli_help_lists_dry_run_flag() -> None:
    """``python -m ctm_bench.scripts.bench_phase3_cache_aware --help``
    runs cleanly and lists the new --dry-run flag and the
    --shared-prefix-* flags."""
    result = subprocess.run(
        [
            sys.executable, "-m",
            "ctm_bench.scripts.bench_phase3_cache_aware",
            "--help",
        ],
        cwd="/home/user/symbolu/CTM_plus/Bench",
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"--help failed: stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    for flag in (
        "--dry-run",
        "--cells",
        "--shared-prefix-length",
        "--shared-prefix-unique-tail-choices",
        "--n-shared-prefixes",
        "--output-dir",
    ):
        assert flag in result.stdout, f"missing flag in --help: {flag}"


def test_cli_dry_run_writes_artifacts(tmp_path: Path) -> None:
    """The CLI ``--dry-run`` mode runs to completion + emits the
    per-cell streaming_summary.json + comparison.json artifacts."""
    out = tmp_path / "phase3b_cli_test"
    result = subprocess.run(
        [
            sys.executable, "-m",
            "ctm_bench.scripts.bench_phase3_cache_aware",
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
    assert (out / "cell_A" / "streaming_summary.json").exists()
    assert (out / "cell_B" / "streaming_summary.json").exists()
    assert (out / "cell_C" / "streaming_summary.json").exists()
    assert (out / "comparison.json").exists()
    # Sanity: comparison.json is valid JSON with the phase tag.
    comp = json.loads((out / "comparison.json").read_text())
    assert comp["phase"] == "3B"
    assert set(comp["cells"].keys()) == {
        "A_prefix_off_cache_aware_off",
        "B_prefix_on_cache_aware_off",
        "C_prefix_on_cache_aware_on",
    }


def test_cli_rejects_unknown_cell(tmp_path: Path) -> None:
    """Bad --cells value exits with non-zero."""
    result = subprocess.run(
        [
            sys.executable, "-m",
            "ctm_bench.scripts.bench_phase3_cache_aware",
            "--cells", "A,Z",
            "--output-dir", str(tmp_path),
            "--dry-run",
        ],
        cwd="/home/user/symbolu/CTM_plus/Bench",
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "unknown cell" in result.stderr.lower() or \
        "unknown cell" in result.stdout.lower()
