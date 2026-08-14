"""GV-2E-a — neutral evidence contracts: structural invariants & determinism.

These tests prove the contracts *structurally reject* inconsistent combinations
before a record is admitted, that the five evidence axes are orthogonal, and
that caller-selected enum values alone never satisfy the attestation /
attribution / verification structural requirements. They assert no cryptographic
or organizational verification — only structure.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta, timezone

import pytest

import ugence_governance_contracts as g
from ugence_governance_contracts import api
from ugence_governance_contracts.contracts.evidence import (
    AssessmentWindow,
    AttestationStatus,
    AttributionStatus,
    BenchmarkReference,
    ConfidenceBasis,
    EvidenceContractError,
    EvidenceProvenance,
    EvidenceReference,
    EvidenceUsageScope,
    ForecastHorizon,
    MetricClaim,
    MetricObservation,
    PopulationSlice,
    SourceBasis,
    TransformationMethod,
    VerificationStatus,
)

DIGEST = "a" * 64
_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _window():
    return AssessmentWindow(start=_T0, end=_T0 + timedelta(days=30))


def _horizon():
    return ForecastHorizon(as_of=_T0, horizon_end=_T0 + timedelta(days=90))


def _evref(eid="e1", tenant="t1", subject="s1"):
    return EvidenceReference(
        evidence_id=eid, tenant_id=tenant, subject_id=subject,
        evidence_kind="measurement", content_digest=DIGEST,
    )


def _base(**kw):
    d = dict(
        claim_id="c1", tenant_id="t1", subject_id="s1", metric_id="accuracy",
        value="0.97", governed_unit="ratio",
        source_basis=SourceBasis.REPORTED, transformation_method=TransformationMethod.DIRECT,
    )
    d.update(kw)
    return MetricClaim(**d)


# --------------------------------------------------------------------------- #
# Enums & public surface
# --------------------------------------------------------------------------- #
def test_enum_values_serialize_deterministically():
    assert [m.value for m in SourceBasis] == ["REPORTED", "OBSERVED", "SYNTHETIC", "MIXED"]
    assert [m.value for m in TransformationMethod] == ["DIRECT", "CALCULATED", "MODELED"]
    assert [m.value for m in AttestationStatus] == ["UNATTESTED", "ATTESTED"]
    assert [m.value for m in AttributionStatus] == [
        "NOT_APPLICABLE", "NOT_ATTRIBUTED", "PARTIALLY_ATTRIBUTED", "ATTRIBUTED"]
    assert [m.value for m in VerificationStatus] == [
        "UNVERIFIED", "VERIFICATION_FAILED", "VERIFIED"]
    # str-Enum serializes as its stable value.
    assert json.dumps(SourceBasis.OBSERVED) == '"OBSERVED"'


def test_public_evidence_symbols_exported():
    for name in ("SourceBasis", "TransformationMethod", "AttestationStatus",
                 "AttributionStatus", "VerificationStatus", "EvidenceUsageScope",
                 "EvidenceContractError", "EvidenceReference", "EvidenceProvenance",
                 "BenchmarkReference", "AssessmentWindow", "ForecastHorizon",
                 "PopulationSlice", "ConfidenceBasis", "MetricClaim", "MetricObservation"):
        assert hasattr(api, name) and hasattr(g, name), name
        assert getattr(api, name) is getattr(g, name)


# --------------------------------------------------------------------------- #
# Valid constructions
# --------------------------------------------------------------------------- #
def test_valid_direct_reported_claim():
    c = _base()
    assert c.source_basis is SourceBasis.REPORTED
    assert c.attestation_status is AttestationStatus.UNATTESTED
    assert c.attribution_status is AttributionStatus.NOT_APPLICABLE
    assert c.verification_status is VerificationStatus.UNVERIFIED


def test_valid_direct_observed_metric_observation():
    o = MetricObservation(
        observation_id="o1", tenant_id="t1", subject_id="s1", metric_id="latency",
        value="123", governed_unit="ms", assessment_window=_window(), evidence_refs=("e1",),
    )
    claim = o.to_metric_claim()
    assert claim.source_basis is SourceBasis.OBSERVED
    # does not auto-elevate
    assert claim.attestation_status is AttestationStatus.UNATTESTED
    assert claim.attribution_status is AttributionStatus.NOT_APPLICABLE
    assert claim.verification_status is VerificationStatus.UNVERIFIED


def test_valid_calculated_claim_with_input_evidence():
    c = _base(transformation_method=TransformationMethod.CALCULATED,
              input_evidence_refs=("e1", "e2"), calculation_ref="calc://v1")
    assert c.transformation_method is TransformationMethod.CALCULATED


def test_valid_modeled_forecast():
    c = _base(transformation_method=TransformationMethod.MODELED,
              input_evidence_refs=("e1",), model_ref="model://v3", forecast_horizon=_horizon())
    assert c.forecast_horizon is not None


def test_valid_retrospective_modeled_over_observed_inputs():
    # ADR: a model-based estimate over measured inputs = (OBSERVED, MODELED) + window.
    c = _base(source_basis=SourceBasis.OBSERVED,
              transformation_method=TransformationMethod.MODELED,
              input_evidence_refs=("e1",), model_ref="m://1", assessment_window=_window())
    assert c.source_basis is SourceBasis.OBSERVED


def test_valid_attested_attributed_verified_positive():
    c = _base(
        source_basis=SourceBasis.OBSERVED, assessment_window=_window(),
        attestation_status=AttestationStatus.ATTESTED, attestation_ref="att://1", attester_identity="authority://a",
        attribution_status=AttributionStatus.ATTRIBUTED, attribution_ref="attr://1",
        counterfactual_ref="cf://1", causal_method_ref="cm://1",
        verification_status=VerificationStatus.VERIFIED, verification_ref="ver://1",
        verifier_identity="verifier://v", verified_at=_T0, verified_claim_ref="claim://exact",
    )
    assert c.verification_status is VerificationStatus.VERIFIED


# --------------------------------------------------------------------------- #
# Transformation-method rejections
# --------------------------------------------------------------------------- #
def test_calculated_without_input_evidence_rejected():
    with pytest.raises(EvidenceContractError):
        _base(transformation_method=TransformationMethod.CALCULATED, calculation_ref="c://1")


def test_calculated_without_calculation_ref_rejected():
    with pytest.raises(EvidenceContractError):
        _base(transformation_method=TransformationMethod.CALCULATED, input_evidence_refs=("e1",))


def test_modeled_without_model_reference_rejected():
    with pytest.raises(EvidenceContractError):
        _base(transformation_method=TransformationMethod.MODELED,
              input_evidence_refs=("e1",), forecast_horizon=_horizon())


def test_direct_with_calculation_or_model_ref_rejected():
    with pytest.raises(EvidenceContractError):
        _base(calculation_ref="c://1")
    with pytest.raises(EvidenceContractError):
        _base(model_ref="m://1")


# --------------------------------------------------------------------------- #
# Source-basis rejections
# --------------------------------------------------------------------------- #
def test_observed_claim_with_forecast_horizon_rejected():
    with pytest.raises(EvidenceContractError):
        _base(source_basis=SourceBasis.OBSERVED, forecast_horizon=_horizon())


def test_metric_observation_without_assessment_window_rejected():
    with pytest.raises(EvidenceContractError):
        MetricObservation(observation_id="o1", tenant_id="t1", subject_id="s1",
                          metric_id="m", value="1", governed_unit="u", evidence_refs=("e1",))


def test_metric_observation_cannot_be_modeled():
    with pytest.raises(EvidenceContractError):
        MetricObservation(observation_id="o1", tenant_id="t1", subject_id="s1",
                          metric_id="m", value="1", governed_unit="u",
                          assessment_window=_window(), evidence_refs=("e1",),
                          transformation_method=TransformationMethod.MODELED)


def test_mixed_requires_at_least_two_inputs():
    with pytest.raises(EvidenceContractError):
        _base(source_basis=SourceBasis.MIXED, input_evidence_refs=("e1",))
    # valid with two distinguishable inputs
    c = _base(source_basis=SourceBasis.MIXED, input_evidence_refs=("e1", "e2"))
    assert c.source_basis is SourceBasis.MIXED


# --------------------------------------------------------------------------- #
# Attestation / attribution / verification structural rejections
# --------------------------------------------------------------------------- #
def test_attested_without_attestation_reference_rejected():
    with pytest.raises(EvidenceContractError):
        _base(attestation_status=AttestationStatus.ATTESTED, attester_identity="a")


def test_verified_without_exact_claim_reference_rejected():
    with pytest.raises(EvidenceContractError):
        _base(verification_status=VerificationStatus.VERIFIED,
              verification_ref="v://1", verifier_identity="v", verified_at=_T0)


def test_verified_without_verification_assessment_rejected():
    with pytest.raises(EvidenceContractError):
        _base(verification_status=VerificationStatus.VERIFIED,
              verified_claim_ref="claim://x", verifier_identity="v", verified_at=_T0)


def test_verification_failed_without_verification_evidence_rejected():
    with pytest.raises(EvidenceContractError):
        _base(verification_status=VerificationStatus.VERIFICATION_FAILED,
              verified_claim_ref="claim://x", verifier_identity="v", verified_at=_T0)


def test_attributed_without_counterfactual_rejected():
    with pytest.raises(EvidenceContractError):
        _base(attribution_status=AttributionStatus.ATTRIBUTED,
              attribution_ref="a://1", causal_method_ref="cm://1")


def test_attributed_without_causal_method_rejected():
    with pytest.raises(EvidenceContractError):
        _base(attribution_status=AttributionStatus.ATTRIBUTED,
              attribution_ref="a://1", counterfactual_ref="cf://1")


# --------------------------------------------------------------------------- #
# Orthogonality
# --------------------------------------------------------------------------- #
def test_verified_and_not_attributed_remains_valid():
    c = _base(
        source_basis=SourceBasis.OBSERVED, assessment_window=_window(),
        verification_status=VerificationStatus.VERIFIED, verification_ref="v://1",
        verifier_identity="v", verified_at=_T0, verified_claim_ref="claim://x",
        attribution_status=AttributionStatus.NOT_ATTRIBUTED,
    )
    assert c.verification_status is VerificationStatus.VERIFIED
    assert c.attribution_status is AttributionStatus.NOT_ATTRIBUTED


def test_attested_reported_does_not_become_observed():
    c = _base(attestation_status=AttestationStatus.ATTESTED,
              attestation_ref="att://1", attester_identity="authority://a")
    # attestation signed provenance; the source basis is unchanged.
    assert c.attestation_status is AttestationStatus.ATTESTED
    assert c.source_basis is SourceBasis.REPORTED


def test_caller_labels_alone_cannot_satisfy_structural_requirements():
    # Selecting the strongest enum value with no supporting references is rejected.
    with pytest.raises(EvidenceContractError):
        _base(attestation_status=AttestationStatus.ATTESTED)
    with pytest.raises(EvidenceContractError):
        _base(attribution_status=AttributionStatus.ATTRIBUTED)
    with pytest.raises(EvidenceContractError):
        _base(verification_status=VerificationStatus.VERIFIED)


# --------------------------------------------------------------------------- #
# References, tenancy, digests, time
# --------------------------------------------------------------------------- #
def test_duplicate_input_references_rejected():
    with pytest.raises(EvidenceContractError):
        _base(transformation_method=TransformationMethod.CALCULATED,
              calculation_ref="c://1", input_evidence_refs=("e1", "e1"))


def test_cross_tenant_evidence_mixing_rejected():
    with pytest.raises(EvidenceContractError):
        MetricClaim.from_evidence(
            claim_id="c1", tenant_id="t1", subject_id="s1", metric_id="m",
            value="1", governed_unit="u", source_basis=SourceBasis.REPORTED,
            transformation_method=TransformationMethod.DIRECT,
            evidence=(_evref(eid="e1", tenant="t2", subject="s1"),),
        )


def test_cross_subject_evidence_mixing_rejected():
    with pytest.raises(EvidenceContractError):
        MetricClaim.from_evidence(
            claim_id="c1", tenant_id="t1", subject_id="s1", metric_id="m",
            value="1", governed_unit="u", source_basis=SourceBasis.REPORTED,
            transformation_method=TransformationMethod.DIRECT,
            evidence=(_evref(eid="e1", tenant="t1", subject="s2"),),
        )


def test_from_evidence_same_binding_valid():
    c = MetricClaim.from_evidence(
        claim_id="c1", tenant_id="t1", subject_id="s1", metric_id="m",
        value="1", governed_unit="u", source_basis=SourceBasis.REPORTED,
        transformation_method=TransformationMethod.DIRECT,
        evidence=(_evref("e1"), _evref("e2")),
    )
    assert c.evidence_refs == ("e1", "e2")


def test_malformed_digest_rejected():
    with pytest.raises(EvidenceContractError):
        _base(content_digest="not-a-digest")
    with pytest.raises(EvidenceContractError):
        EvidenceReference(evidence_id="e", tenant_id="t", subject_id="s",
                          evidence_kind="k", content_digest="zz")


def test_invalid_time_window_rejected():
    with pytest.raises(EvidenceContractError):
        AssessmentWindow(start=_T0 + timedelta(days=1), end=_T0)
    with pytest.raises(EvidenceContractError):
        ForecastHorizon(as_of=_T0 + timedelta(days=1), horizon_end=_T0)


def test_naive_datetime_rejected():
    with pytest.raises(EvidenceContractError):
        AssessmentWindow(start=datetime(2026, 1, 1), end=datetime(2026, 2, 1))


def test_empty_identity_rejected():
    with pytest.raises(EvidenceContractError):
        _base(claim_id="")
    with pytest.raises(EvidenceContractError):
        _base(tenant_id="  ")


# --------------------------------------------------------------------------- #
# Synthetic-evidence restrictions
# --------------------------------------------------------------------------- #
def _synthetic(**kw):
    d = dict(source_basis=SourceBasis.SYNTHETIC,
             usage_scope=EvidenceUsageScope.EVALUATION_ONLY,
             evidence_refs=("dataset://1",), content_digest=DIGEST)
    d.update(kw)
    return _base(**d)


def test_valid_synthetic_evaluation_only():
    c = _synthetic()
    assert c.source_basis is SourceBasis.SYNTHETIC
    assert c.usage_scope is EvidenceUsageScope.EVALUATION_ONLY


def test_synthetic_without_evaluation_only_rejected():
    with pytest.raises(EvidenceContractError):
        _synthetic(usage_scope=EvidenceUsageScope.GENERAL)


def test_synthetic_attempting_verified_realized_use_rejected():
    with pytest.raises(EvidenceContractError):
        _synthetic(verification_status=VerificationStatus.VERIFIED,
                   verification_ref="v://1", verifier_identity="v",
                   verified_at=_T0, verified_claim_ref="claim://x")


def test_synthetic_cannot_be_attributed():
    with pytest.raises(EvidenceContractError):
        _synthetic(attribution_status=AttributionStatus.ATTRIBUTED,
                   attribution_ref="a://1", counterfactual_ref="cf://1", causal_method_ref="cm://1")


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_deterministic_construction_identical_canonical_digest():
    a = _base(evidence_refs=("e1", "e2"))
    b = _base(evidence_refs=("e1", "e2"))
    assert a == b
    assert a.canonical_digest() == b.canonical_digest()
    assert dataclasses.asdict(a) == dataclasses.asdict(b)
    # digest is a stable sha-256 hex
    assert len(a.canonical_digest()) == 64


def test_reference_and_support_types_validate():
    assert PopulationSlice(population_id="p1", size=100).population_id == "p1"
    with pytest.raises(EvidenceContractError):
        PopulationSlice(population_id="p1", size=-1)
    assert ConfidenceBasis(method="bootstrap", sample_size=1000).method == "bootstrap"
    assert BenchmarkReference(benchmark_id="b", version="1", content_digest=DIGEST).version == "1"
    with pytest.raises(EvidenceContractError):
        BenchmarkReference(benchmark_id="b", version="1", content_digest="bad")
    assert EvidenceProvenance(source_identity="src://1", source_type="OBSERVED").source_type == "OBSERVED"
