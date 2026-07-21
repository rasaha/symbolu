"""
Leakage-controlled public loader for TAP-E3.

Exposes only the input projection of each case (case_id, split, request_text, and the
public evidence-unit texts). Relationship gold — gold_relationships, expected_conflicts,
expected_gaps, dimensions — is never returned here.
"""

from __future__ import annotations

from typing import Dict, Tuple

from truth_assurance_pipeline.tap_e3_relationship_truth.corpus import cases as corpus

_BANNED = ("gold", "expected_conflicts", "expected_gaps", "acceptable_predicates",
           "polarity", "modality", "temporality")


def public_cases(split: str) -> Tuple[Dict[str, object], ...]:
    out = []
    for c in corpus.cases_for_split(split):
        pub = c.public_dict()
        for k in _BANNED:
            assert k not in pub, f"leakage: {k} in public projection"
        out.append(pub)
    return tuple(out)


def verify_eval_lock() -> bool:
    a = corpus.eval_lock()
    b = corpus.eval_lock()
    return a == b and a["n_eval"] == len(corpus.cases_for_split("eval"))
