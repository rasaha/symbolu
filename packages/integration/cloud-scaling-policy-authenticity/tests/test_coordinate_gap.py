"""ADR residual R-3, closed at this boundary: the coordinate must name the body that was signed.

The measured defect
-------------------
``issue_policy`` enforces two digest equalities: ``declared_content_digest ==
policy_body_digest`` **and** ``coordinate.content_digest == policy_body_digest``.
``resolve_policy`` re-enforces only the first. A registered record whose coordinate carries a
content digest other than its signed body digest therefore resolves ``RESOLVED/RESOLVED``,
while ``issue_policy`` would refuse the same artifact outright.

It is **not reachable through the shipped UVI adapter**, which derives both values from the
same ``metadata.content_digest`` and cannot decouple them. Reproducing it requires a synthetic
adapter that deliberately does, which is what this module builds — a real defect of the core
*resolution* contract, latent under the current adapter set.

Why 5B-0B closes it here rather than waiting
---------------------------------------------
D-5B0B-2 rules that ``policy_body_digest`` is the content binding. A record whose coordinate
names one body while its signature covers another would let a verified proof carry a
coordinate that addresses a policy nobody signed — the exact confusion the coordinate exists
to prevent. Fixing the authority's resolution contract is the Policy Authority's work and is
out of this phase's scope; refusing the record at this boundary is not, and is what these
tests pin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from _authority_fixtures import APPROVAL_DIGEST, APPROVAL_REF, APPROVING_AUTHORITY, T_FROM, T_MID, T_TO
from _policy_fixtures import make_authority
from ugence_policy_authority.api import (
    AdapterRegistry,
    IssuedPolicyRecord,
    PolicyArtifactDescriptor,
    PolicyCoordinate,
    PolicyResolutionStatus,
    framed_body_digest,
    issuance_signing_payload,
    resolve_policy,
)

from ugence_cloud_scaling_policy_authenticity import (
    PolicyAuthenticityOutcome as O,
    PolicyAuthenticityVerifier,
    PolicyAuthorityResolutionPort,
)

_ADAPTER_ID = "test.decoupled-digest-adapter/v1"
_POLICY_TYPE = "DecoupledPolicy"
#: A syntactically perfect digest that binds nothing. It is what the coordinate will carry.
_UNBOUND_DIGEST = "b" * 64


@dataclass(frozen=True)
class DecoupledPolicy:
    """A synthetic family artifact whose coordinate digest is not its body digest."""

    policy_id: str = "decoupled-1"
    version: str = "1.0.0"
    limit: int = 7


class DecoupledAdapter:
    """A deliberately non-conforming adapter. Not shipped, and not a supported posture."""

    adapter_id = _ADAPTER_ID

    def recognizes(self, artifact: object) -> bool:
        return type(artifact) is DecoupledPolicy

    def projection(self, artifact: DecoupledPolicy) -> dict:
        return {"policy_id": artifact.policy_id, "version": artifact.version,
                "limit": artifact.limit}

    def body_digest(self, artifact: DecoupledPolicy) -> str:
        return framed_body_digest(
            adapter_id=_ADAPTER_ID,
            policy_type=_POLICY_TYPE,
            projection=self.projection(artifact),
        )

    def coordinate(self, artifact: DecoupledPolicy) -> PolicyCoordinate:
        # The decoupling, in one line: the coordinate carries a digest the body does not.
        return PolicyCoordinate(
            policy_family="decoupled",
            policy_id=artifact.policy_id,
            version=artifact.version,
            content_digest=_UNBOUND_DIGEST,
            scope="GLOBAL",
            tenant_id="",
        )

    def describe(self, artifact: DecoupledPolicy) -> PolicyArtifactDescriptor:
        return PolicyArtifactDescriptor(
            adapter_id=_ADAPTER_ID,
            policy_type=_POLICY_TYPE,
            coordinate=self.coordinate(artifact),
            # Equal to the body digest, so resolution's one digest check passes...
            declared_content_digest=self.body_digest(artifact),
            canonical_projection=self.projection(artifact),
            lifecycle_label="APPROVED_ACTIVE",
            lifecycle_is_active=True,
            effective_from=T_FROM,
            effective_to=T_TO,
        )

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        return reference if isinstance(reference, PolicyCoordinate) else None


def _register_decoupled_record(authority):
    """Hand-assemble a correctly signed record under the decoupled adapter, and register it.

    Every signature here is genuine. The record is refused by ``issue_policy`` and accepted
    by ``resolve_policy``; that asymmetry is the residual.
    """

    adapter = DecoupledAdapter()
    policy = DecoupledPolicy()
    coordinate = adapter.coordinate(policy)
    body_digest = adapter.body_digest(policy)
    assert coordinate.content_digest != body_digest

    payload = issuance_signing_payload(
        record_id="decoupled-rec-1",
        coordinate=coordinate,
        adapter_id=_ADAPTER_ID,
        policy_body_digest=body_digest,
        approving_authority_id=APPROVING_AUTHORITY,
        approval_ref=APPROVAL_REF,
        approval_digest=APPROVAL_DIGEST,
        issuing_authority_id=authority.signer.authority_id,
        key_id=authority.signer.key_id,
        signature_alg=authority.signer.signature_alg,
        issued_at=T_FROM,
    )
    record = IssuedPolicyRecord(
        record_id="decoupled-rec-1",
        coordinate=coordinate,
        adapter_id=_ADAPTER_ID,
        policy_type=_POLICY_TYPE,
        policy=policy,
        policy_body_digest=body_digest,
        issuing_authority_id=authority.signer.authority_id,
        key_id=authority.signer.key_id,
        signature_alg=authority.signer.signature_alg,
        signature=authority.signer.sign(payload),
        approving_authority_id=APPROVING_AUTHORITY,
        approval_ref=APPROVAL_REF,
        approval_digest=APPROVAL_DIGEST,
        issued_at=T_FROM,
    )
    authority.registry.append_issuance(record)
    return adapter, record


@pytest.mark.invariant
def test_the_authority_still_resolves_the_decoupled_record_this_is_the_residual():
    """The measurement, stated as a test so the residual cannot quietly change under us.

    If a future Policy Authority closes R-3, this test fails — and that is the signal to
    delete the gate below, not to weaken this assertion.
    """

    authority = make_authority()
    adapter, record = _register_decoupled_record(authority)
    resolution = resolve_policy(
        reference=record.coordinate,
        expected_reference_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=authority.key_ring,
        adapters=AdapterRegistry((adapter,)),
    )
    assert resolution.status is PolicyResolutionStatus.RESOLVED
    assert resolution.record.coordinate.content_digest != resolution.record.policy_body_digest


@pytest.mark.adversarial
def test_this_boundary_refuses_a_coordinate_that_does_not_name_its_own_signed_body():
    authority = make_authority()
    adapter, record = _register_decoupled_record(authority)
    port = PolicyAuthorityResolutionPort(
        registry=authority.registry,
        signature_verifier=authority.key_ring,
        adapters=AdapterRegistry((adapter,)),
    )
    result = PolicyAuthenticityVerifier(resolution_port=port).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id="",
        as_of=T_MID,
    )
    assert result.outcome is O.COORDINATE_DIGEST_UNBOUND
    assert result.verified_policy is None


@pytest.mark.adversarial
def test_the_same_artifact_is_refused_by_issuance_which_is_why_resolution_should_refuse_it():
    """``issue_policy`` refuses what ``resolve_policy`` accepts. That gap is the whole point."""

    from ugence_policy_authority.api import PolicyDigestMismatchError, issue_policy

    from _authority_fixtures import RecordingApprovalVerifier, approval_evidence

    authority = make_authority()
    adapter = DecoupledAdapter()
    with pytest.raises(PolicyDigestMismatchError):
        issue_policy(
            policy=DecoupledPolicy(),
            record_id="decoupled-rec-2",
            approval=approval_evidence(),
            approval_verifier=RecordingApprovalVerifier(),
            signer=authority.signer,
            registry=authority.registry,
            adapters=AdapterRegistry((adapter,)),
            issued_at=T_FROM,
        )
