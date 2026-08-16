"""Deterministic builders and test-only fakes.

Everything in this module lives under ``tests/`` on purpose. The production
package ships **no** allow-all approval verifier and **no** always-valid
signature verifier; the deterministic fakes below exist solely so the authority's
own rules can be exercised, and ``tests/packaging/test_dependency_boundary.py``
asserts nothing like them leaked into ``src/``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from ugence_uvi_policy_authority.api import (
    ApprovalEvidenceRef,
    ApprovalVerification,
    ApprovalVerificationStatus,
    Ed25519PolicySigner,
    InMemoryPolicyRegistry,
    PolicyKeyRing,
    SigningKey,
    canonical_policy_body_digest,
    issue_policy,
)
from ugence_uvi_policy_contracts.api import (
    ComponentEvidenceRequirement,
    DomainPolicy,
    GateCategory,
    GeographyPolicy,
    GovernedThreshold,
    ComparisonOperator,
    IntendedOutcomePolicy,
    PolicyArtifactMetadata,
    PolicyFamily,
    PolicyGate,
    PolicyLifecycleState,
    PolicyScope,
    ReadinessPolicy,
    ReadinessTarget,
    RequirementClass,
    ValuationPolicy,
    ValueComponent,
)

# --------------------------------------------------------------------------- #
# Fixed instants — every test time is explicit and timezone-aware.
# --------------------------------------------------------------------------- #
T_BEFORE = datetime(2025, 6, 1, tzinfo=timezone.utc)
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
T_AFTER = datetime(2027, 6, 1, tzinfo=timezone.utc)

ISSUING_AUTHORITY = "ugence.uvi.policy-authority"
APPROVING_AUTHORITY = "ugence.governance.policy-approval-board"
APPROVAL_REF = "APPROVAL-2026-0001"
APPROVAL_DIGEST = hashlib.sha256(b"approval-artifact-bytes").hexdigest()

#: A syntactically perfect sha-256 hex string that binds nothing.
ARBITRARY_DIGEST = hashlib.sha256(b"arbitrary but well-formed").hexdigest()


def _metadata(
    *,
    family: PolicyFamily,
    content_digest: str,
    policy_id: str = "pol-1",
    version: str = "1.0.0",
    scope: PolicyScope = PolicyScope.GLOBAL,
    tenant_id: str = "",
    lifecycle_state: PolicyLifecycleState = PolicyLifecycleState.APPROVED_ACTIVE,
    effective_from: Optional[datetime] = T_FROM,
    effective_to: Optional[datetime] = T_TO,
    supersedes_ref: str = "",
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
        supersedes_ref=supersedes_ref,
    )


_BODIES = {
    PolicyFamily.GEOGRAPHY: (
        GeographyPolicy,
        dict(jurisdiction="US-CA", reporting_currency="USD", functional_currency="USD"),
    ),
    PolicyFamily.DOMAIN: (
        DomainPolicy,
        dict(governed_outcome_unit="resolved_ticket", criticality_class="HIGH"),
    ),
    PolicyFamily.INTENDED_OUTCOME: (
        IntendedOutcomePolicy,
        dict(target_outcome="reduce handling time", task_definition="triage a ticket"),
    ),
    PolicyFamily.VALUATION: (
        ValuationPolicy,
        dict(
            required_components=(
                ComponentEvidenceRequirement(component=ValueComponent.GROSS_BENEFIT),
            ),
        ),
    ),
    PolicyFamily.READINESS: (
        ReadinessPolicy,
        dict(
            gates=(
                PolicyGate(
                    gate_id="safety-1",
                    category=GateCategory.SAFETY,
                    requirement_class=RequirementClass.MANDATORY,
                    applicability=(ReadinessTarget.PILOT, ReadinessTarget.PRODUCTION),
                    threshold=GovernedThreshold(
                        threshold_id="t1",
                        governed_unit="ratio",
                        comparator=ComparisonOperator.GTE,
                        literal_value="0.99",
                    ),
                ),
            ),
        ),
    ),
}

ALL_FAMILIES = tuple(_BODIES)


def make_policy(
    family: PolicyFamily = PolicyFamily.DOMAIN,
    *,
    overrides: Optional[dict] = None,
    **meta_kwargs,
):
    """Build a policy whose ``content_digest`` genuinely binds its body.

    Built in two passes: the body digest excludes ``metadata.content_digest``
    entirely, so digesting a placeholder-carrying draft yields exactly the digest
    the final artifact must declare. No fixed-point iteration is involved — the
    second pass is a construction, not a re-computation.
    """

    cls, body = _BODIES[family]
    body = dict(body)
    if overrides:
        body.update(overrides)

    draft = cls(metadata=_metadata(family=family, content_digest="0" * 64, **meta_kwargs), **body)
    digest = canonical_policy_body_digest(draft)
    return cls(metadata=_metadata(family=family, content_digest=digest, **meta_kwargs), **body)


# --------------------------------------------------------------------------- #
# Test-only fakes
# --------------------------------------------------------------------------- #
@dataclass
class RecordingApprovalVerifier:
    """A deterministic verifier that records every call it received.

    ``calls`` lets a test prove the verifier was **not** reached when an earlier
    structural stage failed.
    """

    status: ApprovalVerificationStatus = ApprovalVerificationStatus.APPROVED
    approving_authority_id: str = APPROVING_AUTHORITY
    approved_from: Optional[datetime] = None
    approved_to: Optional[datetime] = None
    override_reference = None
    override_body_digest: Optional[str] = None
    calls: list = field(default_factory=list)

    def verify_approval(self, *, policy_reference, policy_body_digest, approval, as_of):
        self.calls.append((policy_reference, policy_body_digest, approval, as_of))
        return ApprovalVerification(
            verified=self.status is ApprovalVerificationStatus.APPROVED,
            status=self.status,
            policy_reference=self.override_reference or policy_reference,
            policy_body_digest=self.override_body_digest or policy_body_digest,
            approving_authority_id=self.approving_authority_id,
            approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest,
            verified_at=as_of,
            approved_from=self.approved_from,
            approved_to=self.approved_to,
        )


@dataclass
class RecordingSigner:
    """Wraps a real signer and records whether it was ever asked to sign."""

    inner: Ed25519PolicySigner
    calls: list = field(default_factory=list)

    @property
    def authority_id(self) -> str:
        return self.inner.authority_id

    @property
    def key_id(self) -> str:
        return self.inner.key_id

    @property
    def signature_alg(self) -> str:
        return self.inner.signature_alg

    def sign(self, payload: bytes) -> bytes:
        self.calls.append(payload)
        return self.inner.sign(payload)


def make_signer(
    *, authority_id: str = ISSUING_AUTHORITY, key_id: str = "uvi-pa-key-1", seed: int = 1
) -> Ed25519PolicySigner:
    return Ed25519PolicySigner(
        authority_id=authority_id,
        key_id=key_id,
        signing_key=SigningKey.from_seed(bytes([seed]) * 32),
    )


def make_key_ring(signer: Ed25519PolicySigner, **kwargs) -> PolicyKeyRing:
    return PolicyKeyRing().with_key(signer.verification_key(**kwargs))


def approval_evidence(
    *, approving_authority_id: str = APPROVING_AUTHORITY, approval_ref: str = APPROVAL_REF
) -> ApprovalEvidenceRef:
    return ApprovalEvidenceRef(
        approval_ref=approval_ref,
        approval_digest=APPROVAL_DIGEST,
        approving_authority_id=approving_authority_id,
    )


@dataclass
class Authority:
    """A fully wired reference authority for a test."""

    signer: Ed25519PolicySigner
    key_ring: PolicyKeyRing
    registry: InMemoryPolicyRegistry
    approval: RecordingApprovalVerifier

    def issue(self, policy, *, record_id="rec-1", issued_at=T_MID, evidence=None, **kwargs):
        return issue_policy(
            policy=policy,
            record_id=record_id,
            approval=evidence or approval_evidence(),
            approval_verifier=self.approval,
            signer=self.signer,
            registry=self.registry,
            issued_at=issued_at,
            **kwargs,
        )


def make_authority(**signer_kwargs) -> Authority:
    signer = make_signer(**signer_kwargs)
    return Authority(
        signer=signer,
        key_ring=make_key_ring(signer),
        registry=InMemoryPolicyRegistry(),
        approval=RecordingApprovalVerifier(),
    )


def registry_snapshot(registry: InMemoryPolicyRegistry) -> tuple:
    """A comparable snapshot proving a failed operation mutated nothing."""

    from ugence_uvi_policy_authority.canonical import canonical_bytes

    return (
        tuple(sorted(canonical_bytes(r) for r in registry._issued.values())),
        tuple(sorted(canonical_bytes(r) for r in registry._revocations.values())),
    )


ONE_SECOND = timedelta(seconds=1)
