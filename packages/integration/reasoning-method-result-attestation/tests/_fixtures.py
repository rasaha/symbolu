"""Pinned fixtures for the suite. Fixed seeds, fixed instants, no clock, no randomness.

The independent isolated-install probe (``scripts/verify_isolated_install.py``)
does **not** import this module; it re-declares the same literals so a bug in a
shared helper cannot make a probe and a test agree with each other while both
disagree with reality.

Every comparison result here is a SYNTHETIC FIXTURE: it has the exact shape the
engine emits and proves the signing mechanism, never that any method is fit.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ugence_reasoning_method_governance.api import (
    AUTHORITY_RESOLUTION_BASIS_V1,
    COMPARISON_RESULT_SCHEMA_VERSION,
    EVIDENCE_STATUS_SOURCE_V1,
    FIT_SCHEMA_VERSION,
    USAGE_SCOPE_RESEARCH_ONLY,
    FitOutcome,
    ReadinessComparisonResult,
    ReasoningMethodCatalogRef,
    ReasoningMethodFitAssessment,
    ReasoningMethodRef,
    ResourceDimension,
)

import ugence_reasoning_method_result_attestation as ra

#: The comparison engine's identity, as the advisor mirrors it by literal.
ENGINE_ID = "ugence-readiness-comparison"
ENGINE_KEY = "engine-key-1"
ENGINE_VERSION = "0.2.0"
OTHER_ENGINE_ID = "someone-elses-engine"
STRANGER_ID = "stranger-sigma"

ENGINE_SEED = b"\x01" * 32
STRANGER_SEED = b"\x03" * 32

PRODUCED_AT = datetime(2026, 9, 6, 11, 0, 0, tzinfo=timezone.utc)
SIGNED_AT = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
AS_OF = datetime(2026, 9, 6, 12, 5, 0, tzinfo=timezone.utc)
VALID_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
VALID_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
ONE_US = timedelta(microseconds=1)

SET_ID = "comparison-result-anchors"
SET_VERSION = "1"

HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_D = "d" * 64

ENGINE = ra.ComparisonResultAttesterRole.COMPARISON_ENGINE


def catalog_ref(digest: str = HEX_A) -> ReasoningMethodCatalogRef:
    return ReasoningMethodCatalogRef("catalog.synthetic", "1", digest)


def assessment(method_id: str = "map_reduce", *, outcome=FitOutcome.SUFFICIENT_PARETO_EFFICIENT,
               assessment_id: str = "a.1", engine: str = ENGINE_ID, class_digest: str = HEX_B,
               engine_version: str = ENGINE_VERSION):
    cref = catalog_ref()
    return ReasoningMethodFitAssessment(
        FIT_SCHEMA_VERSION, assessment_id, "study.synthetic", class_digest, HEX_D, "",
        ReasoningMethodRef(cref, method_id, "1"), ReasoningMethodRef(cref, "linear_chain", "1"),
        outcome, None, None, (), (), (ResourceDimension.LLM_CALLS,), "pol.cmp", "1", "",
        (), EVIDENCE_STATUS_SOURCE_V1, USAGE_SCOPE_RESEARCH_ONLY, engine, engine_version, PRODUCED_AT,
        "synthetic fixture",
    )


def result(*assessments, engine: str = ENGINE_ID, request_id: str = "cmp.synthetic",
           request_digest: str = HEX_A, produced_at: datetime = PRODUCED_AT,
           engine_version: str = ENGINE_VERSION) -> ReadinessComparisonResult:
    """A hand-built engine result: the SHAPE the engine emits, with synthetic content."""

    if not assessments:
        assessments = (assessment(engine=engine, engine_version=engine_version),)
    ordered = tuple(sorted(assessments, key=lambda a: a.method.sort_key))
    return ReadinessComparisonResult(
        COMPARISON_RESULT_SCHEMA_VERSION, request_id, request_digest, ordered, (), (), (),
        AUTHORITY_RESOLUTION_BASIS_V1, engine, engine_version, produced_at,
    )


def engine_signer(seed: bytes = ENGINE_SEED, **overrides):
    kwargs = dict(signer_identity=ENGINE_ID, signer_key_id=ENGINE_KEY, signer_role=ENGINE)
    kwargs.update(overrides)
    return ra.ReferenceEd25519ComparisonResultSigner(seed, **kwargs)


def anchor_of(signer, **overrides) -> ra.TrustAnchorRecord:
    kwargs = dict(trust_anchor_set_id=SET_ID, trust_anchor_set_version=SET_VERSION,
                  effective_from=VALID_FROM, effective_to=VALID_TO)
    kwargs.update(overrides)
    return signer.trust_anchor(**kwargs)


def directory(*anchors) -> ra.StaticTrustAnchorDirectory:
    return ra.StaticTrustAnchorDirectory(
        list(anchors), trust_anchor_set_id=SET_ID, trust_anchor_set_version=SET_VERSION
    )


def verifier(*anchors, production_mode: bool = False) -> ra.Ed25519ComparisonResultVerifier:
    return ra.Ed25519ComparisonResultVerifier(
        trust_anchor_resolver=directory(*anchors), production_mode=production_mode
    )


def signed(signer=None, res=None, signed_at=SIGNED_AT):
    return ra.sign_comparison_result(
        res if res is not None else result(),
        signer=signer if signer is not None else engine_signer(),
        signed_at=signed_at,
    )


def verify(v, sr, *, role=ENGINE, engine=ENGINE_ID, res=None, as_of=AS_OF, expected_anchor=None):
    return v.verify(
        signed_result=sr,
        expected_role=role,
        expected_engine_identity=engine,
        expected_result=res if res is not None else result(),
        as_of=as_of,
        expected_anchor_record_digest=expected_anchor,
    )
