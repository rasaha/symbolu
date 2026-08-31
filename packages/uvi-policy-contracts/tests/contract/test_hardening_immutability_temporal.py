"""Adversarial tests for the GV-2C-a hardening corrections.

GV2C-F1 — every tuple-typed public field is normalized into a real immutable
tuple, so a caller-owned ``list`` cannot mutate a constructed contract or its
digest, and scalar substitutes (str/bytes/mapping/non-iterable) are rejected.

GV2C-F2 — ``AssessmentContext.bind_policies`` requires an explicit, timezone-aware
``as_of``; temporal validation cannot be omitted and is never read from a clock.

GV2C-F3 — ``as_of`` (policy applicability instant) and ``assessment_window``
(evidence period) are deliberately distinct.

These assert the *security property*, not merely that a constructor runs.
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from ugence_governance_contracts.api import AssessmentWindow, BenchmarkReference, SourceBasis
from ugence_uvi_policy_contracts.api import (
    AssessmentContext,
    AssessmentPurpose,
    ComparisonOperator,
    ComponentEvidenceRequirement,
    DomainPolicy,
    GateCategory,
    GeographyPolicy,
    GovernedThreshold,
    IntendedOutcomePolicy,
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


def meta(family, pid, *, scope=PolicyScope.GLOBAL, tenant="", life=PolicyLifecycleState.APPROVED_ACTIVE, ef=T0, et=T1):
    return PolicyArtifactMetadata(
        policy_id=pid, policy_family=family, version="1", content_digest=DIGEST,
        scope=scope, tenant_id=tenant, lifecycle_state=life, effective_from=ef, effective_to=et,
    )


def bench(bid="b"):
    return BenchmarkReference(benchmark_id=bid, version="1", content_digest=DIGEST)


def thr(tid="t"):
    return GovernedThreshold(threshold_id=tid, governed_unit="pct", comparator=ComparisonOperator.GTE, literal_value="0.9")


def gate(gid="g"):
    return PolicyGate(gate_id=gid, category=GateCategory.SAFETY, requirement_class=RequirementClass.MANDATORY, applicability=[ReadinessTarget.PRODUCTION])


def val_ref(pid="v"):
    return PolicyReference(policy_id=pid, policy_family=PolicyFamily.VALUATION, version="1", content_digest=DIGEST)


# One representative instance of every shape that has sequence fields, built with
# LISTS for every sequence field (the adversarial input).
def _instances_with_list_inputs():
    return {
        "GeographyPolicy": GeographyPolicy(
            metadata=meta(PolicyFamily.GEOGRAPHY, "geo"), jurisdiction="US",
            reporting_currency="USD", functional_currency="USD",
            applicable_regulations=["reg-a", "reg-b"], language_requirements=["en"],
            residency_requirements=["eu"], cost_benchmark_refs=[bench("wage")],
            regional_thresholds=[thr("rt")], valuation_policy_refs=[val_ref("vg")],
        ),
        "DomainPolicy": DomainPolicy(
            metadata=meta(PolicyFamily.DOMAIN, "dom"), governed_outcome_unit="ticket",
            task_taxonomy=["classify"], benefit_taxonomy=["labor"], loss_taxonomy=["error"],
            permitted_valuation_methods=["dcf"], domain_benchmark_refs=[bench("db")], gates=[gate("dg")],
        ),
        "IntendedOutcomePolicy": IntendedOutcomePolicy(
            metadata=meta(PolicyFamily.INTENDED_OUTCOME, "io"), target_outcome="resolve",
            task_definition="handle ticket", success_criteria=["sla"],
            required_effect_evidence=["obs"], acceptance_thresholds=[thr("at")],
            valuation_policy_refs=[val_ref("vio")],
        ),
        "ValuationPolicy": ValuationPolicy(
            metadata=meta(PolicyFamily.VALUATION, "val"), permitted_valuation_methods=["dcf"],
            required_components=[ComponentEvidenceRequirement(component=ValueComponent.GROSS_BENEFIT)],
            acceptance_thresholds=[thr("vt")],
        ),
        "ReadinessPolicy": ReadinessPolicy(
            metadata=meta(PolicyFamily.READINESS, "rdy"), gates=[gate("rg")],
            readiness_targets=[ReadinessTarget.PILOT, ReadinessTarget.PRODUCTION],
        ),
        "PolicyGate": gate("solo"),
        "AssessmentContext": AssessmentContext(
            context_id="c", tenant_id="t", subject_id="s",
            geography_ref=PolicyReference(policy_id="g", policy_family=PolicyFamily.GEOGRAPHY, version="1", content_digest=DIGEST),
            domain_ref=PolicyReference(policy_id="d", policy_family=PolicyFamily.DOMAIN, version="1", content_digest=DIGEST),
            intended_outcome_ref=PolicyReference(policy_id="i", policy_family=PolicyFamily.INTENDED_OUTCOME, version="1", content_digest=DIGEST),
            additional_policy_refs=[val_ref("extra")],
        ),
    }


# --------------------------------------------------------------------------- #
# F1: structural coverage — no tuple-annotated field is left as a list
# --------------------------------------------------------------------------- #
def test_every_tuple_field_normalized_to_tuple_across_all_shapes():
    instances = _instances_with_list_inputs()
    checked = 0
    for name, obj in instances.items():
        for f in dataclasses.fields(obj):
            if "tuple" in str(f.type):
                value = getattr(obj, f.name)
                assert isinstance(value, tuple), f"{name}.{f.name} stored as {type(value).__name__}, not tuple"
                checked += 1
    # Guard against the introspection silently matching nothing.
    assert checked >= 15, f"expected many tuple fields, only checked {checked}"


def test_original_list_mutation_does_not_affect_contract_or_digest():
    regs = ["reg-a"]
    gp = GeographyPolicy(
        metadata=meta(PolicyFamily.GEOGRAPHY, "geo"), jurisdiction="US",
        reporting_currency="USD", functional_currency="USD", applicable_regulations=regs,
    )
    d0 = gp.canonical_digest()
    regs.append("INJECTED")        # mutate the caller-owned list afterwards
    regs.append("")                # try to inject a blank too
    assert gp.applicable_regulations == ("reg-a",)
    assert gp.canonical_digest() == d0


def test_stored_tuple_cannot_be_mutated():
    gp = GeographyPolicy(
        metadata=meta(PolicyFamily.GEOGRAPHY, "geo"), jurisdiction="US",
        reporting_currency="USD", functional_currency="USD", applicable_regulations=["reg-a"],
    )
    with pytest.raises(AttributeError):
        gp.applicable_regulations.append("x")  # type: ignore[attr-defined]


def test_additional_policy_refs_normalized_and_mutation_proof():
    refs = [val_ref("extra")]
    ctx = AssessmentContext(
        context_id="c", tenant_id="t", subject_id="s",
        geography_ref=PolicyReference(policy_id="g", policy_family=PolicyFamily.GEOGRAPHY, version="1", content_digest=DIGEST),
        domain_ref=PolicyReference(policy_id="d", policy_family=PolicyFamily.DOMAIN, version="1", content_digest=DIGEST),
        intended_outcome_ref=PolicyReference(policy_id="i", policy_family=PolicyFamily.INTENDED_OUTCOME, version="1", content_digest=DIGEST),
        additional_policy_refs=refs,
    )
    d0 = ctx.canonical_digest()
    # Attempt to inject a duplicate/cross-family/cross-tenant ref post-construction.
    refs.append(PolicyReference(policy_id="d", policy_family=PolicyFamily.DOMAIN, version="1", content_digest=DIGEST))
    assert isinstance(ctx.additional_policy_refs, tuple)
    assert len(ctx.policy_refs) == 4  # g, d, i, extra — injection had no effect
    assert ctx.canonical_digest() == d0


def test_policy_gate_applicability_normalized():
    g = PolicyGate(gate_id="g", category=GateCategory.SAFETY, requirement_class=RequirementClass.MANDATORY, applicability=[ReadinessTarget.PILOT])
    assert isinstance(g.applicability, tuple)


def test_list_and_tuple_inputs_produce_identical_digest():
    kw = dict(metadata=meta(PolicyFamily.GEOGRAPHY, "geo"), jurisdiction="US", reporting_currency="USD", functional_currency="USD")
    from_list = GeographyPolicy(applicable_regulations=["a", "b"], **kw)
    from_tuple = GeographyPolicy(applicable_regulations=("a", "b"), **kw)
    assert from_list.canonical_digest() == from_tuple.canonical_digest()


def test_materially_different_content_differs_in_digest():
    kw = dict(metadata=meta(PolicyFamily.GEOGRAPHY, "geo"), jurisdiction="US", reporting_currency="USD", functional_currency="USD")
    a = GeographyPolicy(applicable_regulations=["a"], **kw)
    b = GeographyPolicy(applicable_regulations=["a", "b"], **kw)
    assert a.canonical_digest() != b.canonical_digest()


@pytest.mark.parametrize("bad", ["a-string", b"bytes", {"k": "v"}, 5])
def test_scalar_substitutes_rejected_for_string_sequence(bad):
    with pytest.raises(PolicyContractError):
        GeographyPolicy(
            metadata=meta(PolicyFamily.GEOGRAPHY, "geo"), jurisdiction="US",
            reporting_currency="USD", functional_currency="USD", applicable_regulations=bad,
        )


@pytest.mark.parametrize("bad", ["x", b"x", {"a": 1}, 3])
def test_scalar_substitutes_rejected_for_ref_sequence(bad):
    with pytest.raises(PolicyContractError):
        AssessmentContext(
            context_id="c", tenant_id="t", subject_id="s",
            geography_ref=PolicyReference(policy_id="g", policy_family=PolicyFamily.GEOGRAPHY, version="1", content_digest=DIGEST),
            domain_ref=PolicyReference(policy_id="d", policy_family=PolicyFamily.DOMAIN, version="1", content_digest=DIGEST),
            intended_outcome_ref=PolicyReference(policy_id="i", policy_family=PolicyFamily.INTENDED_OUTCOME, version="1", content_digest=DIGEST),
            additional_policy_refs=bad,
        )


def test_blank_and_wrong_type_element_rejected_not_coerced():
    with pytest.raises(PolicyContractError):
        GeographyPolicy(
            metadata=meta(PolicyFamily.GEOGRAPHY, "geo"), jurisdiction="US",
            reporting_currency="USD", functional_currency="USD", applicable_regulations=["ok", "  "],
        )
    with pytest.raises(PolicyContractError):
        DomainPolicy(metadata=meta(PolicyFamily.DOMAIN, "d"), governed_outcome_unit="u", gates=["not-a-gate"])


def test_frozen_reassignment_still_fails():
    gp = GeographyPolicy(metadata=meta(PolicyFamily.GEOGRAPHY, "geo"), jurisdiction="US", reporting_currency="USD", functional_currency="USD")
    with pytest.raises(dataclasses.FrozenInstanceError):
        gp.jurisdiction = "CA"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# F2: mandatory, explicit, timezone-aware as_of
# --------------------------------------------------------------------------- #
def _geo():
    return GeographyPolicy(metadata=meta(PolicyFamily.GEOGRAPHY, "geo"), jurisdiction="US", reporting_currency="USD", functional_currency="USD")


def _dom():
    return DomainPolicy(metadata=meta(PolicyFamily.DOMAIN, "dom"), governed_outcome_unit="ticket")


def _io():
    return IntendedOutcomePolicy(metadata=meta(PolicyFamily.INTENDED_OUTCOME, "io"), target_outcome="o", task_definition="t")


def test_bind_requires_as_of_argument():
    # as_of has no default: omitting it is a Python TypeError, not a fail-open bind.
    with pytest.raises(TypeError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io())


def test_bind_rejects_none_as_of():
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), as_of=None)


def test_bind_rejects_naive_as_of():
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), as_of=datetime(2026, 6, 1))


def test_bind_rejects_non_datetime_as_of():
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), as_of="2026-06-01")


def test_bind_rejects_expired_policy():
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), as_of=datetime(2030, 1, 1, tzinfo=timezone.utc))


def test_bind_rejects_future_policy():
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), as_of=datetime(2020, 1, 1, tzinfo=timezone.utc))


def test_bind_boundary_exactly_at_effective_from():
    ctx = AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), as_of=T0)
    assert ctx.geography_ref.policy_id == "geo"  # inclusive lower bound


def test_bind_boundary_one_instant_before_from_rejected():
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), as_of=T0 - timedelta(microseconds=1))


def test_bind_boundary_one_instant_before_to_ok():
    ctx = AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), as_of=T1 - timedelta(microseconds=1))
    assert ctx.domain_ref.policy_id == "dom"


def test_bind_boundary_exactly_at_effective_to_rejected():
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), as_of=T1)  # exclusive upper bound


def test_bind_open_ended_effective_period():
    # effective_to=None means no declared upper bound — effective at any instant
    # at/after effective_from. All three required artifacts are open-ended here.
    open_geo = GeographyPolicy(
        metadata=meta(PolicyFamily.GEOGRAPHY, "geo", et=None),
        jurisdiction="US", reporting_currency="USD", functional_currency="USD",
    )
    open_dom = DomainPolicy(metadata=meta(PolicyFamily.DOMAIN, "dom", et=None), governed_outcome_unit="ticket")
    open_io = IntendedOutcomePolicy(metadata=meta(PolicyFamily.INTENDED_OUTCOME, "io", et=None), target_outcome="o", task_definition="t")
    ctx = AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=open_geo, domain=open_dom, intended_outcome=open_io, as_of=datetime(2099, 1, 1, tzinfo=timezone.utc))
    assert ctx.geography_ref.policy_id == "geo"


def test_bind_required_policy_invalid_while_others_valid():
    # domain expired, geography+io valid → fails closed on the invalid one.
    expired_dom = DomainPolicy(metadata=meta(PolicyFamily.DOMAIN, "dom", ef=datetime(2020, 1, 1, tzinfo=timezone.utc), et=datetime(2021, 1, 1, tzinfo=timezone.utc)), governed_outcome_unit="u")
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=expired_dom, intended_outcome=_io(), as_of=MID)


def test_bind_optional_valuation_gets_same_temporal_check():
    expired_val = ValuationPolicy(metadata=meta(PolicyFamily.VALUATION, "val", ef=datetime(2020, 1, 1, tzinfo=timezone.utc), et=datetime(2021, 1, 1, tzinfo=timezone.utc)))
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), valuation=expired_val, as_of=MID)


def test_bind_optional_readiness_gets_same_temporal_check():
    expired_rdy = ReadinessPolicy(metadata=meta(PolicyFamily.READINESS, "rdy", ef=datetime(2020, 1, 1, tzinfo=timezone.utc), et=datetime(2021, 1, 1, tzinfo=timezone.utc)))
    with pytest.raises(PolicyContractError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), readiness=expired_rdy, as_of=MID)


# --------------------------------------------------------------------------- #
# F3: as_of and assessment_window are distinct
# --------------------------------------------------------------------------- #
def test_as_of_and_assessment_window_are_distinct():
    # Evidence window sits far outside the policy effective period; binding still
    # succeeds because as_of (not the window) governs policy applicability.
    window = AssessmentWindow(start=datetime(2010, 1, 1, tzinfo=timezone.utc), end=datetime(2010, 6, 1, tzinfo=timezone.utc))
    ctx = AssessmentContext.bind_policies(
        context_id="c", tenant_id="t", subject_id="s",
        geography=_geo(), domain=_dom(), intended_outcome=_io(),
        as_of=MID, assessment_window=window,
    )
    assert ctx.assessment_window is window
    assert ctx.purpose is AssessmentPurpose.PRE_ROI_READINESS


def test_assessment_window_cannot_substitute_for_as_of():
    # Supplying only an assessment_window (no as_of) is still a TypeError — the
    # window does not fulfil the mandatory policy-evaluation instant.
    window = AssessmentWindow(start=T0, end=MID)
    with pytest.raises(TypeError):
        AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s", geography=_geo(), domain=_dom(), intended_outcome=_io(), assessment_window=window)
