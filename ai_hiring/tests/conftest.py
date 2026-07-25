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


# --------------------------------------------------------------------------
# Phase 2.5 evidence helpers
# --------------------------------------------------------------------------
import io as _io
import zipfile as _zipfile

from ai_hiring.normalization.models import EvidenceFormat, RawSubmission

SVC = "svc-ats"


def text_sub(text: str, **kw) -> RawSubmission:
    base = dict(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.TEXT, uploader=SVC, filename="f.txt",
    )
    base.update(kw)
    return RawSubmission.from_text(text, **base)


def struct_sub(fields: dict, **kw) -> RawSubmission:
    base = dict(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.STRUCTURED_RESPONSE, uploader=SVC,
    )
    base.update(kw)
    return RawSubmission(fields=fields, **base)


def docx_bytes(text: str) -> bytes:
    doc = (
        '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
        + "".join(f"<w:p><w:r><w:t>{ln}</w:t></w:r></w:p>" for ln in text.split("\n") if ln)
        + "</w:body></w:document>"
    )
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", doc)
    return buf.getvalue()


def zip_bytes(entries: dict[str, bytes], compression=_zipfile.ZIP_DEFLATED) -> bytes:
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w", compression) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


PDF_NATIVE = b"%PDF-1.4\nBT (Hello world native text) Tj ET\n%%EOF"
PDF_EMPTY = b"%PDF-1.4\n%%EOF"
PDF_FLATE = b"%PDF-1.4\n<< /Filter /FlateDecode >>\nstream\n\x78\x9c\nendstream\n%%EOF"
PDF_ENCRYPTED = b"%PDF-1.4\n<< /Encrypt 1 0 R >>\nBT (secret) Tj ET\n%%EOF"


# --------------------------------------------------------------------------
# Phase 3A ontology / rubric helpers
# --------------------------------------------------------------------------
from ai_hiring.ontology import Capability, EvidenceType
from ai_hiring.rubrics import EvidenceRule, Rubric, RubricCapability

AUTHOR = "hm-alex"
APPROVER = "domain-expert-1"
PUBLISHER = "hr-partner-1"


def make_capability(cap_id="cap.python", name="Python", parent_id=None, **kw) -> Capability:
    base = dict(
        capability_id=cap_id, name=name, category="Programming", parent_id=parent_id,
        allowed_evidence_types=(EvidenceType.CODING_TEST, EvidenceType.GITHUB),
        required_evidence_types=(EvidenceType.CODING_TEST,), minimum_evidence_count=1,
    )
    base.update(kw)
    return Capability(**base)


def publish_capability(platform, cap_id="cap.python", **kw) -> Capability:
    return platform.ontology_service.publish(
        make_capability(cap_id=cap_id, **kw), actor_id=AUTHOR)


def make_rubric(cap_id="cap.python", cap_version=1, weight=1.0, rubric_id="rub.be",
                scale="scale.1_5", **kw) -> Rubric:
    rule = EvidenceRule(
        capability_id=cap_id, allowed_types=(EvidenceType.CODING_TEST,),
        required_types=(EvidenceType.CODING_TEST,), prohibited_types=(EvidenceType.PHOTO,),
        minimum_count=1, freshness_days=365)
    rc = RubricCapability(capability_id=cap_id, capability_version=cap_version,
                          weight=weight, scoring_scale_id=scale, evidence_rule=rule)
    base = dict(rubric_id=rubric_id, role="Backend Engineer", version=1,
                capabilities=(rc,), default_scoring_scale_id=scale)
    base.update(kw)
    return Rubric(**base)


def publish_rubric(platform, rubric: Rubric) -> Rubric:
    platform.rubric_service.create(rubric, author_id=AUTHOR)
    platform.rubric_service.submit(rubric.rubric_id, author_id=AUTHOR)
    platform.rubric_service.approve(rubric.rubric_id, approver_id=APPROVER)
    return platform.rubric_service.publish(rubric.rubric_id, publisher_id=PUBLISHER)
