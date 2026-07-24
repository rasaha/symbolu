"""Ambiguity handling (Phase 20). Real text often permits multiple valid decompositions. This module
decides whether to commit to one, emit alternates, defer splitting, or abstain - rather than forcing
false precision. Deterministic.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .taxonomy import Disposition


def policy(example: Dict[str, Any], produced_n: int) -> str:
    """Decide the ambiguity disposition for a decomposition given the example's acceptable set."""
    acceptable_ns = {len(d) for d in example.get("acceptable_decompositions", [])}
    gold_n = example["expected_claim_count"]
    disagreed = example.get("annotator_disagreement", False)

    if disagreed and len(acceptable_ns) > 1:
        # annotators accepted more than one granularity -> alternates are valid, not error
        return Disposition.VALID_WITH_ALTERNATIVES.value
    if produced_n in acceptable_ns or produced_n == gold_n:
        return Disposition.VALID.value
    # a borderline conjunction / dependency the method resolved differently but not clearly wrong
    if abs(produced_n - gold_n) == 1 and example["partition"] in ("MULTI_CLAIM", "CROSS_SENTENCE"):
        return Disposition.AMBIGUOUS.value
    return Disposition.INDETERMINATE.value


def prefer_preserve_over_false_precision(example: Dict[str, Any]) -> bool:
    """True when preserving the whole unit is safer than committing to a contested split - i.e. an
    exception/condition spans a conjunction (splitting risks detaching scope)."""
    text = example["original_text"].lower()
    return (" unless " in text or " except " in text) and (" and " in text or " but " in text)
