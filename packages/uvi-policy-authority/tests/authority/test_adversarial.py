"""Anti-gaming proofs: what an untrusted caller cannot do (GV-2C-b §14).

Each test takes the position of a caller who holds the public entry points and
wants a policy treated as valid that should not be. Every one of them fails
closed.
"""

from __future__ import annotations

import dataclasses
from dataclasses import replace

import pytest

from _authority_fixtures import (
    APPROVING_AUTHORITY,
    ARBITRARY_DIGEST,
    ISSUING_AUTHORITY,
    ONE_SECOND,
    T_AFTER,
    T_MID,
    T_TO,
    approval_evidence,
    make_authority,
    make_policy,
    make_signer,
    registry_snapshot,
)
from ugence_uvi_policy_authority.api import (
    ApprovalVerification,
    ApprovalVerificationStatus,
    DenyAllApprovalVerifier,
    DenyAllSignatureVerifier,
    IssuedPolicyRecord,
    PolicyApprovalError,
    PolicyAuthorityRequestError,
    PolicyDigestMismatchError,
    PolicyIssuanceError,
    PolicyRegistryConflictError,
    PolicyResolutionReason,
    PolicyRevocationReasonCode,
    UnsupportedPolicyFamilyError,
    issue_policy,
    resolve_policy,
    revoke_policy,
)
from ugence_uvi_policy_contracts.api import (
    PolicyFamily,
    PolicyLifecycleState,
    PolicyScope,
)


def _resolve(authority, reference, *, as_of=T_MID, tenant="", **kwargs):
    return resolve_policy(
        reference=reference,
        expected_tenant_id=tenant,
        as_of=as_of,
        registry=authority.registry,
        signature_verifier=authority.key_ring,
        **kwargs,
    )


# 1 -------------------------------------------------------------------------
def test_a_caller_cannot_self_approve():
    """No boolean, no name, no label, and not by naming itself the approver."""

    authority = make_authority()
    policy = make_policy()

    # (a) there is no `approved` parameter at all
    with pytest.raises(TypeError):
        issue_policy(
            policy=policy,
            record_id="r",
            approved=True,
            approval_verifier=authority.approval,
            signer=authority.signer,
            registry=authority.registry,
            issued_at=T_MID,
        )
    # (b) a bare authority name is not evidence
    with pytest.raises(PolicyAuthorityRequestError):
        issue_policy(
            policy=policy,
            record_id="r",
            approval=APPROVING_AUTHORITY,
            approval_verifier=authority.approval,
            signer=authority.signer,
            registry=authority.registry,
            issued_at=T_MID,
        )
    # (c) the issuing authority naming itself the approver
    authority.approval.approving_authority_id = ISSUING_AUTHORITY
    with pytest.raises(PolicyApprovalError, match="cannot approve its own"):
        authority.issue(
            policy, evidence=approval_evidence(approving_authority_id=ISSUING_AUTHORITY)
        )
    # (d) the artifact declaring itself APPROVED_ACTIVE, with no verifier wired up
    assert policy.metadata.lifecycle_state is PolicyLifecycleState.APPROVED_ACTIVE
    with pytest.raises(PolicyApprovalError):
        issue_policy(
            policy=policy,
            record_id="r",
            approval=approval_evidence(),
            approval_verifier=DenyAllApprovalVerifier(),
            signer=authority.signer,
            registry=authority.registry,
            issued_at=T_MID,
        )
    assert registry_snapshot(authority.registry) == ((), ())


# 2 -------------------------------------------------------------------------
def test_a_caller_cannot_forge_issuance_by_constructing_a_record():
    authority = make_authority()
    policy = make_policy()
    forged = IssuedPolicyRecord(
        record_id="forged",
        policy_reference=policy.reference,
        policy_family=policy.metadata.policy_family,
        policy=policy,
        policy_body_digest=policy.metadata.content_digest,
        issuing_authority_id=ISSUING_AUTHORITY,
        key_id=authority.signer.key_id,
        signature_alg="ed25519",
        signature=b"\xaa" * 64,
        approving_authority_id=APPROVING_AUTHORITY,
        approval_ref="APPROVAL-FORGED",
        approval_digest=ARBITRARY_DIGEST,
        issued_at=T_MID,
    )
    authority.registry.append_issuance(forged)
    assert _resolve(authority, policy.reference).reason is PolicyResolutionReason.SIGNATURE_INVALID


# 3 -------------------------------------------------------------------------
def test_a_caller_cannot_replace_a_stored_version():
    authority = make_authority()
    policy = make_policy()
    good = authority.issue(policy)
    evil = replace(good, record_id="evil", approval_ref="APPROVAL-EVIL")
    with pytest.raises(PolicyRegistryConflictError):
        authority.registry.append_issuance(evil)
    assert authority.registry.get_issued(policy.reference) == good
    assert _resolve(authority, policy.reference).resolved


# 4 -------------------------------------------------------------------------
def test_a_caller_cannot_change_content_while_keeping_the_reference_valid():
    authority = make_authority()
    policy = make_policy(PolicyFamily.GEOGRAPHY)
    record = authority.issue(policy)
    reference = policy.reference

    swapped = replace(record.policy, jurisdiction="XX-OFFSHORE")
    object.__setattr__(record, "policy", swapped)
    assert _resolve(authority, reference).reason is PolicyResolutionReason.CONTENT_DIGEST_MISMATCH


# 5 -------------------------------------------------------------------------
def test_a_caller_cannot_alter_tenant_or_scope():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    authority.issue(policy, expected_tenant_id="tenant-a")

    hijacked = replace(policy.reference, tenant_id="tenant-b")
    assert _resolve(authority, hijacked, tenant="tenant-b").reason is (
        PolicyResolutionReason.NOT_FOUND
    )
    assert _resolve(authority, policy.reference, tenant="tenant-b").reason is (
        PolicyResolutionReason.TENANT_SCOPE_MISMATCH
    )


# 6 -------------------------------------------------------------------------
def test_a_caller_cannot_substitute_another_family():
    authority = make_authority()
    readiness = make_policy(PolicyFamily.READINESS, policy_id="p", version="1.0.0")
    authority.issue(readiness)
    probe = replace(readiness.reference, policy_family=PolicyFamily.VALUATION)
    assert _resolve(authority, probe).reason is PolicyResolutionReason.NOT_FOUND


# 7 -------------------------------------------------------------------------
def test_a_caller_cannot_use_a_floating_reference():
    from ugence_uvi_policy_contracts.api import PolicyContractError, PolicyReference

    with pytest.raises(PolicyContractError):
        PolicyReference(
            policy_id="p", policy_family=PolicyFamily.DOMAIN, version="1.0.0", content_digest=""
        )
    authority = make_authority()
    for forbidden in ("latest", "current", "find_by_id", "resolve_by_id"):
        assert not hasattr(authority.registry, forbidden)


# 8 -------------------------------------------------------------------------
def test_a_caller_cannot_provide_its_own_signature_as_trusted():
    import inspect

    # There is no signature parameter on either mutating entry point.
    assert "signature" not in inspect.signature(issue_policy).parameters
    assert "signature" not in inspect.signature(revoke_policy).parameters

    # And a signature from an unregistered key never verifies.
    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    attacker = make_signer(key_id=record.key_id, seed=42)
    object.__setattr__(record, "signature", attacker.sign(record.signing_payload()))
    assert _resolve(authority, policy.reference).reason is PolicyResolutionReason.SIGNATURE_INVALID


# 9 -------------------------------------------------------------------------
def test_a_caller_cannot_bypass_revocation():
    authority = make_authority()
    policy = make_policy(effective_to=None)
    record = authority.issue(policy)
    revoke_policy(
        reference=policy.reference,
        revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=authority.registry,
        revoked_at=T_MID,
        signer=authority.signer,
    )
    # Re-appending the original issuance does not clear the revocation.
    authority.registry.append_issuance(record)
    assert _resolve(authority, policy.reference).reason is PolicyResolutionReason.REVOKED
    # Nor does asking as_of far in the future.
    assert _resolve(authority, policy.reference, as_of=T_AFTER).reason is (
        PolicyResolutionReason.REVOKED
    )


# 10 ------------------------------------------------------------------------
def test_a_caller_cannot_mark_an_expired_policy_active():
    authority = make_authority()
    policy = make_policy(effective_to=T_TO)
    record = authority.issue(policy)
    assert _resolve(authority, policy.reference, as_of=T_AFTER).reason is (
        PolicyResolutionReason.EXPIRED
    )
    # Relabelling the lifecycle changes the body, so the digest stops matching.
    relabelled = make_policy(effective_to=T_TO, lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE)
    object.__setattr__(record, "policy", relabelled)
    assert _resolve(authority, policy.reference, as_of=T_AFTER).reason is (
        PolicyResolutionReason.EXPIRED
    )


# 11 ------------------------------------------------------------------------
def test_a_caller_cannot_elevate_evidence_status():
    """No evidence axis appears anywhere on the authority surface."""

    from ugence_uvi_policy_authority import api

    banned = {
        "SourceBasis",
        "AttestationStatus",
        "AttributionStatus",
        "VerificationStatus",
        "TransformationMethod",
        "MetricClaim",
        "MetricObservation",
    }
    assert not banned & set(api.__all__)

    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for f in dataclasses.fields(obj):
                assert "evidence_status" not in f.name
                assert "verification_status" not in f.name


# 12 ------------------------------------------------------------------------
def test_a_caller_cannot_inject_a_financial_multiplier():
    from ugence_uvi_policy_authority import api

    for name in api.__all__:
        obj = getattr(api, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        for f in dataclasses.fields(obj):
            lowered = f.name.lower()
            for banned in ("multiplier", "roi", "weight", "factor", "score", "uplift", "value_"):
                assert banned not in lowered, (name, f.name)


# 13 ------------------------------------------------------------------------
def test_the_authority_evaluates_no_readiness_and_calculates_no_value():
    from ugence_uvi_policy_authority import api

    for banned in (
        "evaluate_readiness",
        "calculate_value",
        "FinancialValuation",
        "ReadinessDetermination",
        "forecast",
        "resolve_benchmark",
    ):
        assert banned not in api.__all__
        assert not hasattr(api, banned)


# --------------------------------------------------------------------------- #
# Additional probes
# --------------------------------------------------------------------------- #
def test_an_arbitrary_well_formed_digest_never_substitutes_for_the_body():
    authority = make_authority()
    policy = make_policy()
    forged = replace(policy, metadata=replace(policy.metadata, content_digest=ARBITRARY_DIGEST))
    with pytest.raises(PolicyDigestMismatchError):
        authority.issue(forged)
    assert registry_snapshot(authority.registry) == ((), ())


def test_a_lax_verifier_still_cannot_get_a_mismatched_policy_issued():
    class LaxVerifier:
        """Says APPROVED for everything, binding whatever it was handed."""

        def verify_approval(self, *, policy_reference, policy_body_digest, approval, as_of):
            return ApprovalVerification(
                verified=True,
                status=ApprovalVerificationStatus.APPROVED,
                policy_reference=policy_reference,
                policy_body_digest=policy_body_digest,
                approving_authority_id=ISSUING_AUTHORITY,  # the issuer itself
                approval_ref=approval.approval_ref,
                approval_digest=approval.approval_digest,
                verified_at=as_of,
            )

    authority = make_authority()
    with pytest.raises(PolicyApprovalError, match="different approving authority|cannot approve"):
        issue_policy(
            policy=make_policy(),
            record_id="r",
            approval=approval_evidence(),
            approval_verifier=LaxVerifier(),
            signer=authority.signer,
            registry=authority.registry,
            issued_at=T_MID,
        )


def test_an_unconfigured_deployment_can_issue_nothing_and_resolve_nothing():
    authority = make_authority()
    policy = make_policy()
    with pytest.raises(PolicyApprovalError):
        issue_policy(
            policy=policy,
            record_id="r",
            approval=approval_evidence(),
            approval_verifier=DenyAllApprovalVerifier(),
            signer=authority.signer,
            registry=authority.registry,
            issued_at=T_MID,
        )
    authority.issue(policy)
    assert (
        resolve_policy(
            reference=policy.reference,
            expected_tenant_id="",
            as_of=T_MID,
            registry=authority.registry,
            signature_verifier=DenyAllSignatureVerifier(),
        ).reason
        is PolicyResolutionReason.KEY_UNKNOWN
    )


def test_no_production_module_ships_an_allow_all_verifier():
    """No shipped verifier class can produce an APPROVED or VALID outcome.

    AST-scans every concrete class in ``src/`` that implements ``verify_approval``
    or ``verify`` and asserts none of them mentions the granting enum member, so
    the only shipped implementations are the deny-by-default ones.
    """

    import ast
    import pathlib

    import ugence_uvi_policy_authority

    root = pathlib.Path(ugence_uvi_policy_authority.__file__).resolve().parent
    checked = 0
    for path in root.rglob("*.py"):
        source = path.read_text()
        assert "AllowAll" not in source, path
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            methods = {
                n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if not methods & {"verify_approval", "verify"}:
                continue
            # Protocols declare the signature; only concrete classes matter.
            if any(
                isinstance(b, ast.Name) and b.id == "Protocol" for b in node.bases
            ):
                continue
            granting = {
                a.attr
                for a in ast.walk(node)
                if isinstance(a, ast.Attribute) and a.attr in {"APPROVED", "VALID"}
            }
            if node.name == "PolicyKeyRing":
                # The key ring is the reference *signature* verifier: it may
                # return VALID, but only after an Ed25519 check it cannot fake.
                assert granting <= {"VALID"}, (path, node.name)
                checked += 1
                continue
            assert not granting, (path, node.name, granting)
            checked += 1
    assert checked >= 3


def test_every_public_entry_point_refuses_a_naive_datetime():
    from datetime import datetime

    authority = make_authority()
    policy = make_policy()
    naive = datetime(2026, 6, 1)

    with pytest.raises(PolicyAuthorityRequestError):
        authority.issue(policy, issued_at=naive)
    authority.issue(policy)
    with pytest.raises(PolicyAuthorityRequestError):
        _resolve(authority, policy.reference, as_of=naive)
    with pytest.raises(PolicyAuthorityRequestError):
        revoke_policy(
            reference=policy.reference,
            revocation_id="rv",
            reason_code=PolicyRevocationReasonCode.OTHER,
            registry=authority.registry,
            revoked_at=naive,
        )
