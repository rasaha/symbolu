"""Compose the §20.1 four-cell FP8-vs-INT4 throughput comparison from
the four JSON artefacts produced by the GPU run.

Reads:
  * Cell A — bench_out/fp8_int4_throughput/vllm_fp16/streaming_summary.json
  * Cell B — bench_out/fp8_int4_throughput/vllm_fp8/streaming_summary.json
  * Cell C+D — bench_out/track_e_audit_followups/int4_throughput_hf.json

Writes:
  * stdout: a copy-paste-ready markdown table for PHASE4_GPU_FINDINGS §20.1
  * --json-output (optional): a single merged JSON with the headline numbers,
    ratios, and verdicts pre-computed against the runbook's decision trees.

Handles partial input — if one cell is missing the script clearly marks
``MEASUREMENT MISSING`` for that row rather than emitting fake numbers.
This is the operator's last step before they paste numbers into the §20.1
table; the script's output IS the section content.

CLI
---

  # Default paths (the runbook's recommended locations).
  python -m ctm_bench.scripts.compose_throughput_comparison

  # Override paths (if the GPU run wrote elsewhere).
  python -m ctm_bench.scripts.compose_throughput_comparison \\
      --cell-a path/to/vllm_fp16/streaming_summary.json \\
      --cell-b path/to/vllm_fp8/streaming_summary.json \\
      --cell-cd path/to/int4_throughput_hf.json \\
      --json-output bench_out/track_e_audit_followups/fp8_int4_comparison.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# Default paths anchored to the Bench root. The script is run from
# `CTM_plus/Bench`; if you cd elsewhere, pass explicit paths.
DEFAULT_CELL_A = Path("bench_out/fp8_int4_throughput/vllm_fp16/streaming_summary.json")
DEFAULT_CELL_B = Path("bench_out/fp8_int4_throughput/vllm_fp8/streaming_summary.json")
DEFAULT_CELL_CD = Path("bench_out/track_e_audit_followups/int4_throughput_hf.json")
DEFAULT_JSON_OUTPUT = Path("bench_out/track_e_audit_followups/fp8_int4_comparison.json")


MISSING_MARK = "MEASUREMENT MISSING — GPU run pending"


@dataclass
class CellResult:
    """One measurement cell. ``tokens_per_second`` is None when the
    cell's JSON file isn't present; the formatter renders MISSING_MARK
    in that case. ``extra`` carries cell-specific detail (vLLM cells
    have swap counters; HF cells have prefill/decode breakdowns)."""
    label: str
    source: str
    tokens_per_second: Optional[float] = None
    note: Optional[str] = None
    extra: dict = field(default_factory=dict)


def _load_vllm_cell(path: Path, label: str) -> CellResult:
    """Read a `streaming_summary.json` produced by `run_streaming.py`.

    Cells A and B both produce this shape. Headline: tokens_per_second.
    Also captures completed-request count and swap_out blocks (the §13.3
    secondary axes that matter for the FP8 KV story too).
    """
    if not path.exists():
        return CellResult(label=label, source=str(path), note="file not found")
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        return CellResult(
            label=label, source=str(path),
            note=f"failed to parse: {type(exc).__name__}: {exc}",
        )
    return CellResult(
        label=label,
        source=str(path),
        tokens_per_second=float(data.get("tokens_per_second") or 0.0),
        extra={
            "n_requests_completed": int(data.get("n_requests_completed") or 0),
            "n_requests_admitted": int(data.get("n_requests_admitted") or 0),
            "n_decode_tokens": int(data.get("n_decode_tokens") or 0),
            "swap_out_blocks": int(data.get("swap_out_blocks") or 0),
            "wall_clock_seconds": float(data.get("wall_clock_seconds") or 0.0),
            "workload_name": data.get("workload_name"),
            "policy_name": data.get("policy_name"),
        },
    )


def _load_hf_cells(path: Path, *, prefill_len: int) -> dict:
    """Read the `int4_throughput_hf.json` produced by `track_e_throughput.py`.

    One file holds both Cells C and D. The headline at each prefill
    length is the BEST decode tokens/sec (best-of-N trials), keyed
    under ``aggregates[<cache>@prefill=<plen>][best_decode_tokens_per_sec]``.

    Returns a dict with ``cell_c``, ``cell_d``, and the cross-ratio if
    both legs are present.
    """
    if not path.exists():
        return {
            "cell_c": CellResult(
                label=f"C — HF FP16 (decode-only, prefill={prefill_len})",
                source=str(path), note="file not found",
            ),
            "cell_d": CellResult(
                label=f"D — HF INT4 KIVI (decode-only, prefill={prefill_len})",
                source=str(path), note="file not found",
            ),
            "ratio": None,
        }
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        note = f"failed to parse: {type(exc).__name__}: {exc}"
        return {
            "cell_c": CellResult(label="C", source=str(path), note=note),
            "cell_d": CellResult(label="D", source=str(path), note=note),
            "ratio": None,
        }
    aggs = data.get("aggregates", {})
    b_key = f"baseline@prefill={prefill_len}"
    q_key = f"int4-per-channel@prefill={prefill_len}"
    base = aggs.get(b_key)
    quant = aggs.get(q_key)
    c = CellResult(
        label=f"C — HF FP16 (decode-only, prefill={prefill_len})",
        source=str(path),
        tokens_per_second=(
            float(base["best_decode_tokens_per_sec"]) if base else None
        ),
        extra={
            "median_decode_tokens_per_sec": (
                base.get("median_decode_tokens_per_sec") if base else None
            ),
            "median_prefill_ms": (
                base.get("median_prefill_ms") if base else None
            ),
            "n_trials": base.get("n_trials") if base else None,
        },
        note=None if base else f"missing aggregate {b_key!r} in {path}",
    )
    d = CellResult(
        label=f"D — HF INT4 KIVI (decode-only, prefill={prefill_len})",
        source=str(path),
        tokens_per_second=(
            float(quant["best_decode_tokens_per_sec"]) if quant else None
        ),
        extra={
            "median_decode_tokens_per_sec": (
                quant.get("median_decode_tokens_per_sec") if quant else None
            ),
            "median_prefill_ms": (
                quant.get("median_prefill_ms") if quant else None
            ),
            "n_trials": quant.get("n_trials") if quant else None,
        },
        note=None if quant else f"missing aggregate {q_key!r} in {path}",
    )
    ratio_block = aggs.get("int4_vs_baseline", {}).get(f"prefill={prefill_len}")
    return {
        "cell_c": c,
        "cell_d": d,
        "ratio": ratio_block,
        "config": data.get("config"),
        "model_id": data.get("model_id"),
    }


def _ratio(numer: Optional[float], denom: Optional[float]) -> Optional[float]:
    if numer is None or denom is None or denom <= 0:
        return None
    return numer / denom


def _verdict_d_over_c(ratio: Optional[float]) -> str:
    """Map the D/C decode-tokens-per-sec ratio to the §20.1 decision-tree
    band. Pre-decided in `FP8_INT4_THROUGHPUT_RUNBOOK.md`."""
    if ratio is None:
        return MISSING_MARK
    if ratio >= 0.80:
        return (
            "**GREEN.** Route-B INT4 is throughput-competitive in HF. "
            "Route-A `cache_kv` integration alone closes the FP8 gap."
        )
    if ratio >= 0.50:
        return (
            "**YELLOW.** Algorithm overhead measurable but fixable. "
            "Route-A first, then Marlin-style kernel (§20.6)."
        )
    return (
        "**RED.** Pure-PyTorch unpack dominates. Marlin-style kernel "
        "is the actual blocker (§20.6); route-A second."
    )


def _verdict_b_over_a(ratio: Optional[float]) -> str:
    """Map the B/A ratio (FP8 vs FP16 in vLLM) to the runbook's bands."""
    if ratio is None:
        return MISSING_MARK
    if ratio >= 0.95:
        return "FP8 is throughput-free vs FP16 in vLLM (matches the published claim)."
    if ratio >= 0.85:
        return "Modest FP8 dispatch overhead. Still partner-shareable."
    return "Investigate: FP8 kernels may not be compiled in, or workload is dispatch-bound."


def _fmt_tps(cell: CellResult) -> str:
    if cell.tokens_per_second is None:
        return f"_{MISSING_MARK}_"
    return f"**{cell.tokens_per_second:.2f}**"


def render_markdown(
    *, cell_a: CellResult, cell_b: CellResult,
    cell_c: CellResult, cell_d: CellResult,
    prefill_len: int,
    hf_config: Optional[dict] = None,
    hf_model_id: Optional[str] = None,
) -> str:
    """Produce the §20.1 fill-in markdown. Drop-in replacement for the
    'Expected measured outcomes (placeholders)' table in
    `PHASE4_GPU_FINDINGS.md` §20.1.
    """
    b_over_a = _ratio(cell_b.tokens_per_second, cell_a.tokens_per_second)
    d_over_c = _ratio(cell_d.tokens_per_second, cell_c.tokens_per_second)
    d_over_a = _ratio(cell_d.tokens_per_second, cell_a.tokens_per_second)

    lines: list[str] = []
    lines.append("#### §20.1 Measured outcomes (composed from GPU run)")
    lines.append("")
    if hf_model_id:
        lines.append(f"Model: `{hf_model_id}` — HF cells at prefill={prefill_len} tokens.")
        lines.append("")
    lines.append("| Cell | Stack | KV layer | Measured tok/s | Source |")
    lines.append("|------|-------|---------|---------------:|---|")
    lines.append(
        f"| A | vLLM 0.7+ | FP16 (auto) | {_fmt_tps(cell_a)} | `{cell_a.source}` |"
    )
    lines.append(
        f"| B | vLLM 0.7+ | **FP8**     | {_fmt_tps(cell_b)} | `{cell_b.source}` |"
    )
    lines.append(
        f"| C | HF | FP16 (DynamicCache) | {_fmt_tps(cell_c)} | `{cell_c.source}` |"
    )
    lines.append(
        f"| D | HF | **INT4 KIVI** | {_fmt_tps(cell_d)} | `{cell_d.source}` |"
    )
    lines.append("")
    lines.append("**Ratios and decision-tree verdicts:**")
    lines.append("")
    lines.append("| Ratio | Value | Verdict |")
    lines.append("|---|---:|---|")
    lines.append(
        f"| B / A (FP8 vs FP16 in vLLM) | "
        f"{'%.3f' % b_over_a if b_over_a is not None else MISSING_MARK} | "
        f"{_verdict_b_over_a(b_over_a)} |"
    )
    lines.append(
        f"| D / C (INT4 vs FP16 in HF, the route-B algorithm cost) | "
        f"{'%.3f' % d_over_c if d_over_c is not None else MISSING_MARK} | "
        f"{_verdict_d_over_c(d_over_c)} |"
    )
    lines.append(
        f"| D / A (headline INT4-HF vs FP16-vLLM) | "
        f"{'%.3f' % d_over_a if d_over_a is not None else MISSING_MARK} | "
        "Decomposes into (D/C) × (C/A); the C/A axis is the HF-vs-vLLM stack tax. |"
    )
    lines.append("")

    # Surface any cell that didn't load — operator should know before
    # pasting.
    notes = []
    for label, c in (("A", cell_a), ("B", cell_b), ("C", cell_c), ("D", cell_d)):
        if c.note:
            notes.append(f"  * Cell {label}: {c.note}")
    if notes:
        lines.append("**Cells with issues:**")
        lines.append("")
        lines.extend(notes)
        lines.append("")
    if hf_config:
        lines.append("HF cell config (INT4 KIVI):")
        lines.append("")
        lines.append("```")
        lines.append(json.dumps(hf_config, indent=2, sort_keys=True))
        lines.append("```")
    return "\n".join(lines)


def build_json_summary(
    *, cell_a: CellResult, cell_b: CellResult,
    cell_c: CellResult, cell_d: CellResult,
    prefill_len: int,
    hf_config: Optional[dict] = None,
    hf_model_id: Optional[str] = None,
) -> dict:
    """Single merged JSON with the headline numbers and pre-computed
    ratios. Safe to publish under `bench_out/track_e_audit_followups/`
    as the §20.1 partner-shareable artefact (one file, four cells,
    explicit verdicts).
    """
    b_over_a = _ratio(cell_b.tokens_per_second, cell_a.tokens_per_second)
    d_over_c = _ratio(cell_d.tokens_per_second, cell_c.tokens_per_second)
    d_over_a = _ratio(cell_d.tokens_per_second, cell_a.tokens_per_second)
    return {
        "schema_version": "§20.1.v1",
        "model_id": hf_model_id,
        "hf_int4_config": hf_config,
        "hf_prefill_length_for_decode_cells": prefill_len,
        "cells": {
            "A_vllm_fp16": {
                "label": cell_a.label,
                "tokens_per_second": cell_a.tokens_per_second,
                "source": cell_a.source,
                "note": cell_a.note,
                **cell_a.extra,
            },
            "B_vllm_fp8": {
                "label": cell_b.label,
                "tokens_per_second": cell_b.tokens_per_second,
                "source": cell_b.source,
                "note": cell_b.note,
                **cell_b.extra,
            },
            "C_hf_fp16": {
                "label": cell_c.label,
                "tokens_per_second": cell_c.tokens_per_second,
                "source": cell_c.source,
                "note": cell_c.note,
                **cell_c.extra,
            },
            "D_hf_int4": {
                "label": cell_d.label,
                "tokens_per_second": cell_d.tokens_per_second,
                "source": cell_d.source,
                "note": cell_d.note,
                **cell_d.extra,
            },
        },
        "ratios": {
            "B_over_A": b_over_a,
            "D_over_C": d_over_c,
            "D_over_A": d_over_a,
        },
        "verdicts": {
            "fp8_overhead": _verdict_b_over_a(b_over_a),
            "int4_route_b_algorithm_cost": _verdict_d_over_c(d_over_c),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="compose_throughput_comparison",
        description=(
            "Compose the §20.1 four-cell FP8-vs-INT4 throughput "
            "comparison from the four JSON artefacts produced by the GPU "
            "run. Outputs a markdown table for PHASE4_GPU_FINDINGS §20.1 "
            "and (optionally) a merged JSON for partner-shareable archive."
        ),
    )
    parser.add_argument(
        "--cell-a", type=Path, default=DEFAULT_CELL_A,
        help=f"vLLM FP16 streaming_summary.json (default: {DEFAULT_CELL_A})",
    )
    parser.add_argument(
        "--cell-b", type=Path, default=DEFAULT_CELL_B,
        help=f"vLLM FP8 streaming_summary.json (default: {DEFAULT_CELL_B})",
    )
    parser.add_argument(
        "--cell-cd", type=Path, default=DEFAULT_CELL_CD,
        help=f"track_e_throughput JSON (default: {DEFAULT_CELL_CD})",
    )
    parser.add_argument(
        "--prefill-length", type=int, default=2048,
        help=(
            "Which prefill length cell to use from the track_e_throughput "
            "JSON (2048 = steady-state by default). Try 8192 or 32768 to "
            "see how the ratio shifts with context length."
        ),
    )
    parser.add_argument(
        "--json-output", type=Path, default=None,
        help=(
            "When set, also write a merged JSON summary with the four "
            "cells, the ratios, and the decision-tree verdicts. "
            f"Recommended path: {DEFAULT_JSON_OUTPUT}"
        ),
    )
    args = parser.parse_args(argv)

    cell_a = _load_vllm_cell(args.cell_a, label="A — vLLM FP16")
    cell_b = _load_vllm_cell(args.cell_b, label="B — vLLM FP8")
    hf = _load_hf_cells(args.cell_cd, prefill_len=args.prefill_length)

    md = render_markdown(
        cell_a=cell_a, cell_b=cell_b,
        cell_c=hf["cell_c"], cell_d=hf["cell_d"],
        prefill_len=args.prefill_length,
        hf_config=hf.get("config"),
        hf_model_id=hf.get("model_id"),
    )
    print(md)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        summary = build_json_summary(
            cell_a=cell_a, cell_b=cell_b,
            cell_c=hf["cell_c"], cell_d=hf["cell_d"],
            prefill_len=args.prefill_length,
            hf_config=hf.get("config"),
            hf_model_id=hf.get("model_id"),
        )
        args.json_output.write_text(json.dumps(summary, indent=2))
        print(f"\nWrote merged JSON: {args.json_output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
