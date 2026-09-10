"""Shared builders for the GV-3R-b evaluator tests.

Deliberately explicit: every fixture states its policy, gates, indicator results
and conditions, so a test asserting a decision-table row can be read on its own.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from ugence_governance_contracts.api import (
    AssessmentWindow,
    MetricClaim,
    SourceBasis,
    TransformationMethod,
)
from ugence_uvi_policy_contracts.api import (
    AssessmentContext,
    DomainPolicy,
    GateCategory,
    GeographyPolicy,
    IntendedOutcomePolicy,
    PolicyArtifactMetadata,
    PolicyFamily,
    PolicyGate,
    PolicyLifecycleState,
    ReadinessPolicy,
    ReadinessTarget,
    RequirementClass,
)

from ugence_agent_value_readiness.api import (
    AdoptionDimension,
    AdoptionReadinessResult,
    CapabilityDemonstration,
    CapabilityDimension,
    CapabilityReadinessResult,
    ConditionSet,
    ConditionStatus,
    GateResult,
    GateStatus,
    IntelligenceDimension,
    IntelligenceFitnessResult,
    ReadinessEvaluationCase,
)

D = hashlib.sha256(b"content").hexdigest()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2027, 1, 1, tzinfo=timezone.utc)
NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)
FUTURE = datetime(2026, 9, 1, tzinfo=timezone.utc)
PAST = datetime(2026, 3, 1, tzinfo=timezone.utc)

PILOT = ReadinessTarget.PILOT
PROD = ReadinessTarget.PRODUCTION
BOTH = (PILOT, PROD)

MANDATORY = RequirementClass.MANDATORY
CONDITIONAL = RequirementClass.CONDITIONAL
ADVISORY = RequirementClass.ADVISORY

WINDOW = AssessmentWindow(start=T0, end=NOW)


def meta(family, pid, digest=D, state=PolicyLifecycleState.APPROVED_ACTIVE,
         effective_from=T0, effective_to=T1):
    return PolicyArtifactMetadata(
        policy_id=pid,
        policy_family=family,
        version="1",
        content_digest=digest,
        lifecycle_state=state,
        effective_from=effective_from,
        effective_to=effective_to,
    )


def gate(gid, kind, applicability=BOTH, compensable=False, category=GateCategory.SAFETY):
    return PolicyGate(
        gate_id=gid,
        category=category,
        requirement_class=kind,
        applicability=applicability,
        conditionally_compensable=compensable,
    )


def readiness_policy(gates, pid="rp", targets=BOTH, digest=D,
                     state=PolicyLifecycleState.APPROVED_ACTIVE,
                     effective_from=T0, effective_to=T1):
    return ReadinessPolicy(
        metadata=meta(PolicyFamily.READINESS, pid, digest, state, effective_from, effective_to),
        gates=tuple(gates), readiness_targets=tuple(targets))


def _gdo():
    return (
        GeographyPolicy(metadata=meta(PolicyFamily.GEOGRAPHY, "g"), jurisdiction="US",
                        reporting_currency="USD", functional_currency="USD"),
        DomainPolicy(metadata=meta(PolicyFamily.DOMAIN, "d"), governed_outcome_unit="ticket"),
        IntendedOutcomePolicy(metadata=meta(PolicyFamily.INTENDED_OUTCOME, "i"),
                              target_outcome="o", task_definition="t"),
    )


def context(policy, tenant="t1", subject="a1", bind_readiness=True, bind=False):
    """Build an AssessmentContext.

    ``bind=False`` (default) constructs the context directly, which a caller may
    legitimately do and which is the only way to represent a context over a
    policy the fail-closed binder would reject (a non-APPROVED_ACTIVE or
    out-of-period policy). ``bind=True`` routes through
    ``AssessmentContext.bind_policies`` at ``as_of=NOW``.
    """

    geo, dom, io = _gdo()
    if bind:
        return AssessmentContext.bind_policies(
            context_id="ctx1", tenant_id=tenant, subject_id=subject,
            geography=geo, domain=dom, intended_outcome=io,
            readiness=policy if bind_readiness else None, as_of=NOW)
    return AssessmentContext(
        context_id="ctx1", tenant_id=tenant, subject_id=subject,
        geography_ref=geo.reference, domain_ref=dom.reference,
        intended_outcome_ref=io.reference,
        readiness_ref=policy.reference if bind_readiness else None)


def claim(
    cid="c1",
    tenant="t1",
    subject="a1",
    source_basis=SourceBasis.REPORTED,
    transformation=TransformationMethod.DIRECT,
):
    return MetricClaim(
        claim_id=cid,
        tenant_id=tenant,
        subject_id=subject,
        metric_id="accuracy",
        value="0.95",
        governed_unit="ratio",
        source_basis=source_basis,
        transformation_method=transformation,
        assessment_window=WINDOW,
    )


def indicators(target=PROD, tenant="t1", subject="a1", context_id="ctx1"):
    """One applicable result for each of the three indicator families."""

    targets = (target,)
    common = dict(tenant_id=tenant, subject_id=subject, context_id=context_id,
                  task_or_outcome_ref="task", requirement_class=MANDATORY,
                  applicable_targets=targets, status=GateStatus.PASS)
    return (
        (
            IntelligenceFitnessResult(
                result_id="ir1", dimension=IntelligenceDimension.ACCURACY,
                claim=claim("c-int", tenant, subject), **common,
            ),
        ),
        (
            CapabilityReadinessResult(
                result_id="cr1", dimension=CapabilityDimension.TOOL_READINESS,
                claim=claim("c-cap", tenant, subject),
                demonstration=CapabilityDemonstration.MET_THRESHOLD,
                evidence_sufficient=True, **common,
            ),
        ),
        (
            AdoptionReadinessResult(
                result_id="ar1", dimension=AdoptionDimension.EXPECTED_UTILIZATION,
                claim=claim("c-ado", tenant, subject), **common,
            ),
        ),
    )


def gate_result(policy, gid, status, target=PROD, policy_ref=None):
    owned = {g.gate_id: g for g in policy.gates}[gid]
    return GateResult(
        policy_gate=owned,
        readiness_policy_ref=policy_ref or policy.reference,
        requested_target=target,
        status=status,
    )


def condition(
    cid,
    source,
    status=ConditionStatus.APPROVED_ACTIVE,
    effective_from=T0,
    effective_to=None,
    expiry=None,
):
    kw = dict(
        condition_id=cid,
        source_gate_or_finding_ref=source,
        concern_requirement_class=CONDITIONAL,
        current_status=status,
        effective_from=effective_from,
        effective_to=effective_to,
        expiry=expiry,
    )
    if status is ConditionStatus.APPROVED_ACTIVE:
        kw.update(
            approved_mitigation_ref="mitigation-1",
            approving_authority_ref="authority-1",
            accountable_owner="owner-1",
            scope_exposure_limit="10% of eligible population",
            monitoring_requirement="weekly override-rate review",
            evidence_refs=("ev-cond-1",),
            revocation_trigger="override rate > 5%",
        )
    return ConditionSet(**kw)


def case(
    *,
    policy,
    gate_results=(),
    conditions=(),
    target=PROD,
    ctx=None,
    tenant="t1",
    subject="a1",
    with_indicators=True,
    intelligence=None,
    capability=None,
    adoption=None,
    composite=None,
    policy_ref=None,
    case_id="case-1",
):
    ctx = ctx if ctx is not None else context(policy, tenant=tenant, subject=subject)
    intel, cap, ado = indicators(target=target, tenant=tenant, subject=subject,
                                 context_id=ctx.context_id)
    if not with_indicators:
        intel = cap = ado = ()
    return ReadinessEvaluationCase(
        case_id=case_id,
        tenant_id=tenant,
        subject_id=subject,
        context=ctx,
        readiness_policy=policy,
        readiness_policy_ref=policy_ref or policy.reference,
        requested_target=target,
        intelligence_results=intel if intelligence is None else intelligence,
        capability_results=cap if capability is None else capability,
        adoption_results=ado if adoption is None else adoption,
        gate_results=tuple(gate_results),
        conditions=tuple(conditions),
        advisory_composite=composite,
    )
