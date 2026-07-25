"""Domain-contract validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_hiring.domain.decision import Decision, Override
from ai_hiring.domain.enums import (
    ActorType,
    CapabilityLayer,
    ConfidenceLevel,
    Disposition,
    EvaluationStatus,
)
from ai_hiring.domain.evaluation import (
    CandidateEvaluation,
    EvidenceRef,
    LayerScore,
    ReasonCode,
)
from ai_hiring.domain.evidence import NormalizedEvidence
from ai_hiring.domain.recommendation import Recommendation
from ai_hiring.errors import BoundaryViolationError, DomainValidationError

from .conftest import MODEL, PANEL, RUBRIC, make_evaluation, make_layer_score

REJECTED = (ValidationError, DomainValidationError, BoundaryViolationError)


# --- LayerScore ------------------------------------------------------------
def test_score_within_range_is_accepted():
    ls = make_layer_score(CapabilityLayer.EXECUTION, score=4)
    assert ls.score == 4


@pytest.mark.parametrize("bad", [-1, 5, 10])
def test_score_outside_0_4_is_rejected(bad):
    with pytest.raises(REJECTED):
        LayerScore(
            layer_id=CapabilityLayer.EXECUTION,
            score=bad,
            confidence=ConfidenceLevel.HIGH,
            reason_codes=(ReasonCode(code="X", evidence_refs=(EvidenceRef(evidence_id="e1"),)),),
            evidence_links=(EvidenceRef(evidence_id="e1"),),
            rubric_version=RUBRIC,
            model_version=MODEL,
        )


def test_missing_reason_codes_is_rejected():
    with pytest.raises(REJECTED):
        LayerScore(
            layer_id=CapabilityLayer.EXECUTION,
            score=3,
            confidence=ConfidenceLevel.HIGH,
            reason_codes=(),
            evidence_links=(EvidenceRef(evidence_id="e1"),),
            rubric_version=RUBRIC,
            model_version=MODEL,
        )


def test_positive_score_reason_code_requires_evidence_link():
    with pytest.raises(REJECTED):
        LayerScore(
            layer_id=CapabilityLayer.EXECUTION,
            score=3,
            confidence=ConfidenceLevel.HIGH,
            reason_codes=(ReasonCode(code="NO_REFS"),),  # no evidence_refs
            evidence_links=(EvidenceRef(evidence_id="e1"),),
            rubric_version=RUBRIC,
            model_version=MODEL,
        )


def test_zero_score_requires_gap_or_no_evidence_reason():
    # A bare score-0 with an ordinary reason code and no gap is rejected.
    with pytest.raises(REJECTED):
        LayerScore(
            layer_id=CapabilityLayer.EXECUTION,
            score=0,
            confidence=ConfidenceLevel.LOW,
            reason_codes=(ReasonCode(code="SOMETHING"),),
            rubric_version=RUBRIC,
            model_version=MODEL,
        )
    # With a gap it is accepted.
    ok = make_layer_score(CapabilityLayer.EXECUTION, score=0)
    assert ok.score == 0


# --- CandidateEvaluation ---------------------------------------------------
def test_full_evaluation_has_ten_unique_layers():
    ev = make_evaluation()
    assert len(ev.layer_scores) == 10
    assert {ls.layer_id for ls in ev.layer_scores} == set(CapabilityLayer)


def test_evaluation_missing_a_layer_is_rejected():
    nine = tuple(
        make_layer_score(layer) for layer in list(CapabilityLayer)[:9]
    )
    with pytest.raises(REJECTED):
        CandidateEvaluation(
            evaluation_id="e", candidate_id="c", role_id="r",
            rubric_version=RUBRIC, model_version=MODEL, layer_scores=nine,
        )


def test_evaluation_with_duplicate_layer_is_rejected():
    dup = tuple(
        make_layer_score(CapabilityLayer.EXECUTION) for _ in range(10)
    )
    with pytest.raises(REJECTED):
        CandidateEvaluation(
            evaluation_id="e", candidate_id="c", role_id="r",
            rubric_version=RUBRIC, model_version=MODEL, layer_scores=dup,
        )


def test_weighted_summary_is_non_binding():
    ev = make_evaluation()
    assert ev.weighted_summary.binding is False


# --- NormalizedEvidence ----------------------------------------------------
def test_evidence_requires_ids_and_hash():
    with pytest.raises(REJECTED):
        NormalizedEvidence(
            evidence_id="", candidate_id="c", role_id="r",
            content_hash="h", job_relevant=True,
        )
    with pytest.raises(REJECTED):
        NormalizedEvidence(
            evidence_id="e", candidate_id="c", role_id="r",
            content_hash="", job_relevant=True,
        )


def test_evidence_job_relevant_is_explicit():
    # job_relevant has no default; omitting it is a validation error.
    with pytest.raises(ValidationError):
        NormalizedEvidence(
            evidence_id="e", candidate_id="c", role_id="r", content_hash="h",
        )


def test_evidence_is_immutable_and_revision_bumps_version():
    ev = NormalizedEvidence(
        evidence_id="e", candidate_id="c", role_id="r",
        content_hash="h", job_relevant=True,
    )
    with pytest.raises(ValidationError):
        ev.job_relevant = False  # frozen
    revised = ev.revise(content_hash="h2")
    assert revised.version == 2
    assert ev.version == 1  # original untouched
    assert revised.evidence_id == ev.evidence_id


# --- Actor-type invariants -------------------------------------------------
def test_recommendation_must_be_ai():
    with pytest.raises(BoundaryViolationError):
        Recommendation(
            recommendation_id="r", evaluation_id="e",
            suggested_disposition=Disposition.ADVANCE,
            actor_type=ActorType.HUMAN,
        )


def test_decision_cannot_be_constructed_with_ai_actor():
    with pytest.raises(BoundaryViolationError):
        Decision(
            decision_id="d", recommendation_id="r", evaluation_id="e",
            candidate_id="c", role_id="ro", disposition=Disposition.REJECT,
            human_actor_id="hm", panel=("hm",),
            rationale_job_related="insufficient execution evidence",
            actor_type=ActorType.AI,
        )


def test_decision_requires_rationale_and_panel_membership():
    with pytest.raises(REJECTED):  # empty rationale
        Decision(
            decision_id="d", recommendation_id="r", evaluation_id="e",
            candidate_id="c", role_id="ro", disposition=Disposition.ADVANCE,
            human_actor_id="hm", panel=("hm",), rationale_job_related="   ",
        )
    with pytest.raises(REJECTED):  # actor not in panel
        Decision(
            decision_id="d", recommendation_id="r", evaluation_id="e",
            candidate_id="c", role_id="ro", disposition=Disposition.ADVANCE,
            human_actor_id="hm", panel=("someone-else",),
            rationale_job_related="strong across all layers",
        )


def test_override_requires_reason():
    with pytest.raises(REJECTED):
        Override(reason="  ")


def test_capability_layer_numbering():
    assert CapabilityLayer.EXECUTION.layer_number == 1
    assert CapabilityLayer.SYSTEM_AND_STAKEHOLDER_RESPONSIBILITY.layer_number == 10
    assert len(CapabilityLayer.ordered()) == 10


def test_evaluation_status_enum():
    ev = make_evaluation(status=EvaluationStatus.REVIEW_BLOCKED)
    assert ev.is_blocked
