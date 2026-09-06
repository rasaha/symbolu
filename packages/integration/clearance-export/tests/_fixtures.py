"""Shared builders. Every instant is explicit — the package reads no clock, and
neither do its tests, so a run in June and a run in December produce the same bytes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ugence_action_clearance import ClearanceReceiptBody, ClearanceResult, ClearanceStatus

from ugence_clearance_export import (
    ExportAuthenticity,
    ExportDataClassification,
    IdentityAssurance,
    build_export,
)

T0 = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
TENANT = "tenant-alpha"


def result(
    *,
    tenant_id: str = TENANT,
    request_id: str = "req-1",
    status: ClearanceStatus = ClearanceStatus.CLEAR,
    evaluated_at: datetime = T0,
    valid_for: timedelta = timedelta(minutes=15),
) -> ClearanceResult:
    return ClearanceResult(
        request_id=request_id,
        authorization_ref="authz-1",
        authorized_action_fingerprint="actfp-1",
        status=status,
        reason_codes=("OPERATIONALLY_SAFE",),
        effective_constraints=("window:15m",),
        obligations=("record-outcome",),
        evaluated_at=evaluated_at,
        valid_until=evaluated_at + valid_for,
        policy_refs=("policy:clearance:v1",),
        signal_refs=("sig-1", "sig-2"),
        request_fingerprint="reqfp-1",
        tenant_id=tenant_id,
        signal_bundle_fingerprint="bundlefp-1",
    )


def body(**kwargs) -> ClearanceReceiptBody:
    return ClearanceReceiptBody.from_result(result(**kwargs))


def artifact(**kwargs):
    """An artifact built the only way the package permits: all three labels stated."""

    return build_export(
        body(**kwargs),
        identity_assurance=IdentityAssurance.PRESENTED_UNPROVEN,
        authenticity=ExportAuthenticity.UNSIGNED,
        data_classification=ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY,
    )
