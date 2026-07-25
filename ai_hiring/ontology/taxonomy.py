"""Frozen controlled vocabularies: evidence types and the reason-code taxonomy.

These are the *constitution*'s vocabulary — the fixed sets that capabilities and
rubrics may reference. A future evaluator may only use codes/types defined here;
it may not invent new ones. Nothing in this module scores or evaluates.
"""

from __future__ import annotations

from enum import Enum

from ..domain.base import DomainModel


class EvidenceType(str, Enum):
    """The controlled vocabulary of evidence *sources* a rubric may reference.

    Distinct from Phase-2 ``EvidenceFormat`` (a file format); this is the kind of
    evidence artifact (resume, portfolio, coding test, ...).
    """

    RESUME = "RESUME"
    PORTFOLIO = "PORTFOLIO"
    GITHUB = "GITHUB"
    CODING_TEST = "CODING_TEST"
    INTERVIEW = "INTERVIEW"
    WORK_SAMPLE = "WORK_SAMPLE"
    STRUCTURED_RESPONSE = "STRUCTURED_RESPONSE"
    ASSESSMENT = "ASSESSMENT"
    CERTIFICATION = "CERTIFICATION"
    TRANSCRIPT = "TRANSCRIPT"
    REFERENCE_LETTER = "REFERENCE_LETTER"
    PHOTO = "PHOTO"


def is_known_evidence_type(value: str) -> bool:
    return value in EvidenceType._value2member_map_


# --- Reason-code vocabulary: extracted to the DGM kernel in Phase 5A ---------
# ``ReasonCode`` and its catalog are domain-neutral governance vocabulary; they
# now live in ``decision_governance.vocabulary`` and are re-exported here so the
# historical ``ai_hiring.ontology.taxonomy`` import path is unchanged.
from decision_governance.vocabulary import (  # noqa: E402,F401
    REASON_CODE_CATALOG,
    ReasonCode,
    ReasonCodeSpec,
    get_reason_code_spec,
    is_known_reason_code,
)
