"""Run the frozen ablation experiment against the naturalistic corpus.

Orchestrates: load corpus -> ablate every item -> stratified metrics + CIs ->
economics -> two-pass annotation review -> per-partition + combined naturalistic
verdicts -> render PUBLIC_CORPUS_RESULTS.md, a machine-readable JSON, the corpus
manifest, and a naturalistic section appended to RESULTS_RECORD.md (the synthetic
result is preserved unchanged).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import ablation, adapter, annotation, economics, naturalistic_metrics, verdict
from .corpus import manifest, registry
from .corpus.schema import AUTHORED, PUBLIC


@dataclass
class PartitionStudy:
    label: str
    items: list
    runs: list
    report: object
    econ: object
    verdict: object


@dataclass
class NaturalisticStudy:
    items: list
    runs: list
    combined: object
    econ: object
    review: object
    partitions: dict          # label -> PartitionStudy
    manifest: dict


def run_corpus(items=None):
    items = items if items is not None else registry.load_all()
    sp = adapter.default_signed_policy()
    # DEV/VALIDATION exercise interaction ablation; HELDOUT is left untouched (dev=False).
    from .corpus.schema import HELDOUT
    runs = [ablation.run_ablations(it.context, sp, dev=(it.split != HELDOUT)) for it in items]
    return items, runs


def _partition(items, runs, label):
    pit, prun = zip(*[(it, r) for it, r in zip(items, runs) if it.partition == label])
    pit, prun = list(pit), list(prun)
    rep = naturalistic_metrics.compute(pit, prun)
    econ = economics.model(rep.agg)
    v = verdict.decide_naturalistic(rep.agg, econ, rep.by_domain, label)
    return PartitionStudy(label=label, items=pit, runs=prun, report=rep, econ=econ, verdict=v)


def run_study() -> NaturalisticStudy:
    items, runs = run_corpus()
    combined = naturalistic_metrics.compute(items, runs)
    econ = economics.model(combined.agg)
    review = annotation.review(items, runs)
    partitions = {PUBLIC: _partition(items, runs, PUBLIC),
                  AUTHORED: _partition(items, runs, AUTHORED)}
    return NaturalisticStudy(items=items, runs=runs, combined=combined, econ=econ,
                             review=review, partitions=partitions,
                             manifest=manifest.build_manifest(items))


# ----------------------------- rendering ------------------------------------
def _pct(x):
    return f"{100 * x:.1f}%"


def _ci(rep, field):
    lo, hi = rep.ci[field]
    return f"[{_pct(lo)}, {_pct(hi)}]"


def to_json(study: NaturalisticStudy) -> dict:
    def agg_row(a):
        return {"n_contexts": a.n_contexts, "total_units": a.total_units,
                "total_ablations": a.total_ablations, "total_tokens": a.total_tokens,
                "f_envelope": a.f_envelope, "f_decision": a.f_decision,
                "f_assurance": a.f_assurance, "f_critical_union": a.f_critical_union,
                "f_protected": a.f_protected, "recall_p0": a.recall_p0,
                "precision_p0": a.precision_p0, "oracle_ceiling": a.oracle_ceiling,
                "deployable_ceiling": a.deployable_ceiling,
                "interaction_miss_rate": a.interaction_miss_rate,
                "extractor_instability_rate": a.extractor_instability_rate}

    def part(ps):
        return {"verdict": ps.verdict.verdict, "rationale": ps.verdict.rationale,
                "aggregate": agg_row(ps.report.agg),
                "by_domain": {d: agg_row(a) for d, a in ps.report.by_domain.items()},
                "heldout_instability": ps.report.heldout_instability,
                "redundancy_only_fraction": ps.report.redundancy_only_fraction,
                "economics": {"naive": ps.econ.naive_savings_ratio,
                              "cache_adjusted": ps.econ.cache_adjusted_savings_ratio,
                              "clears": ps.econ.clears_threshold}}

    return {
        "disclaimer": ("This study uses public and authored naturalistic data, "
                       "NOT confidential customer operational data."),
        "manifest_hash": study.manifest["manifest_hash"],
        "coverage": study.manifest["coverage"],
        "combined": agg_row(study.combined.agg),
        "combined_ci": {k: list(v) for k, v in study.combined.ci.items()},
        "length_distribution": study.combined.length_dist,
        "annotation": {"n_annotated": study.review.n_annotated,
                       "agreement_rate": study.review.agreement_rate,
                       "n_disagree": study.review.n_disagree,
                       "n_uncertain": study.review.n_uncertain},
        "economics_combined": {"naive": study.econ.naive_savings_ratio,
                               "cache_adjusted": study.econ.cache_adjusted_savings_ratio,
                               "clears": study.econ.clears_threshold},
        "partitions": {label: part(ps) for label, ps in study.partitions.items()},
        "by_action_type": {a: {"f_critical_union": m.f_critical_union,
                               "oracle_ceiling": m.oracle_ceiling,
                               "deployable_ceiling": m.deployable_ceiling}
                           for a, m in study.combined.by_action.items()},
    }


def render_public_results_md(study: NaturalisticStudy) -> str:
    L, ap = [], None
    out = []
    ap = out.append
    ap("# PUBLIC_CORPUS_RESULTS — Naturalistic ActionGate Span-Ablation\n")
    ap("> **This study uses public (repository-derived) and authored naturalistic "
       "data, NOT confidential customer operational data.** It cannot and does not "
       "emit REAL_CUSTOMER_VALIDATED.\n")
    ap(f"- ActionGate reference: `{adapter.REF_VERSION}`  | manifest: "
       f"`{study.manifest['manifest_hash'][:23]}…`")
    cov = study.manifest["coverage"]
    ap(f"- Corpus: **{cov['n_items']}** contexts "
       f"({cov['by_partition'].get(PUBLIC, 0)} public / "
       f"{cov['by_partition'].get(AUTHORED, 0)} authored), "
       f"**{cov['n_domains']}** domains, **{cov['n_action_types']}** action types, "
       f"**{cov['total_units']}** units, **{cov['total_tokens']}** tokens.\n")

    for label in (PUBLIC, AUTHORED):
        ps = study.partitions[label]
        ap(f"## {label}\n")
        ap(f"**Verdict: `{ps.verdict.verdict}`**  (scientific=False — naturalistic, "
           f"not customer data)\n")
        ap(f"- {ps.verdict.rationale}\n")
        a = ps.report.agg
        ap("| metric | value | 95% CI |")
        ap("|---|---|---|")
        ap(f"| critical-union fraction | {_pct(a.f_critical_union)} | {_ci(ps.report,'f_critical_union')} |")
        ap(f"| decision-critical fraction | {_pct(a.f_decision)} | — |")
        ap(f"| assurance-critical fraction | {_pct(a.f_assurance)} | — |")
        ap(f"| conservative protected fraction | {_pct(a.f_protected)} | — |")
        ap(f"| P0 recall / precision | {_pct(a.recall_p0)} / {_pct(a.precision_p0)} | "
           f"{_ci(ps.report,'recall_p0')} / {_ci(ps.report,'precision_p0')} |")
        ap(f"| oracle ceiling | {_pct(a.oracle_ceiling)} | {_ci(ps.report,'oracle_ceiling')} |")
        ap(f"| deployable ceiling | {_pct(a.deployable_ceiling)} | {_ci(ps.report,'deployable_ceiling')} |")
        ap(f"| extractor instability (all / held-out) | "
           f"{_pct(a.extractor_instability_rate)} / {_pct(ps.report.heldout_instability)} | — |")
        ap(f"| interaction-miss / redundancy-only | {_pct(a.interaction_miss_rate)} / "
           f"{_pct(ps.report.redundancy_only_fraction)} | — |")
        ap(f"| cache-adjusted net savings | {_pct(ps.econ.cache_adjusted_savings_ratio)} | — |\n")

        ap("### By domain (not averaged away)\n")
        ap("| domain | contexts | critical-union | oracle ceiling | deployable ceiling | P0 precision |")
        ap("|---|---|---|---|---|---|")
        for dom, da in sorted(ps.report.by_domain.items()):
            ap(f"| {dom} | {da.n_contexts} | {_pct(da.f_critical_union)} | "
               f"{_pct(da.oracle_ceiling)} | {_pct(da.deployable_ceiling)} | "
               f"{_pct(da.precision_p0)} |")
        ap("")

    ap("## Annotation (two-pass) & context lengths\n")
    r = study.review
    ap(f"- Pass-1 declared vs pass-2 gate-derived agreement: **{_pct(r.agreement_rate)}** "
       f"({r.n_agree if hasattr(r,'n_agree') else '?'} agree / {r.n_disagree} disagree / "
       f"{r.n_uncertain} uncertain over {r.n_annotated} annotated). Disagreements are "
       f"recorded, not resolved.")
    d = study.combined.length_dist
    ap(f"- Context length (tokens): min {d['min']}, p25 {d['p25']:.0f}, median "
       f"{d['median']:.0f}, p75 {d['p75']:.0f}, max {d['max']}, mean {d['mean']:.1f}.\n")

    ap("## By action type (heterogeneity)\n")
    ap("| action type | critical-union | oracle ceiling | deployable ceiling |")
    ap("|---|---|---|---|")
    for act, m in sorted(study.combined.by_action.items()):
        ap(f"| {act} | {_pct(m.f_critical_union)} | {_pct(m.oracle_ceiling)} | "
           f"{_pct(m.deployable_ceiling)} |")
    ap("")
    ap("_Naturalistic corpora may emit corpus-level opportunity verdicts but never "
       "REAL_CUSTOMER_VALIDATED. Real customer operational data is still required for "
       "a production decision._")
    return "\n".join(out)


def write_artifacts(study: NaturalisticStudy, root) -> dict:
    """Write all naturalistic artifacts idempotently. `root` is the experiment dir."""
    import json as _json
    import pathlib
    root = pathlib.Path(root)
    (root / "PUBLIC_CORPUS_RESULTS.md").write_text(render_public_results_md(study) + "\n")
    (root / "results" / "naturalistic_results.json").write_text(
        _json.dumps(to_json(study), indent=2, sort_keys=True) + "\n")
    manifest.write_manifest(
        str(root / "actiongate_context_ablation" / "corpus" / "manifest.json"), study.items)
    # append naturalistic section to RESULTS_RECORD.md, preserving the synthetic part
    rr = root / "results" / "RESULTS_RECORD.md"
    text = rr.read_text()
    marker = "# NATURALISTIC-CORPUS SECTION"
    idx = text.find(marker)
    if idx != -1:
        text = text[:idx].rstrip().rstrip("-").rstrip()
    rr.write_text(text.rstrip() + naturalistic_record_section(study) + "\n")
    return {"manifest_hash": study.manifest["manifest_hash"]}


def naturalistic_record_section(study: NaturalisticStudy) -> str:
    pub = study.partitions[PUBLIC].verdict.verdict
    auth = study.partitions[AUTHORED].verdict.verdict
    a = study.combined.agg
    L = ["\n\n---\n", "# NATURALISTIC-CORPUS SECTION\n",
         "> Public + authored naturalistic data, NOT customer operational data. "
         "The synthetic result above is preserved unchanged.\n",
         f"- Corpus: {a.n_contexts} contexts, {a.total_units} units, "
         f"{a.total_ablations} ablations, {a.total_tokens} tokens.",
         f"- PUBLIC verdict: **`{pub}`** | AUTHORED verdict: **`{auth}`**",
         f"- Combined critical-union {_pct(a.f_critical_union)} "
         f"(CI {_ci(study.combined,'f_critical_union')}); "
         f"deployable ceiling {_pct(a.deployable_ceiling)} "
         f"(CI {_ci(study.combined,'deployable_ceiling')}).",
         f"- P0 recall/precision {_pct(a.recall_p0)}/{_pct(a.precision_p0)}; "
         f"extractor instability {_pct(a.extractor_instability_rate)} "
         f"(held-out {_pct(study.combined.heldout_instability)}).",
         f"- Cache-adjusted net savings {_pct(study.econ.cache_adjusted_savings_ratio)}; "
         f"annotation agreement {_pct(study.review.agreement_rate)}.",
         "- Full detail: `PUBLIC_CORPUS_RESULTS.md`, `results/naturalistic_results.json`, "
         "`corpus/manifest.json`.\n"]
    return "\n".join(L)
