"""Compose the §20.2 sink-FP16 sweep markdown summary + merged JSON.

Reads the JSON produced by `sink_fp16_sweep.py` and emits:

  * stdout: a copy-paste-ready markdown table for `PHASE4_GPU_FINDINGS.md`
    §20.2, with each sink row mapped to the runbook's decision-tree band.
  * --json-output (optional): a single merged JSON (schema_version
    "§20.2.v1") with the best sink size, the headline MMLU delta vs
    FP8 (the partner-relevant comparison), and the pre-computed
    GREEN/YELLOW/RED verdict.

CLI
---

  python -m ctm_bench.scripts.compose_sink_fp16_summary \\
      --input bench_out/track_e_audit_followups/sink_fp16_sweep.json \\
      --json-output bench_out/track_e_audit_followups/sink_fp16_summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


# Pre-decided decision-tree bands (matches PHASE4_GPU_FINDINGS §20.2
# and RUNPOD_TRACK_D_E_RUNBOOK §5i).
GREEN_THRESHOLD_PT = -0.3   # MMLU delta <= -0.3pt → GREEN (FP8-competitive)
YELLOW_THRESHOLD_PT = -0.5  # MMLU delta in [-0.5, -0.3) → YELLOW


def _verdict_best_sink(best_mmlu_delta_pt: Optional[float]) -> str:
    """Map the BEST per-sink MMLU delta vs FP16 baseline to the
    runbook's GREEN/YELLOW/RED bands. The thresholds are pre-decided
    in PHASE4_GPU_FINDINGS §20.2."""
    if best_mmlu_delta_pt is None:
        return "MEASUREMENT MISSING — sweep didn't produce MMLU deltas"
    # Note: MMLU delta vs FP16 is typically negative (quantization
    # hurts). "Better" means closer to 0 (less hurt).
    if best_mmlu_delta_pt >= GREEN_THRESHOLD_PT:
        return (
            "**GREEN.** Quality is competitive with FP8 KV. "
            "**Algorithm axis closed.** Update the VC brief's 'Measured' "
            "table; the −0.9pt @1000q gap is recovered by sink-FP16 + "
            "body-INT4."
        )
    if best_mmlu_delta_pt >= YELLOW_THRESHOLD_PT:
        return (
            "**YELLOW.** Materially better than −0.9pt but still trails "
            "FP8. Partner-shareable; consider AWQ-style sink-specific "
            "calibration for the remaining gap (~3-5 engineer-days)."
        )
    return (
        "**RED.** Sink-FP16 doesn't recover the gap. The −0.9pt MMLU "
        "delta is distributed across positions, not concentrated on "
        "sinks. Investigate per-layer bit allocation or per-head "
        "dynamic quant before further sink-axis work."
    )


def _find_best_sink(per_sink_deltas: dict) -> tuple[Optional[int], Optional[float]]:
    """Identify the sink size (≠ 0) with the smallest MMLU loss vs FP16.

    Returns (sink_size, mmlu_delta_pt). Excludes sink=0 because that's
    the control measurement (= the §19.4 ship config result we want
    to improve on).
    """
    best_sink: Optional[int] = None
    best_delta: Optional[float] = None
    for key, delta_block in per_sink_deltas.items():
        if not key.startswith("sink="):
            continue
        sink = int(key.split("=", 1)[1])
        if sink == 0:
            continue  # exclude control
        delta = delta_block.get("mmlu_delta_pt")
        if delta is None:
            continue
        if best_delta is None or delta > best_delta:
            best_delta = delta
            best_sink = sink
    return best_sink, best_delta


def _fmt_delta_pt(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.2f}pt"


def _fmt_ratio(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"{v:.4f}×"


def render_markdown(sweep: dict) -> str:
    """Build the §20.2 markdown table from the sweep JSON.

    The table renders:
      * One row per sink_size with INT4 MMLU + perplexity + delta-vs-FP16.
      * The best-sink summary block with the GREEN/YELLOW/RED verdict.
      * The §19.4 ship-config (sink=0) row anchored as the baseline
        the sweep tries to improve on.
    """
    lines: list[str] = []
    lines.append("#### §20.2 Sink-FP16 + body-INT4 sweep — measured outcomes")
    lines.append("")
    lines.append(f"Model: `{sweep.get('model_id', 'UNKNOWN')}`")
    cfg = sweep.get("int4_config", {})
    lines.append(
        f"Config (held fixed across sinks): {cfg.get('scheme', 'unknown')}"
    )
    lines.append("")

    deltas = sweep.get("deltas", {})
    fp16_baseline = deltas.get("baseline_fp16_mmlu_accuracy")
    fp16_ppl = deltas.get("baseline_fp16_perplexity")
    if fp16_baseline is not None:
        lines.append(
            f"FP16 baseline anchor: MMLU = "
            f"**{fp16_baseline*100:.2f}%**, perplexity = **{fp16_ppl:.4f}**."
        )
    lines.append("")

    per_sink_vs_fp16 = deltas.get("per_sink_vs_fp16", {})

    lines.append("| sink_size | INT4 MMLU | Δ vs FP16 | INT4 ppl | ppl ratio vs FP16 | Note |")
    lines.append("|---:|---:|---:|---:|---:|---|")
    for row in sweep.get("rows", []):
        if row.get("cache_type") != "int4-per-channel":
            continue
        sink = row.get("sink_size")
        mmlu_pct = (
            f"{row['mmlu_accuracy']*100:.2f}%"
            if row.get("mmlu_accuracy") is not None else "n/a"
        )
        ppl = (
            f"{row['perplexity']:.4f}"
            if row.get("perplexity") is not None else "n/a"
        )
        delta_block = per_sink_vs_fp16.get(f"sink={sink}", {})
        delta_str = _fmt_delta_pt(delta_block.get("mmlu_delta_pt"))
        ratio_str = _fmt_ratio(delta_block.get("perplexity_ratio"))
        note = "control (§19.4 ship config)" if sink == 0 else ""
        lines.append(
            f"| {sink} | {mmlu_pct} | {delta_str} | {ppl} | {ratio_str} | {note} |"
        )
    lines.append("")

    best_sink, best_delta = _find_best_sink(per_sink_vs_fp16)
    sink0_delta = per_sink_vs_fp16.get("sink=0", {}).get("mmlu_delta_pt")
    lines.append("**Verdict — best non-zero sink vs FP16:**")
    lines.append("")
    if best_sink is not None and best_delta is not None:
        improvement = (
            (sink0_delta - best_delta)
            if sink0_delta is not None else None
        )
        improvement_str = (
            f" (improvement over sink=0 control: {improvement:+.2f}pt)"
            if improvement is not None else ""
        )
        lines.append(
            f"* Best sink = **{best_sink}** at Δ_MMLU vs FP16 = "
            f"**{best_delta:+.2f}pt**{improvement_str}."
        )
        lines.append(f"* {_verdict_best_sink(best_delta)}")
    else:
        lines.append("* No non-zero sink in the sweep produced a usable delta.")
    lines.append("")
    return "\n".join(lines)


def build_json_summary(sweep: dict) -> dict:
    """Build the partner-shareable merged JSON for §20.2."""
    deltas = sweep.get("deltas", {})
    per_sink_vs_fp16 = deltas.get("per_sink_vs_fp16", {})
    best_sink, best_delta = _find_best_sink(per_sink_vs_fp16)
    return {
        "schema_version": "§20.2.v1",
        "source_sweep": sweep.get("schema_version"),
        "model_id": sweep.get("model_id"),
        "int4_config": sweep.get("int4_config"),
        "fp16_baseline": {
            "mmlu_accuracy": deltas.get("baseline_fp16_mmlu_accuracy"),
            "perplexity": deltas.get("baseline_fp16_perplexity"),
        },
        "control_int4_at_sink_0": {
            "mmlu_accuracy": deltas.get("sink0_mmlu_accuracy"),
            "perplexity": deltas.get("sink0_perplexity"),
            "mmlu_delta_pt_vs_fp16": per_sink_vs_fp16.get(
                "sink=0", {},
            ).get("mmlu_delta_pt"),
        },
        "per_sink_vs_fp16": per_sink_vs_fp16,
        "best_non_zero_sink": {
            "sink_size": best_sink,
            "mmlu_delta_pt_vs_fp16": best_delta,
        },
        "verdict": _verdict_best_sink(best_delta),
        "decision_tree_thresholds_pt": {
            "green": GREEN_THRESHOLD_PT,
            "yellow": YELLOW_THRESHOLD_PT,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="compose_sink_fp16_summary",
        description=(
            "Compose §20.2 sink-FP16 sweep summary. Reads the JSON "
            "produced by `sink_fp16_sweep.py` and emits a markdown "
            "table + merged §20.2.v1 JSON with the GREEN/YELLOW/RED "
            "verdict."
        ),
    )
    parser.add_argument(
        "--input", type=Path, required=True,
        help="Path to the sweep JSON (sink_fp16_sweep.py output).",
    )
    parser.add_argument(
        "--json-output", type=Path, default=None,
        help=(
            "When set, also write the merged §20.2.v1 JSON. Recommended: "
            "bench_out/track_e_audit_followups/sink_fp16_summary.json"
        ),
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"input not found: {args.input}", file=sys.stderr)
        return 2
    sweep = json.loads(args.input.read_text())
    print(render_markdown(sweep))
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(build_json_summary(sweep), indent=2),
        )
        print(f"\nWrote merged JSON: {args.json_output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
