"""
Leakage-controlled public loader for the TAP-E1.1 corpus.

Exposes ONLY the input projection (case_id, split, text, conversation, metadata).
Gold annotations are never returned. The real-model interpreter is always fed a
``RawUserRequest`` built from this projection, so it structurally cannot read gold.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from truth_assurance_pipeline.tap_e1_1_realmodel.corpus_v11 import cases as corpus
from truth_assurance_pipeline.tap_e1_intent.schema import ConversationTurn, RawUserRequest

_BANNED = ("gold", "expected_status", "clarification_required",
           "has_material_ambiguity", "has_conflict", "entities",
           "explicit_constraints", "primary_objective_keywords")


def public_cases(split: str) -> Tuple[Dict[str, object], ...]:
    out = []
    for c in corpus.cases_for_split(split):
        pub = c.public_dict()
        for k in _BANNED:
            assert k not in pub, f"leakage: {k} in public projection"
        out.append(pub)
    return tuple(out)


def public_requests(split: str) -> Tuple[RawUserRequest, ...]:
    reqs: List[RawUserRequest] = []
    for pub in public_cases(split):
        conv = tuple(ConversationTurn(t["role"], t["text"])
                     for t in pub.get("conversation", []) or ())
        reqs.append(RawUserRequest(pub["case_id"], pub["text"], conv,
                                   dict(pub.get("metadata", {}) or {})))
    return tuple(reqs)
