"""Anti-gaming: what an untrusted caller cannot do, through the public API only."""

from __future__ import annotations

import dataclasses
import inspect
from dataclasses import replace
from datetime import datetime

import pytest

from _authority_fixtures import (
    APPROVING_AUTHORITY,
    ARBITRARY_DIGEST,
    ISSUING_AUTHORITY,
    T_AFTER,
    T_FROM,
    T_MID,
    T_TO,
    approval_evidence,
    coordinate_of,
    make_authority,
    make_policy,
    make_signer,
    registry_snapshot,
)
from ugence_policy_authority.api import (
    ApprovalVerification,
    ApprovalVerificationStatus,
    DenyAllApprovalVerifier,
    DenyAllSignatureVerifier,
    IssuedPolicyRecord,
    PolicyApprovalError,
    PolicyAuthorityRequestError,
    PolicyDigestMismatchError,
    PolicyRegistryConflictError,
    PolicyResolutionReason,
    PolicyRevocationReasonCode,
    UnsupportedPolicyArtifactError,
    UnsupportedSupersessionError,
    issue_policy,
    resolve_policy,
    revoke_policy,
)
from ugence_uvi_policy_contracts.api import PolicyFamily, PolicyLifecycleState, PolicyScope


# 1 -------------------------------------------------------------------------
def test_a_caller_cannot_self_approve():
    authority = make_authority()
    policy = make_policy()

    with pytest.raises(TypeError):
        issue_policy(
            policy=policy,
            record_id="r",
            approved=True,
            approval_verifier=authority.approval,
            signer=authority.signer,
            registry=authority.registry,
            adapters=authority.adapters,
            issued_at=T_MID,
        )
    with pytest.raises(PolicyAuthorityRequestError):
        issue_policy(
            policy=policy,
            record_id="r",
            approval=APPROVING_AUTHORITY,
            approval_verifier=authority.approval,
            signer=authority.signer,
            registry=authority.registry,
            adapters=authority.adapters,
            issued_at=T_MID,
        )
    authority.approval.approving_authority_id = ISSUING_AUTHORITY
    with pytest.raises(PolicyApprovalError, match="cannot approve its own"):
        authority.issue(
            policy, evidence=approval_evidence(approving_authority_id=ISSUING_AUTHORITY)
        )
    assert policy.metadata.lifecycle_state is PolicyLifecycleState.APPROVED_ACTIVE
    with pytest.raises(PolicyApprovalError):
        issue_policy(
            policy=policy,
            record_id="r",
            approval=approval_evidence(),
            approval_verifier=DenyAllApprovalVerifier(),
            signer=authority.signer,
            registry=authority.registry,
            adapters=authority.adapters,
            issued_at=T_MID,
        )
    assert len(authority.registry._issued) == 0


def test_a_lax_verifier_is_still_constrained_by_authority_side_checks():
    class LaxVerifier:
        def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
            return ApprovalVerification(
                verified=True,
                status=ApprovalVerificationStatus.APPROVED,
                coordinate=coordinate,
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
            adapters=authority.adapters,
            issued_at=T_MID,
        )


# 2 -------------------------------------------------------------------------
def test_a_caller_cannot_forge_issuance_by_constructing_a_record():
    authority = make_authority()
    policy = make_policy()
    forged = IssuedPolicyRecord(
        record_id="forged",
        coordinate=coordinate_of(policy),
        adapter_id="ugence.uvi.policy-family/v1",
        policy_type="DomainPolicy",
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
    assert authority.resolve(policy.reference).reason is PolicyResolutionReason.SIGNATURE_INVALID


def test_raw_registry_retrieval_cannot_bypass_resolution():
    authority = make_authority()
    policy = make_policy()
    forged = IssuedPolicyRecord(
        record_id="forged",
        coordinate=coordinate_of(policy),
        adapter_id="ugence.uvi.policy-family/v1",
        policy_type="DomainPolicy",
        policy=policy,
        policy_body_digest=policy.metadata.content_digest,
        issuing_authority_id="attacker",
        key_id="attacker-key",
        signature_alg="ed25519",
        signature=b"\xbb" * 64,
        approving_authority_id=APPROVING_AUTHORITY,
        approval_ref="A",
        approval_digest=ARBITRARY_DIGEST,
        issued_at=T_MID,
    )
    authority.registry.append_issuance(forged)
    # Retrieval succeeds — and proves nothing.
    assert authority.registry.get_issued(coordinate_of(policy)) is forged
    # Only resolution decides, and it denies.
    assert not authority.resolve(policy.reference).resolved


# 3 -------------------------------------------------------------------------
def test_a_caller_cannot_replace_a_stored_version():
    authority = make_authority()
    policy = make_policy()
    good = authority.issue(policy)
    with pytest.raises(PolicyRegistryConflictError):
        authority.registry.append_issuance(
            replace(good, record_id="evil", approval_ref="APPROVAL-EVIL")
        )
    assert authority.registry.get_issued(coordinate_of(policy)) == good
    assert authority.resolve(policy.reference).resolved


# 4 -------------------------------------------------------------------------
def test_a_caller_cannot_change_content_while_keeping_the_reference_valid():
    authority = make_authority()
    policy = make_policy(PolicyFamily.GEOGRAPHY)
    record = authority.issue(policy)
    object.__setattr__(record, "policy", replace(record.policy, jurisdiction="XX-OFFSHORE"))
    assert authority.resolve(policy.reference).reason is (
        PolicyResolutionReason.CONTENT_DIGEST_MISMATCH
    )


def test_an_arbitrary_well_formed_digest_is_not_proof():
    authority = make_authority()
    policy = make_policy()
    forged = replace(policy, metadata=replace(policy.metadata, content_digest=ARBITRARY_DIGEST))
    with pytest.raises(PolicyDigestMismatchError):
        authority.issue(forged)
    assert len(authority.registry._issued) == 0


# 5 -------------------------------------------------------------------------
def test_a_caller_cannot_alter_tenant_or_scope():
    authority = make_authority()
    policy = make_policy(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    authority.issue(policy, expected_reference_tenant_id="tenant-a")

    hijacked = replace(policy.reference, tenant_id="tenant-b")
    assert authority.resolve(hijacked, tenant="tenant-b").reason is (
        PolicyResolutionReason.NOT_FOUND
    )
    cross = authority.resolve(policy.reference, tenant="tenant-b")
    assert cross.reason is PolicyResolutionReason.TENANT_SCOPE_MISMATCH
    assert "tenant-a" not in cross.detail


# 6 -------------------------------------------------------------------------
def test_a_caller_cannot_substitute_another_family():
    authority = make_authority()
    readiness = make_policy(PolicyFamily.READINESS)
    authority.issue(readiness)
    probe = replace(readiness.reference, policy_family=PolicyFamily.VALUATION)
    assert authority.resolve(probe).reason is PolicyResolutionReason.NOT_FOUND


# 7 -------------------------------------------------------------------------
def test_a_caller_cannot_use_a_floating_reference():
    from ugence_uvi_policy_contracts.api import PolicyContractError, PolicyReference

    with pytest.raises(PolicyContractError):
        PolicyReference(
            policy_id="p", policy_family=PolicyFamily.DOMAIN, version="1.0.0", content_digest=""
        )
    from ugence_policy_authority.api import PolicyCoordinate

    with pytest.raises(PolicyAuthorityRequestError):
        PolicyCoordinate(
            policy_family="DOMAIN", policy_id="p", version="1", content_digest="", scope="GLOBAL"
        )


# 8 -------------------------------------------------------------------------
def test_a_caller_cannot_provide_its_own_signature_as_trusted():
    assert "signature" not in inspect.signature(issue_policy).parameters
    assert "signature" not in inspect.signature(revoke_policy).parameters

    authority = make_authority()
    policy = make_policy()
    record = authority.issue(policy)
    attacker = make_signer(key_id=record.key_id, seed=42)
    object.__setattr__(record, "signature", attacker.sign(record.signing_payload()))
    assert authority.resolve(policy.reference).reason is PolicyResolutionReason.SIGNATURE_INVALID


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
        adapters=authority.adapters,
        signer=authority.revocation_signer,
        signature_verifier=authority.key_ring,
        revoked_at=T_MID,
    )
    authority.registry.append_issuance(record)  # re-append does not clear it
    assert authority.resolve(policy.reference).reason is PolicyResolutionReason.REVOKED
    assert authority.resolve(policy.reference, as_of=T_AFTER).reason is (
        PolicyResolutionReason.REVOKED
    )


# 10 ------------------------------------------------------------------------
def test_a_caller_cannot_mark_an_expired_policy_active():
    authority = make_authority()
    policy = make_policy(effective_to=T_TO)
    record = authority.issue(policy)
    assert authority.resolve(policy.reference, as_of=T_AFTER).reason is (
        PolicyResolutionReason.EXPIRED
    )
    object.__setattr__(
        record, "policy", make_policy(effective_to=T_TO, lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE)
    )
    assert authority.resolve(policy.reference, as_of=T_AFTER).reason is (
        PolicyResolutionReason.EXPIRED
    )


# 11 ------------------------------------------------------------------------
def test_a_caller_cannot_elevate_evidence_status():
    from ugence_policy_authority import api

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
    from ugence_policy_authority import api

    for name in api.__all__:
        obj = getattr(api, name)
        if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
            continue
        for f in dataclasses.fields(obj):
            lowered = f.name.lower()
            for banned in ("multiplier", "roi", "weight", "factor", "score", "uplift", "money", "amount", "currency"):
                assert banned not in lowered, (name, f.name)


# 13 ------------------------------------------------------------------------
def test_the_authority_is_not_a_runtime_authorizer_and_computes_nothing():
    from ugence_policy_authority import api

    for banned in (
        "evaluate_readiness",
        "calculate_value",
        "FinancialValuation",
        "ReadinessDetermination",
        "forecast",
        "resolve_benchmark",
        "authorize_action",
        "authorize",
        "RiskAuthorizationEnvelope",
        "ActionGate",
    ):
        assert banned not in api.__all__, banned
        assert not hasattr(api, banned), banned


def test_no_public_function_returns_a_runtime_authorization():
    from ugence_policy_authority.api import PolicyResolution

    fields = {f.name for f in dataclasses.fields(PolicyResolution)}
    for banned in ("authorized", "authorization", "envelope", "permit", "grant", "token"):
        assert not any(banned in f for f in fields), banned


# --------------------------------------------------------------------------- #
# Naming: the prohibited UVI-owned authority identity is gone
# --------------------------------------------------------------------------- #
def test_the_old_namespace_is_not_importable():
    import importlib.util

    assert importlib.util.find_spec("ugence_uvi_policy_authority") is None


def test_no_source_file_mentions_the_retired_names():
    import pathlib

    import ugence_policy_authority

    root = pathlib.Path(ugence_policy_authority.__file__).resolve().parent
    for path in root.rglob("*.py"):
        source = path.read_text()
        assert "ugence_uvi_policy_authority" not in source, path
        assert "ugence-uvi-policy-authority" not in source, path


def test_the_protocol_identity_is_platform_neutral_and_versioned():
    from ugence_policy_authority.api import (
        AUTHORITY_PROTOCOL,
        AUTHORITY_PROTOCOL_ID,
        AUTHORITY_PROTOCOL_VERSION,
    )

    assert AUTHORITY_PROTOCOL == "ugence.policy-authority"
    assert AUTHORITY_PROTOCOL_VERSION == "v0.1"
    assert AUTHORITY_PROTOCOL_ID == "ugence.policy-authority/v0.1"
    for identifier in (AUTHORITY_PROTOCOL, AUTHORITY_PROTOCOL_VERSION, AUTHORITY_PROTOCOL_ID):
        assert "uvi" not in identifier.lower()
        assert "gv-2c" not in identifier.lower()


def test_no_public_constant_carries_a_uvi_authority_identity():
    from ugence_policy_authority.api import (
        ISSUANCE_SIGNING_DOMAIN,
        POLICY_BODY_DIGEST_DOMAIN,
        REVOCATION_SIGNING_DOMAIN,
        CANONICALIZATION_VERSION,
    )

    for domain in (
        POLICY_BODY_DIGEST_DOMAIN,
        ISSUANCE_SIGNING_DOMAIN,
        REVOCATION_SIGNING_DOMAIN,
        CANONICALIZATION_VERSION,
    ):
        assert domain.startswith("ugence.policy-authority/")


# --------------------------------------------------------------------------- #
# Determinism and clock
# --------------------------------------------------------------------------- #
def test_every_public_entry_point_refuses_a_naive_datetime():
    authority = make_authority()
    policy = make_policy()
    naive = datetime(2026, 6, 1)

    with pytest.raises(PolicyAuthorityRequestError):
        authority.issue(policy, issued_at=naive)
    authority.issue(policy)
    with pytest.raises(PolicyAuthorityRequestError):
        authority.resolve(policy.reference, as_of=naive)
    with pytest.raises(PolicyAuthorityRequestError):
        revoke_policy(
            reference=policy.reference,
            revocation_id="rv",
            reason_code=PolicyRevocationReasonCode.OTHER,
            registry=authority.registry,
            adapters=authority.adapters,
            signer=authority.revocation_signer,
            signature_verifier=authority.key_ring,
            revoked_at=naive,
        )


def test_issuance_and_resolution_are_byte_deterministic():
    from ugence_policy_authority.core.canonical import canonical_bytes

    policy = make_policy(PolicyFamily.VALUATION)
    payloads = set()
    for _ in range(3):
        authority = make_authority()
        payloads.add(authority.issue(policy).signing_payload())
    assert len(payloads) == 1


def test_an_unconfigured_deployment_issues_nothing_and_resolves_nothing():
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
            adapters=authority.adapters,
            issued_at=T_MID,
        )
    authority.issue(policy)
    assert resolve_policy(
        reference=policy.reference,
        expected_reference_tenant_id="",
        as_of=T_MID,
        registry=authority.registry,
        signature_verifier=DenyAllSignatureVerifier(),
        adapters=authority.adapters,
    ).reason is PolicyResolutionReason.KEY_UNKNOWN


def test_no_shipped_verifier_can_grant():
    """AST sweep: no concrete shipped class produces APPROVED."""

    import ast
    import pathlib

    import ugence_policy_authority

    root = pathlib.Path(ugence_policy_authority.__file__).resolve().parent
    checked = 0
    for path in root.rglob("*.py"):
        source = path.read_text()
        assert "AllowAll" not in source, path
        for node in ast.walk(ast.parse(source, filename=str(path))):
            if not isinstance(node, ast.ClassDef):
                continue
            methods = {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if not methods & {"verify_approval", "verify"}:
                continue
            if any(isinstance(b, ast.Name) and b.id == "Protocol" for b in node.bases):
                continue
            granting = {
                a.attr for a in ast.walk(node) if isinstance(a, ast.Attribute) and a.attr in {"APPROVED", "VALID"}
            }
            if node.name == "PolicyKeyRing":
                assert granting <= {"VALID"}, (path, node.name)
            else:
                assert not granting, (path, node.name, granting)
            checked += 1
    assert checked >= 3
