"""Immutability, determinism, and anti-gaming tests (GV-3R-a)."""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from ugence_governance_contracts.api import AssessmentWindow, MetricClaim, SourceBasis, TransformationMethod
from ugence_uvi_policy_contracts.api import (
    PolicyFamily,
    PolicyReference,
    ReadinessTarget,
    RequirementClass,
)
from ugence_agent_value_readiness import api as ready_api
from ugence_agent_value_readiness.api import (
    AdvisoryComposite,
    CapabilityDemonstration,
    CapabilityDimension,
    CapabilityReadinessResult,
    GateResult,
    GateStatus,
    IntelligenceDimension,
    IntelligenceFitnessResult,
    ReadinessContractError,
)

D = hashlib.sha256(b"content").hexdigest()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
WIN = AssessmentWindow(start=T0, end=MID)


def claim(metric="accuracy"):
    return MetricClaim(claim_id=f"c-{metric}", tenant_id="t1", subject_id="a1", metric_id=metric, value="0.9",
                       governed_unit="ratio", source_basis=SourceBasis.OBSERVED, transformation_method=TransformationMethod.DIRECT, assessment_window=WIN)


def intel(**kw):
    base = dict(result_id="ir1", tenant_id="t1", subject_id="a1", context_id="ctx1", task_or_outcome_ref="i",
                dimension=IntelligenceDimension.ACCURACY, claim=claim(), requirement_class=RequirementClass.MANDATORY,
                applicable_targets=[ReadinessTarget.PILOT], status=GateStatus.PASS)
    base.update(kw)
    return IntelligenceFitnessResult(**base)


# --------------------------------------------------------------------------- #
# Immutability: list inputs coerced, mutation-proof, digest stable
# --------------------------------------------------------------------------- #
def test_sequence_fields_stored_as_tuple():
    r = intel(applicable_targets=[ReadinessTarget.PILOT], evidence_refs=["e1"], reason_codes=["ok"])
    assert isinstance(r.applicable_targets, tuple)
    assert isinstance(r.evidence_refs, tuple)
    assert isinstance(r.reason_codes, tuple)


def test_caller_list_mutation_has_no_effect():
    evid = ["e1"]
    r = intel(evidence_refs=evid)
    d0 = r.canonical_digest()
    evid.append("INJECT")
    assert r.evidence_refs == ("e1",)
    assert r.canonical_digest() == d0


def test_stored_tuple_cannot_be_mutated():
    r = intel(evidence_refs=["e1"])
    with pytest.raises(AttributeError):
        r.evidence_refs.append("x")  # type: ignore[attr-defined]


def test_list_and_tuple_inputs_equal_digest():
    a = intel(applicable_targets=[ReadinessTarget.PILOT])
    b = intel(applicable_targets=(ReadinessTarget.PILOT,))
    assert a.canonical_digest() == b.canonical_digest()


def test_scalar_substitute_rejected():
    with pytest.raises(ReadinessContractError):
        intel(evidence_refs="e1")
    with pytest.raises(ReadinessContractError):
        intel(applicable_targets={"k": 1})


def test_frozen_reassignment_fails():
    r = intel()
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.result_id = "x"  # type: ignore[misc]


def test_empty_applicable_targets_rejected():
    with pytest.raises(ReadinessContractError):
        intel(applicable_targets=[])


def test_blank_identifier_rejected():
    with pytest.raises(ReadinessContractError):
        intel(result_id="  ")


def test_gate_result_naive_timestamp_rejected():
    with pytest.raises(ReadinessContractError):
        GateResult(gate_id="g", readiness_policy_ref=PolicyReference(policy_id="r", policy_family=PolicyFamily.READINESS, version="1", content_digest=D),
                   gate_kind=RequirementClass.MANDATORY, requested_target=ReadinessTarget.PILOT, applicable=True, status=GateStatus.PASS,
                   evaluated_at=datetime(2026, 6, 1))


# --------------------------------------------------------------------------- #
# Anti-gaming: no financial concepts anywhere in the public readiness surface
# --------------------------------------------------------------------------- #
_FINANCIAL = ("money", "currency", "usd", "roi", "benefit", "cost", "price", "revenue",
              "profit", "npv", "cashflow", "cash_flow", "dollar", "monetary", "value_multiplier",
              "multiplier", "financial", "wage", "spend")


def _public_readiness_types():
    out = []
    for name in ready_api.__all__:
        obj = getattr(ready_api, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            # only the types this package defines (skip reused policy types)
            if obj.__module__.startswith("ugence_agent_value_readiness"):
                out.append(obj)
    return out


def test_no_financial_fields_in_readiness_types():
    offenders = {}
    for shape in _public_readiness_types():
        for f in dataclasses.fields(shape):
            low = f.name.lower()
            for term in _FINANCIAL:
                if term in low:
                    offenders.setdefault(shape.__name__, []).append(f.name)
    assert not offenders, offenders


def test_readiness_enums_carry_no_financial_values():
    import enum
    for name in ready_api.__all__:
        obj = getattr(ready_api, name)
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            for member in obj:
                low = member.value.lower()
                assert not any(t in low for t in _FINANCIAL), f"{obj.__name__}.{member.name}"


def test_composite_cannot_encode_financial_multiplier():
    # AdvisoryComposite exposes only method/version/score/scale/components — no weight/multiplier.
    names = {f.name.lower() for f in dataclasses.fields(AdvisoryComposite)}
    assert not any("weight" in n or "multiplier" in n or "roi" in n for n in names)
