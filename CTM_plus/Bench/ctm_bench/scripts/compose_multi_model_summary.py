"""Compose the §20.3 multi-model replication summary.

Reads N per-model JSON files produced by `track_e_quality_eval.py`
(one run per model, see runbook §5j for the bash loop) and emits:

  * stdout: a copy-paste-ready markdown table for `PHASE4_GPU_FINDINGS.md`
    §20.3, with each model row showing its INT4-vs-FP16 MMLU and
    perplexity deltas plus an individual GREEN/YELLOW/RED verdict.
  * --json-output (optional): a merged JSON pinned at `§20.3.v1` with
    per-model deltas and a worst-case combined verdict (the worst
    individual model defines the cross-model verdict — a single
    failure means INT4 doesn't generalize).

The point: removes the "one-model demo" caveat from the Honest
Validation Status table. If KIVI INT4 generalizes (the brief's
prediction), all models land in GREEN.

CLI
---

  # Pass per-model JSONs with explicit short labels (label=path):
  python -m ctm_bench.scripts.compose_multi_model_summary \\
      --inputs \\
          Qwen-7B=bench_out/track_e_audit_followups/int4_mmlu_1000.json \\
          Llama-3-8B=/tmp/multi_model/llama/results.json \\
          Mistral-7B=/tmp/multi_model/mistral/results.json \\
      --json-output bench_out/track_e_audit_followups/multi_model_summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# Decision-tree thresholds — pre-decided in PHASE4_GPU_FINDINGS §20.3.
# Each model's MMLU delta vs its OWN FP16 baseline (the within-model
# quantization cost) is compared to the canonical KIVI literature range.
# A model whose delta lands beyond -3pt indicates model-specific
# failure (not just statistical noise on a 1000-question sample at
# ~±1.5pt CI).
MMLU_GREEN_THRESHOLD_PT = -1.5    # delta >= -1.5pt → GREEN (matches KIVI lit)
MMLU_YELLOW_THRESHOLD_PT = -3.0   # delta in [-3.0, -1.5) → YELLOW

# Perplexity ratio thresholds (secondary signal — MMLU is the headline).
PPL_GREEN_RATIO = 1.05
PPL_YELLOW_RATIO = 1.15


@dataclass
class PerModelRow:
    """One model's per-eval headline numbers."""
    label: str
    model_id: str
    source_path: str
    baseline_mmlu_accuracy: Optional[float] = None
    int4_mmlu_accuracy: Optional[float] = None
    mmlu_delta_pt: Optional[float] = None
    baseline_perplexity: Optional[float] = None
    int4_perplexity: Optional[float] = None
    perplexity_ratio: Optional[float] = None
    note: Optional[str] = None


def _verdict_mmlu(delta_pt: Optional[float]) -> str:
    if delta_pt is None:
        return "MEASUREMENT MISSING"
    if delta_pt >= MMLU_GREEN_THRESHOLD_PT:
        return "GREEN"
    if delta_pt >= MMLU_YELLOW_THRESHOLD_PT:
        return "YELLOW"
    return "RED"


def _verdict_ppl(ratio: Optional[float]) -> str:
    if ratio is None:
        return "MEASUREMENT MISSING"
    if ratio <= PPL_GREEN_RATIO:
        return "GREEN"
    if ratio <= PPL_YELLOW_RATIO:
        return "YELLOW"
    return "RED"


def _combined_per_model_verdict(mmlu_v: str, ppl_v: str) -> str:
    """One model's combined verdict = worst of MMLU and perplexity."""
    order = ["GREEN", "YELLOW", "RED", "MEASUREMENT MISSING"]
    if mmlu_v == "MEASUREMENT MISSING" and ppl_v == "MEASUREMENT MISSING":
        return "MEASUREMENT MISSING"
    if mmlu_v == "MEASUREMENT MISSING":
        return ppl_v
    if ppl_v == "MEASUREMENT MISSING":
        return mmlu_v
    return max(mmlu_v, ppl_v, key=order.index)


def _cross_model_verdict(per_model_verdicts: List[str]) -> str:
    """Cross-model verdict = worst single-model verdict. One model's
    failure means INT4 doesn't generalize, even if the others succeed.
    """
    if not per_model_verdicts:
        return "MEASUREMENT MISSING"
    order = ["GREEN", "YELLOW", "RED", "MEASUREMENT MISSING"]
    return max(per_model_verdicts, key=order.index)


def _verdict_text(cross_verdict: str, n_models: int) -> str:
    """Operator-facing combined-verdict text."""
    if cross_verdict == "GREEN":
        return (
            f"**GREEN.** INT4 KIVI generalizes across all {n_models} "
            f"tested models. The 'one-model demo' caveat is removed; "
            f"update the VC brief's 'Measured' table — multi-model "
            f"generalization is now measured, not projected."
        )
    if cross_verdict == "YELLOW":
        return (
            f"**YELLOW.** INT4 KIVI mostly generalizes but at least "
            f"one model trails. Partner-shareable with a per-model "
            f"caveat. Investigate the trailing model's per-subject "
            f"MMLU breakdown to identify whether the failure is "
            f"concentrated on specific subject types."
        )
    if cross_verdict == "RED":
        return (
            f"**RED.** At least one model shows model-specific INT4 "
            f"failure (delta beyond -3.0pt). The 'one-model demo' "
            f"caveat stays. Investigate per-layer behavior on the "
            f"failing model; consider per-model bits config or "
            f"per-head scaling refinement."
        )
    return f"**MEASUREMENT MISSING** across {n_models} models."


def _load_per_model(label: str, path: Path) -> PerModelRow:
    """Read one model's `track_e_quality_eval` results.json."""
    if not path.exists():
        return PerModelRow(
            label=label, model_id="UNKNOWN", source_path=str(path),
            note="file not found",
        )
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        return PerModelRow(
            label=label, model_id="UNKNOWN", source_path=str(path),
            note=f"failed to parse: {type(exc).__name__}: {exc}",
        )

    row = PerModelRow(
        label=label,
        model_id=data.get("model_id", "UNKNOWN"),
        source_path=str(path),
    )

    # MMLU: find baseline + int4-per-channel rows.
    for r in data.get("mmlu", []):
        if r.get("cache_type") == "baseline":
            row.baseline_mmlu_accuracy = float(r.get("accuracy") or 0.0)
        elif r.get("cache_type") == "int4-per-channel":
            row.int4_mmlu_accuracy = float(r.get("accuracy") or 0.0)
    if (row.baseline_mmlu_accuracy is not None
            and row.int4_mmlu_accuracy is not None):
        row.mmlu_delta_pt = (
            (row.int4_mmlu_accuracy - row.baseline_mmlu_accuracy) * 100.0
        )

    # Perplexity: find baseline + int4-per-channel rows.
    for r in data.get("perplexity", []):
        if r.get("cache_type") == "baseline":
            row.baseline_perplexity = float(r.get("perplexity") or 0.0)
        elif r.get("cache_type") == "int4-per-channel":
            row.int4_perplexity = float(r.get("perplexity") or 0.0)
    if (row.baseline_perplexity is not None
            and row.int4_perplexity is not None
            and row.baseline_perplexity > 0):
        row.perplexity_ratio = row.int4_perplexity / row.baseline_perplexity

    return row


def render_markdown(rows: List[PerModelRow], qwen_anchor_pt: float = -0.9) -> str:
    """Build the §20.3 markdown table.

    `qwen_anchor_pt` is the published Qwen2.5-7B reference (§19.4
    measured -0.9pt @1000q). Used as context in the verdict text;
    other models' deltas are compared against their OWN FP16 baseline,
    not Qwen's.
    """
    lines: List[str] = []
    lines.append("#### §20.3 Multi-model replication — measured outcomes")
    lines.append("")
    lines.append(
        f"Reference: §19.4 measured Qwen2.5-7B INT4 KIVI at "
        f"**{qwen_anchor_pt:+.2f}pt MMLU @1000q**. Each model below is "
        f"compared against its OWN FP16 baseline (within-model "
        f"quantization cost). GREEN if the per-model delta is "
        f"≥ {MMLU_GREEN_THRESHOLD_PT:+.1f}pt (matches the KIVI "
        f"literature range)."
    )
    lines.append("")
    lines.append(
        "| Model | model_id | base MMLU | INT4 MMLU | Δ MMLU | base ppl | INT4 ppl | ppl ratio | MMLU band | ppl band | overall |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---|---|---|")
    per_model_verdicts: List[str] = []
    for row in rows:
        def fmt(v, prec=4):
            return f"{v:.{prec}f}" if v is not None else "n/a"
        def fmt_pct(v):
            return f"{v*100:.2f}%" if v is not None else "n/a"

        mmlu_band = _verdict_mmlu(row.mmlu_delta_pt)
        ppl_band = _verdict_ppl(row.perplexity_ratio)
        combined = _combined_per_model_verdict(mmlu_band, ppl_band)
        per_model_verdicts.append(combined)

        delta_str = (
            f"{row.mmlu_delta_pt:+.2f}pt"
            if row.mmlu_delta_pt is not None else "n/a"
        )
        ratio_str = (
            f"{row.perplexity_ratio:.4f}×"
            if row.perplexity_ratio is not None else "n/a"
        )
        note_suffix = f" ({row.note})" if row.note else ""
        lines.append(
            f"| {row.label}{note_suffix} | `{row.model_id}` | "
            f"{fmt_pct(row.baseline_mmlu_accuracy)} | "
            f"{fmt_pct(row.int4_mmlu_accuracy)} | {delta_str} | "
            f"{fmt(row.baseline_perplexity)} | {fmt(row.int4_perplexity)} | "
            f"{ratio_str} | {mmlu_band} | {ppl_band} | {combined} |"
        )
    lines.append("")

    cross = _cross_model_verdict(per_model_verdicts)
    lines.append(f"**Cross-model verdict (worst single model):**")
    lines.append("")
    lines.append(f"* {_verdict_text(cross, len(rows))}")
    return "\n".join(lines)


def build_json_summary(rows: List[PerModelRow]) -> dict:
    """Build the partner-shareable merged §20.3.v1 JSON."""
    per_model_out: dict = {}
    per_model_verdicts: List[str] = []
    for row in rows:
        mmlu_band = _verdict_mmlu(row.mmlu_delta_pt)
        ppl_band = _verdict_ppl(row.perplexity_ratio)
        combined = _combined_per_model_verdict(mmlu_band, ppl_band)
        per_model_verdicts.append(combined)
        per_model_out[row.label] = {
            "model_id": row.model_id,
            "source_path": row.source_path,
            "baseline_mmlu_accuracy": row.baseline_mmlu_accuracy,
            "int4_mmlu_accuracy": row.int4_mmlu_accuracy,
            "mmlu_delta_pt": row.mmlu_delta_pt,
            "baseline_perplexity": row.baseline_perplexity,
            "int4_perplexity": row.int4_perplexity,
            "perplexity_ratio": row.perplexity_ratio,
            "mmlu_verdict": mmlu_band,
            "perplexity_verdict": ppl_band,
            "combined_verdict": combined,
            "note": row.note,
        }
    cross = _cross_model_verdict(per_model_verdicts)
    return {
        "schema_version": "§20.3.v1",
        "n_models": len(rows),
        "models": per_model_out,
        "cross_model_verdict": cross,
        "verdict_text": _verdict_text(cross, len(rows)),
        "decision_tree_thresholds": {
            "mmlu_green_pt": MMLU_GREEN_THRESHOLD_PT,
            "mmlu_yellow_pt": MMLU_YELLOW_THRESHOLD_PT,
            "perplexity_green_ratio": PPL_GREEN_RATIO,
            "perplexity_yellow_ratio": PPL_YELLOW_RATIO,
        },
    }


def _parse_input_arg(spec: str) -> tuple[str, Path]:
    """Parse `label=path` argument. Falls back to using the path's
    parent directory name as the label if no `=` separator."""
    if "=" in spec:
        label, raw_path = spec.split("=", 1)
        return label.strip(), Path(raw_path.strip())
    p = Path(spec)
    return p.parent.name or p.stem, p


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="compose_multi_model_summary",
        description=(
            "Compose §20.3 multi-model replication summary. Reads N "
            "per-model JSON files (one per `track_e_quality_eval` run) "
            "and emits a markdown table + merged §20.3.v1 JSON with "
            "per-model deltas + cross-model GREEN/YELLOW/RED verdict."
        ),
    )
    parser.add_argument(
        "--inputs", nargs="+", required=True,
        help=(
            "Per-model input paths. Each item is `label=path` (e.g., "
            "`Qwen-7B=/path/to/results.json`). Without `=`, the path's "
            "parent directory name is used as the label."
        ),
    )
    parser.add_argument(
        "--qwen-anchor-pt", type=float, default=-0.9,
        help=(
            "The §19.4 measured Qwen2.5-7B MMLU delta in pt. Used as "
            "context in the verdict text. Default -0.9 matches §19.4."
        ),
    )
    parser.add_argument(
        "--json-output", type=Path, default=None,
        help=(
            "When set, also write the merged §20.3.v1 JSON. Recommended: "
            "bench_out/track_e_audit_followups/multi_model_summary.json"
        ),
    )
    args = parser.parse_args(argv)

    rows = [_load_per_model(*_parse_input_arg(spec)) for spec in args.inputs]
    print(render_markdown(rows, qwen_anchor_pt=args.qwen_anchor_pt))
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(build_json_summary(rows), indent=2),
        )
        print(f"\nWrote merged JSON: {args.json_output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
