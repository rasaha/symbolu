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
import math
import sys
from pathlib import Path
from typing import Optional, Tuple


# Pre-decided decision-tree bands (matches PHASE4_GPU_FINDINGS §20.2
# and RUNPOD_TRACK_D_E_RUNBOOK §5i).
GREEN_THRESHOLD_PT = -0.3   # MMLU delta <= -0.3pt → GREEN (FP8-competitive)
YELLOW_THRESHOLD_PT = -0.5  # MMLU delta in [-0.5, -0.3) → YELLOW


def _verdict_best_sink(
    best_mmlu_delta_pt: Optional[float],
    sink0_mmlu_delta_pt: Optional[float] = None,
) -> str:
    """Map the BEST per-sink MMLU delta vs FP16 baseline to the
    runbook's GREEN/YELLOW/RED bands. The thresholds are pre-decided
    in PHASE4_GPU_FINDINGS §20.2.

    `sink0_mmlu_delta_pt` is the control measurement (the §19.4 ship
    config's MMLU gap, which on Qwen2.5-7B was −0.9pt at 1000q). When
    provided, the verdict text reports the actual measured control
    instead of hardcoding −0.9pt — important when the GPU run lands a
    different control number (statistical noise can push the §19.4
    reproduction to −0.7pt or −1.1pt depending on seed / question
    subset).
    """
    if best_mmlu_delta_pt is None:
        return "MEASUREMENT MISSING — sweep didn't produce MMLU deltas"

    def _fmt_control() -> str:
        if sink0_mmlu_delta_pt is None:
            return "the §19.4 reproduction (−0.9pt baseline expected)"
        return f"the sink=0 control ({sink0_mmlu_delta_pt:+.2f}pt @1000q)"

    # Note: MMLU delta vs FP16 is typically negative (quantization
    # hurts). "Better" means closer to 0 (less hurt).
    if best_mmlu_delta_pt >= GREEN_THRESHOLD_PT:
        return (
            f"**GREEN.** Quality is competitive with FP8 KV. "
            f"**Algorithm axis closed.** Update the VC brief's "
            f"'Measured' table; {_fmt_control()} is recovered by "
            f"sink-FP16 + body-INT4."
        )
    if best_mmlu_delta_pt >= YELLOW_THRESHOLD_PT:
        return (
            f"**YELLOW.** Materially better than {_fmt_control()} but "
            f"still trails FP8. Partner-shareable; consider AWQ-style "
            f"sink-specific calibration for the remaining gap "
            f"(~3-5 engineer-days)."
        )
    return (
        f"**RED.** Sink-FP16 doesn't recover the gap relative to "
        f"{_fmt_control()}. The MMLU delta is distributed across "
        f"positions, not concentrated on sinks. Investigate "
        f"per-layer bit allocation or per-head dynamic quant before "
        f"further sink-axis work."
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


def _sweep_is_noise_dominated(sweep: dict) -> Tuple[bool, str]:
    """True when the per-sink MMLU deltas all sit inside the binomial
    measurement-noise band — i.e. the sweep cannot resolve a real
    sink-FP16 effect, so a GREEN/YELLOW/RED verdict would be a noise
    artefact.

    Rationale: MMLU accuracy on N questions is a binomial proportion;
    the difference of two such measurements has 1σ ≈
    100·sqrt(2·p(1−p)/N) percentage points. If the full spread of
    per-sink deltas is below the 2σ band, the sink configurations are
    statistically indistinguishable from each other (and from the
    control) — the honest verdict is INCONCLUSIVE, not GREEN.

    Returns ``(is_noise_dominated, reason)``.
    """
    rows = sweep.get("rows", [])
    n = max((r.get("mmlu_total") or 0) for r in rows) if rows else 0
    deltas = sweep.get("deltas", {}).get("per_sink_vs_fp16", {})
    pts = [
        b.get("mmlu_delta_pt") for b in deltas.values()
        if b.get("mmlu_delta_pt") is not None
    ]
    if n <= 0 or len(pts) < 2:
        return False, "insufficient MMLU data to assess measurement noise"
    spread = max(pts) - min(pts)
    # Pairwise-difference 1σ at a representative MMLU accuracy. The
    # band is insensitive to p over the 0.6-0.8 range.
    p = 0.70
    sigma_diff = 100.0 * math.sqrt(2.0 * p * (1.0 - p) / n)
    band = 2.0 * sigma_diff
    # Corroborating signal: a non-zero sink WORSE than the no-sink
    # control means the sweep is non-monotonic (no clean recovery).
    sink0 = deltas.get("sink=0", {}).get("mmlu_delta_pt")
    non_monotonic = False
    if sink0 is not None:
        for key, b in deltas.items():
            if key == "sink=0":
                continue
            d = b.get("mmlu_delta_pt")
            if d is not None and d < sink0:
                non_monotonic = True
                break
    if spread < band:
        reason = (
            f"MMLU-delta spread {spread:.2f}pt across sinks is within "
            f"the 2σ binomial noise band (±{band:.2f}pt at {n} "
            f"questions) — the sink configurations are statistically "
            f"indistinguishable"
        )
        if non_monotonic:
            reason += (
                "; and the sweep is non-monotonic (a non-zero sink "
                "scores worse than the no-sink control), confirming "
                "no clean recovery mechanism"
            )
        return True, reason
    return False, (
        f"MMLU-delta spread {spread:.2f}pt exceeds the 2σ noise band "
        f"(±{band:.2f}pt at {n} questions) — the sink effect is "
        f"statistically resolved"
    )


def _overall_verdict(
    sweep: dict,
    best_delta: Optional[float],
    sink0_delta: Optional[float],
) -> str:
    """The verdict string. Noise check runs FIRST: a noise-dominated
    sweep is INCONCLUSIVE regardless of which sink numerically 'won' —
    a GREEN stamp on a within-noise result would overclaim."""
    noise, reason = _sweep_is_noise_dominated(sweep)
    if noise:
        return (
            f"**INCONCLUSIVE.** {reason}. The §20.2 hypothesis "
            f"(sink-FP16 recovers the −0.9pt gap) is neither confirmed "
            f"nor refuted — INT4 KV quality is within measurement noise "
            f"of FP16, and no sink-FP16 recovery mechanism is resolved. "
            f"A decisive test needs ~4-5× more questions (~5000) to "
            f"shrink the CI below the effect size. Report as "
            f"tested-inconclusive, not as a quality win."
        )
    return _verdict_best_sink(best_delta, sink0_delta)


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
        lines.append(f"* {_overall_verdict(sweep, best_delta, sink0_delta)}")
    else:
        lines.append("* No non-zero sink in the sweep produced a usable delta.")
    lines.append("")
    return "\n".join(lines)


def build_json_summary(sweep: dict) -> dict:
    """Build the partner-shareable merged JSON for §20.2."""
    deltas = sweep.get("deltas", {})
    per_sink_vs_fp16 = deltas.get("per_sink_vs_fp16", {})
    best_sink, best_delta = _find_best_sink(per_sink_vs_fp16)
    sink0_delta = per_sink_vs_fp16.get("sink=0", {}).get("mmlu_delta_pt")
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
            "mmlu_delta_pt_vs_fp16": sink0_delta,
        },
        "per_sink_vs_fp16": per_sink_vs_fp16,
        "best_non_zero_sink": {
            "sink_size": best_sink,
            "mmlu_delta_pt_vs_fp16": best_delta,
        },
        "verdict": _overall_verdict(sweep, best_delta, sink0_delta),
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
