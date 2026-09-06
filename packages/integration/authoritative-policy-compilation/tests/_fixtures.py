"""Hand-assembled Policy Authority artifacts.

`PolicyResolution` is a public dataclass anyone may hand-assemble, which is exactly
what lets this root's five requirements be exercised — and refused — without a
registry, a key, a signer or a clock. The composition root builds none of those; its
tests should not need them either.
"""

from __future__ import annotations

from datetime import datetime, timezone

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
    SCHEMA_VERSION_V2,
    PolicyPack,
)
from ugence_policy_workflow_compiler.reference.procurement import (
    build_procurement_policy_pack,
)

ADAPTER_ID = "procurement-adapter"
POLICY_TYPE = "procurement.purchase_approval"
PROJECTION = {"policy_id": "policy.purchase_approval", "threshold": 1_000_000}
AS_OF = datetime(2026, 9, 6, tzinfo=timezone.utc)


def coordinate(**overrides) -> PolicyCoordinate:
    fields = {
        "policy_family": "procurement",
        "policy_id": "policy.purchase_approval",
        "version": "4",
        "content_digest": "a" * 64,
        "scope": "global",
        "tenant_id": "tenant-1",
    }
    fields.update(overrides)
    return PolicyCoordinate(**fields)


def issued_record(coord: PolicyCoordinate, *, body_digest: str = "") -> IssuedPolicyRecord:
    return IssuedPolicyRecord(
        record_id="rec-1",
        coordinate=coord,
        adapter_id=ADAPTER_ID,
        policy_type=POLICY_TYPE,
        policy=dict(PROJECTION),
        policy_body_digest=body_digest
        or framed_body_digest(
            adapter_id=ADAPTER_ID, policy_type=POLICY_TYPE, projection=PROJECTION
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


def resolution(
    *,
    status: PolicyResolutionStatus = PolicyResolutionStatus.RESOLVED,
    reason: PolicyResolutionReason = None,
    coord: PolicyCoordinate = None,
    record: IssuedPolicyRecord = None,
    historical: bool = False,
    with_descriptor: bool = True,
) -> PolicyResolution:
    coord = coord if coord is not None else coordinate()
    record = record if record is not None else issued_record(coord)
    # PA refuses a descriptor projection on an UNRESOLVED resolution — a failed
    # answer carries no artifact to describe.
    descriptor = (
        {
            "descriptor_adapter_id": ADAPTER_ID,
            "descriptor_policy_type": POLICY_TYPE,
            "descriptor_canonical_projection": dict(PROJECTION),
        }
        if with_descriptor and status is PolicyResolutionStatus.RESOLVED
        else {}
    )
    return PolicyResolution(
        status=status,
        reason=reason or PolicyResolutionReason.RESOLVED,
        requested_coordinate=coord,
        as_of=AS_OF,
        # PA requires a RESOLVED resolution to return the record's OWN artifact.
        policy=record.policy if status is PolicyResolutionStatus.RESOLVED else None,
        record=record if status is PolicyResolutionStatus.RESOLVED else None,
        historical=historical,
        **descriptor,
    )


def pack_builder(artifact) -> PolicyPack:
    """A stand-in for a family builder (ruling CR-2: families supply their own)."""
    return build_procurement_policy_pack().model_copy(
        update={"schema_version": SCHEMA_VERSION_V2}
    )
