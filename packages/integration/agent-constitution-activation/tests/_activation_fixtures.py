"""Deterministic builders for the issuance & activation suite.

Named ``_activation_fixtures`` rather than ``_fixtures`` so a combined
multi-package pytest run cannot shadow another package's fixtures.

**Every key here is ephemeral** (`ACC-IA-2`). The Ed25519 seeds are drawn from
process randomness at run time — ``os.urandom`` — never from a committed
constant, and the approval evidence is random bytes minted the same way, hashed
at run time by a verifier that checks the digest against the bytes it actually
holds. Nothing key-shaped or evidence-shaped exists in this repository; a
re-run mints a different world.

**The constitution is the ratified one.** The content values below are exactly
the `ACC-FC-2`..`ACC-FC-4` table: identity, GLOBAL scope with the canonical
empty tenant, the single governed role reference, the full closed vocabularies
(derived from the source enums, never restated), and the two-scope tool
ceiling. The effective window opens at the issuance instant and is unbounded
(`effective_to=None`), which is the ratified window rule.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import ugence_agentic_proposer as ap
from _authority_fixtures import RecordingApprovalVerifier
from ugence_agent_constitution_activation import ActivationRoot, build_activation_root
from ugence_agent_constitution_policy import (
    LIFECYCLE_APPROVED_ACTIVE,
    PLACEHOLDER_CONTENT_DIGEST,
    POLICY_SCOPE_GLOBAL,
    AgentConstitutionPolicy,
    AgentConstitutionPolicyFamilyAdapter,
    AgentConstitutionPolicyMetadata,
    agent_constitution_coordinate,
)
from ugence_policy_authority.api import (
    GLOBAL_TENANT,
    ApprovalEvidenceRef,
    ApprovalVerification,
    ApprovalVerificationStatus,
    Ed25519PolicySigner,
    InMemoryPolicyRegistry,
    KeyEntitlement,
    PolicyKeyRing,
    PolicyRevocationReasonCode,
    SigningKey,
    revoke_policy,
)

# --------------------------------------------------------------------------- #
# Fixed instants — every test time is explicit and timezone-aware.
# --------------------------------------------------------------------------- #
T_ISSUE = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)
T_ACTIVATE = T_ISSUE + timedelta(minutes=5)
T_RESOLVE = T_ISSUE + timedelta(hours=1)

# --------------------------------------------------------------------------- #
# The ratified ACC-FC content values (the §2 table of the pinned content
# specification, ratified whole by ACC-FC-2..ACC-FC-4).
# --------------------------------------------------------------------------- #
POLICY_ID = "agent-constitution-ugence"
POLICY_VERSION = "1.0.0"
CONSTITUTION_REF = "ugence.agent-constitution/ugence/baseline/v1"
GOVERNED_ROLE_REF = "ugence.roles/ugence/invoice-reconciler/v1"
TOOL_SCOPES_BOUND = ("invoice.read", "ledger.read")

#: The full closed vocabularies, derived from the imported enums, never restated.
DISPOSITIONS_BOUND = tuple(sorted(m.value for m in ap.CandidateDisposition))
REVIEW_ACTIONS_BOUND = tuple(sorted(m.value for m in ap.ReviewAction))

ISSUING_AUTHORITY = "ugence.policy-authority"
APPROVING_AUTHORITY = "ugence.governance.policy-approval-board"
REVOKING_AUTHORITY = "ugence.policy-authority.revocation"

ADAPTER = AgentConstitutionPolicyFamilyAdapter()


# --------------------------------------------------------------------------- #
# Ephemeral custody — minted at run time, discarded with the process
# --------------------------------------------------------------------------- #


def make_ephemeral_signer(
    *, authority_id: str = ISSUING_AUTHORITY, key_id: str = "issuance-key-1"
) -> Ed25519PolicySigner:
    """A real Ed25519 signer over a seed drawn from process randomness."""

    return Ed25519PolicySigner(
        authority_id=authority_id,
        key_id=key_id,
        signing_key=SigningKey.from_seed(os.urandom(32)),
    )


def make_runtime_approval() -> tuple:
    """Approval evidence whose digest binds bytes minted at run time.

    Returns ``(evidence_ref, verifier)``: the reference carries the sha-256 of
    random artifact bytes, and the verifier holds those bytes and answers
    APPROVED only when the presented digest matches what the bytes it holds
    actually hash to — a genuine digest check, not an echo.
    """

    artifact_bytes = os.urandom(48)
    evidence = ApprovalEvidenceRef(
        approval_ref="APPROVAL-RUNTIME-1",
        approval_digest=hashlib.sha256(artifact_bytes).hexdigest(),
        approving_authority_id=APPROVING_AUTHORITY,
    )
    return evidence, EvidenceBackedApprovalVerifier(
        artifacts={evidence.approval_ref: artifact_bytes}
    )


@dataclass
class EvidenceBackedApprovalVerifier:
    """A verifier that re-hashes the evidence bytes it actually holds.

    Test support, deliberately under ``tests/``: production ships only the
    deny-by-default verifier. ``artifacts`` maps ``approval_ref`` to the raw
    artifact bytes; a reference it does not hold, or a digest the held bytes do
    not hash to, is not approval.
    """

    artifacts: dict
    approving_authority_id: str = APPROVING_AUTHORITY

    def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
        held = self.artifacts.get(approval.approval_ref)
        genuine = (
            held is not None
            and hashlib.sha256(held).hexdigest() == approval.approval_digest
            and approval.approving_authority_id == self.approving_authority_id
        )
        return ApprovalVerification(
            verified=genuine,
            status=(
                ApprovalVerificationStatus.APPROVED
                if genuine
                else ApprovalVerificationStatus.UNVERIFIED
            ),
            coordinate=coordinate,
            policy_body_digest=policy_body_digest,
            approving_authority_id=self.approving_authority_id,
            approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest,
            verified_at=as_of,
        )


# --------------------------------------------------------------------------- #
# The constitution artifact — the ratified content, digest-bound in two passes
# --------------------------------------------------------------------------- #


def _metadata(content_digest: str, **overrides) -> AgentConstitutionPolicyMetadata:
    fields = dict(
        policy_id=POLICY_ID,
        version=POLICY_VERSION,
        content_digest=content_digest,
        scope=POLICY_SCOPE_GLOBAL,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
        tenant_id=GLOBAL_TENANT,
        effective_from=T_ISSUE,
        effective_to=None,
    )
    fields.update(overrides)
    return AgentConstitutionPolicyMetadata(**fields)


def make_first_constitution(
    *,
    agent_constitution_ref: str = CONSTITUTION_REF,
    governed_role_refs=None,
    tool_scopes_bound=None,
    **meta_overrides,
) -> AgentConstitutionPolicy:
    """The first constitution, its ``content_digest`` genuinely binding its body."""

    body = dict(
        agent_constitution_ref=agent_constitution_ref,
        governed_role_refs=(
            (GOVERNED_ROLE_REF,) if governed_role_refs is None else governed_role_refs
        ),
        permitted_candidate_dispositions_bound=DISPOSITIONS_BOUND,
        permitted_review_actions_bound=REVIEW_ACTIONS_BOUND,
        permitted_tool_scopes_bound=(
            TOOL_SCOPES_BOUND if tool_scopes_bound is None else tool_scopes_bound
        ),
    )
    draft = AgentConstitutionPolicy(
        metadata=_metadata(PLACEHOLDER_CONTENT_DIGEST, **meta_overrides), **body
    )
    digest = ADAPTER.describe(draft).body_digest()
    return AgentConstitutionPolicy(metadata=_metadata(digest, **meta_overrides), **body)


def coordinate_of(policy: AgentConstitutionPolicy):
    return agent_constitution_coordinate(policy.metadata)


# --------------------------------------------------------------------------- #
# A wired world: ephemeral trust, real registry, the composition root
# --------------------------------------------------------------------------- #


@dataclass
class ActivationWorld:
    """Everything one test needs: the root, its dependencies, and the evidence."""

    root: ActivationRoot
    registry: InMemoryPolicyRegistry
    signer: Ed25519PolicySigner
    revocation_signer: Ed25519PolicySigner
    key_ring: PolicyKeyRing
    approval_verifier: object
    evidence: ApprovalEvidenceRef

    def issue_first_constitution(self, *, policy=None, record_id="rec-acc-fc-1"):
        policy = policy if policy is not None else make_first_constitution()
        receipt = self.root.issue_constitution(
            policy=policy,
            record_id=record_id,
            approval=self.evidence,
            issued_at=T_ISSUE,
        )
        return policy, receipt

    def revoke(self, coordinate, *, revoked_at=None):
        return revoke_policy(
            reference=coordinate,
            revocation_id="revocation-1",
            reason_code=PolicyRevocationReasonCode.APPROVAL_WITHDRAWN,
            registry=self.registry,
            adapters=self.root._adapters,
            signer=self.revocation_signer,
            signature_verifier=self.key_ring,
            revoked_at=revoked_at if revoked_at is not None else T_ACTIVATE,
        )


def make_world(
    *,
    approval_verifier: Optional[object] = None,
    signature_verifier: Optional[object] = None,
    key_in_ring: bool = True,
) -> ActivationWorld:
    """A fully wired world on ephemeral custody.

    ``key_in_ring=False`` builds the missing-trust posture: the signer is real,
    but the configured key ring never learned its verification key, so
    resolution cannot verify what issuance signed.
    """

    signer = make_ephemeral_signer()
    revoker = make_ephemeral_signer(
        authority_id=REVOKING_AUTHORITY, key_id="revocation-key-1"
    )
    ring_keys = [revoker.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,))]
    if key_in_ring:
        ring_keys.insert(
            0, signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,))
        )
    key_ring = PolicyKeyRing(ring_keys)
    evidence, evidence_verifier = make_runtime_approval()
    verifier = approval_verifier if approval_verifier is not None else evidence_verifier
    registry = InMemoryPolicyRegistry()
    root = build_activation_root(
        registry=registry,
        signer=signer,
        signature_verifier=(
            signature_verifier if signature_verifier is not None else key_ring
        ),
        approval_verifier=verifier,
    )
    return ActivationWorld(
        root=root,
        registry=registry,
        signer=signer,
        revocation_signer=revoker,
        key_ring=key_ring,
        approval_verifier=verifier,
        evidence=evidence,
    )


def make_recording_world():
    """A world whose approval verifier records calls, for order/dry-run proofs."""

    world = make_world(approval_verifier=RecordingApprovalVerifier())
    return world
