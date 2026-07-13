"""Milestone benchmark harness: before/after for the two bottlenecks.

Compares, on the EXISTING corpus (unchanged) against the REAL gate:
  * extractor instability — baseline v1 vs multi-stage v2 (all / held-out / by domain)
  * protected-span detection — baseline keyword detector vs trained detector vs a
    fail-closed hybrid (all / held-out / by domain), with recall / precision /
    protected fraction / deployable ceiling / oracle ceiling.

Deterministic. Anti-leakage: the detector is trained ONLY on DEV+VALIDATION; the
held-out block is the honest generalization number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ablation, adapter, extractor_v2, metrics, protected_detector as PD
from .corpus import registry
from .corpus.schema import HELDOUT
from .units import SOURCE_TYPES

# fail-closed safety net: structural source types + any extractor-found fact.
_SAFE_SRC = {"json_field", "table_row", "table_cell", "evidence_record",
             "approval_record", "policy_rule", "exception", "tool_argument"}


def _safety_net(unit) -> bool:
    if unit.source_type in _SAFE_SRC:
        return True
    # structural-reference spans (needed to interpret their partner) are protected
    if unit.references or unit.dependency_links:
        return True
    ex = extractor_v2.extract_unit(unit.text)
    return bool(ex.concepts or ex.structured_keys)


def hybrid_protect_fn(trained):
    def protect(ctx):
        base = trained.protect(ctx)
        return base | {u.id for u in ctx.units if _safety_net(u)}
    return protect


@dataclass
class DetectorRow:
    name: str
    recall: float
    precision: float
    protected_fraction: float
    deployable_ceiling: float
    oracle_ceiling: float


def _det_row(name, runs, protect_fn):
    a = metrics.aggregate(runs, protect_fn)
    return DetectorRow(name, a.recall_p0, a.precision_p0, a.f_protected,
                       a.deployable_ceiling, a.oracle_ceiling)


@dataclass
class BenchResult:
    n_contexts: int
    # extractor instability
    instab_v1_all: float
    instab_v2_all: float
    instab_v1_heldout: float
    instab_v2_heldout: float
    instab_v2_by_domain: dict
    # detectors (held-out = generalization; overall = all splits)
    detectors_heldout: list
    detectors_overall: list
    det_by_domain: dict          # domain -> {"baseline":row,"hybrid":row}
    per_class_recall_heldout: dict
    residual_unprotected_heldout: list  # (item_id, unit_id, label) still missed by hybrid


def _instability(items, runs):
    return metrics.aggregate(runs).extractor_instability_rate


def run_bench(items=None) -> BenchResult:
    items = items if items is not None else registry.load_all()
    sp = adapter.default_signed_policy()

    # ablation runs with baseline (v1) and v2 extractors
    runs_v1 = [ablation.run_ablations(it.context, sp) for it in items]
    runs_v2 = [ablation.run_ablations(it.context, sp,
                                      realistic_spec_fn=extractor_v2.realistic_spec_v2)
               for it in items]
    ho_idx = [i for i, it in enumerate(items) if it.split == HELDOUT]

    def sub(runs, idx):
        return [runs[i] for i in idx]

    instab_v2_by_domain = {}
    domains = sorted({it.domain for it in items})
    for d in domains:
        idx = [i for i, it in enumerate(items) if it.domain == d]
        instab_v2_by_domain[d] = metrics.aggregate(sub(runs_v2, idx)).extractor_instability_rate

    # train detector on DEV+VAL (labels from gate-derived ablation)
    trained = PD.fit(items, runs_v1)
    hybrid = hybrid_protect_fn(trained)

    def det_block(idx):
        rr = sub(runs_v1, idx)
        return [_det_row("baseline_keyword", rr, None),
                _det_row("trained_classifier", rr, trained.protect),
                _det_row("fail_closed_hybrid", rr, hybrid)]

    all_idx = list(range(len(items)))
    det_heldout = det_block(ho_idx)
    det_overall = det_block(all_idx)

    det_by_domain = {}
    for d in domains:
        idx = [i for i, it in enumerate(items) if it.domain == d]
        rr = sub(runs_v1, idx)
        det_by_domain[d] = {
            "baseline": _det_row("baseline", rr, None),
            "hybrid": _det_row("hybrid", rr, hybrid),
        }

    # per-class recall + residual misses on held-out, measured against the FULL
    # metrics critical union (includes interaction/redundancy-only spans that
    # single-ablation labels alone would miss). This is the honest safety audit.
    per_class = {c: [0, 0] for c in PD.CLASSES}
    per_class["INTERACTION_ONLY"] = [0, 0]
    residual = []
    for i in ho_idx:
        it, run = items[i], runs_v1[i]
        prot = hybrid(it.context)
        single = (run.decision_units | run.envelope_units | run.assurance_units
                  | run.structure_units)
        union = single | run.redundant_units | run.interaction_units
        for uid in union:
            lbl = PD.derive_label(run, uid)
            key = lbl if lbl != PD.NON_CRITICAL else "INTERACTION_ONLY"
            per_class[key][1] += 1
            if uid in prot:
                per_class[key][0] += 1
            else:
                residual.append((it.item_id, uid, key))
    per_class_recall = {c: (p / t if t else 1.0) for c, (p, t) in per_class.items()}

    return BenchResult(
        n_contexts=len(items),
        instab_v1_all=_instability(items, runs_v1),
        instab_v2_all=_instability(items, runs_v2),
        instab_v1_heldout=metrics.aggregate(sub(runs_v1, ho_idx)).extractor_instability_rate,
        instab_v2_heldout=metrics.aggregate(sub(runs_v2, ho_idx)).extractor_instability_rate,
        instab_v2_by_domain=instab_v2_by_domain,
        detectors_heldout=det_heldout, detectors_overall=det_overall,
        det_by_domain=det_by_domain, per_class_recall_heldout=per_class_recall,
        residual_unprotected_heldout=residual)


# --- preregistered milestone targets (mirror MILESTONE_PREREGISTRATION.md) ---
TARGET_HELDOUT_INSTABILITY = 0.10
TARGET_MIN_RECALL = 1.0            # safety: never drop a decision-relevant fact
TARGET_MIN_PRECISION_GAIN = 0.20  # "substantial" precision increase over baseline


def evaluate_targets(b: BenchResult) -> dict:
    ho = {r.name: r for r in b.detectors_heldout}
    base, hyb = ho["baseline_keyword"], ho["fail_closed_hybrid"]
    return {
        "heldout_instability_below_10pct": b.instab_v2_heldout < TARGET_HELDOUT_INSTABILITY,
        "all_domains_instability_below_10pct": all(
            v < TARGET_HELDOUT_INSTABILITY for v in b.instab_v2_by_domain.values()),
        "heldout_recall_is_1": hyb.recall >= TARGET_MIN_RECALL - 1e-9,
        "heldout_precision_gain_substantial": (hyb.precision - base.precision) >= TARGET_MIN_PRECISION_GAIN,
    }


def _pct(x):
    return f"{100 * x:.1f}%"


def to_json(b: BenchResult) -> dict:
    def row(r):
        return {"name": r.name, "recall": r.recall, "precision": r.precision,
                "protected_fraction": r.protected_fraction,
                "deployable_ceiling": r.deployable_ceiling, "oracle_ceiling": r.oracle_ceiling}
    return {
        "n_contexts": b.n_contexts,
        "targets_met": evaluate_targets(b),
        "extractor_instability": {
            "all": {"v1": b.instab_v1_all, "v2": b.instab_v2_all},
            "heldout": {"v1": b.instab_v1_heldout, "v2": b.instab_v2_heldout},
            "v2_by_domain": b.instab_v2_by_domain},
        "detectors": {"heldout": [row(r) for r in b.detectors_heldout],
                      "overall": [row(r) for r in b.detectors_overall]},
        "detector_by_domain": {d: {"baseline": row(v["baseline"]), "hybrid": row(v["hybrid"])}
                               for d, v in b.det_by_domain.items()},
        "heldout_per_class_recall": b.per_class_recall_heldout,
        "heldout_residual_unprotected": b.residual_unprotected_heldout,
    }


def render_report_md(b: BenchResult) -> str:
    L, ap = [], None
    out = []
    ap = out.append
    tgt = evaluate_targets(b)
    ap("# EXTRACTOR_V2_RESULTS — Milestone: extraction + protected-span quality\n")
    ap("> Improves the two bottlenecks from the naturalistic study ONLY (extractor "
       "instability, protected-span precision). No compressor, SCC, or USE. Existing "
       "corpus and ActionGate unchanged. Detector trained on DEV+VALIDATION; held-out "
       "is the honest generalization number. Deterministic.\n")
    ap(f"- Corpus: **{b.n_contexts}** contexts (unchanged from the naturalistic study).\n")

    ap("## Targets (preregistered)\n")
    for k, v in tgt.items():
        ap(f"- {'✅' if v else '❌'} `{k}`")
    ap("")

    ap("## 1 · Extractor instability (before → after)\n")
    ap("| scope | v1 baseline | v2 multi-stage |")
    ap("|---|---|---|")
    ap(f"| all splits | {_pct(b.instab_v1_all)} | **{_pct(b.instab_v2_all)}** |")
    ap(f"| held-out | {_pct(b.instab_v1_heldout)} | **{_pct(b.instab_v2_heldout)}** |")
    ap("\n**v2 instability by domain** (target < 10%):\n")
    ap("| domain | v2 instability |")
    ap("|---|---|")
    for d, v in sorted(b.instab_v2_by_domain.items()):
        ap(f"| {d} | {_pct(v)}{'' if v < 0.10 else '  ⚠️'} |")
    ap("")

    ap("## 2 · Protected-span detection (held-out generalization)\n")
    ap("| detector | recall | precision | protected frac | deployable ceiling | oracle ceiling |")
    ap("|---|---|---|---|---|---|")
    for r in b.detectors_heldout:
        ap(f"| {r.name} | {_pct(r.recall)} | {_pct(r.precision)} | {_pct(r.protected_fraction)} | "
           f"{_pct(r.deployable_ceiling)} | {_pct(r.oracle_ceiling)} |")
    ap("\n**Overall (all splits):**\n")
    ap("| detector | recall | precision | deployable ceiling |")
    ap("|---|---|---|---|")
    for r in b.detectors_overall:
        ap(f"| {r.name} | {_pct(r.recall)} | {_pct(r.precision)} | {_pct(r.deployable_ceiling)} |")
    ap(f"\nHeld-out per-class recall (hybrid, vs full critical union): "
       f"{ {k: round(v, 3) for k, v in b.per_class_recall_heldout.items()} }.  "
       f"Residual unprotected critical spans: **{len(b.residual_unprotected_heldout)}**.\n")

    ap("## 3 · Protected-span detection by domain (baseline → hybrid)\n")
    ap("| domain | baseline R/P | hybrid R/P | hybrid deployable ceiling |")
    ap("|---|---|---|---|")
    for d, v in sorted(b.det_by_domain.items()):
        bl, hy = v["baseline"], v["hybrid"]
        ap(f"| {d} | {_pct(bl.recall)}/{_pct(bl.precision)} | "
           f"{_pct(hy.recall)}/{_pct(hy.precision)} | {_pct(hy.deployable_ceiling)} |")
    ap("")

    ap("## Honest caveats\n")
    ap("- **Precision ≈ 100% is partly a corpus-cleanliness artifact.** In this corpus "
       "the fact-bearing source types (evidence/approval/policy/json/table) are exactly "
       "the critical spans, and prose is filler — so the safety net separates them "
       "cleanly. Real customer context will mix critical and non-critical instances of "
       "the same source type, lowering precision. This number will not survive intact on "
       "messier data.")
    ap("- The detector's labels come from **single-ablation** gate effects; jointly-"
       "necessary (interaction-only) spans are covered here by the fail-closed structural "
       "safety net, not by the learned model.")
    ap("- Instability and ceilings are pre-economics; prompt-cache-adjusted savings still "
       "depend on real cache behaviour (unchanged from the naturalistic study).")

    ap("\n## Recommendation — is the compressor now justified?\n")
    allmet = all(tgt.values())
    ho = {r.name: r for r in b.detectors_heldout}
    hyb = ho["fail_closed_hybrid"]
    if allmet:
        ap("**The two milestone blockers are cleared on this corpus.** Held-out extractor "
           f"instability fell to {_pct(b.instab_v2_heldout)} (< 10%, all domains), and the "
           f"fail-closed detector reaches {_pct(hyb.recall)} recall at {_pct(hyb.precision)} "
           f"precision on held-out, lifting the deployable ceiling to "
           f"{_pct(hyb.deployable_ceiling)} (≈ the {_pct(hyb.oracle_ceiling)} oracle ceiling). "
           "The previous negative verdict (`EXTRACTOR_NOT_RELIABLE`) no longer holds on this data.")
        ap("\n**Recommendation: conditionally proceed — build a NARROW prototype, not a "
           "general compressor.** Justified now: a bounded structural + P0-protected "
           "context-minimization prototype, since the extractor is reliable and the "
           "protected-span detector is high-precision at full recall. NOT yet justified: a "
           "general paraphrase-robust compressor sold on these numbers, because (a) the "
           "≈100% precision is partly a corpus-cleanliness artifact, and (b) prompt-cache-"
           "adjusted economics still require real customer data. Gate the full build on a "
           "`FIELD_REAL` corpus run through these same frozen thresholds.")
    else:
        ap("**One or more targets were not met.** The blockers are not cleared; do NOT "
           "proceed to a compressor. Fix the failing component and re-run before revisiting "
           "the build decision.")
    return "\n".join(out)
