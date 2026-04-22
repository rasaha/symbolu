"""Post-hoc analysis of §6 benchmark runs.

Takes the CSV + manifest JSON produced by
``python -m symbolu_bcvf_llm.benchmark`` and generates a
verdict-agnostic diagnostic report:

  - accuracy table + paired McNemar (vanilla vs blend, vs trust,
    blend vs trust)
  - flip analysis: where trust flips blend's prediction, did it
    gain or lose?
  - score-margin distribution per decoder (confidence proxy)
  - latency distribution + trust/blend ratio
  - trust/blend-agreement rate (proxy for BCVF dormancy — if trust
    agrees with blend on 95%+, the trust layer was near-uniform)
  - paraphrase quality audit (sample + diversity stats, if the
    paraphrase cache file is provided)
  - §1.10 verdict interpretation with recommended next step

Designed to consume the combined CSV. Does not require the
running process to have finished (partial CSVs from the pre-fix
harness still work).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from symbolu_bcvf_llm.benchmark.metrics import (
    classify_phase_six_result,
    latency_stats,
    mcnemar_paired,
)


DECODER_ORDER = ("vanilla", "conventional_blend", "bcvf_trust")


@dataclass
class DecoderSummary:
    name: str
    n: int
    accuracy: float
    mean_latency_s: float
    median_latency_s: float
    p95_latency_s: float
    correct: np.ndarray        # (N,) bool
    predicted: np.ndarray      # (N,) int
    scores: List[List[float]]  # (N, K) per-choice log-probs


@dataclass
class FlipAnalysis:
    """Where decoder A predicts one choice and decoder B predicts another."""

    a_name: str
    b_name: str
    n_disagree: int
    a_wins_b_loses: int   # A correct, B wrong
    a_loses_b_wins: int   # A wrong, B correct
    both_wrong: int        # both wrong but picked different wrong choices
    net_gain_for_a: int    # = a_wins_b_loses - a_loses_b_wins


@dataclass
class AnalysisReport:
    """All computed diagnostics for a benchmark run."""

    manifest: Dict[str, Any]
    decoders: Dict[str, DecoderSummary]
    flips: Dict[Tuple[str, str], FlipAnalysis]
    agreement_rates: Dict[Tuple[str, str], float]
    margin_stats: Dict[str, Dict[str, float]]  # decoder → {mean, median, min}
    dormancy_signal: Optional[Dict[str, Any]] = None
    verdict: Optional[Dict[str, Any]] = None
    paraphrase_audit: Optional[Dict[str, Any]] = field(default=None)


# --------------------------------------------------------------------------- #
# Load functions
# --------------------------------------------------------------------------- #


def load_manifest(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text())


def load_results_csv(path: Path) -> Dict[str, DecoderSummary]:
    """Parse the combined per-decoder-per-question CSV into
    DecoderSummary objects keyed by decoder name."""
    import csv

    by_decoder: Dict[str, List[Dict[str, Any]]] = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            by_decoder.setdefault(row["decoder"], []).append(row)

    out: Dict[str, DecoderSummary] = {}
    for decoder, rows in by_decoder.items():
        rows.sort(key=lambda r: int(r["question_id"]))
        correct = np.array(
            [r["correct"].lower() == "true" for r in rows], dtype=bool
        )
        predicted = np.array(
            [int(r["predicted"]) for r in rows], dtype=np.int64
        )
        latency = np.array(
            [float(r["latency_s"]) for r in rows], dtype=np.float64
        )
        scores_list = [json.loads(r["scores"]) for r in rows]
        ls = latency_stats(latency)
        out[decoder] = DecoderSummary(
            name=decoder,
            n=len(rows),
            accuracy=float(correct.mean()) if len(correct) else 0.0,
            mean_latency_s=ls.mean_s,
            median_latency_s=ls.median_s,
            p95_latency_s=ls.p95_s,
            correct=correct,
            predicted=predicted,
            scores=scores_list,
        )
    return out


# --------------------------------------------------------------------------- #
# Analyses
# --------------------------------------------------------------------------- #


def flip_analysis(a: DecoderSummary, b: DecoderSummary) -> FlipAnalysis:
    """Where do decoders A and B disagree, and who wins?"""
    if a.n != b.n:
        raise ValueError(f"decoder lengths differ: {a.n} vs {b.n}")
    disagree = a.predicted != b.predicted
    n_dis = int(disagree.sum())
    a_right_b_wrong = int(((a.correct) & (~b.correct) & disagree).sum())
    a_wrong_b_right = int(((~a.correct) & (b.correct) & disagree).sum())
    both_wrong = int(((~a.correct) & (~b.correct) & disagree).sum())
    return FlipAnalysis(
        a_name=a.name,
        b_name=b.name,
        n_disagree=n_dis,
        a_wins_b_loses=a_right_b_wrong,
        a_loses_b_wins=a_wrong_b_right,
        both_wrong=both_wrong,
        net_gain_for_a=a_right_b_wrong - a_wrong_b_right,
    )


def agreement_rate(a: DecoderSummary, b: DecoderSummary) -> float:
    """Fraction of questions where A and B predicted the same choice."""
    if a.n == 0:
        return 0.0
    return float((a.predicted == b.predicted).mean())


def score_margins(summary: DecoderSummary) -> Dict[str, float]:
    """Per-decoder 'confidence' proxy: difference between top-1 and
    top-2 log-probs per question. Wider = more confident."""
    margins: List[float] = []
    for scores in summary.scores:
        if len(scores) < 2:
            continue
        sorted_desc = sorted(scores, reverse=True)
        margins.append(sorted_desc[0] - sorted_desc[1])
    if not margins:
        return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
    arr = np.array(margins, dtype=np.float64)
    return {
        "mean": float(arr.mean()),
        "median": float(np.median(arr)),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "n": len(arr),
    }


def dormancy_signal(
    trust: DecoderSummary, blend: DecoderSummary
) -> Dict[str, Any]:
    """Proxy for BCVF dormancy: if trust's predictions nearly-always
    match blend's, the trust weights were near-uniform most of the
    time (since uniform weights reduce trust to blend).

    Returns a dict with the agreement rate, an interpretation label,
    and the number of questions where trust actively diverged.
    """
    if trust.n == 0:
        return {"agreement_rate": 0.0, "interpretation": "no data"}
    agree = int((trust.predicted == blend.predicted).sum())
    rate = agree / trust.n
    # Thresholds from §5.2: autonomy observed ~80% uniform weights.
    # For LLM, we'd expect similar or higher dormancy in a NULL verdict.
    if rate >= 0.99:
        interp = (
            "extreme dormancy — trust agreed with blend on >99% of questions. "
            "Trust layer was effectively inactive; BCVF never moved the needle. "
            "Consistent with NULL verdict; see §5.2 caveat on trust-weight flatness."
        )
    elif rate >= 0.95:
        interp = (
            "high dormancy — trust agreed with blend on >95%. "
            "BCVF signal was weak; improvements (if any) come from the <5% where "
            "trust diverged."
        )
    elif rate >= 0.85:
        interp = (
            "moderate dormancy — trust actively shifted weights on 5-15% of "
            "questions. Expected regime per §5.2 autonomy evidence."
        )
    else:
        interp = (
            "low dormancy — trust diverged from blend on >15% of questions. "
            "BCVF was active; whether that helped or hurt depends on accuracy."
        )
    return {
        "agreement_rate": rate,
        "n_agree": agree,
        "n_diverge": trust.n - agree,
        "interpretation": interp,
    }


def paraphrase_audit(
    cache_path: Optional[Path],
    sample_n: int = 5,
    seed: int = 0,
) -> Optional[Dict[str, Any]]:
    """Sample + summarize the paraphrase cache for quality inspection.

    Returns a dict with:
      - total entries
      - mean paraphrase length (chars)
      - length distribution summary
      - random sample of `sample_n` entries (for manual inspection)
      - "empty_rate": fraction of empty/placeholder paraphrases
    """
    if cache_path is None or not Path(cache_path).exists():
        return None
    payload = json.loads(Path(cache_path).read_text())
    entries = payload.get("entries", {})
    if not entries:
        return {
            "cache_path": str(cache_path),
            "total": 0,
            "empty_rate": 0.0,
            "mean_length_chars": 0.0,
            "samples": [],
        }
    lengths = [len(v) for v in entries.values()]
    empty = sum(1 for v in entries.values() if not v.strip())
    rng = np.random.default_rng(seed=seed)
    keys = list(entries.keys())
    idxs = rng.choice(len(keys), size=min(sample_n, len(keys)), replace=False)
    samples = []
    for i in idxs:
        k = keys[int(i)]
        samples.append({
            "key": k,
            "text": entries[k],
            "length_chars": len(entries[k]),
        })
    return {
        "cache_path": str(cache_path),
        "model_name": payload.get("model_name"),
        "split": payload.get("split"),
        "total": len(entries),
        "empty_rate": empty / len(entries),
        "mean_length_chars": float(np.mean(lengths)),
        "median_length_chars": float(np.median(lengths)),
        "min_length_chars": int(min(lengths)),
        "max_length_chars": int(max(lengths)),
        "samples": samples,
    }


# --------------------------------------------------------------------------- #
# Top-level driver
# --------------------------------------------------------------------------- #


def analyze(
    results_csv: Path,
    manifest_path: Optional[Path] = None,
    paraphrase_cache_path: Optional[Path] = None,
    sample_n: int = 5,
) -> AnalysisReport:
    """Produce a complete `AnalysisReport` from the benchmark artifacts."""
    manifest: Dict[str, Any] = {}
    if manifest_path is not None and Path(manifest_path).exists():
        manifest = load_manifest(manifest_path)

    decoders = load_results_csv(results_csv)

    # Flip analyses between every decoder pair.
    flips: Dict[Tuple[str, str], FlipAnalysis] = {}
    agreement: Dict[Tuple[str, str], float] = {}
    names = [n for n in DECODER_ORDER if n in decoders]
    for i, a_name in enumerate(names):
        for b_name in names[i + 1 :]:
            a, b = decoders[a_name], decoders[b_name]
            flips[(a_name, b_name)] = flip_analysis(a, b)
            agreement[(a_name, b_name)] = agreement_rate(a, b)

    # Score margins (confidence proxy) per decoder.
    margin_stats = {name: score_margins(decoders[name]) for name in names}

    # Dormancy proxy (trust ↔ blend).
    dormancy = None
    if "bcvf_trust" in decoders and "conventional_blend" in decoders:
        dormancy = dormancy_signal(
            decoders["bcvf_trust"], decoders["conventional_blend"]
        )

    # §1.10 verdict.
    verdict = None
    if "bcvf_trust" in decoders and "conventional_blend" in decoders:
        trust = decoders["bcvf_trust"]
        blend = decoders["conventional_blend"]
        v = classify_phase_six_result(
            trust_correct=trust.correct,
            blend_correct=blend.correct,
            trust_latencies=np.array([trust.mean_latency_s] * trust.n),
            blend_latencies=np.array([blend.mean_latency_s] * blend.n),
        )
        verdict = {
            "classification": v.classification,
            "delta_pp": v.delta_pp,
            "latency_ratio": v.latency_ratio,
            "mcnemar": {
                "b": v.mcnemar.b, "c": v.mcnemar.c,
                "p_value": v.mcnemar.p_value_exact,
            },
            "notes": v.notes,
        }

    # Paraphrase audit.
    p_audit = paraphrase_audit(paraphrase_cache_path, sample_n=sample_n)

    return AnalysisReport(
        manifest=manifest,
        decoders=decoders,
        flips=flips,
        agreement_rates=agreement,
        margin_stats=margin_stats,
        dormancy_signal=dormancy,
        verdict=verdict,
        paraphrase_audit=p_audit,
    )


# --------------------------------------------------------------------------- #
# Markdown rendering
# --------------------------------------------------------------------------- #


def render_markdown(report: AnalysisReport) -> str:
    lines: List[str] = []
    m = report.manifest
    env = m.get("environment", {})
    model = m.get("model", {})
    args = m.get("args", {})
    lines.append("# §6 Phase 4 benchmark analysis\n")
    lines.append(
        f"- **Benchmark:** `{args.get('benchmark', 'unknown')}`\n"
        f"- **Model:** `{model.get('name', 'unknown')}`"
    )
    if model.get("rewrite_seed_pair") is not None:
        lines.append(
            f"- **Evaluation seed:** `{model.get('evaluation_seed', '?')}` → "
            f"rewrite pair `{tuple(model.get('rewrite_seed_pair', []))}`"
        )
    if model.get("compile_status"):
        lines.append(f"- **torch.compile:** `{model['compile_status']}`")
    lines.append(f"- **Outcome:** `{m.get('outcome', 'unknown')}`\n")

    # § 1.10 verdict
    if report.verdict:
        v = report.verdict
        lines.append("## §1.10 Classification\n")
        lines.append(
            f"**`{v['classification']}`**  "
            f"(Δ = `{v['delta_pp']:+.2f} pp`, "
            f"latency ratio = `{v['latency_ratio']:.2f}×`, "
            f"McNemar p = `{v['mcnemar']['p_value']:.3f}` "
            f"with b = {v['mcnemar']['b']}, c = {v['mcnemar']['c']})\n"
        )
        lines.append(f"*{v['notes']}*\n")

    # Accuracy + latency table
    lines.append("## Per-decoder results\n")
    lines.append(
        "| Decoder | N | Accuracy | Mean latency | Median | P95 |"
    )
    lines.append("|---|---|---|---|---|---|")
    for name in DECODER_ORDER:
        if name not in report.decoders:
            continue
        d = report.decoders[name]
        lines.append(
            f"| {name} | {d.n} | {d.accuracy:.2%} | "
            f"{d.mean_latency_s * 1e3:.1f} ms | "
            f"{d.median_latency_s * 1e3:.1f} ms | "
            f"{d.p95_latency_s * 1e3:.1f} ms |"
        )
    lines.append("")

    # Paired McNemar + flip analysis
    lines.append("## Paired comparisons\n")
    lines.append(
        "| A vs B | disagreements | A✓B✗ | A✗B✓ | both wrong | net A gain |"
    )
    lines.append("|---|---|---|---|---|---|")
    for (a_name, b_name), f in report.flips.items():
        lines.append(
            f"| {a_name} vs {b_name} | {f.n_disagree} | "
            f"{f.a_wins_b_loses} | {f.a_loses_b_wins} | "
            f"{f.both_wrong} | {f.net_gain_for_a:+d} |"
        )
    lines.append("")

    # Dormancy proxy — the most important interpretive finding
    if report.dormancy_signal:
        d = report.dormancy_signal
        lines.append("## BCVF dormancy proxy (trust ↔ blend agreement)\n")
        lines.append(
            f"- Trust predictions matched blend on "
            f"**{d['n_agree']}/{d['n_agree'] + d['n_diverge']} = "
            f"{d['agreement_rate']:.1%}** of questions."
        )
        lines.append(f"- Trust diverged on **{d['n_diverge']}** questions.")
        lines.append(f"\n**Interpretation:** {d['interpretation']}\n")

    # Score margin (confidence proxy)
    lines.append("## Score margins (top-1 − top-2 log-prob; confidence proxy)\n")
    lines.append("| Decoder | Mean | Median | Min | Max |")
    lines.append("|---|---|---|---|---|")
    for name, stats in report.margin_stats.items():
        lines.append(
            f"| {name} | {stats['mean']:.3f} | {stats['median']:.3f} | "
            f"{stats['min']:.3f} | {stats['max']:.3f} |"
        )
    lines.append("")

    # Paraphrase audit
    if report.paraphrase_audit:
        p = report.paraphrase_audit
        lines.append("## Paraphrase audit\n")
        lines.append(
            f"- **Cache file:** `{p['cache_path']}`\n"
            f"- **Model × split:** `{p.get('model_name', '?')}` / "
            f"`{p.get('split', '?')}`\n"
            f"- **Total entries:** {p['total']}\n"
            f"- **Empty rate:** {p['empty_rate']:.2%}\n"
            f"- **Length (chars):** mean {p.get('mean_length_chars', 0):.0f}, "
            f"median {p.get('median_length_chars', 0):.0f}, "
            f"min {p.get('min_length_chars', 0)}, "
            f"max {p.get('max_length_chars', 0)}"
        )
        if p.get("samples"):
            lines.append("\n**Random samples:**\n")
            for s in p["samples"]:
                text = s["text"].replace("\n", " ")
                if len(text) > 240:
                    text = text[:240] + "…"
                lines.append(f"- `{s['key']}` ({s['length_chars']} chars): {text}")
            lines.append("")

    # Next-step recommendation
    lines.append("## Recommended next step\n")
    lines.append(_recommendation(report))
    lines.append("")

    return "\n".join(lines)


def _recommendation(report: AnalysisReport) -> str:
    if not report.verdict:
        return "Verdict not computable (trust or blend missing)."
    cls = report.verdict["classification"]
    dormancy_rate = (
        report.dormancy_signal["agreement_rate"]
        if report.dormancy_signal else None
    )
    dormancy_note = (
        f" (dormancy rate {dormancy_rate:.0%})" if dormancy_rate is not None else ""
    )
    recs = {
        "PASS": (
            "**`PASS` (single seed):** run seed 2 (`--seed 2`) to confirm "
            "§1.10 replication within ±1 pp. If seed 2 also passes, V1 "
            "succeeds and §10 decision gate proceeds."
        ),
        "NULL": (
            f"**`NULL`**{dormancy_note}: structural claim does not transfer. "
            "Skip seed 2 — replicating null adds no signal. Write up result, "
            "consult §9 V2 roadmap for alternative approaches. Likely fix "
            "candidates: stronger paraphrase diversity (different rewrite "
            "instructions, or cross-model sources to increase natural "
            "disagreement)."
        ),
        "REGRESSION": (
            f"**`REGRESSION`**{dormancy_note}: post-mortem required. Which "
            "of {detector, composition, invariance} broke? Check the flip "
            "analysis — if trust loses on questions blend gets right, trust "
            "may be down-weighting the *correct* source. Consider §9 veto-"
            "structured composition (anchor-relative) as the V2 alternative."
        ),
        "UNVIABLE_COST": (
            "**`UNVIABLE_COST`**: benchmark latency ratio > 5×, regardless "
            "of accuracy. §9 optimization tier: batch M sources in one "
            "forward pass, KV-cache sharing. Real-time generation would "
            "show ~2× instead of ~30×; re-evaluate cost question in that "
            "mode."
        ),
        "AMBIGUOUS": (
            f"**`AMBIGUOUS`**{dormancy_note}: between NULL and PASS bands. "
            "Run seed 2; combined N=1634 may push past the statistical "
            "boundary."
        ),
    }
    return recs.get(cls, f"Unknown classification `{cls}`.")
