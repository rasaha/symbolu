"""Atomicity & completeness (Phase 12). Classifies a decomposition as over-split, under-split, or
correct against gold - and, crucially, against the per-claim-type atomicity policy (taxonomy):
maximum splitting is NOT optimal. Deterministic.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .taxonomy import ATOMICITY_POLICY


def classify_count(produced_n: int, gold_n: int, acceptable_ns=()) -> str:
    if produced_n in acceptable_ns or produced_n == gold_n:
        return "atomic_ok"
    return "over_split" if produced_n > gold_n else "under_split"


def type_expectation(claim_type: str) -> str:
    """What the claim TYPE says about splitting: atomic|preserve|split|chain|no_extract."""
    return ATOMICITY_POLICY.get(claim_type, "atomic")


def assess(example: Dict[str, Any], produced: List[str]) -> Dict[str, Any]:
    gold_n = example["expected_claim_count"]
    acceptable = {len(d) for d in example.get("acceptable_decompositions", [])}
    verdict = classify_count(len(produced), gold_n, acceptable)
    # a 'preserve' or 'no_extract' gold type that got split is a policy violation even if count matches
    gold_types = [g["claim_type"] for g in example["gold_claims"]]
    preserve_violation = any(type_expectation(t) in ("preserve", "no_extract")
                             for t in gold_types) and len(produced) > gold_n
    return {
        "verdict": verdict,
        "produced_n": len(produced),
        "gold_n": gold_n,
        "preserve_policy_violation": preserve_violation,
    }
