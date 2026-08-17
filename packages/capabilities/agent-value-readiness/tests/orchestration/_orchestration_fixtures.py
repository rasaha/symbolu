"""Builders and **test-only** fakes for the orchestration tests.

Everything here lives under ``tests/`` on purpose. The distribution ships **no**
allow-all resolver and **no** permissive gate or condition verifier; the
deterministic stubs below exist solely so the orchestration boundary's own rules
can be exercised, and ``tests/packaging/test_dependency_boundary.py`` asserts
nothing like them leaked into ``src/``.

The readiness policy used by these tests is genuinely **issued, signed and
registered** through the shared Ugence Policy Authority's public API, so a test
that resolves it exercises the real trusted-resolution path — digest binding,
key trust, signature verification, approval re-verification, lifecycle and
effective period included — rather than a stand-in for it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ugence_governance_contracts.api import (
    AssessmentWindow,
    MetricClaim,
    SourceBasis,
    TransformationMethod,
)
from ugence_policy_authority.api import (
    AdapterRegistry,
    ApprovalEvidenceRef,
    IssuedPolicyRecord,
    ApprovalVerification,
    ApprovalVerificationStatus,
    Ed25519PolicySigner,
    InMemoryPolicyRegistry,
    KeyEntitlement,
    PolicyKeyRing,
    SigningKey,
    UviPolicyFamilyAdapter,
    default_uvi_adapters,
    issue_policy,
)
from ugence_uvi_policy_contracts.api import (
    AssessmentContext,
    ComparisonOperator,
    DomainPolicy,
    GateCategory,
    GeographyPolicy,
    GovernedThreshold,
    IntendedOutcomePolicy,
    PolicyArtifactMetadata,
    PolicyFamily,
    PolicyGate,
    PolicyLifecycleState,
    PolicyScope,
    ReadinessPolicy,
    ReadinessTarget,
    RequirementClass,
)

from ugence_agent_value_readiness.api import (
    AdoptionReadinessCatalog,
    AdoptionReadinessIndicatorDefinition,
    AssessedSystemBinding,
    CapabilityReadinessCatalog,
    CapabilityReadinessIndicatorDefinition,
    IntelligenceFitnessCatalog,
    IntelligenceFitnessIndicatorDefinition,
    ReadinessIndicatorCatalogSet,
    AdoptionDimension,
    AdoptionReadinessResult,
    CapabilityDemonstration,
    CapabilityDimension,
    CapabilityReadinessResult,
    ConditionSet,
    ConditionSetVerification,
    ConditionStatus,
    GateResult,
    GateResultVerification,
    GateStatus,
    IntelligenceDimension,
    IntelligenceFitnessResult,
    PolicyAuthorityReadinessPolicyResolver,
    ReadinessAssessmentRequest,
    ReadinessInputVerificationStatus,
)

# --------------------------------------------------------------------------- #
# Fixed instants — every test time is explicit and timezone-aware.
# --------------------------------------------------------------------------- #
T_BEFORE = datetime(2025, 6, 1, tzinfo=timezone.utc)
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_LATER = datetime(2026, 9, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
T_AFTER = datetime(2027, 6, 1, tzinfo=timezone.utc)

#: Sentinel distinguishing "not supplied" from an explicit ``None``.
_UNSET = object()

TENANT = "t1"
SUBJECT = "a1"
CONTEXT_ID = "ctx1"
ASSESSMENT_ID = "assessment-1"

PILOT = ReadinessTarget.PILOT
PROD = ReadinessTarget.PRODUCTION
BOTH = (PILOT, PROD)
MANDATORY = RequirementClass.MANDATORY
CONDITIONAL = RequirementClass.CONDITIONAL
ADVISORY = RequirementClass.ADVISORY

ISSUING_AUTHORITY = "ugence.policy-authority"
APPROVING_AUTHORITY = "ugence.governance.policy-approval-board"
APPROVAL_REF = "APPROVAL-2026-0001"
APPROVAL_DIGEST = hashlib.sha256(b"approval-artifact-bytes").hexdigest()
ARBITRARY_DIGEST = hashlib.sha256(b"arbitrary but well-formed").hexdigest()

WINDOW = AssessmentWindow(start=T_FROM, end=T_MID)
_ADAPTER = UviPolicyFamilyAdapter()


# --------------------------------------------------------------------------- #
# Policy artifacts whose content digest genuinely binds their body
# --------------------------------------------------------------------------- #
def _metadata(
    *,
    family: PolicyFamily,
    content_digest: str,
    policy_id: str,
    version: str = "1.0.0",
    scope: PolicyScope = PolicyScope.GLOBAL,
    tenant_id: str = "",
    lifecycle_state: PolicyLifecycleState = PolicyLifecycleState.APPROVED_ACTIVE,
    effective_from: Optional[datetime] = T_FROM,
    effective_to: Optional[datetime] = T_TO,
) -> PolicyArtifactMetadata:
    return PolicyArtifactMetadata(
        policy_id=policy_id,
        policy_family=family,
        version=version,
        content_digest=content_digest,
        scope=scope,
        tenant_id=tenant_id,
        lifecycle_state=lifecycle_state,
        effective_from=effective_from,
        effective_to=effective_to,
    )


def _bind_digest(cls, family, body, meta_kwargs):
    """Two passes: the projection excludes ``metadata.content_digest`` entirely."""

    draft = cls(
        metadata=_metadata(family=family, content_digest="0" * 64, **meta_kwargs), **body
    )
    digest = _ADAPTER.describe(draft).body_digest()
    return cls(metadata=_metadata(family=family, content_digest=digest, **meta_kwargs), **body)


def gate(gid, kind, applicability=BOTH, compensable=False, threshold=None,
         category=GateCategory.SAFETY) -> PolicyGate:
    return PolicyGate(
        gate_id=gid,
        category=category,
        requirement_class=kind,
        applicability=applicability,
        conditionally_compensable=compensable,
        threshold=threshold,
    )


def literal_threshold(tid="t1") -> GovernedThreshold:
    return GovernedThreshold(
        threshold_id=tid,
        governed_unit="ratio",
        comparator=ComparisonOperator.GTE,
        literal_value="0.99",
    )


def readiness_policy(
    gates=(),
    *,
    policy_id="readiness-1",
    targets=BOTH,
    **meta_kwargs,
) -> ReadinessPolicy:
    return _bind_digest(
        ReadinessPolicy,
        PolicyFamily.READINESS,
        dict(gates=tuple(gates), readiness_targets=tuple(targets)),
        dict(policy_id=policy_id, **meta_kwargs),
    )


def geography_policy(policy_id="geo-1") -> GeographyPolicy:
    return _bind_digest(
        GeographyPolicy,
        PolicyFamily.GEOGRAPHY,
        dict(jurisdiction="US-CA", reporting_currency="USD", functional_currency="USD"),
        dict(policy_id=policy_id),
    )


def domain_policy(policy_id="dom-1") -> DomainPolicy:
    return _bind_digest(
        DomainPolicy,
        PolicyFamily.DOMAIN,
        dict(governed_outcome_unit="resolved_ticket"),
        dict(policy_id=policy_id),
    )


def intended_outcome_policy(policy_id="out-1") -> IntendedOutcomePolicy:
    return _bind_digest(
        IntendedOutcomePolicy,
        PolicyFamily.INTENDED_OUTCOME,
        dict(target_outcome="reduce handling time", task_definition="triage a ticket"),
        dict(policy_id=policy_id),
    )


def context(
    policy: Optional[ReadinessPolicy],
    *,
    tenant=TENANT,
    subject=SUBJECT,
    context_id=CONTEXT_ID,
) -> AssessmentContext:
    """A context bound (or deliberately not bound) to ``policy``."""

    return AssessmentContext(
        context_id=context_id,
        tenant_id=tenant,
        subject_id=subject,
        geography_ref=geography_policy().reference,
        domain_ref=domain_policy().reference,
        intended_outcome_ref=intended_outcome_policy().reference,
        readiness_ref=policy.reference if policy is not None else None,
    )


# --------------------------------------------------------------------------- #
# A fully wired reference authority (test-only approval fake)
# --------------------------------------------------------------------------- #
@dataclass
class _ApprovalVerifier:
    """Deterministic approval verifier — test-only, never shipped."""

    def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
        return ApprovalVerification(
            verified=True,
            status=ApprovalVerificationStatus.APPROVED,
            coordinate=coordinate,
            policy_body_digest=policy_body_digest,
            approving_authority_id=APPROVING_AUTHORITY,
            approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest,
            verified_at=as_of,
        )


@dataclass
class Authority:
    """A reference authority plus the readiness resolver adapter over it."""

    signer: Ed25519PolicySigner
    key_ring: PolicyKeyRing
    registry: InMemoryPolicyRegistry
    adapters: AdapterRegistry
    issued: list = field(default_factory=list)

    def issue(self, policy, *, record_id="rec-1", issued_at=T_FROM):
        record = issue_policy(
            policy=policy,
            record_id=record_id,
            approval=ApprovalEvidenceRef(
                approval_ref=APPROVAL_REF,
                approval_digest=APPROVAL_DIGEST,
                approving_authority_id=APPROVING_AUTHORITY,
            ),
            approval_verifier=_ApprovalVerifier(),
            signer=self.signer,
            registry=self.registry,
            adapters=self.adapters,
            issued_at=issued_at,
        )
        self.issued.append(record)
        return record

    def resolver(self, **kwargs) -> PolicyAuthorityReadinessPolicyResolver:
        return PolicyAuthorityReadinessPolicyResolver(
            registry=self.registry,
            signature_verifier=self.key_ring,
            adapters=self.adapters,
            **kwargs,
        )


def make_authority() -> Authority:
    signer = Ed25519PolicySigner(
        authority_id=ISSUING_AUTHORITY,
        key_id="policy-authority-key-1",
        signing_key=SigningKey.from_seed(bytes([1]) * 32),
    )
    return Authority(
        signer=signer,
        key_ring=PolicyKeyRing(
            [signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,))]
        ),
        registry=InMemoryPolicyRegistry(),
        adapters=default_uvi_adapters(),
    )


_ISSUED: dict = {}


def issued_authority(policy: ReadinessPolicy) -> Authority:
    """Issue ``policy`` through an authority, memoized by its exact reference.

    Memoization keeps the pure-Python Ed25519 signing cost off every test while
    changing nothing observable: the registry is only ever read afterwards, and
    resolution — the operation under test — still runs in full on every call.
    """

    key = policy.reference
    authority = _ISSUED.get(key)
    if authority is None:
        authority = make_authority()
        authority.issue(policy)
        _ISSUED[key] = authority
    return authority


def issued_resolver(policy: ReadinessPolicy, **resolver_kwargs):
    """Issue ``policy`` (memoized) and return a resolver over that authority."""

    return issued_authority(policy).resolver(**resolver_kwargs)


def forged_record(policy, *, record_id="forged-rec") -> IssuedPolicyRecord:
    """A hand-assembled issuance record. Construction is **not** authenticity.

    Every field is well formed and the signature bytes are arbitrary — nothing
    signed this artifact. It exists so a test can hand the orchestrator a
    perfectly-shaped ``RESOLVED`` answer that no authority ever produced.
    """

    from ugence_policy_authority.api import SIGNATURE_ALG, uvi_coordinate

    return IssuedPolicyRecord(
        record_id=record_id,
        coordinate=uvi_coordinate(policy.reference),
        adapter_id="ugence.uvi.policy-family/v1",
        policy_type=type(policy).__name__,
        policy=policy,
        policy_body_digest=ARBITRARY_DIGEST,
        issuing_authority_id=ISSUING_AUTHORITY,
        key_id="not-a-real-key",
        signature_alg=SIGNATURE_ALG,
        signature=b"not-a-real-signature",
        approving_authority_id=APPROVING_AUTHORITY,
        approval_ref=APPROVAL_REF,
        approval_digest=APPROVAL_DIGEST,
        issued_at=T_FROM,
    )


# --------------------------------------------------------------------------- #
# Readiness inputs
# --------------------------------------------------------------------------- #
def gate_result(
    policy: ReadinessPolicy,
    gid: str,
    status: GateStatus,
    *,
    target=PROD,
    policy_ref=None,
    evidence_refs=(),
    observed_claim_refs=(),
) -> GateResult:
    owned = {g.gate_id: g for g in policy.gates}[gid]
    return GateResult(
        policy_gate=owned,
        readiness_policy_ref=policy_ref or policy.reference,
        requested_target=target,
        status=status,
        evidence_refs=evidence_refs,
        observed_claim_refs=observed_claim_refs,
    )


def condition(
    cid: str,
    source: str,
    *,
    status=ConditionStatus.APPROVED_ACTIVE,
    effective_from=T_FROM,
    effective_to=None,
    expiry=None,
) -> ConditionSet:
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


def claim(cid="c1", tenant=TENANT, subject=SUBJECT) -> MetricClaim:
    return MetricClaim(
        claim_id=cid,
        tenant_id=tenant,
        subject_id=subject,
        metric_id="accuracy",
        value="0.95",
        governed_unit="ratio",
        source_basis=SourceBasis.REPORTED,
        transformation_method=TransformationMethod.DIRECT,
        assessment_window=WINDOW,
    )


def indicators(
    target=PROD,
    tenant=TENANT,
    subject=SUBJECT,
    context_id=CONTEXT_ID,
    system_binding=None,
):
    """One applicable result for each of the three distinct indicator families.

    When ``system_binding`` is supplied every result declares it, so the results
    are admissible on the bound orchestration path. Without one they are
    catalog- and system-unbound, exactly as an M-3R.1 record was.
    """

    bound = (
        dict(
            system_binding_ref=system_binding.binding_id,
            system_binding_digest=system_binding.canonical_digest(),
        )
        if system_binding is not None
        else {}
    )
    common = dict(
        tenant_id=tenant,
        subject_id=subject,
        context_id=context_id,
        task_or_outcome_ref="task",
        requirement_class=MANDATORY,
        applicable_targets=(target,),
        status=GateStatus.PASS,
        **bound,
    )
    return (
        (
            IntelligenceFitnessResult(
                result_id="ir1",
                indicator_id="ind-int-accuracy",
                dimension=IntelligenceDimension.ACCURACY,
                claim=claim("c-int", tenant, subject),
                **common,
            ),
        ),
        (
            CapabilityReadinessResult(
                result_id="cr1",
                indicator_id="ind-cap-tools",
                dimension=CapabilityDimension.TOOL_READINESS,
                claim=claim("c-cap", tenant, subject),
                demonstration=CapabilityDemonstration.MET_THRESHOLD,
                evidence_sufficient=True,
                **common,
            ),
        ),
        (
            AdoptionReadinessResult(
                result_id="ar1",
                indicator_id="ind-ado-utilization",
                dimension=AdoptionDimension.EXPECTED_UTILIZATION,
                claim=claim("c-ado", tenant, subject),
                **common,
            ),
        ),
    )


SYSTEM_ID = "agent-sys-1"
SYSTEM_VERSION = "1.4.2"
CONFIG_ID = "cfg-prod-a"
CONFIG_DIGEST = hashlib.sha256(b"configuration-a-bytes").hexdigest()
CONFIG_DIGEST_B = hashlib.sha256(b"configuration-b-bytes").hexdigest()


def binding(
    *,
    ctx,
    tenant=TENANT,
    subject=SUBJECT,
    binding_id="bind-1",
    system_id=SYSTEM_ID,
    system_version=SYSTEM_VERSION,
    configuration_id=CONFIG_ID,
    configuration_digest=CONFIG_DIGEST,
    **kwargs,
) -> AssessedSystemBinding:
    """The exact assessed system for ``ctx`` — structural, never authenticated."""

    return AssessedSystemBinding(
        binding_id=binding_id,
        tenant_id=tenant,
        subject_id=subject,
        context_id=ctx.context_id,
        context_digest=ctx.canonical_digest(),
        system_id=system_id,
        system_version=system_version,
        configuration_id=configuration_id,
        configuration_digest=configuration_digest,
        **kwargs,
    )


def catalogs(
    *,
    target=PROD,
    tenant="",
    intelligence=True,
    capability=True,
    adoption=True,
    metric_id="accuracy",
) -> ReadinessIndicatorCatalogSet:
    """A catalog set recognizing exactly the :func:`indicators` definitions."""

    intel = (
        IntelligenceFitnessCatalog(
            catalog_id="cat-int",
            catalog_version="1.0.0",
            tenant_id=tenant,
            entries=(
                IntelligenceFitnessIndicatorDefinition(
                    indicator_id="ind-int-accuracy",
                    dimension=IntelligenceDimension.ACCURACY,
                    metric_id=metric_id,
                    task_or_outcome_ref="task",
                    applicable_targets=(target,),
                ),
            ),
        )
        if intelligence
        else None
    )
    cap = (
        CapabilityReadinessCatalog(
            catalog_id="cat-cap",
            catalog_version="1.0.0",
            tenant_id=tenant,
            entries=(
                CapabilityReadinessIndicatorDefinition(
                    indicator_id="ind-cap-tools",
                    dimension=CapabilityDimension.TOOL_READINESS,
                    metric_id=metric_id,
                    task_or_outcome_ref="task",
                    applicable_targets=(target,),
                ),
            ),
        )
        if capability
        else None
    )
    ado = (
        AdoptionReadinessCatalog(
            catalog_id="cat-ado",
            catalog_version="1.0.0",
            tenant_id=tenant,
            entries=(
                AdoptionReadinessIndicatorDefinition(
                    indicator_id="ind-ado-utilization",
                    dimension=AdoptionDimension.EXPECTED_UTILIZATION,
                    metric_id=metric_id,
                    task_or_outcome_ref="task",
                    applicable_targets=(target,),
                ),
            ),
        )
        if adoption
        else None
    )
    return ReadinessIndicatorCatalogSet(
        intelligence=intel, capability=cap, adoption=ado
    )


def request(
    *,
    policy: ReadinessPolicy,
    gate_results=(),
    conditions=(),
    target=PROD,
    ctx=None,
    tenant=TENANT,
    subject=SUBJECT,
    evaluation_time=T_MID,
    with_indicators=False,
    composite=None,
    policy_ref=None,
    assessment_id=ASSESSMENT_ID,
    evidence_refs=(),
    system_binding=_UNSET,
    indicator_catalogs=_UNSET,
) -> ReadinessAssessmentRequest:
    ctx = ctx if ctx is not None else context(policy, tenant=tenant, subject=subject)
    # The bound path is the only path, so the default request carries a valid
    # binding. A test proves a *missing* binding by passing ``system_binding=None``.
    if system_binding is _UNSET:
        system_binding = binding(ctx=ctx, tenant=tenant, subject=subject)
    if indicator_catalogs is _UNSET:
        indicator_catalogs = catalogs(target=target) if with_indicators else None
    intel = cap = ado = ()
    if with_indicators:
        intel, cap, ado = indicators(
            target=target,
            tenant=tenant,
            subject=subject,
            context_id=ctx.context_id,
            system_binding=system_binding,
        )
    return ReadinessAssessmentRequest(
        assessment_id=assessment_id,
        tenant_id=tenant,
        subject_id=subject,
        context=ctx,
        readiness_policy_ref=policy_ref or policy.reference,
        requested_target=target,
        evaluation_time=evaluation_time,
        gate_results=tuple(gate_results),
        conditions=tuple(conditions),
        intelligence_results=intel,
        capability_results=cap,
        adoption_results=ado,
        advisory_composite=composite,
        evidence_refs=tuple(evidence_refs),
        system_binding=system_binding,
        indicator_catalogs=indicator_catalogs,
    )


# --------------------------------------------------------------------------- #
# Test-only verifiers. Nothing resembling these ships in the distribution.
# --------------------------------------------------------------------------- #
@dataclass
class StubGateVerifier:
    """Echoes the requested binding back as ``VERIFIED``, unless told otherwise.

    ``overrides`` mutates exactly one returned coordinate so a test can prove
    the orchestrator rechecks it independently rather than trusting the answer.
    """

    status: ReadinessInputVerificationStatus = ReadinessInputVerificationStatus.VERIFIED
    verifier_id: str = "test.gate-verifier"
    overrides: dict = field(default_factory=dict)
    only_gate_ids: Optional[frozenset] = None
    raises: bool = False
    returns_foreign_object: bool = False
    calls: list = field(default_factory=list)

    def verify_gate_result(self, request):
        self.calls.append(request)
        if self.raises:
            raise RuntimeError("verifier exploded")
        if self.returns_foreign_object:
            return {"status": "VERIFIED"}
        status = self.status
        if self.only_gate_ids is not None and request.gate_id not in self.only_gate_ids:
            status = ReadinessInputVerificationStatus.EVIDENCE_NOT_VERIFIED
        verified = status is ReadinessInputVerificationStatus.VERIFIED
        fields = dict(
            status=status,
            verifier_id=self.verifier_id,
            gate_id=request.gate_id,
            gate_digest=request.gate_digest,
            readiness_policy_ref=request.readiness_policy_ref,
            tenant_id=request.tenant_id,
            subject_id=request.subject_id,
            context_digest=request.context_digest,
            requested_target=request.requested_target,
            verified_at=request.evaluation_time,
            verified_status=request.claimed_status if verified else None,
            evidence_verified=verified,
            benchmark_resolved=verified,
            threshold_evaluation_verified=verified,
        )
        fields.update(self.overrides)
        return GateResultVerification(**fields)


@dataclass
class StubConditionVerifier:
    """Echoes the requested binding back as ``VERIFIED``, unless told otherwise."""

    status: ReadinessInputVerificationStatus = ReadinessInputVerificationStatus.VERIFIED
    verifier_id: str = "test.condition-verifier"
    overrides: dict = field(default_factory=dict)
    only_condition_ids: Optional[frozenset] = None
    raises: bool = False
    returns_foreign_object: bool = False
    calls: list = field(default_factory=list)

    def verify_condition(self, request):
        self.calls.append(request)
        if self.raises:
            raise RuntimeError("verifier exploded")
        if self.returns_foreign_object:
            return object()
        status = self.status
        if (
            self.only_condition_ids is not None
            and request.condition_id not in self.only_condition_ids
        ):
            status = ReadinessInputVerificationStatus.APPROVAL_NOT_VERIFIED
        verified = status is ReadinessInputVerificationStatus.VERIFIED
        fields = dict(
            status=status,
            verifier_id=self.verifier_id,
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
            verified_status=request.claimed_status if verified else None,
            approval_authority_verified=verified,
            approval_evidence_verified=verified,
            owner_and_monitoring_verified=verified,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
            expiry=request.expiry,
        )
        fields.update(self.overrides)
        return ConditionSetVerification(**fields)


@dataclass
class RecordingResolver:
    """Wraps a resolver and records every call, or returns a canned answer."""

    inner: object = None
    answer: object = None
    raises: bool = False
    returns_foreign_object: bool = False
    calls: list = field(default_factory=list)

    def resolve_readiness_policy(self, *, reference, expected_tenant_id, as_of):
        self.calls.append((reference, expected_tenant_id, as_of))
        if self.raises:
            raise RuntimeError("resolver exploded")
        if self.returns_foreign_object:
            return "RESOLVED"
        if self.answer is not None:
            return self.answer
        return self.inner.resolve_readiness_policy(
            reference=reference, expected_tenant_id=expected_tenant_id, as_of=as_of
        )
