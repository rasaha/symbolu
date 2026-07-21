"""
Leakage-controlled public loader for TAP-E2.

Exposes the corpus documents/evidence units (public by design — they are the
searchable corpus) and the INPUT projection of queries only (query_id, split,
request_text). Query gold — relevant/partial/distractor units, expected gaps,
conflict/missing flags — is never returned here.
"""

from __future__ import annotations

from typing import Dict, Tuple

from truth_assurance_pipeline.tap_e2_trusted_retrieval.corpus import documents, queries

_BANNED = ("relevant", "partial", "distractors", "expected_gaps",
           "conflict_expected", "missing_evidence", "authoritative_required")


def public_queries(split: str) -> Tuple[Dict[str, object], ...]:
    out = []
    for q in queries.queries_for_split(split):
        pub = q.public_dict()
        for k in _BANNED:
            assert k not in pub, f"leakage: {k} in public query projection"
        out.append(pub)
    return tuple(out)


def public_units() -> Tuple[Dict[str, object], ...]:
    return tuple(u.to_public_dict() for u in documents.units())


def verify_eval_lock() -> bool:
    a = queries.eval_lock()
    b = queries.eval_lock()
    return a == b and a["n_eval"] == len(queries.queries_for_split("eval"))
