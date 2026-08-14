"""Structural-invariant tests for the UVI policy & assessment-context contracts.

These assert *structure* only: constructors accept well-formed artifacts and
reject malformed ones. They never assert that any policy was approved, signed,
resolved, or trust-verified — that is Policy-Authority work, out of scope.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from ugence_governance_contracts.api import (
    AttributionStatus,
    BenchmarkReference,
    SourceBasis,
    VerificationStatus,
)
from ugence_uvi_policy_contracts.api import (
    AssessmentContext,
    AssessmentPurpose,
    ComparisonOperator,
    ComponentEvidenceRequirement,
    DomainPolicy,
    GateCategory,
    GeographyPolicy,
    GovernedThreshold,
    HeadlineClassificationPolicy,
    IntendedOutcomePolicy,
    MissingComponentBehavior,
    PolicyArtifactMetadata,
    PolicyContractError,
    PolicyFamily,
    PolicyGate,
    PolicyLifecycleState,
    PolicyReference,
    PolicyScope,
    ReadinessPolicy,
    ReadinessTarget,
    RequirementClass,
    ValuationPolicy,
    ValueComponent,
)

DIGEST = hashlib.sha256(b"content").hexdigest()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2027, 1, 1, tzinfo=timezone.utc)
MID = datetime(2026, 6, 1, tzinfo=timezone.utc)


def meta(
    family: PolicyFamily,
    pid: str,
    *,
    scope: PolicyScope = PolicyScope.GLOBAL,
    tenant: str = "",
    life: PolicyLifecycleState = PolicyLifecycleState.APPROVED_ACTIVE,
    eff_from=T0,
    eff_to=T1,
) -> PolicyArtifactMetadata:
    return PolicyArtifactMetadata(
        policy_id=pid,
        policy_family=family,
        version="1.0.0",
        content_digest=DIGEST,
        scope=scope,
        tenant_id=tenant,
        lifecycle_state=life,
        effective_from=eff_from,
        effective_to=eff_to,
    )


def geo(**kw) -> GeographyPolicy:
    return GeographyPolicy(
        metadata=meta(PolicyFamily.GEOGRAPHY, kw.pop("pid", "geo-1"), **kw.pop("m", {})),
        jurisdiction="US-CA",
        reporting_currency="USD",
        functional_currency="USD",
        **kw,
    )


def dom(**kw) -> DomainPolicy:
    return DomainPolicy(
        metadata=meta(PolicyFamily.DOMAIN, kw.pop("pid", "dom-1"), **kw.pop("m", {})),
        governed_outcome_unit="resolved_ticket",
        **kw,
    )


def io(**kw) -> IntendedOutcomePolicy:
    return IntendedOutcomePolicy(
        metadata=meta(PolicyFamily.INTENDED_OUTCOME, kw.pop("pid", "io-1"), **kw.pop("m", {})),
        target_outcome="resolve ticket",
        task_definition="handle a support ticket end to end",
        **kw,
    )


# --------------------------------------------------------------------------- #
# Identity / references
# --------------------------------------------------------------------------- #
def test_policy_reference_requires_content_digest():
    with pytest.raises(PolicyContractError):
        PolicyReference(policy_id="p", policy_family=PolicyFamily.DOMAIN, version="1", content_digest="")


def test_policy_reference_rejects_bad_digest():
    with pytest.raises(PolicyContractError):
        PolicyReference(policy_id="p", policy_family=PolicyFamily.DOMAIN, version="1", content_digest="NOTHEX")


def test_global_scope_forbids_tenant_id():
    with pytest.raises(PolicyContractError):
        PolicyReference(
            policy_id="p", policy_family=PolicyFamily.DOMAIN, version="1",
            content_digest=DIGEST, scope=PolicyScope.GLOBAL, tenant_id="t1",
        )


def test_tenant_scope_requires_tenant_id():
    with pytest.raises(PolicyContractError):
        PolicyReference(
            policy_id="p", policy_family=PolicyFamily.DOMAIN, version="1",
            content_digest=DIGEST, scope=PolicyScope.TENANT, tenant_id="",
        )


def test_metadata_effective_period_ordering():
    with pytest.raises(PolicyContractError):
        meta(PolicyFamily.DOMAIN, "d", eff_from=T1, eff_to=T0)


def test_metadata_to_reference_roundtrip():
    m = meta(PolicyFamily.GEOGRAPHY, "geo-x")
    ref = m.to_reference()
    assert ref.policy_id == "geo-x"
    assert ref.policy_family is PolicyFamily.GEOGRAPHY
    assert ref.content_digest == DIGEST


def test_metadata_is_effective_at():
    m = meta(PolicyFamily.DOMAIN, "d")
    assert m.is_effective_at(MID) is True
    assert m.is_effective_at(datetime(2025, 1, 1, tzinfo=timezone.utc)) is False
    assert m.is_effective_at(T1) is False  # half-open: effective_to is exclusive


def test_metadata_rejects_naive_datetime():
    with pytest.raises(PolicyContractError):
        PolicyArtifactMetadata(
            policy_id="p", policy_family=PolicyFamily.DOMAIN, version="1",
            content_digest=DIGEST, effective_from=datetime(2026, 1, 1),
        )


# --------------------------------------------------------------------------- #
# GovernedThreshold — literal XOR benchmark
# --------------------------------------------------------------------------- #
def test_threshold_literal_only():
    t = GovernedThreshold(threshold_id="t", governed_unit="pct", comparator=ComparisonOperator.GTE, literal_value="0.9")
    assert t.is_literal is True


def test_threshold_benchmark_only():
    bench = BenchmarkReference(benchmark_id="b", version="1", content_digest=DIGEST)
    t = GovernedThreshold(threshold_id="t", governed_unit="usd", comparator=ComparisonOperator.LTE, benchmark_ref=bench)
    assert t.is_literal is False


def test_threshold_rejects_neither():
    with pytest.raises(PolicyContractError):
        GovernedThreshold(threshold_id="t", governed_unit="u", comparator=ComparisonOperator.GTE)


def test_threshold_rejects_both():
    bench = BenchmarkReference(benchmark_id="b", version="1", content_digest=DIGEST)
    with pytest.raises(PolicyContractError):
        GovernedThreshold(
            threshold_id="t", governed_unit="u", comparator=ComparisonOperator.GTE,
            literal_value="1", benchmark_ref=bench,
        )


# --------------------------------------------------------------------------- #
# PolicyGate — non-waivable mandatory invariant (D-6)
# --------------------------------------------------------------------------- #
def test_gate_mandatory_cannot_be_conditionally_compensable():
    with pytest.raises(PolicyContractError):
        PolicyGate(
            gate_id="g", category=GateCategory.SAFETY, requirement_class=RequirementClass.MANDATORY,
            applicability=(ReadinessTarget.PRODUCTION,), conditionally_compensable=True,
        )


def test_gate_advisory_cannot_be_conditionally_compensable():
    with pytest.raises(PolicyContractError):
        PolicyGate(
            gate_id="g", category=GateCategory.QUALITY, requirement_class=RequirementClass.ADVISORY,
            applicability=(ReadinessTarget.PILOT,), conditionally_compensable=True,
        )


def test_gate_conditional_may_be_compensable():
    g = PolicyGate(
        gate_id="g", category=GateCategory.QUALITY, requirement_class=RequirementClass.CONDITIONAL,
        applicability=(ReadinessTarget.PRODUCTION,), conditionally_compensable=True,
    )
    assert g.conditionally_compensable is True


def test_gate_requires_applicability():
    with pytest.raises(PolicyContractError):
        PolicyGate(gate_id="g", category=GateCategory.SAFETY, requirement_class=RequirementClass.MANDATORY, applicability=())


def test_gate_rejects_duplicate_applicability():
    with pytest.raises(PolicyContractError):
        PolicyGate(
            gate_id="g", category=GateCategory.SAFETY, requirement_class=RequirementClass.MANDATORY,
            applicability=(ReadinessTarget.PILOT, ReadinessTarget.PILOT),
        )


# --------------------------------------------------------------------------- #
# Policies — family binding, anti-gaming, structural rules
# --------------------------------------------------------------------------- #
def test_geography_requires_geography_family():
    with pytest.raises(PolicyContractError):
        GeographyPolicy(
            metadata=meta(PolicyFamily.DOMAIN, "g"), jurisdiction="US",
            reporting_currency="USD", functional_currency="USD",
        )


def test_geography_rejects_bad_currency():
    with pytest.raises(PolicyContractError):
        GeographyPolicy(
            metadata=meta(PolicyFamily.GEOGRAPHY, "g"), jurisdiction="US",
            reporting_currency="dollars", functional_currency="USD",
        )


def test_geography_has_no_roi_multiplier_field():
    # Anti-gaming: there is structurally no field to express a caller multiplier.
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(GeographyPolicy)}
    for forbidden in ("roi_multiplier", "value_multiplier", "multiplier", "weight", "scaling_factor"):
        assert forbidden not in field_names
    # Only currency + benchmark refs + thresholds are the monetary levers.
    assert {"reporting_currency", "functional_currency", "cost_benchmark_refs"} <= field_names


def test_no_policy_shape_exposes_a_numeric_multiplier():
    import dataclasses

    for shape in (GeographyPolicy, DomainPolicy, IntendedOutcomePolicy, ValuationPolicy, ReadinessPolicy):
        names = {f.name.lower() for f in dataclasses.fields(shape)}
        assert not any("multiplier" in n or n.endswith("_weight") or n == "weight" for n in names), shape


def test_geography_valuation_refs_must_be_valuation_family():
    dref = PolicyReference(policy_id="d", policy_family=PolicyFamily.DOMAIN, version="1", content_digest=DIGEST)
    with pytest.raises(PolicyContractError):
        geo(valuation_policy_refs=(dref,))


def test_domain_requires_outcome_unit():
    with pytest.raises(PolicyContractError):
        DomainPolicy(metadata=meta(PolicyFamily.DOMAIN, "d"), governed_outcome_unit="")


def test_domain_rejects_duplicate_gate_ids():
    g1 = PolicyGate(gate_id="g", category=GateCategory.SAFETY, requirement_class=RequirementClass.MANDATORY, applicability=(ReadinessTarget.PRODUCTION,))
    g2 = PolicyGate(gate_id="g", category=GateCategory.QUALITY, requirement_class=RequirementClass.ADVISORY, applicability=(ReadinessTarget.PILOT,))
    with pytest.raises(PolicyContractError):
        dom(gates=(g1, g2))


def test_intended_outcome_requires_target_and_task():
    with pytest.raises(PolicyContractError):
        IntendedOutcomePolicy(metadata=meta(PolicyFamily.INTENDED_OUTCOME, "io"), target_outcome="", task_definition="t")


def test_valuation_rejects_duplicate_components():
    r1 = ComponentEvidenceRequirement(component=ValueComponent.GROSS_BENEFIT)
    r2 = ComponentEvidenceRequirement(component=ValueComponent.GROSS_BENEFIT, required_verification=VerificationStatus.VERIFIED)
    with pytest.raises(PolicyContractError):
        ValuationPolicy(metadata=meta(PolicyFamily.VALUATION, "v"), required_components=(r1, r2))


def test_valuation_headline_defaults_to_weakest_required():
    v = ValuationPolicy(metadata=meta(PolicyFamily.VALUATION, "v"))
    assert v.headline_classification is HeadlineClassificationPolicy.WEAKEST_REQUIRED_COMPONENT
    assert v.missing_component_behavior is MissingComponentBehavior.FAIL_CLOSED


def test_component_requirement_reuses_gv2e_axes():
    r = ComponentEvidenceRequirement(
        component=ValueComponent.AVOIDED_LOSS,
        required_source_basis=SourceBasis.OBSERVED,
        required_attribution=AttributionStatus.ATTRIBUTED,
        required_verification=VerificationStatus.VERIFIED,
    )
    assert r.required_source_basis is SourceBasis.OBSERVED


def test_readiness_composite_must_be_advisory():
    with pytest.raises(PolicyContractError):
        ReadinessPolicy(metadata=meta(PolicyFamily.READINESS, "r"), composite_is_advisory=False)


def test_readiness_requires_targets():
    with pytest.raises(PolicyContractError):
        ReadinessPolicy(metadata=meta(PolicyFamily.READINESS, "r"), readiness_targets=())


# --------------------------------------------------------------------------- #
# AssessmentContext
# --------------------------------------------------------------------------- #
def refs():
    return (
        PolicyReference(policy_id="g", policy_family=PolicyFamily.GEOGRAPHY, version="1", content_digest=DIGEST),
        PolicyReference(policy_id="d", policy_family=PolicyFamily.DOMAIN, version="1", content_digest=DIGEST),
        PolicyReference(policy_id="i", policy_family=PolicyFamily.INTENDED_OUTCOME, version="1", content_digest=DIGEST),
    )


def test_context_binds_mandatory_gdo():
    g, d, i = refs()
    ctx = AssessmentContext(context_id="c", tenant_id="t", subject_id="s", geography_ref=g, domain_ref=d, intended_outcome_ref=i)
    assert len(ctx.policy_refs) == 3
    assert ctx.purpose is AssessmentPurpose.PRE_ROI_READINESS


def test_context_rejects_wrong_family_in_slot():
    g, d, i = refs()
    with pytest.raises(PolicyContractError):
        AssessmentContext(context_id="c", tenant_id="t", subject_id="s", geography_ref=d, domain_ref=d, intended_outcome_ref=i)


def test_context_rejects_cross_tenant_reference():
    g, d, i = refs()
    foreign = PolicyReference(
        policy_id="g", policy_family=PolicyFamily.GEOGRAPHY, version="1",
        content_digest=DIGEST, scope=PolicyScope.TENANT, tenant_id="other",
    )
    with pytest.raises(PolicyContractError):
        AssessmentContext(context_id="c", tenant_id="t", subject_id="s", geography_ref=foreign, domain_ref=d, intended_outcome_ref=i)


def test_context_accepts_tenant_reference_for_same_tenant():
    _, d, i = refs()
    own = PolicyReference(
        policy_id="g", policy_family=PolicyFamily.GEOGRAPHY, version="1",
        content_digest=DIGEST, scope=PolicyScope.TENANT, tenant_id="t",
    )
    ctx = AssessmentContext(context_id="c", tenant_id="t", subject_id="s", geography_ref=own, domain_ref=d, intended_outcome_ref=i)
    assert ctx.geography_ref.tenant_id == "t"


def test_context_rejects_duplicate_policy_id_across_slots():
    dup_geo = PolicyReference(policy_id="same", policy_family=PolicyFamily.GEOGRAPHY, version="1", content_digest=DIGEST)
    dup_dom = PolicyReference(policy_id="same", policy_family=PolicyFamily.DOMAIN, version="1", content_digest=DIGEST)
    _, _, i = refs()
    with pytest.raises(PolicyContractError):
        AssessmentContext(context_id="c", tenant_id="t", subject_id="s", geography_ref=dup_geo, domain_ref=dup_dom, intended_outcome_ref=i)


def test_context_optional_valuation_and_readiness_family_checked():
    g, d, i = refs()
    bad_val = PolicyReference(policy_id="v", policy_family=PolicyFamily.DOMAIN, version="1", content_digest=DIGEST)
    with pytest.raises(PolicyContractError):
        AssessmentContext(context_id="c", tenant_id="t", subject_id="s", geography_ref=g, domain_ref=d, intended_outcome_ref=i, valuation_ref=bad_val)


# --------------------------------------------------------------------------- #
# bind_policies — fail-closed binder
# --------------------------------------------------------------------------- #
def test_bind_policies_happy_path():
    ctx = AssessmentContext.bind_policies(
        context_id="c", tenant_id="t", subject_id="s",
        geography=geo(), domain=dom(), intended_outcome=io(),
        purpose=AssessmentPurpose.POST_DEPLOYMENT_VALUE, as_of=MID,
    )
    assert ctx.geography_ref.policy_id == "geo-1"
    assert ctx.valuation_ref is None


def test_bind_policies_fails_closed_on_non_active():
    revoked = geo(m={"life": PolicyLifecycleState.REVOKED})
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=revoked, domain=dom(), intended_outcome=io())


def test_bind_policies_fails_closed_outside_effective_period():
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(
            context_id="c", tenant_id="t", subject_id="s",
            geography=geo(), domain=dom(), intended_outcome=io(),
            as_of=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )


def test_bind_policies_rejects_cross_tenant_artifact():
    tenant_geo = GeographyPolicy(
        metadata=meta(PolicyFamily.GEOGRAPHY, "geo-t", scope=PolicyScope.TENANT, tenant="other"),
        jurisdiction="US", reporting_currency="USD", functional_currency="USD",
    )
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=tenant_geo, domain=dom(), intended_outcome=io())


def test_bind_policies_with_valuation_and_readiness():
    val = ValuationPolicy(metadata=meta(PolicyFamily.VALUATION, "val-1"))
    rdy = ReadinessPolicy(metadata=meta(PolicyFamily.READINESS, "rdy-1"))
    ctx = AssessmentContext.bind_policies(
        context_id="c", tenant_id="t", subject_id="s",
        geography=geo(), domain=dom(), intended_outcome=io(),
        valuation=val, readiness=rdy, as_of=MID,
    )
    assert ctx.valuation_ref.policy_family is PolicyFamily.VALUATION
    assert ctx.readiness_ref.policy_family is PolicyFamily.READINESS
    assert len(ctx.policy_refs) == 5


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_canonical_digest_is_deterministic_and_64_hex():
    a = AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=geo(), domain=dom(), intended_outcome=io(), as_of=MID)
    b = AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=geo(), domain=dom(), intended_outcome=io(), as_of=MID)
    assert a.canonical_digest() == b.canonical_digest()
    assert len(a.canonical_digest()) == 64
    assert all(ch in "0123456789abcdef" for ch in a.canonical_digest())


def test_canonical_digest_changes_with_content():
    a = AssessmentContext.bind_policies(context_id="c1", tenant_id="t", subject_id="s", geography=geo(), domain=dom(), intended_outcome=io(), as_of=MID)
    b = AssessmentContext.bind_policies(context_id="c2", tenant_id="t", subject_id="s", geography=geo(), domain=dom(), intended_outcome=io(), as_of=MID)
    assert a.canonical_digest() != b.canonical_digest()


def test_shapes_are_frozen():
    import dataclasses

    ctx = AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=geo(), domain=dom(), intended_outcome=io(), as_of=MID)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.context_id = "x"  # type: ignore[misc]
