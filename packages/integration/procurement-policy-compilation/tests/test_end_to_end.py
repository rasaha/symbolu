"""Resolution -> draft -> human approval -> compiled release.

This is the chain PA/PWC-X1 exists to produce, exercised end to end with the
Procurement builder supplying the CR-2 mapping the composition root refuses to
invent. No registry, key or clock is needed: `PolicyResolution` is a public
dataclass, and the root builds none of those either.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from ugence_policy_authority.api import (
    AUTHORITY_PROTOCOL,
    AUTHORITY_PROTOCOL_VERSION,
    IssuedPolicyRecord,
    PolicyCoordinate,
    PolicyResolution,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    framed_body_digest,
)
from ugence_policy_workflow_compiler.api import (
    check_authoritative_source,
    compile_policy_pack,
)
from ugence_policy_workflow_compiler.approval.records import build_approval_record

import _projection as proj
from ugence_authoritative_policy_compilation import (
    AuthoritativeCompilationError,
    AuthoritativePolicyCompilationService,
    RefusalCode,
)
from ugence_procurement_policy_compilation import procurement_pack_builder

ADAPTER_ID = "procurement-adapter"
POLICY_TYPE = "procurement.purchase_approval"
AS_OF = datetime(2026, 9, 6, tzinfo=timezone.utc)
SERVICE = AuthoritativePolicyCompilationService()


def _coordinate() -> PolicyCoordinate:
    return PolicyCoordinate(
        policy_family="procurement",
        policy_id="policy.purchase_approval",
        version="4",
        content_digest="a" * 64,
        scope="global",
        tenant_id="tenant-1",
    )


def _resolution(projection=None) -> PolicyResolution:
    projection = dict(projection or proj.FULL)
    coordinate = _coordinate()
    record = IssuedPolicyRecord(
        record_id="rec-1",
        coordinate=coordinate,
        adapter_id=ADAPTER_ID,
        policy_type=POLICY_TYPE,
        policy=projection,
        policy_body_digest=framed_body_digest(
            adapter_id=ADAPTER_ID, policy_type=POLICY_TYPE, projection=projection
        ),
        issuing_authority_id="authority.policy",
        key_id="key-1",
        signature_alg="ed25519",
        signature=b"signature-bytes",
        approving_authority_id="authority.approval",
        approval_ref="approval/1",
        approval_digest="c" * 64,
        issued_at=AS_OF,
        authority_protocol=AUTHORITY_PROTOCOL,
        authority_protocol_version=AUTHORITY_PROTOCOL_VERSION,
    )
    return PolicyResolution(
        status=PolicyResolutionStatus.RESOLVED,
        reason=PolicyResolutionReason.RESOLVED,
        requested_coordinate=coordinate,
        as_of=AS_OF,
        policy=record.policy,
        record=record,
        descriptor_adapter_id=ADAPTER_ID,
        descriptor_policy_type=POLICY_TYPE,
        descriptor_canonical_projection=projection,
    )


def _draft(projection=None):
    return SERVICE.draft_from_resolution(
        _resolution(projection),
        requested_coordinate=_coordinate(),
        pack_builder=procurement_pack_builder,
    )


def test_the_whole_chain_produces_a_compiled_release():
    draft = _draft()

    # The reference is derived from the resolution, not authored by the builder.
    source = draft.authoritative_source
    assert source.policy_id == "policy.purchase_approval"
    assert source.policy_version == "4"
    assert source.record_id == "rec-1"
    assert check_authoritative_source(draft.pack, required=True) == []

    # A human approves the digest the root reports (ruling CR-1).
    approval = build_approval_record(
        approval_id="approval-1",
        pack=draft.pack,
        reviewer_id="reviewer-1",
        reviewer_role="approver",
        is_fixture=True,
    )
    assert approval.policy_pack_digest == draft.pack_digest

    result = compile_policy_pack(draft.pack, approval)
    assert result.success, [d.message for d in result.validation_report.diagnostics]

    # The release is bound to the exact issuance, and the manifest shows it.
    compiled = result.compiled_package
    assert compiled.policy_pack.authoritative_source == source
    assert compiled.manifest.authoritative_source_coordinate.startswith("procurement/")


def test_the_chain_is_deterministic():
    first, second = _draft(), _draft()
    assert first.pack_digest == second.pack_digest
    assert first.authoritative_source == second.authoritative_source


def test_a_policy_stating_less_still_compiles():
    draft = _draft(proj.MINIMAL)
    approval = build_approval_record(
        approval_id="approval-2",
        pack=draft.pack,
        reviewer_id="reviewer-1",
        reviewer_role="approver",
        is_fixture=True,
    )
    assert compile_policy_pack(draft.pack, approval).success


def test_a_tampered_projection_is_refused_before_any_pack_is_built():
    # The body digest is re-verified with Policy Authority's own function, so an
    # artifact that disagrees with its issuance record never reaches the builder.
    resolution = _resolution()
    tampered = dict(resolution.descriptor_canonical_projection, approval_threshold=1)
    broken = PolicyResolution(
        status=resolution.status,
        reason=resolution.reason,
        requested_coordinate=resolution.requested_coordinate,
        as_of=resolution.as_of,
        policy=resolution.policy,
        record=resolution.record,
        descriptor_adapter_id=resolution.descriptor_adapter_id,
        descriptor_policy_type=resolution.descriptor_policy_type,
        descriptor_canonical_projection=tampered,
    )
    with pytest.raises(AuthoritativeCompilationError) as excinfo:
        SERVICE.draft_from_resolution(
            broken,
            requested_coordinate=_coordinate(),
            pack_builder=procurement_pack_builder,
        )
    assert excinfo.value.code is RefusalCode.BODY_DIGEST_MISMATCH
