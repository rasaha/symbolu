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


class ReasonCode(str, Enum):
    """The frozen reason-code taxonomy a future evaluator must draw from."""

    MISSING_REQUIRED_EVIDENCE = "MISSING_REQUIRED_EVIDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    PROHIBITED_EVIDENCE = "PROHIBITED_EVIDENCE"
    QUARANTINED_CONTENT = "QUARANTINED_CONTENT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReasonCodeSpec(DomainModel):
    """Documentation record for one reason code."""

    code: ReasonCode
    summary: str
    description: str
    category: str


REASON_CODE_CATALOG: dict[ReasonCode, ReasonCodeSpec] = {
    ReasonCode.MISSING_REQUIRED_EVIDENCE: ReasonCodeSpec(
        code=ReasonCode.MISSING_REQUIRED_EVIDENCE,
        summary="Required evidence was not provided",
        description="A capability's required evidence type is absent for the candidate.",
        category="evidence"),
    ReasonCode.STALE_EVIDENCE: ReasonCodeSpec(
        code=ReasonCode.STALE_EVIDENCE,
        summary="Evidence is older than the allowed freshness window",
        description="Provided evidence exceeds the capability's freshness limit.",
        category="evidence"),
    ReasonCode.INSUFFICIENT_SAMPLE: ReasonCodeSpec(
        code=ReasonCode.INSUFFICIENT_SAMPLE,
        summary="Not enough evidence to meet the minimum count",
        description="Fewer admissible evidence items than the required minimum.",
        category="evidence"),
    ReasonCode.CONFLICTING_EVIDENCE: ReasonCodeSpec(
        code=ReasonCode.CONFLICTING_EVIDENCE,
        summary="Evidence sources contradict one another",
        description="Two or more sources make incompatible claims for a capability.",
        category="conflict"),
    ReasonCode.PROHIBITED_EVIDENCE: ReasonCodeSpec(
        code=ReasonCode.PROHIBITED_EVIDENCE,
        summary="A prohibited evidence type was supplied",
        description="Evidence of a type the rubric explicitly forbids was present.",
        category="evidence"),
    ReasonCode.QUARANTINED_CONTENT: ReasonCodeSpec(
        code=ReasonCode.QUARANTINED_CONTENT,
        summary="Content was quarantined and withheld",
        description="Evidence content was quarantined (e.g. protected attributes).",
        category="governance"),
    ReasonCode.LOW_CONFIDENCE: ReasonCodeSpec(
        code=ReasonCode.LOW_CONFIDENCE,
        summary="Assessment confidence is low",
        description="A future evaluator expressed low confidence for a capability.",
        category="uncertainty"),
    ReasonCode.NOT_APPLICABLE: ReasonCodeSpec(
        code=ReasonCode.NOT_APPLICABLE,
        summary="Capability is not applicable",
        description="The capability does not apply given the role/context.",
        category="applicability"),
}


def is_known_reason_code(value: str) -> bool:
    return value in ReasonCode._value2member_map_


def get_reason_code_spec(code: ReasonCode) -> ReasonCodeSpec:
    return REASON_CODE_CATALOG[code]
