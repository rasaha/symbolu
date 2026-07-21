"""Input validation for the TAP-E3 pipeline (stage 1)."""

from __future__ import annotations

from typing import Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import IntentRecord
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import RetrievalRecord


class InvalidInput(Exception):
    pass


def validate_inputs(intent, retrieval) -> Tuple[bool, Tuple[str, ...]]:
    problems = []
    if not isinstance(intent, IntentRecord):
        problems.append("intent is not an IntentRecord")
    if not isinstance(retrieval, RetrievalRecord):
        problems.append("retrieval is not a RetrievalRecord")
    if isinstance(retrieval, RetrievalRecord):
        for c in retrieval.candidates:
            if not c.provenance.source_id:
                problems.append(f"candidate {c.unit.unit_id} missing upstream provenance")
    return (not problems, tuple(problems))


def require_valid(intent, retrieval) -> None:
    ok, problems = validate_inputs(intent, retrieval)
    if not ok:
        raise InvalidInput("; ".join(problems))
