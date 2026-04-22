#!/usr/bin/env python
"""Post-hoc diagnostic analysis of a §6 benchmark run.

Takes the CSV + manifest JSON (+ optional paraphrase cache) produced
by ``python -m symbolu_bcvf_llm.benchmark`` and emits a Markdown
report + a human-readable stdout summary. Verdict-agnostic: works
for PASS, NULL, REGRESSION, and AMBIGUOUS runs.

Typical usage (after seed 1 finishes):

    python scripts/analyze_seed_results.py \\
        --csv docs/experiments/phase_6_truthfulqa_results_mistral_seed1.csv \\
        --manifest docs/experiments/phase_6_truthfulqa_manifest_mistral_seed1.json \\
        --paraphrase-cache docs/experiments/paraphrase_cache_mistralai_Mistral-7B-Instruct-v0.3__validation.json

The report is written to the CSV's sibling directory as
``<csv-stem>__analysis.md`` by default; override with ``--out``.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Optional

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from symbolu_bcvf_llm.analysis.summary import analyze, render_markdown  # noqa: E402


def _infer_manifest_path(csv_path: pathlib.Path) -> pathlib.Path:
    """If manifest isn't passed explicitly, try the standard naming."""
    # CSV is typically `phase_6_<bench>_results<suffix>.csv`
    # Manifest is `phase_6_<bench>_manifest<suffix>.json`
    stem = csv_path.stem
    if "_results" in stem:
        manifest_stem = stem.replace("_results", "_manifest")
        return csv_path.parent / f"{manifest_stem}.json"
    return csv_path.parent / f"{stem}_manifest.json"


def _stdout_summary(report) -> str:
    """One-screen console summary matching what gets written to the md file."""
    lines = []
    lines.append("=" * 72)
    lines.append("§6 BENCHMARK ANALYSIS")
    lines.append("=" * 72)

    m = report.manifest
    args = m.get("args", {})
    model = m.get("model", {})
    lines.append(
        f"benchmark={args.get('benchmark')}  "
        f"model={model.get('name', 'unknown')}  "
        f"outcome={m.get('outcome')}"
    )

    lines.append("-" * 72)
    lines.append(f"{'decoder':<22} {'accuracy':>10} {'mean_latency':>14} {'p95':>10}")
    for name, d in report.decoders.items():
        lines.append(
            f"{d.name:<22} {d.accuracy:>9.2%} "
            f"{d.mean_latency_s * 1e3:>12.1f}ms "
            f"{d.p95_latency_s * 1e3:>8.1f}ms"
        )

    if report.verdict:
        v = report.verdict
        lines.append("-" * 72)
        lines.append(
            f"§1.10 {v['classification']}  "
            f"Δ={v['delta_pp']:+.2f} pp  "
            f"latency_ratio={v['latency_ratio']:.2f}×  "
            f"McNemar p={v['mcnemar']['p_value']:.3f}"
        )
        lines.append(v["notes"])

    if report.dormancy_signal:
        d = report.dormancy_signal
        lines.append("-" * 72)
        lines.append(
            f"Trust↔Blend agreement: {d['agreement_rate']:.1%} "
            f"({d['n_agree']} agree, {d['n_diverge']} diverge)"
        )
        lines.append(d["interpretation"])

    lines.append("-" * 72)
    lines.append("Pairwise flips (who wins when they disagree):")
    for (a, b), f in report.flips.items():
        lines.append(
            f"  {a:>22} vs {b:<22}: "
            f"{f.n_disagree} disagree → {a} wins {f.a_wins_b_loses}, "
            f"{b} wins {f.a_loses_b_wins}, "
            f"both-wrong {f.both_wrong}, net={f.net_gain_for_a:+d}"
        )

    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Post-hoc analysis of a §6 benchmark run."
    )
    parser.add_argument(
        "--csv", type=pathlib.Path, required=True,
        help="results CSV (e.g. phase_6_truthfulqa_results_mistral_seed1.csv)",
    )
    parser.add_argument(
        "--manifest", type=pathlib.Path, default=None,
        help="manifest JSON (inferred from --csv if omitted)",
    )
    parser.add_argument(
        "--paraphrase-cache", type=pathlib.Path, default=None,
        help="optional paraphrase cache JSON (enables paraphrase quality audit)",
    )
    parser.add_argument(
        "--out", type=pathlib.Path, default=None,
        help="Markdown output path (default: <csv-stem>__analysis.md next to CSV)",
    )
    parser.add_argument(
        "--samples", type=int, default=5,
        help="paraphrase samples to include in the audit (default 5)",
    )
    args = parser.parse_args(argv)

    if not args.csv.exists():
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        return 1

    manifest_path: Optional[pathlib.Path] = args.manifest
    if manifest_path is None:
        manifest_path = _infer_manifest_path(args.csv)
        if not manifest_path.exists():
            print(
                f"warning: manifest not found at {manifest_path}; "
                "proceeding without manifest context.",
                file=sys.stderr,
            )
            manifest_path = None

    report = analyze(
        results_csv=args.csv,
        manifest_path=manifest_path,
        paraphrase_cache_path=args.paraphrase_cache,
        sample_n=args.samples,
    )

    out_path = args.out or (
        args.csv.parent / f"{args.csv.stem}__analysis.md"
    )
    out_path.write_text(render_markdown(report))

    print(_stdout_summary(report))
    print()
    print(f"Markdown report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
