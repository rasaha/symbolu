"""
Deterministic experiment runner + hidden lock.

Runs V0..V4 over the synthetic corpus, computes paired metrics vs the V0 baseline,
and returns one fully-deterministic result dict. Two invocations return identical
output (REPRODUCIBILITY_REPORT.md).

The "hidden lock" hashes the frozen components (judge rules, deterministic rules,
schema, thresholds) and the corpus so a downstream re-run can prove zero drift.
There is NO prior lock in this repository to verify against; the lock is created
here for this new track.
"""

from __future__ import annotations

import inspect
from typing import Dict, Mapping

from relationship_claim_validation import corpus, deterministic, judges, metrics
from relationship_claim_validation.model import GoldLabel, stable_hash
from relationship_claim_validation.validator import (
    ABLATIONS, ClaimValidationLayer,
)


def run_all() -> Dict[str, object]:
    docs = corpus.documents()
    claims = corpus.claims()
    gold: Mapping[str, GoldLabel] = corpus.gold()

    per_ablation: Dict[str, object] = {}
    records_by_ablation: Dict[str, Dict] = {}
    for cfg in ABLATIONS:
        layer = ClaimValidationLayer(cfg, docs)
        recs = {r.relationship_id: r for r in layer.validate_corpus(claims)}
        records_by_ablation[cfg.name] = recs
        conf = metrics.confusion(recs, gold)
        per_ablation[cfg.name] = {
            "description": cfg.description,
            "confusion": {"tp": conf.tp, "fp": conf.fp, "tn": conf.tn, "fn": conf.fn},
            "precision": conf.precision,
            "recall": conf.recall,
            "status_accuracy": metrics.status_accuracy(recs, gold),
            "n_retained": sum(1 for r in recs.values()
                              if r.recommended_action.value in ("retain", "narrow")),
            "n_deterministic_removed": sum(1 for r in recs.values()
                                           if r.deterministic_removed),
            "n_adjudicated": sum(1 for r in recs.values() if r.adjudicated),
        }

    baseline = records_by_ablation["V0"]
    paired: Dict[str, object] = {}
    for name, recs in records_by_ablation.items():
        if name == "V0":
            continue
        p = metrics.paired_vs_baseline(recs, baseline, gold)
        lo, hi = metrics.bootstrap_ci_net_fix_rate(recs, baseline, gold)
        p["net_fix_rate_ci95"] = [lo, hi]
        paired[name] = p

    # status-distribution per ablation (for the results tables)
    status_dist: Dict[str, Dict[str, int]] = {}
    for name, recs in records_by_ablation.items():
        dd: Dict[str, int] = {}
        for r in recs.values():
            dd[r.validation_status.value] = dd.get(r.validation_status.value, 0) + 1
        status_dist[name] = dd

    return {
        "n_claims": len(claims),
        "n_documents": len(docs),
        "gold_distribution": _gold_dist(gold),
        "per_ablation": per_ablation,
        "paired_vs_V0": paired,
        "status_distribution": status_dist,
        "hidden_lock": hidden_lock(),
    }


def _gold_dist(gold: Mapping[str, GoldLabel]) -> Dict[str, int]:
    dd: Dict[str, int] = {}
    for g in gold.values():
        dd[g.gold_status.value] = dd.get(g.gold_status.value, 0) + 1
    return dd


def hidden_lock() -> Dict[str, str]:
    """Content hashes of the frozen components + corpus (public projection only)."""
    frozen_source = {
        "deterministic_rules": inspect.getsource(deterministic),
        "judge_rules": inspect.getsource(judges),
        "legal_types": sorted(deterministic.LEGAL_RELATIONSHIP_TYPES),
        "bootstrap": {"seed": metrics.BOOTSTRAP_SEED, "n": metrics.BOOTSTRAP_N},
    }
    return {
        "frozen_components_hash": stable_hash(frozen_source),
        "corpus_public_hash": stable_hash(corpus.public_claims()),
        "documents_hash": stable_hash({
            d: [(s.span_id, s.text, dict(s.assertions)) for s in doc.spans]
            for d, doc in corpus.documents().items()}),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_all(), indent=2, sort_keys=True))
