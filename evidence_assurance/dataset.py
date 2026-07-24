"""Evidence-provenance corpus (Phase 5) + independent ground truth (Phase 6). Deterministic,
synthetic, no credentials/customer data/live retrieval. Each case carries a TRUE latent state
(is the claim correct? is the evidence genuinely independent? aligned? fresh? authoritative?) and
an OBSERVED metadata view (what a method sees — possibly incomplete or, in ADVERSARIAL_PROVENANCE,
deliberately misleading). Ground truth (expected evidence state) is adjudicated from TWO independent
annotator rubrics on the TRUE latent state — never from EvidenceAssurance rules.

The pivotal design: CLEAN_DEPENDENT (true claim, fake corroboration) and CORRELATED_FAILURE (false
claim, fake corroboration) look IDENTICAL to source-count/diversity — they differ only in whether the
single upstream source is actually correct+aligned. That is what makes provenance+alignment
potentially load-bearing beyond counting.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from evidence_assurance.taxonomy import EvidenceState as ES, more_conservative

DATASET_VERSION = "ea_corpus_v1"
DOMAINS = ["medical", "legal", "financial", "scientific", "cybersecurity", "software",
           "enterprise_policy", "public_policy", "general_fact", "rapidly_changing",
           "jurisdiction_sensitive", "high_risk_reco", "low_risk_descriptive"]
HIGH_RISK = {"medical", "legal", "financial", "cybersecurity", "jurisdiction_sensitive", "high_risk_reco"}
PARTITIONS = ["CLEAN_INDEPENDENT", "CLEAN_DEPENDENT", "CORRELATED_FAILURE", "ADVERSARIAL_PROVENANCE"]


@dataclass
class Case:
    case_id: str
    partition: str
    domain: str
    risk_class: str
    claim: str
    # TRUE latent state (ground-truth world; methods do NOT see these directly)
    true_claim_correct: bool
    true_overstated: bool
    true_n_independent: int          # number of genuinely independent supporting sources
    true_all_derive_from_one: bool   # all evidence derives from a single upstream source
    true_upstream_correct: bool      # is that single upstream source itself correct+aligned?
    true_aligned: bool               # cited passages actually support THIS claim
    true_fresh: bool
    true_authoritative: bool
    true_counterevidence_exists: bool
    correlated_failure_type: Optional[int]   # taxonomy id, or None
    # OBSERVED metadata view (what methods see)
    n_evidence_items: int            # apparent source count (may be inflated by duplication)
    observed_distinct_publishers: int
    observed_distinct_domains: int
    observed_distinct_retrieval_paths: int
    observed_upstream_ids: List[str]        # upstream_source_id per item (None-like => 'primary_k')
    observed_content_hashes: List[str]
    observed_authority_classes: List[str]
    observed_publication_years: List[int]
    observed_passage_aligned: List[bool]    # per-item claimed alignment (may lie in adversarial)
    observed_provenance_confidence: float   # confidence in the metadata itself
    metadata_complete: bool
    # ground truth
    annot_A: str
    annot_B: str
    gold_state: str
    gold_delivery: str               # expected AssertionGate effect
    annotator_disagreement: bool
    split: str
    rationale: str = ""


# ---- independent annotators on the TRUE latent state ----------------------

def _hard_precedence(c: Dict[str, Any]) -> Optional[str]:
    """Safety-critical issues both annotators agree on (shared precedence)."""
    if not c["true_aligned"]:
        return ES.MISALIGNED.value
    if not c["true_claim_correct"] or (c["true_all_derive_from_one"] and not c["true_upstream_correct"]):
        return ES.REJECT_EVIDENCE_STATE.value           # false claim, or correlated on a WRONG source
    if c["true_counterevidence_exists"]:
        return ES.CONFLICTED.value
    if not c["true_authoritative"] and c["risk_class"] in HIGH_RISK:
        return ES.AUTHORITY_MISMATCH.value
    return None


def annotator_A(c: Dict[str, Any]) -> str:
    """Source/provenance rubric. Shared hard precedence, then provenance-first soft tail:
    stale > dependent > insufficient > limitations."""
    hard = _hard_precedence(c)
    if hard:
        return hard
    if not c["true_fresh"]:
        return ES.STALE.value
    if c["true_all_derive_from_one"]:
        return ES.DEPENDENT.value                       # correct upstream, but corroboration is fake
    if c["true_n_independent"] <= 1:
        return ES.INSUFFICIENT.value
    if c["true_overstated"]:
        return ES.VERIFIED_WITH_LIMITATIONS.value
    return ES.VERIFIED.value


def annotator_B(c: Dict[str, Any]) -> str:
    """Claim/evidence-relationship rubric. Shared hard precedence, then claim-first soft tail:
    limitations(overstated) > dependent > stale > insufficient."""
    hard = _hard_precedence(c)
    if hard:
        return hard
    if c["true_overstated"]:
        return ES.VERIFIED_WITH_LIMITATIONS.value
    if c["true_all_derive_from_one"]:
        return ES.DEPENDENT.value
    if not c["true_fresh"]:
        return ES.STALE.value
    if c["true_n_independent"] <= 1:
        return ES.INSUFFICIENT.value
    return ES.VERIFIED.value


def _adjudicate(a: str, b: str):
    if a == b:
        return a, False
    return more_conservative(a, b), True


def _delivery(state: str, risk_class: str) -> str:
    from evidence_assurance.taxonomy import DELIVERY_EFFECT, EvidenceState
    eff = DELIVERY_EFFECT[EvidenceState(state)]
    # high-risk raises soft withholds to ESCALATE
    if risk_class in HIGH_RISK and eff in ("INDETERMINATE", "QUALIFY") and state in (
            ES.INSUFFICIENT.value, ES.DEPENDENT.value, ES.STALE.value):
        return "ESCALATE"
    return eff


def _mk(idx: int, partition: str, domain: str, latent: Dict[str, Any], observed: Dict[str, Any],
        cf_type: Optional[int]) -> Case:
    risk = "critical" if (domain in HIGH_RISK and idx % 3 == 0) else ("high" if domain in HIGH_RISK
            else ("medium" if domain in ("scientific", "enterprise_policy", "public_policy") else "low"))
    c = {"risk_class": risk, **latent}
    a = annotator_A(c); b = annotator_B(c)
    gold, disagree = _adjudicate(a, b)
    split = "dev" if idx % 4 == 0 else "eval"
    return Case(
        case_id=f"EA{idx:04d}", partition=partition, domain=domain, risk_class=risk,
        claim=f"[{domain}] claim {idx}",
        true_claim_correct=latent["true_claim_correct"], true_overstated=latent["true_overstated"],
        true_n_independent=latent["true_n_independent"],
        true_all_derive_from_one=latent["true_all_derive_from_one"],
        true_upstream_correct=latent["true_upstream_correct"], true_aligned=latent["true_aligned"],
        true_fresh=latent["true_fresh"], true_authoritative=latent["true_authoritative"],
        true_counterevidence_exists=latent["true_counterevidence_exists"],
        correlated_failure_type=cf_type,
        annot_A=a, annot_B=b, gold_state=gold, gold_delivery=_delivery(gold, risk),
        annotator_disagreement=disagree, split=split,
        rationale=f"A(prov)={a}; B(claim)={b}; adjudicated={gold}",
        **observed)


def _observed(n, pubs, doms, paths, upstream, hashes, auth, years, aligned, prov_conf, complete):
    return {"n_evidence_items": n, "observed_distinct_publishers": pubs,
            "observed_distinct_domains": doms, "observed_distinct_retrieval_paths": paths,
            "observed_upstream_ids": upstream, "observed_content_hashes": hashes,
            "observed_authority_classes": auth, "observed_publication_years": years,
            "observed_passage_aligned": aligned, "observed_provenance_confidence": prov_conf,
            "metadata_complete": complete}


def _base(**kw):
    d = dict(true_claim_correct=True, true_overstated=False, true_n_independent=3,
             true_all_derive_from_one=False, true_upstream_correct=True, true_aligned=True,
             true_fresh=True, true_authoritative=True, true_counterevidence_exists=False)
    d.update(kw)
    return d


def _templates() -> List[Dict[str, Any]]:
    """Twelve latent templates spanning the vocabulary + inducing genuine A/B disagreement.
    Each: (partition, latent-overrides, cf_type, observed-style)."""
    return [
        # CLEAN_INDEPENDENT family (correct, independent) — spans VERIFIED / limitations / stale / conflicted / misaligned / authority
        {"p": "CLEAN_INDEPENDENT", "l": _base(), "cf": None, "obs": "indep"},
        {"p": "CLEAN_INDEPENDENT", "l": _base(true_overstated=True), "cf": 13, "obs": "indep"},          # VERIFIED_WITH_LIMITATIONS
        {"p": "CLEAN_INDEPENDENT", "l": _base(true_fresh=False), "cf": 8, "obs": "indep_stale"},          # STALE
        {"p": "CLEAN_INDEPENDENT", "l": _base(true_counterevidence_exists=True), "cf": 20, "obs": "indep"},# CONFLICTED
        {"p": "CLEAN_INDEPENDENT", "l": _base(true_aligned=False), "cf": 11, "obs": "indep"},             # MISALIGNED
        {"p": "CLEAN_INDEPENDENT", "l": _base(true_authoritative=False), "cf": 17, "obs": "indep_lowauth"},# AUTHORITY_MISMATCH (high-risk)
        # CLEAN_DEPENDENT family (correct claim, fake corroboration) — DEPENDENT, plus disagreement case
        {"p": "CLEAN_DEPENDENT", "l": _base(true_n_independent=1, true_all_derive_from_one=True), "cf": 4, "obs": "dep_correct"},   # DEPENDENT
        {"p": "CLEAN_DEPENDENT", "l": _base(true_n_independent=1, true_all_derive_from_one=True,
                                            true_counterevidence_exists=True), "cf": 5, "obs": "dep_correct"},  # A=DEPENDENT vs B=CONFLICTED -> disagree
        {"p": "CLEAN_DEPENDENT", "l": _base(true_n_independent=1, true_all_derive_from_one=True,
                                            true_fresh=False), "cf": 29, "obs": "dep_correct_stale"},      # A=STALE vs B=DEPENDENT -> disagree
        # CORRELATED_FAILURE family (false claim on one wrong upstream) — REJECT / misaligned
        {"p": "CORRELATED_FAILURE", "l": _base(true_claim_correct=False, true_overstated=True,
                                               true_n_independent=1, true_all_derive_from_one=True,
                                               true_upstream_correct=False, true_counterevidence_exists=True),
         "cf": 1, "obs": "dep_wrong"},
        {"p": "CORRELATED_FAILURE", "l": _base(true_claim_correct=False, true_n_independent=1,
                                               true_all_derive_from_one=True, true_upstream_correct=False,
                                               true_aligned=False), "cf": 12, "obs": "dep_wrong"},        # MISALIGNED + wrong
        # ADVERSARIAL_PROVENANCE family (false claim disguised as independent, low provenance confidence)
        {"p": "ADVERSARIAL_PROVENANCE", "l": _base(true_claim_correct=False, true_overstated=True,
                                                   true_n_independent=1, true_all_derive_from_one=True,
                                                   true_upstream_correct=False,
                                                   true_counterevidence_exists=True), "cf": 25, "obs": "adversarial"},
    ]


def _obs_for(style: str, n: int, idx: int) -> Dict[str, Any]:
    if style == "indep":
        return _observed(n, n, min(n, 3), min(n, 3), [f"prim_{i}" for i in range(n)],
                         [f"h{idx}_{i}" for i in range(n)], ["reputable"] * n, [2024] * n, [True] * n, 0.95, True)
    if style == "indep_stale":
        return _observed(n, n, min(n, 3), min(n, 3), [f"prim_{i}" for i in range(n)],
                         [f"h{idx}_{i}" for i in range(n)], ["reputable"] * n, [2015] * n, [True] * n, 0.95, True)
    if style == "indep_lowauth":
        return _observed(n, n, min(n, 3), min(n, 3), [f"prim_{i}" for i in range(n)],
                         [f"h{idx}_{i}" for i in range(n)], ["low"] * n, [2024] * n, [True] * n, 0.9, True)
    if style in ("dep_correct", "dep_correct_stale"):
        yr = [2015] * n if style.endswith("stale") else [2024] * n
        return _observed(n, n, min(n, 3), 1, ["up_correct"] * n, [f"h{idx}"] * n,
                         ["reputable"] * n, yr, [True] * n, 0.9, True)
    if style == "dep_wrong":
        return _observed(n, n, min(n, 3), 1, ["up_wrong"] * n, [f"hw{idx}"] * n,
                         ["reputable"] * n, [2024] * n, [True] * n, 0.85, True)
    # adversarial: metadata LIES (distinct publishers/paths/hashes) with low provenance_confidence
    return _observed(n, n, min(n, 3), n, [f"fake_prim_{i}" for i in range(n)],
                     [f"ha{idx}_{i}" for i in range(n)], ["reputable"] * n, [2024] * n, [True] * n, 0.4, False)


def all_cases() -> List[Case]:
    cases: List[Case] = []
    idx = 0
    templates = _templates()
    for domain in DOMAINS:
        for size in (0, 1, 2, 3):          # 4 size variants x 12 templates x 13 domains = 624
            for t in templates:
                idx += 1
                n = 3 + size + (2 if t["p"] in ("CLEAN_DEPENDENT", "CORRELATED_FAILURE",
                                                "ADVERSARIAL_PROVENANCE") else 0)
                obs = _obs_for(t["obs"], n, idx)
                cases.append(_mk(idx, t["p"], domain, dict(t["l"]), obs, t["cf"]))
    return cases


def split(name: str) -> List[Case]:
    return [c for c in all_cases() if c.split == name]


def dump_json(path: str) -> int:
    cs = all_cases()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([asdict(c) for c in cs], fh, indent=2, sort_keys=True)
    return len(cs)


def stats() -> Dict[str, Any]:
    from collections import Counter
    cs = all_cases()
    return {"total": len(cs), "dev": sum(1 for c in cs if c.split == "dev"),
            "eval": sum(1 for c in cs if c.split == "eval"),
            "by_partition": dict(Counter(c.partition for c in cs)),
            "by_gold": dict(Counter(c.gold_state for c in cs)),
            "by_domain": dict(Counter(c.domain for c in cs)),
            "annotator_disagreement": sum(1 for c in cs if c.annotator_disagreement),
            "disagreement_rate": round(sum(1 for c in cs if c.annotator_disagreement) / len(cs), 3),
            "high_risk": sum(1 for c in cs if c.risk_class in ("high", "critical"))}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    n = dump_json(os.path.join(here, "data", "v1", "corpus.json"))
    print(f"wrote {n} cases")
    print(json.dumps(stats(), indent=2))
