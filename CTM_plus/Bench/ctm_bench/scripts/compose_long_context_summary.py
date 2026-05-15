"""Compose the §20.4 long-context summary markdown + merged JSON.

Reads the JSON produced by `track_e_long_context.py` and emits:

  * stdout: a copy-paste-ready markdown table for `PHASE4_GPU_FINDINGS.md`
    §20.4, with each context-length row mapped to the runbook's
    decision-tree band (GREEN/YELLOW/RED) for perplexity ratio AND
    needle retrieval accuracy delta.
  * --json-output (optional): a single merged JSON pinned at
    `§20.4.v1` with the headline numbers, the worst-case (largest)
    context length's verdict, and per-length detail.

CLI
---

  python -m ctm_bench.scripts.compose_long_context_summary \\
      --input bench_out/track_e_audit_followups/long_context.json \\
      --json-output bench_out/track_e_audit_followups/long_context_summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


# Decision-tree thresholds — pre-decided in PHASE4_GPU_FINDINGS §20.4
# and RUNPOD_TRACK_D_E_RUNBOOK §5k.
PPL_GREEN_RATIO = 1.05    # ratio <= 1.05 → GREEN
PPL_YELLOW_RATIO = 1.15   # ratio in (1.05, 1.15] → YELLOW
# Needle accuracy delta: int4 accuracy − baseline accuracy in
# percentage POINTS. <= -10pt is alarming (retrieval starts to fail
# under compression at long contexts).
NEEDLE_GREEN_DELTA_PCT = -5.0
NEEDLE_YELLOW_DELTA_PCT = -10.0


def _verdict_ppl(ratio: Optional[float]) -> str:
    if ratio is None:
        return "MEASUREMENT MISSING"
    if ratio <= PPL_GREEN_RATIO:
        return "GREEN"
    if ratio <= PPL_YELLOW_RATIO:
        return "YELLOW"
    return "RED"


def _verdict_needle(delta_pct: Optional[float]) -> str:
    if delta_pct is None:
        return "MEASUREMENT MISSING"
    if delta_pct >= NEEDLE_GREEN_DELTA_PCT:
        return "GREEN"
    if delta_pct >= NEEDLE_YELLOW_DELTA_PCT:
        return "YELLOW"
    return "RED"


def _combined_verdict(ppl_v: str, needle_v: str) -> str:
    """Combine the two axes into a single GREEN/YELLOW/RED verdict.

    Rule: take the worst of the two (perplexity holding but needle
    failing is still a long-context failure; needle holding but
    perplexity blowing up is also a failure). MEASUREMENT MISSING
    on one axis falls back to the other.
    """
    order = ["GREEN", "YELLOW", "RED", "MEASUREMENT MISSING"]
    if ppl_v == "MEASUREMENT MISSING" and needle_v == "MEASUREMENT MISSING":
        return "MEASUREMENT MISSING"
    if ppl_v == "MEASUREMENT MISSING":
        return needle_v
    if needle_v == "MEASUREMENT MISSING":
        return ppl_v
    return max(ppl_v, needle_v, key=order.index)


def _verdict_text(combined: str, ctx_chars: int) -> str:
    """Operator-facing summary string for the combined verdict at the
    headline (largest) context length."""
    if combined == "GREEN":
        return (
            f"**GREEN.** Long-context quality holds at {ctx_chars} chars. "
            f"Partner-shareable; the §19.4 short-context result generalises "
            f"to the context length where KV compression actually pays off."
        )
    if combined == "YELLOW":
        return (
            f"**YELLOW.** Quality degrades at {ctx_chars} chars but is "
            f"materially better than the RED band. Investigate per-layer "
            f"bit allocation or selective FP16 retention before scaling "
            f"to longer contexts."
        )
    if combined == "RED":
        return (
            f"**RED.** Long-context failure at {ctx_chars} chars. The "
            f"§19.4 short-context result does NOT generalise; this is a "
            f"major issue. Investigate before further long-context partner "
            f"conversations."
        )
    return f"**MEASUREMENT MISSING** at {ctx_chars} chars."


def render_markdown(data: dict) -> str:
    lines: list[str] = []
    lines.append("#### §20.4 Long-context validation — measured outcomes")
    lines.append("")
    lines.append(f"Model: `{data.get('model_id', 'UNKNOWN')}`")
    cfg = data.get("int4_config", {})
    lines.append(
        f"Config (route-B): {cfg.get('scheme', 'unknown')}"
    )
    lines.append("")
    lines.append(
        "| ctx (chars) | baseline ppl | INT4 ppl | ppl ratio | "
        "baseline needle | INT4 needle | needle Δ | ppl band | needle band |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---|---|")
    per = data.get("deltas", {}).get("per_context_length", {})
    # Sort by context length ascending.
    sorted_keys = sorted(
        per.keys(),
        key=lambda k: per[k].get("context_length_chars", 0),
    )
    for key in sorted_keys:
        b = per[key]
        ctx = b.get("context_length_chars")
        base_ppl = b.get("baseline_perplexity")
        int4_ppl = b.get("int4_perplexity")
        ratio = b.get("perplexity_ratio")
        base_n = b.get("baseline_needle_accuracy")
        int4_n = b.get("int4_needle_accuracy")
        nd = b.get("needle_accuracy_delta_pct")

        def fmt(v, prec=4):
            return f"{v:.{prec}f}" if v is not None else "n/a"

        def fmt_pct(v):
            return f"{v*100:.0f}%" if v is not None else "n/a"

        ratio_str = f"{fmt(ratio)}×" if ratio is not None else "n/a"
        nd_str = f"{nd:+.0f}pt" if nd is not None else "n/a"
        ppl_band = _verdict_ppl(ratio)
        needle_band = _verdict_needle(nd)
        lines.append(
            f"| {ctx} | {fmt(base_ppl)} | {fmt(int4_ppl)} | {ratio_str} | "
            f"{fmt_pct(base_n)} | {fmt_pct(int4_n)} | {nd_str} | "
            f"{ppl_band} | {needle_band} |"
        )

    lines.append("")
    # Headline verdict at the largest context length.
    if sorted_keys:
        biggest = sorted_keys[-1]
        b = per[biggest]
        ratio = b.get("perplexity_ratio")
        nd = b.get("needle_accuracy_delta_pct")
        ppl_v = _verdict_ppl(ratio)
        needle_v = _verdict_needle(nd)
        combined = _combined_verdict(ppl_v, needle_v)
        lines.append(f"**Verdict at largest context ({b.get('context_length_chars')} chars):**")
        lines.append("")
        lines.append(f"* {_verdict_text(combined, b.get('context_length_chars'))}")
    return "\n".join(lines)


def build_json_summary(data: dict) -> dict:
    """Build the partner-shareable merged JSON pinned at §20.4.v1."""
    per = data.get("deltas", {}).get("per_context_length", {})
    sorted_keys = sorted(
        per.keys(),
        key=lambda k: per[k].get("context_length_chars", 0),
    )
    per_len_out: dict = {}
    headline_verdict = "MEASUREMENT MISSING"
    headline_ctx: Optional[int] = None
    for key in sorted_keys:
        b = per[key]
        ratio = b.get("perplexity_ratio")
        nd = b.get("needle_accuracy_delta_pct")
        ppl_v = _verdict_ppl(ratio)
        needle_v = _verdict_needle(nd)
        combined = _combined_verdict(ppl_v, needle_v)
        per_len_out[key] = {
            "context_length_chars": b.get("context_length_chars"),
            "perplexity_ratio": ratio,
            "needle_accuracy_delta_pct": nd,
            "perplexity_verdict": ppl_v,
            "needle_verdict": needle_v,
            "combined_verdict": combined,
        }
        # Headline = largest context length's combined verdict.
        if b.get("context_length_chars") is not None:
            headline_verdict = combined
            headline_ctx = b.get("context_length_chars")
    return {
        "schema_version": "§20.4.v1",
        "source_long_context": data.get("schema_version"),
        "model_id": data.get("model_id"),
        "int4_config": data.get("int4_config"),
        "per_context_length": per_len_out,
        "headline": {
            "context_length_chars": headline_ctx,
            "combined_verdict": headline_verdict,
            "verdict_text": (
                _verdict_text(headline_verdict, headline_ctx)
                if headline_ctx is not None else "no measurements"
            ),
        },
        "decision_tree_thresholds": {
            "perplexity_ratio_green": PPL_GREEN_RATIO,
            "perplexity_ratio_yellow": PPL_YELLOW_RATIO,
            "needle_delta_pct_green": NEEDLE_GREEN_DELTA_PCT,
            "needle_delta_pct_yellow": NEEDLE_YELLOW_DELTA_PCT,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="compose_long_context_summary",
        description=(
            "Compose §20.4 long-context summary. Reads the JSON produced "
            "by `track_e_long_context.py` and emits a markdown table + "
            "merged §20.4.v1 JSON with the GREEN/YELLOW/RED verdict at "
            "the headline (largest) context length."
        ),
    )
    parser.add_argument(
        "--input", type=Path, required=True,
        help="Path to the long-context JSON (track_e_long_context.py output).",
    )
    parser.add_argument(
        "--json-output", type=Path, default=None,
        help=(
            "When set, also write the merged §20.4.v1 JSON. Recommended: "
            "bench_out/track_e_audit_followups/long_context_summary.json"
        ),
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"input not found: {args.input}", file=sys.stderr)
        return 2
    data = json.loads(args.input.read_text())
    print(render_markdown(data))
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(build_json_summary(data), indent=2),
        )
        print(f"\nWrote merged JSON: {args.json_output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
