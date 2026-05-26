"""Phase TIER5A — Two-cell bench harness for swap-restore verification.

Drives the int4_protected backend through ``preemption_mode='swap'``
and applies the G1..G6 acceptance gates documented in
``NEXT_SESSION_V2.md``:

* **G1** — verifier prompt output bit-identical between
  no-pressure (cell A) and engineered-pressure (cell B).
* **G2** — cell B's ``swap_out_blocks > 0`` (the swap path
  was actually exercised).
* **G3** — telemetry: ``cpu_swap_pool_used_blocks`` AND
  ``swap_in_latency_p50_ms`` are populated in the streaming
  summary.
* **G4** — composition smoke with extended_pinning +
  cache_aware_install (measurement-only) + prefix_hit_probe.
  All three install paths coexist with ``preemption_mode='swap'``
  without crashing.
* **G5 + G6** — orthogonality gate (``tier5a_orthogonality_gate``)
  passes before AND after the run.

## Cells

| Cell | gpu_mem_util | n_pressure | preemption_mode | install layers |
|------|-------------:|-----------:|---|---|
| A    | loose (default 0.5) | 0 | swap | int4_protected |
| B    | engineered (default 0.20) | configurable | swap | int4_protected |
| C (G4 smoke) | engineered | configurable | swap | int4_protected + extended_pinning + cache_aware_measurement_only + prefix_hit_probe |

Cell A establishes the baseline output for the verifier prompt.
Cell B forces preemption + swap-restore on the verifier prompt.
Cell C (optional, ``--g4-smoke``) verifies the full v2 install
stack composes with the swap path.

## Dry-run

``--dry-run`` prints the resolved cell configs + planned workload
and exits WITHOUT loading vLLM. Useful for CPU-side validation of
CLI plumbing.

## Output

Writes ``tier5a_swap_restore_report.json`` to the output dir with:

* Per-cell ``StreamingRunCellResult`` snapshots
* G1 verdict + supporting evidence
* G2..G6 gate verdicts
* Workload spec
* vLLM engine config (gpu_mem_util, swap_space_gb, preemption_mode)

## Orthogonality contract

This module does NOT import the int4_protected backend install
helper or any forked-FA-kernel symbol. The backend is loaded by
the streaming runner via its own ``Int4ProtectedLLM`` entry point
or the runner's existing ``--int4-protected`` flag (out of
TIER5A scope to add — TIER5A composes with whatever loading
mechanism the runner already provides for the shipped backend).

CPU-only logic is unit-testable via ``--dry-run`` + the test
fixtures in ``test_bench_tier5a_swap_restore.py``.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- #
# Cell configs — pure-Python dataclasses; CPU-testable.
# ---------------------------------------------------------------- #


@dataclass(frozen=True)
class CellConfig:
    """Single-cell vLLM + workload spec.

    Frozen so cells can be aggregated. The bench harness drives one
    cell at a time; cross-cell state lives in ``BenchReport``.
    """

    cell_name: str
    gpu_memory_utilization: float
    swap_space_gb: int
    preemption_mode: str
    max_model_len: Optional[int]
    n_pressure_requests: int
    pressure_max_decode_tokens: int
    pressure_arrival_rate: float
    pressure_alpha: float
    verifier_max_decode_tokens: int
    verifier_prompt_length_tokens: int
    enable_prefix_caching: bool
    # G4 smoke composition flags. cell A + cell B set these all to
    # False (just int4_protected). cell C sets the three install
    # flags True to verify composition.
    install_extended_pinning: bool = False
    install_cache_aware_measurement_only: bool = False
    install_prefix_hit_probe: bool = False
    # Optional per-cell override of the pin spec for the composition
    # smoke. None defaults to first-N-blocks=8 (matches Phase 4 cell
    # C). Kept opaque (int) here so the bench dataclass has no
    # dependency on extended_pinning's PinSpec class.
    pin_first_n_blocks: int = 0


@dataclass(frozen=True)
class BenchSpec:
    """Top-level harness spec assembled by ``build_bench_spec``.

    Captured in the report JSON so any operator can reproduce the
    cell matrix from the artifact alone.
    """

    model: str
    seed: int
    output_dir: Path
    cells: Tuple[CellConfig, ...]
    g4_smoke_enabled: bool
    sample_interval_seconds: float


# ---------------------------------------------------------------- #
# Default config builders.
#
# The defaults match the recipe described in NEXT_SESSION_V2.md for
# the TIER5A GPU smoke: start at gpu_memory_utilization=0.20; if
# G2 doesn't fire, the operator manually steps down via the
# --pressure-gpu-mem-util flag.
# ---------------------------------------------------------------- #


def _build_cell_a(
    *,
    base_gpu_mem_util: float,
    swap_space_gb: int,
    max_model_len: Optional[int],
    verifier_decode_tokens: int,
    verifier_prompt_length_tokens: int,
    enable_prefix_caching: bool,
) -> CellConfig:
    return CellConfig(
        cell_name="cell_A_no_pressure",
        gpu_memory_utilization=base_gpu_mem_util,
        swap_space_gb=swap_space_gb,
        preemption_mode="swap",
        max_model_len=max_model_len,
        n_pressure_requests=0,
        pressure_max_decode_tokens=0,
        pressure_arrival_rate=4.0,
        pressure_alpha=1.5,
        verifier_max_decode_tokens=verifier_decode_tokens,
        verifier_prompt_length_tokens=verifier_prompt_length_tokens,
        enable_prefix_caching=enable_prefix_caching,
    )


def _build_cell_b(
    *,
    pressure_gpu_mem_util: float,
    swap_space_gb: int,
    max_model_len: Optional[int],
    n_pressure_requests: int,
    pressure_decode_tokens: int,
    pressure_arrival_rate: float,
    pressure_alpha: float,
    verifier_decode_tokens: int,
    verifier_prompt_length_tokens: int,
    enable_prefix_caching: bool,
) -> CellConfig:
    return CellConfig(
        cell_name="cell_B_pressure",
        gpu_memory_utilization=pressure_gpu_mem_util,
        swap_space_gb=swap_space_gb,
        preemption_mode="swap",
        max_model_len=max_model_len,
        n_pressure_requests=n_pressure_requests,
        pressure_max_decode_tokens=pressure_decode_tokens,
        pressure_arrival_rate=pressure_arrival_rate,
        pressure_alpha=pressure_alpha,
        verifier_max_decode_tokens=verifier_decode_tokens,
        verifier_prompt_length_tokens=verifier_prompt_length_tokens,
        enable_prefix_caching=enable_prefix_caching,
    )


def _build_cell_c_composition(
    *,
    pressure_gpu_mem_util: float,
    swap_space_gb: int,
    max_model_len: Optional[int],
    n_pressure_requests: int,
    pressure_decode_tokens: int,
    pressure_arrival_rate: float,
    pressure_alpha: float,
    verifier_decode_tokens: int,
    verifier_prompt_length_tokens: int,
    pin_first_n_blocks: int,
) -> CellConfig:
    """G4 composition smoke. enable_prefix_caching=True is REQUIRED
    by both extended_pinning and cache_aware_install (they both
    operate on the PrefixCachingBlockAllocator)."""
    return CellConfig(
        cell_name="cell_C_g4_composition",
        gpu_memory_utilization=pressure_gpu_mem_util,
        swap_space_gb=swap_space_gb,
        preemption_mode="swap",
        max_model_len=max_model_len,
        n_pressure_requests=n_pressure_requests,
        pressure_max_decode_tokens=pressure_decode_tokens,
        pressure_arrival_rate=pressure_arrival_rate,
        pressure_alpha=pressure_alpha,
        verifier_max_decode_tokens=verifier_decode_tokens,
        verifier_prompt_length_tokens=verifier_prompt_length_tokens,
        enable_prefix_caching=True,
        install_extended_pinning=True,
        install_cache_aware_measurement_only=True,
        install_prefix_hit_probe=True,
        pin_first_n_blocks=pin_first_n_blocks,
    )


def build_bench_spec(
    *,
    model: str,
    seed: int,
    output_dir: Path,
    base_gpu_mem_util: float = 0.5,
    pressure_gpu_mem_util: float = 0.20,
    swap_space_gb: int = 8,
    max_model_len: Optional[int] = 4096,
    n_pressure_requests: int = 200,
    pressure_decode_tokens: int = 256,
    pressure_arrival_rate: float = 20.0,
    pressure_alpha: float = 1.5,
    verifier_decode_tokens: int = 64,
    verifier_prompt_length_tokens: int = 96,
    enable_prefix_caching_baseline: bool = False,
    g4_smoke_enabled: bool = False,
    g4_pin_first_n_blocks: int = 8,
    sample_interval_seconds: float = 0.05,
) -> BenchSpec:
    """Construct a complete TIER5A bench spec from CLI-shaped
    defaults. Pure-Python; no vLLM dependency.
    """
    cell_a = _build_cell_a(
        base_gpu_mem_util=base_gpu_mem_util,
        swap_space_gb=swap_space_gb,
        max_model_len=max_model_len,
        verifier_decode_tokens=verifier_decode_tokens,
        verifier_prompt_length_tokens=verifier_prompt_length_tokens,
        enable_prefix_caching=enable_prefix_caching_baseline,
    )
    cell_b = _build_cell_b(
        pressure_gpu_mem_util=pressure_gpu_mem_util,
        swap_space_gb=swap_space_gb,
        max_model_len=max_model_len,
        n_pressure_requests=n_pressure_requests,
        pressure_decode_tokens=pressure_decode_tokens,
        pressure_arrival_rate=pressure_arrival_rate,
        pressure_alpha=pressure_alpha,
        verifier_decode_tokens=verifier_decode_tokens,
        verifier_prompt_length_tokens=verifier_prompt_length_tokens,
        enable_prefix_caching=enable_prefix_caching_baseline,
    )
    cells: List[CellConfig] = [cell_a, cell_b]
    if g4_smoke_enabled:
        cells.append(
            _build_cell_c_composition(
                pressure_gpu_mem_util=pressure_gpu_mem_util,
                swap_space_gb=swap_space_gb,
                max_model_len=max_model_len,
                n_pressure_requests=n_pressure_requests,
                pressure_decode_tokens=pressure_decode_tokens,
                pressure_arrival_rate=pressure_arrival_rate,
                pressure_alpha=pressure_alpha,
                verifier_decode_tokens=verifier_decode_tokens,
                verifier_prompt_length_tokens=verifier_prompt_length_tokens,
                pin_first_n_blocks=g4_pin_first_n_blocks,
            )
        )
    return BenchSpec(
        model=model,
        seed=seed,
        output_dir=output_dir,
        cells=tuple(cells),
        g4_smoke_enabled=g4_smoke_enabled,
        sample_interval_seconds=sample_interval_seconds,
    )


# ---------------------------------------------------------------- #
# Gate verdicts — assembled from the cell records.
# ---------------------------------------------------------------- #


@dataclass(frozen=True)
class GateVerdict:
    """One gate's pass/fail + evidence."""

    gate_id: str
    passed: bool
    summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)


def compute_g2_verdict(
    *, cell_b_swap_out_blocks: int,
) -> GateVerdict:
    """G2: cell B's swap_out_blocks > 0."""
    passed = cell_b_swap_out_blocks > 0
    return GateVerdict(
        gate_id="G2",
        passed=passed,
        summary=(
            f"swap_out_blocks={cell_b_swap_out_blocks} "
            f"({'>0 -> GREEN' if passed else '==0 -> RED'})"
        ),
        evidence={"swap_out_blocks": cell_b_swap_out_blocks},
    )


def compute_g3_verdict(
    *,
    cpu_swap_pool_used_blocks_peak: int,
    swap_in_latency_p50_ms: float,
    swap_in_latency_call_count: int,
    cpu_swap_pool_total_blocks: int,
    swap_in_probe_hint_path: str = "",
) -> GateVerdict:
    """G3: telemetry surfaced. Requires BOTH:

    * ``cpu_swap_pool_used_blocks_peak > 0`` — at least one
      sample saw nonzero CPU pool occupancy.
    * ``swap_in_latency_call_count > 0`` — the swap-in probe wrap
      fired at least once.

    The p50 latency is reported as supporting evidence but is NOT
    the gating signal: a legitimately-fast swap can record
    ``dt_ms=0.0`` under coarse ``time.perf_counter()`` resolution
    or zero-block early-exit, which would false-fail the gate if
    p50 were load-bearing.
    """
    passed = (
        cpu_swap_pool_used_blocks_peak > 0
        and swap_in_latency_call_count > 0
    )
    return GateVerdict(
        gate_id="G3",
        passed=passed,
        summary=(
            f"cpu_pool_peak_used_blocks={cpu_swap_pool_used_blocks_peak} "
            f"of {cpu_swap_pool_total_blocks}, "
            f"swap_in_latency_call_count={swap_in_latency_call_count}, "
            f"p50_ms={swap_in_latency_p50_ms:.3f} (evidence only)"
        ),
        evidence={
            "cpu_swap_pool_used_blocks_peak":
                cpu_swap_pool_used_blocks_peak,
            "cpu_swap_pool_total_blocks": cpu_swap_pool_total_blocks,
            "swap_in_latency_p50_ms": swap_in_latency_p50_ms,
            "swap_in_latency_call_count": swap_in_latency_call_count,
            "swap_in_probe_hint_path": swap_in_probe_hint_path,
        },
    )


def _is_install_layer_enabled(status: Any) -> bool:
    """Interpret a layer's status value as a boolean 'this install
    actually composed'. Accepts the shapes the runner / smoke test
    actually emit:

    * ``True`` / ``False`` (raw bool)
    * the strings ``'True'`` / ``'False'`` (from ``str(bool)``)
    * a stats dict carrying ``'enabled'`` or ``'installed'`` keys
    * any other truthy non-empty value (lenient fallback)

    Returns False for ``None``, the empty string, the string
    ``'False'``, the string ``'None'``, an empty dict, or a dict
    whose ``enabled``/``installed`` key is False.
    """
    if status is None:
        return False
    if isinstance(status, bool):
        return status
    if isinstance(status, str):
        s = status.strip()
        if s == "" or s.lower() in ("false", "none", "disabled"):
            return False
        return True
    if isinstance(status, dict):
        if "enabled" in status:
            return bool(status["enabled"])
        if "installed" in status:
            return bool(status["installed"])
        return bool(status)
    return bool(status)


def compute_g4_verdict(
    *,
    composition_cell_completed: bool,
    composition_cell_completed_requests: int,
    composition_install_layer_status: Dict[str, Any],
) -> GateVerdict:
    """G4: composition smoke. cell C ran to completion (no crash,
    no hang past the wall budget) AND all three install layers
    report a truthy 'enabled' status (not merely 'key present').

    ``composition_install_layer_status`` keys: ``extended_pinning``,
    ``cache_aware_measurement_only``, ``prefix_hit_probe``. Values
    may be raw bool, the string ``'True'``/``'False'``, the layer's
    full stats() dict (with ``enabled``/``installed`` key), or any
    other truthy/falsy shape — see ``_is_install_layer_enabled``.

    A layer whose install returned ``enabled=False`` (e.g. the
    allocator-walk fallback didn't resolve) is reported as
    ``not_enabled`` rather than ``missing``, and G4 fails so the
    operator sees the half-installed composition explicitly.
    """
    expected_layers = {
        "extended_pinning",
        "cache_aware_measurement_only",
        "prefix_hit_probe",
    }
    present_layers = set(composition_install_layer_status.keys())
    layers_missing = expected_layers - present_layers
    layers_not_enabled = {
        name for name in (expected_layers & present_layers)
        if not _is_install_layer_enabled(
            composition_install_layer_status.get(name)
        )
    }
    passed = (
        composition_cell_completed
        and composition_cell_completed_requests > 0
        and not layers_missing
        and not layers_not_enabled
    )
    return GateVerdict(
        gate_id="G4",
        passed=passed,
        summary=(
            f"completed={composition_cell_completed}, "
            f"completed_requests={composition_cell_completed_requests}, "
            f"layers_present={sorted(present_layers)}, "
            f"layers_missing={sorted(layers_missing)}, "
            f"layers_not_enabled={sorted(layers_not_enabled)}"
        ),
        evidence={
            "composition_cell_completed": composition_cell_completed,
            "composition_cell_completed_requests":
                composition_cell_completed_requests,
            "install_layer_status": dict(composition_install_layer_status),
            "layers_not_enabled": sorted(layers_not_enabled),
        },
    )


def compute_g5_g6_verdicts(
    *,
    gate_report_dict: Dict[str, Any],
) -> Tuple[GateVerdict, GateVerdict]:
    """G5 (three tracks aggregated) + G6 (defensive CUDA SHA): read
    from the ``tier5a_orthogonality_gate`` GateReport (already
    serialised to dict).

    G5 aggregates three sub-tracks:
      * G5a — AST class fingerprint of Int4ProtectedAttentionImpl +
        Int4ProtectedAttentionBackend
      * G5b — TIER5A modules AST walk (no forbidden symbol refs)
      * G5c — int4_protected python SHA pin
    G5 passes iff all three sub-tracks pass.

    G6 is the CTM_plus/CUDA defensive SHA pin. The load-bearing
    G6 enforcement is the runtime wheel check deferred to
    TIER5A.3 GPU smoke; this bench harness records only the
    defensive in-tree check.
    """
    g5a = bool(gate_report_dict.get("g5a_fingerprint_passed", False))
    g5b = bool(gate_report_dict.get("g5b_ast_passed", False))
    g5c = bool(gate_report_dict.get("g5c_sha_passed", False))
    g5_passed = g5a and g5b and g5c
    g6_passed = bool(gate_report_dict.get("g6_passed", False))

    g5 = GateVerdict(
        gate_id="G5",
        passed=g5_passed,
        summary=(
            f"G5a={'pass' if g5a else 'fail'} "
            f"(class fingerprint), "
            f"G5b={'pass' if g5b else 'fail'} "
            f"(tier5a ast walk), "
            f"G5c={'pass' if g5c else 'fail'} "
            f"(int4_protected python sha)"
        ),
        evidence={
            "g5a_fingerprint_passed": g5a,
            "g5b_ast_passed": g5b,
            "g5c_sha_passed": g5c,
            "g5a_violations":
                dict(gate_report_dict.get("g5a_violations", {})),
            "g5b_violations":
                dict(gate_report_dict.get("g5b_violations", {})),
            "g5c_violations":
                dict(gate_report_dict.get("g5c_violations", {})),
            "fingerprint_baseline_path":
                gate_report_dict.get("fingerprint_baseline_path", ""),
            "int4_sha_baseline_path":
                gate_report_dict.get("int4_sha_baseline_path", ""),
        },
    )
    g6 = GateVerdict(
        gate_id="G6",
        passed=g6_passed,
        summary=(
            "cuda fork defensive SHA pin "
            f"{'GREEN' if g6_passed else 'FAIL'} "
            f"({len(gate_report_dict.get('g6_violations', {}))} "
            "violations); load-bearing G6 wheel check deferred "
            "to TIER5A.3 GPU smoke"
        ),
        evidence={
            "violations": dict(gate_report_dict.get("g6_violations", {})),
            "cuda_sha_baseline_path":
                gate_report_dict.get("cuda_sha_baseline_path", ""),
        },
    )
    return g5, g6


# ---------------------------------------------------------------- #
# BenchReport — the artifact JSON
# ---------------------------------------------------------------- #


@dataclass
class BenchReport:
    """Top-level artifact written to ``output_dir`` at end-of-bench."""

    spec: BenchSpec
    gate_verdicts: Dict[str, GateVerdict]
    cell_records: Dict[str, Dict[str, Any]]
    pre_run_orthogonality: Dict[str, Any]
    post_run_orthogonality: Dict[str, Any]
    g1_result: Dict[str, Any]
    timestamp_unix: float
    dry_run: bool

    def overall_passed(self) -> bool:
        """All gates G1..G6 must pass for the bench to be green."""
        required = {"G1", "G2", "G3", "G5", "G6"}
        if self.spec.g4_smoke_enabled:
            required.add("G4")
        for gid in required:
            v = self.gate_verdicts.get(gid)
            if v is None or not v.passed:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        spec_dict = asdict(self.spec)
        spec_dict["output_dir"] = str(self.spec.output_dir)
        spec_dict["cells"] = [asdict(c) for c in self.spec.cells]
        return {
            "spec": spec_dict,
            "gate_verdicts": {
                k: asdict(v) for k, v in self.gate_verdicts.items()
            },
            "cell_records": dict(self.cell_records),
            "pre_run_orthogonality": dict(self.pre_run_orthogonality),
            "post_run_orthogonality": dict(self.post_run_orthogonality),
            "g1_result": dict(self.g1_result),
            "timestamp_unix": self.timestamp_unix,
            "dry_run": self.dry_run,
            "overall_passed": self.overall_passed(),
        }


# ---------------------------------------------------------------- #
# Dry-run renderer — pure-Python; CPU-testable.
# ---------------------------------------------------------------- #


def render_dry_run(spec: BenchSpec) -> str:
    """Produce a human-readable summary of the bench spec without
    touching vLLM. Used by ``--dry-run`` and by the tests.
    """
    lines: List[str] = []
    lines.append("=" * 72)
    lines.append("Phase TIER5A — swap-restore bench (dry-run)")
    lines.append("=" * 72)
    lines.append(f"model:             {spec.model}")
    lines.append(f"seed:              {spec.seed}")
    lines.append(f"output_dir:        {spec.output_dir}")
    lines.append(f"sample_interval:   {spec.sample_interval_seconds:.3f}s")
    lines.append(f"g4_smoke_enabled:  {spec.g4_smoke_enabled}")
    lines.append(f"n_cells:           {len(spec.cells)}")
    lines.append("")
    for i, c in enumerate(spec.cells):
        lines.append(f"--- Cell {i}: {c.cell_name} ---")
        lines.append(f"  gpu_memory_utilization:   {c.gpu_memory_utilization}")
        lines.append(f"  swap_space_gb:            {c.swap_space_gb}")
        lines.append(f"  preemption_mode:          {c.preemption_mode}")
        lines.append(f"  max_model_len:            {c.max_model_len}")
        lines.append(f"  enable_prefix_caching:    {c.enable_prefix_caching}")
        lines.append(f"  n_pressure_requests:      {c.n_pressure_requests}")
        lines.append(f"  pressure_decode_tokens:   {c.pressure_max_decode_tokens}")
        lines.append(f"  pressure_arrival_rate:    {c.pressure_arrival_rate}")
        lines.append(f"  verifier_decode_tokens:   {c.verifier_max_decode_tokens}")
        lines.append(f"  verifier_prompt_length:   {c.verifier_prompt_length_tokens}")
        lines.append(f"  install_extended_pinning: {c.install_extended_pinning}")
        lines.append(
            f"  install_cache_aware_measurement_only: "
            f"{c.install_cache_aware_measurement_only}"
        )
        lines.append(
            f"  install_prefix_hit_probe: {c.install_prefix_hit_probe}"
        )
        if c.pin_first_n_blocks > 0:
            lines.append(
                f"  pin_first_n_blocks:       {c.pin_first_n_blocks}"
            )
    lines.append("")
    lines.append("Acceptance gates (load-bearing):")
    lines.append("  G1: verifier output bit-identical cell_A vs cell_B")
    lines.append("  G2: cell_B swap_out_blocks > 0")
    lines.append("  G3: cpu_swap_pool_used_blocks_peak > 0 AND "
                 "swap_in_latency_call_count > 0 (p50_ms evidence only)")
    if spec.g4_smoke_enabled:
        lines.append("  G4: cell_C composition (extended_pinning + "
                     "cache_aware_measurement_only + prefix_hit_probe) "
                     "runs to completion")
    lines.append("  G5: int4_protected SHA pin (pre AND post run)")
    lines.append("  G6: CUDA-fork SHA pin (pre AND post run)")
    lines.append("=" * 72)
    return "\n".join(lines)


# ---------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------- #


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bench_tier5a_swap_restore",
        description=(
            "Phase TIER5A — verify int4_protected backend KV layout "
            "survives vLLM's preemption-swap path. Runs two cells "
            "(baseline + engineered pressure), compares output for "
            "bit-identity, and applies the G1..G6 acceptance gates."
        ),
    )
    p.add_argument(
        "--model", default="Qwen/Qwen2.5-7B-Instruct",
        help="HuggingFace model id to load via vLLM.",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--output-dir", type=Path,
        default=Path("./bench_out/TIER5A_SWAP_RESTORE"),
    )
    p.add_argument(
        "--base-gpu-mem-util", type=float, default=0.5,
        help="Cell A (no-pressure) gpu_memory_utilization.",
    )
    p.add_argument(
        "--pressure-gpu-mem-util", type=float, default=0.20,
        help="Cell B / cell C engineered-pressure gpu_memory_utilization. "
             "Drop further (0.15, 0.12) if G2 doesn't fire.",
    )
    p.add_argument(
        "--swap-space-gb", type=int, default=8,
        help="vLLM swap_space (CPU pool size, GB).",
    )
    p.add_argument(
        "--max-model-len", type=int, default=4096,
        help="Cap vLLM's max_model_len to keep engine init under "
             "tight gpu_memory_utilization.",
    )
    p.add_argument(
        "--n-pressure-requests", type=int, default=200,
    )
    p.add_argument(
        "--pressure-decode-tokens", type=int, default=256,
    )
    p.add_argument(
        "--pressure-arrival-rate", type=float, default=20.0,
    )
    p.add_argument(
        "--pressure-alpha", type=float, default=1.5,
    )
    p.add_argument(
        "--verifier-decode-tokens", type=int, default=64,
    )
    p.add_argument(
        "--verifier-prompt-length", type=int, default=96,
    )
    p.add_argument(
        "--enable-prefix-caching-baseline", action="store_true",
        help="Turn prefix caching ON in cell A + cell B. Default OFF "
             "matches the streaming runner's standard LRU baseline.",
    )
    p.add_argument(
        "--g4-smoke", action="store_true",
        help="Add cell C: composition smoke with extended_pinning + "
             "cache_aware_measurement_only + prefix_hit_probe.",
    )
    p.add_argument(
        "--g4-pin-first-n-blocks", type=int, default=8,
        help="pin_first_n_blocks for cell C extended_pinning install.",
    )
    p.add_argument(
        "--sample-interval-seconds", type=float, default=0.05,
        help="Swap-counter + CPU-pool polling cadence.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Print the cell spec + planned workload and exit; do NOT "
             "load vLLM. Use to validate CLI plumbing on CPU.",
    )
    p.add_argument(
        "--skip-orthogonality-pre", action="store_true",
        help="Skip the pre-run orthogonality gate. Default OFF: the "
             "gate must be GREEN before the bench starts.",
    )
    p.add_argument(
        "--skip-orthogonality-post", action="store_true",
        help="Skip the post-run orthogonality gate. Default OFF: the "
             "gate must STILL be GREEN after the bench completes "
             "(no in-flight modification of the int4_protected stack).",
    )
    return p.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    spec = build_bench_spec(
        model=args.model,
        seed=args.seed,
        output_dir=args.output_dir,
        base_gpu_mem_util=args.base_gpu_mem_util,
        pressure_gpu_mem_util=args.pressure_gpu_mem_util,
        swap_space_gb=args.swap_space_gb,
        max_model_len=args.max_model_len,
        n_pressure_requests=args.n_pressure_requests,
        pressure_decode_tokens=args.pressure_decode_tokens,
        pressure_arrival_rate=args.pressure_arrival_rate,
        pressure_alpha=args.pressure_alpha,
        verifier_decode_tokens=args.verifier_decode_tokens,
        verifier_prompt_length_tokens=args.verifier_prompt_length,
        enable_prefix_caching_baseline=args.enable_prefix_caching_baseline,
        g4_smoke_enabled=args.g4_smoke,
        g4_pin_first_n_blocks=args.g4_pin_first_n_blocks,
        sample_interval_seconds=args.sample_interval_seconds,
    )

    if args.dry_run:
        print(render_dry_run(spec))
        return 0

    # Pre-run orthogonality gate.
    from ctm_bench.scripts.tier5a_orthogonality_gate import (  # noqa: E501
        verify_orthogonality,
    )
    pre_report = verify_orthogonality()
    if not args.skip_orthogonality_pre and not pre_report.passed:
        print(
            "TIER5A pre-run orthogonality gate FAILED:",
            pre_report.summary,
            file=sys.stderr,
        )
        return 2

    # GPU-touching execution path is deliberately separated into
    # ``execute_bench_on_engine`` so the test suite can patch it
    # without touching the CLI scaffolding. Default body raises
    # because TIER5A.1 is CPU-only — TIER5A.3 (GPU smoke) wires
    # the streaming runner in.
    try:
        report = execute_bench_on_engine(
            spec=spec,
            pre_orthogonality=pre_report.to_dict(),
            skip_post_orthogonality=args.skip_orthogonality_post,
        )
    except NotImplementedError as exc:
        print(
            "TIER5A bench execution not yet wired in this build: "
            f"{exc}. Use --dry-run for CPU validation.",
            file=sys.stderr,
        )
        return 3

    spec.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = spec.output_dir / "tier5a_swap_restore_report.json"
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2) + "\n"
    )
    print(f"TIER5A report written: {report_path}")
    print(f"overall verdict: "
          f"{'GREEN' if report.overall_passed() else 'RED/INCONCLUSIVE'}")
    return 0 if report.overall_passed() else 1


# ---------------------------------------------------------------- #
# Execute hook — GPU path. TIER5A.1 leaves this as NotImplementedError;
# TIER5A.3 (GPU smoke) wires it to the streaming runner. The CPU
# tests in test_bench_tier5a_swap_restore.py exercise the rest of
# the harness via a monkey-patched stub.
# ---------------------------------------------------------------- #


def execute_bench_on_engine(
    *,
    spec: BenchSpec,
    pre_orthogonality: Dict[str, Any],
    skip_post_orthogonality: bool,
) -> BenchReport:  # pragma: no cover (TIER5A.3 wiring)
    """GPU execution hook. Wired in TIER5A.3 (GPU smoke).

    TIER5A.1 leaves this as a NotImplementedError so the CPU
    surface is fully tested first. The CLI gracefully reports
    the unwired state.
    """
    raise NotImplementedError(
        "execute_bench_on_engine is wired in TIER5A.3 (GPU smoke). "
        "Use --dry-run to validate the CLI + cell spec on CPU."
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
