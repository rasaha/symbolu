"""Robustness corpus (Phase 5) + independent ground truth (Phase 6). Deterministic, synthetic,
no credentials/customer data. Each base item has a TRUE latent state; ground truth is adjudicated
from TWO independent annotator rules (A, B) applied to the TRUE facts — NOT to any gate's logic and
NOT to the observed (noisy) signals. Methods under test see only the OBSERVED SignalBundle, which
equals truth in CLEAN and a perturbed version otherwise.

This is a NEW corpus (not the frozen 343-item AGE dataset). Partitions: CLEAN, CONTROLLED_NOISE,
COMPOUND_FAILURE (>=500 stored cases total). Robustness curves (Phase 12) re-perturb base items
across severities at eval time.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple

from assertion_gate_robustness.perturbations import DETECTABLE, SILENT, apply
from assertion_gate_robustness.signals import EvidenceMeta, Entailment, Grounding, SignalBundle
from assertion_gate_robustness.taxonomy import Disposition as D, more_conservative

DATASET_VERSION = "agr_corpus_v1"
DOMAINS = ["medical", "legal", "financial", "scientific", "cybersecurity",
           "enterprise", "software", "casual"]
HIGH_RISK = {"medical", "legal", "financial", "cybersecurity"}
RELATIONS = ["supports", "supports", "supports", "contradicts", "neutral", "missing", "conflicting"]
SUPPORT_CLAIM = [(0.92, 0.85), (0.80, 0.90), (0.55, 0.95), (0.30, 0.90),
                 (0.70, 0.70), (0.45, 0.88), (0.95, 0.55)]


@dataclass
class BaseItem:
    item_id: str
    domain: str
    risk_class: str
    claim_text: str
    # TRUE latent facts (ground truth is computed from these)
    true_support: float
    true_relation: str
    true_adequacy: float
    claim_strength: float
    true_stale: bool
    # annotations
    annot_A: str
    annot_B: str
    gold: str
    annotator_disagreement: bool
    split: str


# --- independent annotator rules (Phase 6) --------------------------------

def annotator_A(rel: str, support: float, adequacy: float, claim: float, high: bool, stale: bool) -> str:
    """Rule A: relation-and-gap first, adequacy as a modifier."""
    if rel == "contradicts":
        return D.REJECT.value
    if rel == "missing":
        return D.ESCALATE.value if high else D.NOT_SUPPORTED.value
    if rel == "conflicting":
        return D.ESCALATE.value if high else D.INDETERMINATE.value
    if rel == "neutral":
        return D.INDETERMINATE.value
    gap = claim - support
    if adequacy < 0.40 or stale:
        return D.ESCALATE.value if high else D.QUALIFY.value
    if gap <= 0.10:
        return D.ALLOW.value
    if high and gap >= 0.40:
        return D.ESCALATE.value
    return D.QUALIFY.value


def annotator_B(rel: str, support: float, adequacy: float, claim: float, high: bool, stale: bool) -> str:
    """Rule B: adequacy-and-risk first, then relation (different decomposition order)."""
    if adequacy < 0.35:
        return D.ESCALATE.value if high else D.INDETERMINATE.value
    if rel == "contradicts":
        return D.REJECT.value
    if rel == "conflicting":
        return D.ESCALATE.value if high else D.INDETERMINATE.value
    if rel == "missing":
        return D.ESCALATE.value if high else D.NOT_SUPPORTED.value
    if rel == "neutral":
        return D.INDETERMINATE.value
    if stale and high:
        return D.ESCALATE.value
    if support >= claim - 0.10:
        return D.ALLOW.value
    if high and (claim - support) >= 0.40:
        return D.ESCALATE.value
    return D.QUALIFY.value


def _adjudicate(a: str, b: str) -> Tuple[str, bool]:
    if a == b:
        return a, False
    # documented adjudication: take the more conservative (safer) disposition; record disagreement
    return more_conservative(a, b), True


def base_items() -> List[BaseItem]:
    items: List[BaseItem] = []
    idx = 0
    for domain in DOMAINS:
        high = domain in HIGH_RISK
        for rel in RELATIONS:
            for (support, claim) in SUPPORT_CLAIM:
                idx += 1
                risk = ("critical" if idx % 3 == 0 else "high") if high else (
                    "medium" if domain in ("scientific", "enterprise") else "low")
                adequacy = 0.9 if rel in ("supports", "contradicts") else 0.5
                if rel == "missing":
                    adequacy = 0.2
                stale = (idx % 11 == 0)
                a = annotator_A(rel, support, adequacy, claim, risk in ("high", "critical"), stale)
                b = annotator_B(rel, support, adequacy, claim, risk in ("high", "critical"), stale)
                gold, disagree = _adjudicate(a, b)
                split = "dev" if idx % 4 == 0 else "eval"
                items.append(BaseItem(
                    item_id=f"R{idx:03d}", domain=domain, risk_class=risk,
                    claim_text=f"[{domain}] claim", true_support=support, true_relation=rel,
                    true_adequacy=adequacy, claim_strength=claim, true_stale=stale,
                    annot_A=a, annot_B=b, gold=gold, annotator_disagreement=disagree, split=split))
    return items


# --- observed signals (what methods see) ----------------------------------

def clean_bundle(it: BaseItem) -> SignalBundle:
    return SignalBundle(
        grounding=Grounding(support=it.true_support, confidence=1.0, provenance="src"),
        entailment=Entailment(label=it.true_relation if it.true_relation in
                              ("supports", "contradicts", "neutral") else "neutral", confidence=1.0),
        evidence=EvidenceMeta(adequacy=it.true_adequacy,
                              age_days=4000.0 if it.true_stale else 10.0,
                              required_recency_days=365.0,
                              authority="authorized", conflict="major" if it.true_relation == "conflicting"
                              else "none", provenance_present=True),
        risk_class=it.risk_class)


def observed(it: BaseItem, perturbation: str = "clean", severity: float = 0.0) -> SignalBundle:
    return apply(perturbation, clean_bundle(it), severity)


# --- partitions -----------------------------------------------------------

def partitions() -> Dict[str, List[Dict[str, Any]]]:
    items = base_items()
    clean = [{"base": asdict(it), "perturbations": [], "partition": "CLEAN"} for it in items]
    # controlled: one perturbation @0.3, cycling through all types
    all_p = DETECTABLE + SILENT
    controlled = [{"base": asdict(it), "perturbations": [[all_p[i % len(all_p)], 0.3]],
                   "partition": "CONTROLLED_NOISE"} for i, it in enumerate(items)]
    # compound: 2-3 interacting perturbations
    compound = []
    for i, it in enumerate(items):
        combo = [[all_p[i % len(all_p)], 0.3], [all_p[(i + 5) % len(all_p)], 0.2]]
        if i % 2 == 0:
            combo.append([SILENT[i % len(SILENT)], 0.25])
        compound.append({"base": asdict(it), "perturbations": combo, "partition": "COMPOUND_FAILURE"})
    return {"CLEAN": clean, "CONTROLLED_NOISE": controlled, "COMPOUND_FAILURE": compound}


def dump_json(path: str) -> int:
    parts = partitions()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(parts, fh, indent=2, sort_keys=True)
    return sum(len(v) for v in parts.values())


def split(name: str) -> List[BaseItem]:
    return [it for it in base_items() if it.split == name]


def stats() -> Dict[str, Any]:
    from collections import Counter
    items = base_items()
    parts = partitions()
    return {"base_items": len(items), "total_cases": sum(len(v) for v in parts.values()),
            "partitions": {k: len(v) for k, v in parts.items()},
            "dev": sum(1 for i in items if i.split == "dev"),
            "eval": sum(1 for i in items if i.split == "eval"),
            "by_gold": dict(Counter(i.gold for i in items)),
            "annotator_disagreement": sum(1 for i in items if i.annotator_disagreement),
            "disagreement_rate": round(sum(1 for i in items if i.annotator_disagreement) / len(items), 3),
            "high_risk": sum(1 for i in items if i.risk_class in ("high", "critical"))}


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    n = dump_json(os.path.join(here, "data", "v1", "corpus.json"))
    print(f"wrote {n} cases")
    print(json.dumps(stats(), indent=2))
