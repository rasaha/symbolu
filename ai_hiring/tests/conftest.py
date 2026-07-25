"""Shared fixtures and factories for the AI-hiring foundation tests."""

from __future__ import annotations

import pytest

from ai_hiring import HiringPlatform, build_in_memory_platform
from ai_hiring.domain.enums import (
    CapabilityLayer,
    ConfidenceLevel,
    EvaluationStatus,
)
from ai_hiring.domain.evaluation import (
    CandidateEvaluation,
    EvidenceRef,
    Gap,
    LayerScore,
    ReasonCode,
)
from ai_hiring.policies.decision_boundary import StaticIdentityProvider

HUMAN_ID = "hm-alex"
PANEL = (HUMAN_ID, "domain-expert-1", "hr-partner-1")
AI_ID = "ai-eval-engine"
SERVICE_ID = "svc-ats"
RUBRIC = "rubric-1.0.0"
MODEL = "model-1.0.0"


def make_layer_score(
    layer: CapabilityLayer,
    *,
    score: int = 2,
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
) -> LayerScore:
    """A valid layer score. Score 0 attaches a gap; score > 0 links evidence."""
    if score == 0:
        return LayerScore(
            layer_id=layer,
            score=0,
            confidence=ConfidenceLevel.LOW,
            reason_codes=(ReasonCode(code=f"{layer.name}_NO_EVIDENCE", no_evidence=True),),
            gaps=(Gap(description=f"No evidence submitted for {layer.name}"),),
            rubric_version=RUBRIC,
            model_version=MODEL,
        )
    ref = EvidenceRef(evidence_id=f"ev-{layer.name.lower()}", locator="span:1-10")
    return LayerScore(
        layer_id=layer,
        score=score,
        confidence=confidence,
        reason_codes=(
            ReasonCode(
                code=f"{layer.name}_MET",
                description=f"Evidence supports {layer.name} at level {score}",
                evidence_refs=(ref,),
            ),
        ),
        evidence_links=(ref,),
        rubric_version=RUBRIC,
        model_version=MODEL,
    )


def make_evaluation(
    *,
    evaluation_id: str = "eval-1",
    candidate_id: str = "cand-1",
    role_id: str = "role-1",
    status: EvaluationStatus = EvaluationStatus.EVALUATED,
    default_score: int = 2,
) -> CandidateEvaluation:
    """A complete, valid evaluation carrying all ten capability layers."""
    layer_scores = tuple(
        make_layer_score(layer, score=default_score)
        for layer in CapabilityLayer.ordered()
    )
    return CandidateEvaluation(
        evaluation_id=evaluation_id,
        candidate_id=candidate_id,
        role_id=role_id,
        rubric_version=RUBRIC,
        model_version=MODEL,
        layer_scores=layer_scores,
        status=status,
    )


@pytest.fixture
def identity_provider() -> StaticIdentityProvider:
    idp = StaticIdentityProvider()
    idp.register_human(HUMAN_ID)
    idp.register_human("domain-expert-1")
    idp.register_human("hr-partner-1")
    idp.register_ai(AI_ID)
    idp.register_service(SERVICE_ID)
    return idp


@pytest.fixture
def platform(identity_provider: StaticIdentityProvider) -> HiringPlatform:
    return build_in_memory_platform(identity_provider)
