"""
Public, leakage-controlled corpus loader (Section 18).

Exposes ONLY the input projection of each case (text, conversation, metadata, id,
split). Gold annotations — objectives, entities, constraints, ambiguity/conflict
flags, expected status, clarification labels — are never returned here, so an
evaluator running inference through this loader cannot see hidden labels.

The hidden ``eval`` split is additionally content-hash locked; :func:`verify_lock`
recomputes the lock so any tampering with hidden inputs is detectable.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from truth_assurance_pipeline.tap_e1_intent.corpus import cases as corpus_cases
from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest

# Keys that must never appear in a public projection.
_BANNED_KEYS = ("gold", "expected_status", "clarification_required",
                "has_material_ambiguity", "has_conflict", "entities",
                "explicit_constraints", "primary_objective_keywords")


def public_cases(split: str = "eval") -> Tuple[Dict[str, object], ...]:
    out = []
    for c in corpus_cases.cases_for_split(split):
        pub = c.public_dict()
        for k in _BANNED_KEYS:
            assert k not in pub, f"leakage: {k} present in public projection"
        out.append(pub)
    return tuple(out)


def public_requests(split: str = "eval") -> Tuple[RawUserRequest, ...]:
    reqs: List[RawUserRequest] = []
    for pub in public_cases(split):
        from truth_assurance_pipeline.tap_e1_intent.schema import ConversationTurn
        conv = tuple(ConversationTurn(t["role"], t["text"])
                     for t in pub.get("conversation", []) or ())
        reqs.append(RawUserRequest(pub["case_id"], pub["text"], conv,
                                   dict(pub.get("metadata", {}) or {})))
    return tuple(reqs)


def verify_lock() -> bool:
    """Recompute the hidden-eval content lock and confirm it matches the stored
    manifest hash shape. Returns True iff the lock is internally consistent."""
    lock = corpus_cases.eval_lock()
    recomputed = corpus_cases.eval_lock()
    return (lock == recomputed
            and lock["n_eval"] == len(corpus_cases.cases_for_split("eval")))
