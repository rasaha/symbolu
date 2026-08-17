#!/usr/bin/env python3
"""Independent adversarial probes against the trusted readiness orchestration.

Deliberately *separate* from the pytest suite and sharing none of its fixtures:
these probes rebuild every artifact from scratch and attack the package through
its **public API only**, so a mistake in the test fixtures cannot mask a real
hole.

Each probe states an attack an untrusted caller might attempt and asserts the
boundary refuses it. Run:

    python packages/capabilities/agent-value-readiness/adversarial_probes.py

Exit code 0 when every probe held; non-zero on the first breach.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import pathlib
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

_HERE = pathlib.Path(__file__).resolve().parent
for _path in (
    _HERE / "src",
    _HERE.parent.parent / "governance-contracts" / "src",
    _HERE.parent.parent / "uvi-policy-contracts" / "src",
    _HERE.parent.parent / "policy-authority" / "src",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from ugence_governance_contracts.api import (  # noqa: E402
    AssessmentWindow,
    MetricClaim,
    SourceBasis,
    TransformationMethod,
    VerificationStatus,
)
from ugence_policy_authority.api import (  # noqa: E402
    ApprovalEvidenceRef,
    ApprovalVerification,
    ApprovalVerificationStatus,
    Ed25519PolicySigner,
    InMemoryPolicyRegistry,
    IssuedPolicyRecord,
    KeyEntitlement,
    PolicyKeyRing,
    PolicyResolution,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    SIGNATURE_ALG,
    SigningKey,
    UviPolicyFamilyAdapter,
    default_uvi_adapters,
    issue_policy,
    uvi_coordinate,
)
from ugence_uvi_policy_contracts.api import (  # noqa: E402
    AssessmentContext,
    DomainPolicy,
    GateCategory,
    GeographyPolicy,
    IntendedOutcomePolicy,
    PolicyArtifactMetadata,
    PolicyFamily,
    PolicyGate,
    PolicyLifecycleState,
    PolicyReference,
    ReadinessPolicy,
    ReadinessTarget,
    RequirementClass,
)

import ugence_agent_value_readiness as R  # noqa: E402
from ugence_agent_value_readiness.api import (
    AssessedSystemBinding,  # noqa: E402
    READINESS_ORCHESTRATOR_VERSION,
    AdoptionDimension,
    AdoptionReadinessResult,
    AdvisoryComposite,
    CapabilityDemonstration,
    CapabilityDimension,
    CapabilityReadinessResult,
    ConditionSet,
    ConditionSetVerification,
    ConditionStatus,
    DenyAllConditionSetVerifier,
    DenyAllGateResultVerifier,
    DenyAllReadinessPolicyResolver,
    GateResult,
    GateResultVerification,
    GateStatus,
    IntelligenceDimension,
    IntelligenceFitnessResult,
    PolicyAuthorityReadinessPolicyResolver,
    ReadinessAssessmentError,
    ReadinessAssessmentOutcome,
    ReadinessAssessmentRequest,
    ReadinessAssessmentStatus,
    ReadinessClassification,
    ReadinessInputVerificationStatus,
    ReadinessTrustAdvisoryState,
    ReadinessTrustGapCode,
    assess_readiness,
    evaluate_readiness,
)

PASSED = 0
FAILURES: list[str] = []

T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_LATE = datetime(2026, 9, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
DIGEST = hashlib.sha256(b"arbitrary but well-formed").hexdigest()
V = ReadinessInputVerificationStatus
G = ReadinessTrustGapCode


def probe(description: str):
    """Decorator registering one adversarial probe."""

    def decorate(fn):
        global PASSED
        try:
            fn()
        except AssertionError as exc:  # a breach
            FAILURES.append(f"BREACH  {description}: {exc}")
        except Exception as exc:  # noqa: BLE001 - an unexpected error is a breach
            FAILURES.append(f"ERROR   {description}: {type(exc).__name__}: {exc}")
        else:
            PASSED += 1
            print(f"  ok  {description}")
        return fn

    return decorate


# --------------------------------------------------------------------------- #
# Artifacts, built from scratch
# --------------------------------------------------------------------------- #
_ADAPTER = UviPolicyFamilyAdapter()


def _meta(family, policy_id, digest, **kwargs):
    return PolicyArtifactMetadata(
        policy_id=policy_id,
        policy_family=family,
        version="1.0.0",
        content_digest=digest,
        lifecycle_state=kwargs.pop("lifecycle_state", PolicyLifecycleState.APPROVED_ACTIVE),
        effective_from=kwargs.pop("effective_from", T_FROM),
        effective_to=kwargs.pop("effective_to", T_TO),
        **kwargs,
    )


def _bound(cls, family, policy_id, body, **meta_kwargs):
    draft = cls(metadata=_meta(family, policy_id, "0" * 64, **meta_kwargs), **body)
    digest = _ADAPTER.describe(draft).body_digest()
    return cls(metadata=_meta(family, policy_id, digest, **meta_kwargs), **body)


def gate(gid, kind, applicability=(ReadinessTarget.PILOT, ReadinessTarget.PRODUCTION),
         compensable=False):
    return PolicyGate(
        gate_id=gid,
        category=GateCategory.SAFETY,
        requirement_class=kind,
        applicability=applicability,
        conditionally_compensable=compensable,
    )


def readiness(gates, policy_id="probe-readiness", **meta_kwargs):
    return _bound(
        ReadinessPolicy,
        PolicyFamily.READINESS,
        policy_id,
        dict(gates=tuple(gates)),
        **meta_kwargs,
    )


POLICY = readiness(
    [
        gate("m1", RequirementClass.MANDATORY),
        gate("m2", RequirementClass.MANDATORY),
        gate("c1", RequirementClass.CONDITIONAL, compensable=True),
    ]
)
GEO = _bound(
    GeographyPolicy,
    PolicyFamily.GEOGRAPHY,
    "probe-geo",
    dict(jurisdiction="US-CA", reporting_currency="USD", functional_currency="USD"),
)
DOM = _bound(
    DomainPolicy, PolicyFamily.DOMAIN, "probe-dom", dict(governed_outcome_unit="ticket")
)
OUT = _bound(
    IntendedOutcomePolicy,
    PolicyFamily.INTENDED_OUTCOME,
    "probe-out",
    dict(target_outcome="o", task_definition="t"),
)


def context(policy=POLICY, tenant="t1", subject="a1"):
    return AssessmentContext(
        context_id="probe-ctx",
        tenant_id=tenant,
        subject_id=subject,
        geography_ref=GEO.reference,
        domain_ref=DOM.reference,
        intended_outcome_ref=OUT.reference,
        readiness_ref=policy.reference if policy is not None else None,
    )


class _Approval:
    def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
        return ApprovalVerification(
            verified=True,
            status=ApprovalVerificationStatus.APPROVED,
            coordinate=coordinate,
            policy_body_digest=policy_body_digest,
            approving_authority_id="probe.approval-board",
            approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest,
            verified_at=as_of,
        )


def make_resolver(policy=POLICY):
    signer = Ed25519PolicySigner(
        authority_id="probe.authority",
        key_id="probe-key-1",
        signing_key=SigningKey.from_seed(bytes([3]) * 32),
    )
    registry = InMemoryPolicyRegistry()
    adapters = default_uvi_adapters()
    issue_policy(
        policy=policy,
        record_id="probe-rec-1",
        approval=ApprovalEvidenceRef(
            approval_ref="APPROVAL-PROBE",
            approval_digest=hashlib.sha256(b"approval").hexdigest(),
            approving_authority_id="probe.approval-board",
        ),
        approval_verifier=_Approval(),
        signer=signer,
        registry=registry,
        adapters=adapters,
        issued_at=T_FROM,
    )
    return PolicyAuthorityReadinessPolicyResolver(
        registry=registry,
        signature_verifier=PolicyKeyRing(
            [signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,))]
        ),
        adapters=adapters,
    )


RESOLVER = make_resolver()


class Verifier:
    """A probe-local verifier. Nothing like it exists in the distribution."""

    def __init__(self, status=V.VERIFIED, overrides=None, only=None):
        self.status = status
        self.overrides = overrides or {}
        self.only = only
        self.calls = []

    def verify_gate_result(self, request):
        self.calls.append(request)
        status = self.status
        if self.only is not None and request.gate_id not in self.only:
            status = V.EVIDENCE_NOT_VERIFIED
        ok = status is V.VERIFIED
        fields = dict(
            status=status,
            verifier_id="probe.gate-verifier",
            gate_id=request.gate_id,
            gate_digest=request.gate_digest,
            readiness_policy_ref=request.readiness_policy_ref,
            tenant_id=request.tenant_id,
            subject_id=request.subject_id,
            context_digest=request.context_digest,
            requested_target=request.requested_target,
            verified_at=request.evaluation_time,
            verified_status=request.claimed_status if ok else None,
            evidence_verified=ok,
            benchmark_resolved=ok,
            threshold_evaluation_verified=ok,
        )
        fields.update(self.overrides)
        return GateResultVerification(**fields)

    def verify_condition(self, request):
        self.calls.append(request)
        ok = self.status is V.VERIFIED
        fields = dict(
            status=self.status,
            verifier_id="probe.condition-verifier",
            condition_id=request.condition_id,
            condition_digest=request.condition_digest,
            source_gate_or_finding_ref=request.source_gate_or_finding_ref,
            covered_gate_id=request.covered_gate_id,
            gate_digest=request.gate_digest,
            readiness_policy_ref=request.readiness_policy_ref,
            tenant_id=request.tenant_id,
            subject_id=request.subject_id,
            context_digest=request.context_digest,
            requested_target=request.requested_target,
            verified_at=request.evaluation_time,
            verified_status=request.claimed_status if ok else None,
            approval_authority_verified=ok,
            approval_evidence_verified=ok,
            owner_and_monitoring_verified=ok,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
            expiry=request.expiry,
        )
        fields.update(self.overrides)
        return ConditionSetVerification(**fields)


def result(gid, status, target=ReadinessTarget.PRODUCTION, policy=POLICY, ref=None):
    return GateResult(
        policy_gate={g.gate_id: g for g in policy.gates}[gid],
        readiness_policy_ref=ref or policy.reference,
        requested_target=target,
        status=status,
    )


def condition(cid="probe-cond", source="c1", status=ConditionStatus.APPROVED_ACTIVE):
    kw = dict(
        condition_id=cid,
        source_gate_or_finding_ref=source,
        concern_requirement_class=RequirementClass.CONDITIONAL,
        current_status=status,
        effective_from=T_FROM,
    )
    if status is ConditionStatus.APPROVED_ACTIVE:
        kw.update(
            approved_mitigation_ref="m",
            approving_authority_ref="auth",
            accountable_owner="owner",
            scope_exposure_limit="10%",
            monitoring_requirement="weekly",
            evidence_refs=("ev",),
            revocation_trigger="breach",
        )
    return ConditionSet(**kw)


def system_binding(ctx, tenant="t1", subject="a1", **kw):
    """The exact assessed system — structural identity only, never authenticated."""

    base = dict(
        binding_id="probe-binding",
        tenant_id=tenant,
        subject_id=subject,
        context_id=ctx.context_id,
        context_digest=ctx.canonical_digest(),
        system_id="probe-system",
        system_version="1.0.0",
        configuration_id="probe-config",
        configuration_digest=hashlib.sha256(b"probe-configuration").hexdigest(),
    )
    base.update(kw)
    return AssessedSystemBinding(**base)


def make_request(gate_results=(), conditions=(), **kwargs):
    kwargs.setdefault("context", context())
    # M-3R.3: there is exactly one orchestration path and it requires a binding,
    # so the default probe request carries one. A probe that tests the *absence*
    # of a binding passes ``system_binding=None`` explicitly.
    if "system_binding" not in kwargs:
        kwargs["system_binding"] = system_binding(
            kwargs["context"],
            tenant=kwargs.get("tenant_id", "t1"),
            subject=kwargs.get("subject_id", "a1"),
        )
    return ReadinessAssessmentRequest(
        assessment_id=kwargs.pop("assessment_id", "probe-assessment"),
        tenant_id=kwargs.pop("tenant_id", "t1"),
        subject_id=kwargs.pop("subject_id", "a1"),
        readiness_policy_ref=kwargs.pop("readiness_policy_ref", POLICY.reference),
        requested_target=kwargs.pop("requested_target", ReadinessTarget.PRODUCTION),
        evaluation_time=kwargs.pop("evaluation_time", T_MID),
        gate_results=tuple(gate_results),
        conditions=tuple(conditions),
        **kwargs,
    )


def run(request, **kwargs):
    kwargs.setdefault("policy_resolver", RESOLVER)
    kwargs.setdefault("gate_verifier", Verifier())
    kwargs.setdefault("condition_verifier", Verifier())
    return assess_readiness(request, **kwargs)


ALL_PASS = [result("m1", GateStatus.PASS), result("m2", GateStatus.PASS),
            result("c1", GateStatus.PASS)]


# --------------------------------------------------------------------------- #
# 1. Policy resolution
# --------------------------------------------------------------------------- #
@probe("no configured resolver denies, and no headline exists")
def _():
    outcome = assess_readiness(make_request(ALL_PASS))
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert outcome.classification is None
    assert outcome.evaluation is None
    assert G.POLICY_RESOLVER_NOT_CONFIGURED.value in outcome.trust_gap_codes


@probe("a resolver that always says RESOLVED cannot substitute another policy")
def _():
    other = readiness([gate("m1", RequirementClass.MANDATORY)], policy_id="probe-other")

    class Liar:
        def resolve_readiness_policy(self, *, reference, expected_tenant_id, as_of):
            return PolicyResolution(
                status=PolicyResolutionStatus.RESOLVED,
                reason=PolicyResolutionReason.RESOLVED,
                requested_coordinate=uvi_coordinate(reference),
                as_of=as_of,
                policy=other,
                record=IssuedPolicyRecord(
                    record_id="forged",
                    coordinate=uvi_coordinate(other.reference),
                    adapter_id="ugence.uvi.policy-family/v1",
                    policy_type="ReadinessPolicy",
                    policy=other,
                    policy_body_digest=DIGEST,
                    issuing_authority_id="probe.authority",
                    key_id="k",
                    signature_alg=SIGNATURE_ALG,
                    signature=b"not-a-signature",
                    approving_authority_id="a",
                    approval_ref="r",
                    approval_digest=DIGEST,
                    issued_at=T_FROM,
                ),
            )

    outcome = assess_readiness(
        make_request(ALL_PASS), policy_resolver=Liar(), gate_verifier=Verifier()
    )
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert G.POLICY_RESOLUTION_REFERENCE_MISMATCH.value in outcome.trust_gap_codes


@probe("a resolver that raises, or returns a foreign object, fails closed")
def _():
    class Exploding:
        def resolve_readiness_policy(self, **_):
            raise RuntimeError("boom")

    class Foreign:
        def resolve_readiness_policy(self, **_):
            return "RESOLVED"

    for resolver, code in (
        (Exploding(), G.POLICY_RESOLVER_ERROR),
        (Foreign(), G.POLICY_RESOLVER_MALFORMED_RESULT),
        (object(), G.POLICY_RESOLVER_MALFORMED_RESULT),
    ):
        outcome = assess_readiness(make_request(ALL_PASS), policy_resolver=resolver)
        assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
        assert code.value in outcome.trust_gap_codes


@probe("a context that does not bind the resolved policy is refused")
def _():
    outcome = run(make_request(ALL_PASS, context=context(policy=None)))
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert G.POLICY_RESOLUTION_CONTEXT_BINDING_MISMATCH.value in outcome.trust_gap_codes


@probe("a resolved policy the orchestrator refuses is never marked accepted")
def _():
    # The context binds no readiness policy: the authority resolves, the
    # orchestrator refuses, and the two facts are reported separately.
    outcome = run(make_request(ALL_PASS, context=context(policy=None)))
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert outcome.trace.policy_resolution_status is PolicyResolutionStatus.RESOLVED
    assert outcome.trace.policy_resolution_accepted is False
    assert outcome.trace.issuance_record_ref == ""
    try:
        ReadinessAssessmentOutcome(
            status=ReadinessAssessmentStatus.EVALUATED,
            trace=outcome.trace,
            evaluation=run(make_request(ALL_PASS)).evaluation,
        )
    except ReadinessAssessmentError:
        return
    raise AssertionError("an unaccepted resolution produced an EVALUATED outcome")


@probe("a misconfigured verifier is never quieter than an absent one")
def _():
    class BrokenGate:
        verify_gate_result = "not callable"

    class BrokenCondition:
        verify_condition = None

    empty = assess_readiness(
        make_request(), policy_resolver=RESOLVER, gate_verifier=BrokenGate()
    )
    assert G.GATE_VERIFIER_MALFORMED_RESULT.value in empty.trust_gap_codes
    conds = assess_readiness(
        make_request(
            (result("m1", GateStatus.PASS), result("c1", GateStatus.FAIL)), [condition()]
        ),
        policy_resolver=RESOLVER,
        gate_verifier=Verifier(),
        condition_verifier=BrokenCondition(),
    )
    assert G.CONDITION_VERIFIER_MALFORMED_RESULT.value in conds.trust_gap_codes


@probe("policy failure prevents every gate and condition verifier call")
def _():
    gate_verifier, condition_verifier = Verifier(), Verifier()
    outcome = assess_readiness(
        make_request(ALL_PASS, [condition()]),
        policy_resolver=None,
        gate_verifier=gate_verifier,
        condition_verifier=condition_verifier,
    )
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert gate_verifier.calls == [] and condition_verifier.calls == []


@probe("a failed assessment discloses no usable policy material")
def _():
    outcome = assess_readiness(make_request(ALL_PASS))
    assert outcome.trace.issuance_record_ref == ""
    assert outcome.trace.resolved_policy_digest == ""
    assert outcome.evaluation is None


# --------------------------------------------------------------------------- #
# 2. Gate verification and precedence
# --------------------------------------------------------------------------- #
@probe("an unverified PASS cannot unlock readiness")
def _():
    outcome = run(make_request(ALL_PASS), gate_verifier=None)
    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE
    assert outcome.trace.admitted_gate_ids == ()


@probe("an unverified FAIL cannot force NOT_READY")
def _():
    outcome = run(
        make_request([result("m1", GateStatus.FAIL), result("m2", GateStatus.PASS),
                      result("c1", GateStatus.PASS)]),
        gate_verifier=Verifier(status=V.VERIFIER_ERROR),
    )
    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE


@probe("a verified mandatory FAIL dominates an unverified required gate")
def _():
    outcome = run(
        make_request([result("m1", GateStatus.FAIL), result("m2", GateStatus.PASS),
                      result("c1", GateStatus.PASS)]),
        gate_verifier=Verifier(only={"m1"}),
    )
    assert outcome.classification is ReadinessClassification.NOT_READY
    assert outcome.trace.admitted_gate_ids == ("m1",)


@probe("all verified passes reach DEPLOYMENT_READY and PILOT_READY")
def _():
    production = run(make_request(ALL_PASS))
    assert production.classification is ReadinessClassification.DEPLOYMENT_READY

    pilot_results = [
        result(gid, GateStatus.PASS, target=ReadinessTarget.PILOT)
        for gid in ("m1", "m2", "c1")
    ]
    pilot = run(
        make_request(pilot_results, requested_target=ReadinessTarget.PILOT)
    )
    assert pilot.classification is ReadinessClassification.PILOT_READY


@probe("a missing verified required gate is NOT_ASSESSABLE")
def _():
    outcome = run(make_request([result("m1", GateStatus.PASS), result("c1", GateStatus.PASS)]))
    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE


@probe("a tampered gate body is rejected against the resolved policy")
def _():
    tampered_policy = readiness(
        [gate("m1", RequirementClass.ADVISORY)], policy_id="probe-tampered"
    )
    tampered = GateResult(
        policy_gate=tampered_policy.gates[0],
        readiness_policy_ref=POLICY.reference,
        requested_target=ReadinessTarget.PRODUCTION,
        status=GateStatus.PASS,
    )
    outcome = run(make_request([tampered, result("m2", GateStatus.PASS),
                                result("c1", GateStatus.PASS)]))
    assert G.GATE_RESULT_GATE_BODY_MISMATCH.value in outcome.trust_gap_codes
    assert outcome.classification is ReadinessClassification.NOT_ASSESSABLE


@probe("a wrong-policy gate result is rejected")
def _():
    elsewhere = PolicyReference(
        policy_id="elsewhere",
        policy_family=PolicyFamily.READINESS,
        version="1.0.0",
        content_digest=DIGEST,
    )
    outcome = run(make_request([result("m1", GateStatus.PASS, ref=elsewhere)]))
    assert G.GATE_RESULT_POLICY_REFERENCE_MISMATCH.value in outcome.trust_gap_codes


@probe("duplicate gate results reject every copy")
def _():
    outcome = run(
        make_request([result("m1", GateStatus.PASS), result("m1", GateStatus.FAIL)])
    )
    assert G.GATE_RESULT_DUPLICATE.value in outcome.trust_gap_codes
    assert outcome.trace.admitted_gate_ids == ()


@probe("a verifier attesting a different status, gate or instant is rejected")
def _():
    for override, code in (
        ({"verified_status": GateStatus.FAIL}, G.GATE_RESULT_VERIFIED_STATUS_MISMATCH),
        ({"gate_id": "somewhere-else"}, G.GATE_RESULT_VERIFICATION_BINDING_MISMATCH),
        ({"gate_digest": DIGEST}, G.GATE_RESULT_VERIFICATION_BINDING_MISMATCH),
        ({"tenant_id": "another"}, G.GATE_RESULT_VERIFICATION_BINDING_MISMATCH),
        ({"context_digest": DIGEST}, G.GATE_RESULT_VERIFICATION_BINDING_MISMATCH),
        (
            {"verified_at": T_MID + timedelta(seconds=1)},
            G.GATE_RESULT_VERIFICATION_BINDING_MISMATCH,
        ),
    ):
        outcome = run(make_request(ALL_PASS), gate_verifier=Verifier(overrides=override))
        assert code.value in outcome.trust_gap_codes, override
        assert outcome.classification is not ReadinessClassification.DEPLOYMENT_READY


@probe("a non-VERIFIED attestation cannot claim a verified status")
def _():
    try:
        GateResultVerification(
            status=V.EVIDENCE_NOT_VERIFIED,
            verifier_id="v",
            gate_id="m1",
            gate_digest=DIGEST,
            readiness_policy_ref=POLICY.reference,
            tenant_id="t1",
            subject_id="a1",
            context_digest=DIGEST,
            requested_target=ReadinessTarget.PRODUCTION,
            verified_at=T_MID,
            verified_status=GateStatus.PASS,
        )
    except ReadinessAssessmentError:
        return
    raise AssertionError("a non-VERIFIED attestation carried a verified status")


# --------------------------------------------------------------------------- #
# 3. Conditions
# --------------------------------------------------------------------------- #
UNRESOLVED = [result("m1", GateStatus.PASS), result("m2", GateStatus.PASS),
              result("c1", GateStatus.FAIL)]


@probe("an unverified condition cannot compensate")
def _():
    outcome = run(make_request(UNRESOLVED, [condition()]), condition_verifier=None)
    assert outcome.classification is ReadinessClassification.NOT_READY
    assert outcome.trace.admitted_condition_ids == ()


@probe("a verified active condition compensates only its exact concern")
def _():
    covered = run(make_request(UNRESOLVED, [condition()]))
    assert covered.classification is ReadinessClassification.READY_WITH_CONDITIONS

    wrong_gate = run(make_request(UNRESOLVED, [condition(source="m1")]))
    assert wrong_gate.classification is not ReadinessClassification.READY_WITH_CONDITIONS
    assert G.CONDITION_CONCERN_NOT_CONDITIONAL.value in wrong_gate.trust_gap_codes


@probe("a mandatory concern remains non-waivable")
def _():
    outcome = run(
        make_request(
            [result("m1", GateStatus.FAIL), result("m2", GateStatus.PASS),
             result("c1", GateStatus.PASS)],
            [condition(source="m1")],
        )
    )
    assert outcome.classification is ReadinessClassification.NOT_READY


@probe("proposed, expired, revoked and satisfied controls provide no coverage")
def _():
    for status in (
        ConditionStatus.PROPOSED,
        ConditionStatus.EXPIRED,
        ConditionStatus.REVOKED,
        ConditionStatus.SATISFIED,
    ):
        outcome = run(make_request(UNRESOLVED, [condition(status=status)]))
        assert outcome.classification is ReadinessClassification.NOT_READY, status
        assert G.CONDITION_NOT_ACTIVE_AT_EVALUATION_TIME.value in outcome.trust_gap_codes


@probe("a spurious condition over an unknown reference cannot unlock readiness")
def _():
    outcome = run(make_request(UNRESOLVED, [condition(source="not-a-gate")]))
    assert outcome.classification is ReadinessClassification.NOT_READY
    assert G.CONDITION_CONCERN_NOT_IN_RESOLVED_POLICY.value in outcome.trust_gap_codes


@probe("a condition attestation for another tenant, subject or concern is rejected")
def _():
    for override, code in (
        ({"tenant_id": "another"}, G.CONDITION_VERIFICATION_BINDING_MISMATCH),
        ({"subject_id": "another"}, G.CONDITION_VERIFICATION_BINDING_MISMATCH),
        ({"context_digest": DIGEST}, G.CONDITION_VERIFICATION_BINDING_MISMATCH),
        ({"covered_gate_id": "m1"}, G.CONDITION_SOURCE_REFERENCE_MISMATCH),
        ({"condition_digest": DIGEST}, G.CONDITION_DIGEST_MISMATCH),
        ({"approval_authority_verified": False}, G.CONDITION_APPROVAL_NOT_VERIFIED),
    ):
        outcome = run(
            make_request(UNRESOLVED, [condition()]),
            condition_verifier=Verifier(overrides=override),
        )
        assert code.value in outcome.trust_gap_codes, override
        assert outcome.classification is ReadinessClassification.NOT_READY, override


# --------------------------------------------------------------------------- #
# 4. Indicators, evidence and the composite
# --------------------------------------------------------------------------- #
def _claim(cid):
    return MetricClaim(
        claim_id=cid,
        tenant_id="t1",
        subject_id="a1",
        metric_id="accuracy",
        value="0.95",
        governed_unit="ratio",
        source_basis=SourceBasis.REPORTED,
        transformation_method=TransformationMethod.DIRECT,
        assessment_window=AssessmentWindow(start=T_FROM, end=T_MID),
    )


def _indicators():
    common = dict(
        tenant_id="t1",
        subject_id="a1",
        context_id="probe-ctx",
        task_or_outcome_ref="task",
        requirement_class=RequirementClass.MANDATORY,
        applicable_targets=(ReadinessTarget.PRODUCTION,),
        status=GateStatus.PASS,
    )
    return (
        (IntelligenceFitnessResult(
            result_id="i1", dimension=IntelligenceDimension.ACCURACY,
            claim=_claim("ci"), **common),),
        (CapabilityReadinessResult(
            result_id="c1r", dimension=CapabilityDimension.TOOL_READINESS,
            claim=_claim("cc"), demonstration=CapabilityDemonstration.MET_THRESHOLD,
            evidence_sufficient=True, **common),),
        (AdoptionReadinessResult(
            result_id="a1r", dimension=AdoptionDimension.EXPECTED_UTILIZATION,
            claim=_claim("ca"), **common),),
    )


@probe("zero indicators with a gate-complete policy behaves exactly as GV-3R-b")
def _():
    orchestrated = run(make_request(ALL_PASS))
    standalone = evaluate_readiness(
        R.ReadinessEvaluationCase(
            case_id="probe-assessment",
            tenant_id="t1",
            subject_id="a1",
            context=context(),
            readiness_policy=POLICY,
            readiness_policy_ref=POLICY.reference,
            requested_target=ReadinessTarget.PRODUCTION,
            gate_results=tuple(ALL_PASS),
        ),
        evaluation_time=T_MID,
    )
    assert orchestrated.evaluation.canonical_digest() == standalone.canonical_digest()


@probe("evidence axes are never elevated on the way through")
def _():
    intel, cap, ado = _indicators()
    outcome = run(
        make_request(
            ALL_PASS,
            intelligence_results=intel,
            capability_results=cap,
            adoption_results=ado,
        )
    )
    for group in (
        outcome.evaluation.determination.intelligence_results,
        outcome.evaluation.determination.capability_results,
        outcome.evaluation.determination.adoption_results,
    ):
        for record in group:
            assert record.claim.source_basis is SourceBasis.REPORTED
            assert record.claim.verification_status is VerificationStatus.UNVERIFIED


@probe("composite minimum, maximum and reordering cannot affect the classification")
def _():
    def composite(score):
        return AdvisoryComposite(
            method_id="m", method_version="1", score=Decimal(score),
            scale_min=Decimal("0"), scale_max=Decimal("1"),
            component_result_refs=("r1", "r2"),
        )

    low = run(make_request(ALL_PASS, advisory_composite=composite("0")))
    high = run(make_request(ALL_PASS, advisory_composite=composite("1")))
    assert low.classification is high.classification
    assert low.evaluation.reason_codes == high.evaluation.reason_codes


# --------------------------------------------------------------------------- #
# 5. Determinism and immutability
# --------------------------------------------------------------------------- #
@probe("reordered requests yield an identical trace and digest")
def _():
    forward = run(make_request(ALL_PASS, [condition()]))
    backward = run(make_request(list(reversed(ALL_PASS)), [condition()]))
    assert forward.canonical_digest() == backward.canonical_digest()
    assert forward.trace.canonical_digest() == backward.trace.canonical_digest()
    assert forward.trust_gap_codes == backward.trust_gap_codes


@probe("caller-owned list mutation has no effect after construction")
def _():
    results = list(ALL_PASS)
    request = make_request(results)
    before = request.canonical_digest()
    results.append(result("m1", GateStatus.FAIL))
    results.clear()
    assert request.canonical_digest() == before
    assert len(request.gate_results) == 3


@probe("scalar sequence substitutes are rejected")
def _():
    base = dict(
        assessment_id="probe-assessment",
        tenant_id="t1",
        subject_id="a1",
        context=context(),
        readiness_policy_ref=POLICY.reference,
        requested_target=ReadinessTarget.PRODUCTION,
        evaluation_time=T_MID,
    )
    for field in ("gate_results", "conditions", "evidence_refs", "intelligence_results"):
        for scalar in ("m1", b"m1", bytearray(b"m1"), {"m1": 1}, 7):
            try:
                ReadinessAssessmentRequest(**base, **{field: scalar})
            except ReadinessAssessmentError:
                continue
            raise AssertionError(f"{field} accepted the scalar {scalar!r}")


@probe("naive, missing and non-datetime evaluation times are rejected")
def _():
    for value in (datetime(2026, 6, 1), "2026-06-01", 1780000000, None):
        try:
            make_request(ALL_PASS, evaluation_time=value)
        except ReadinessAssessmentError:
            continue
        raise AssertionError(f"a {type(value).__name__} evaluation time was accepted")

    field = {f.name: f for f in dataclasses.fields(ReadinessAssessmentRequest)}[
        "evaluation_time"
    ]
    assert field.default is dataclasses.MISSING
    assert field.default_factory is dataclasses.MISSING


@probe("no wall clock, randomness, uuid, environment or network is reachable")
def _():
    banned_modules = {
        "time", "random", "secrets", "uuid", "os", "socket", "http", "urllib", "requests",
        "subprocess", "threading", "asyncio",
    }
    banned_calls = {"now", "utcnow", "today", "monotonic", "perf_counter", "time_ns"}
    root = pathlib.Path(R.__file__).resolve().parent
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not {a.name.split(".")[0] for a in node.names} & banned_modules, path
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                assert node.module.split(".")[0] not in banned_modules, path
            elif isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                assert name not in banned_calls, f"{path}: {name}"


# --------------------------------------------------------------------------- #
# 6. The outcome envelope
# --------------------------------------------------------------------------- #
@probe("a direct outcome forgery claims no authority provenance")
def _():
    genuine = run(make_request(ALL_PASS))
    forged = ReadinessAssessmentOutcome(
        status=ReadinessAssessmentStatus.EVALUATED,
        trace=genuine.trace,
        evaluation=genuine.evaluation,
    )
    assert forged.authorizes_deployment is False
    assert forged.is_advisory is True
    # No field anywhere claims a signature, key or attestation of provenance.
    names = {f.name for f in dataclasses.fields(ReadinessAssessmentOutcome)}
    names |= {f.name for f in dataclasses.fields(type(genuine.trace))}
    assert not any(
        token in name for name in names for token in ("signature", "signed", "key_id", "attest")
    )


@probe("authorizes_deployment cannot be changed from False")
def _():
    outcome = run(make_request(ALL_PASS))
    for attempt in (
        lambda: setattr(outcome, "authorizes_deployment", True),
        lambda: object.__setattr__(outcome, "authorizes_deployment", True),
    ):
        try:
            attempt()
        except AttributeError:
            continue
        raise AssertionError("authorizes_deployment was reassigned")
    assert outcome.authorizes_deployment is False


@probe("a NOT_EVALUATED outcome cannot carry a classification")
def _():
    genuine = run(make_request(ALL_PASS))
    denied = assess_readiness(make_request(ALL_PASS))
    try:
        ReadinessAssessmentOutcome(
            status=ReadinessAssessmentStatus.NOT_EVALUATED,
            trace=denied.trace,
            evaluation=genuine.evaluation,
        )
    except ReadinessAssessmentError:
        return
    raise AssertionError("a NOT_EVALUATED outcome carried an evaluation result")


@probe("no financial field, ROI, money or forecast exists on any public shape")
def _():
    import enum

    from ugence_agent_value_readiness import api

    tokens = ("roi", "money", "cost", "benefit", "currency", "price", "revenue", "forecast",
              "profit", "margin", "npv", "payback")
    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for field in dataclasses.fields(obj):
                assert not any(t in field.name.lower() for t in tokens), (name, field.name)
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            for member in obj:
                assert not any(t in member.value.lower() for t in tokens), (name, member.value)
    assert "governed_value" not in sys.modules


@probe("no permissive verifier or resolver is exported or importable")
def _():
    from ugence_agent_value_readiness import api

    exported = {n for n in api.__all__ if n.endswith(("Verifier", "Resolver"))}
    assert exported == {
        "ReadinessPolicyResolver",
        "GateResultVerifier",
        "ConditionSetVerifier",
        "DenyAllReadinessPolicyResolver",
        "DenyAllGateResultVerifier",
        "DenyAllConditionSetVerifier",
        "PolicyAuthorityReadinessPolicyResolver",
    }, sorted(exported)
    for cls in (DenyAllGateResultVerifier, DenyAllConditionSetVerifier):
        assert list(inspect.signature(cls).parameters) == []
    resolution = DenyAllReadinessPolicyResolver().resolve_readiness_policy(
        reference=POLICY.reference, expected_tenant_id="", as_of=T_MID
    )
    assert resolution.status is PolicyResolutionStatus.UNRESOLVED


@probe("every trust advisory carries an explicit, honest disposition")
def _():
    outcome = run(make_request(UNRESOLVED, [condition()]))
    states = {d.advisory_code: d.state for d in outcome.dispositions}
    assert set(outcome.evaluation.advisory_codes) <= set(states)
    assert ReadinessTrustAdvisoryState.RESOLVED_BY_POLICY_RESOLUTION in states.values()
    assert ReadinessTrustAdvisoryState.RESOLVED_BY_GATE_VERIFICATION in states.values()
    assert ReadinessTrustAdvisoryState.RESOLVED_BY_CONDITION_VERIFICATION in states.values()

    denied = assess_readiness(make_request(UNRESOLVED, [condition()]))
    denied_states = {d.state for d in denied.dispositions}
    assert ReadinessTrustAdvisoryState.UNRESOLVED in denied_states
    assert ReadinessTrustAdvisoryState.RESOLVED_BY_POLICY_RESOLUTION not in denied_states


@probe("the orchestrator version is platform-neutral and claims no milestone")
def _():
    assert READINESS_ORCHESTRATOR_VERSION == "ugence.readiness-orchestration/v0.2"
    # Platform-neutral: it names a capability, never an ADR milestone. M-3R.3
    # is implemented (v0.2 carries the binding and catalog stages), but the
    # identifier still names no milestone — that is the invariant under test.
    lowered = READINESS_ORCHESTRATOR_VERSION.lower()
    for token in ("gv-3r", "gv3r", "m-3r", "m3r", "milestone"):
        assert token not in lowered, token
    assert R.__version__ == "0.4.1"
    outcome = run(make_request(ALL_PASS))
    assert outcome.trace.evaluator_formula_version == "GV-3R-b.3"
    assert outcome.evaluation.trace.formula_version == "GV-3R-b.3"


# --------------------------------------------------------------------------- #
def main() -> int:
    print(f"\n{PASSED} probe(s) held.")
    if FAILURES:
        print(f"\n{len(FAILURES)} BREACH(ES):")
        for failure in FAILURES:
            print(f"  {failure}")
        return 1
    print("All adversarial probes held.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
