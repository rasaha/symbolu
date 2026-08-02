"""Versioned schemas + validation for supplied enterprise snapshots.

Non-GitHub enterprise sources are integrated in MVP 1D as **already-captured,
supplied snapshots** — no live vendor clients. Each snapshot is validated for
schema version, tenant, subject, source, adapter version, capture time, expiry,
integrity digest, policy reference, and action/authorization binding. Anything
malformed, stale, cross-tenant, or unbound fails **closed** (never a positive
signal).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from ..fingerprints import domain_hash
from .errors import AdapterFailureCode
from .models import (
    AdapterFetchStatus,
    AdapterIdentity,
    AdapterRequest,
    AdapterResult,
    AdapterSourceIdentity,
    CollectedSignalFact,
    ProvenanceMetadata,
)

DOMAIN_SNAPSHOT = "cg.adapter.supplied_snapshot.v1"

#: Supported snapshot schema versions. An unknown/newer version fails closed.
SNAPSHOT_SCHEMAS = {
    "identity": "code_governance.identity_snapshot.v1",
    "change_window": "code_governance.change_window_snapshot.v1",
    "incident": "code_governance.incident_snapshot.v1",
    "target_health": "code_governance.target_health_snapshot.v1",
    "control_status": "code_governance.control_status_snapshot.v1",
}

#: Identity snapshots may carry ONLY these governance-relevant keys under "facts".
IDENTITY_ALLOWED_FACT_KEYS = frozenset({
    "actor_ref", "account_active", "status_category", "roles", "groups",
    "authority_scopes",
})


def snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    """Deterministic integrity digest over a snapshot (excluding its own digest)."""
    body = {k: v for k, v in snapshot.items() if k != "integrity_digest"}
    return domain_hash(DOMAIN_SNAPSHOT, body)


def _parse_ts(value: Any) -> _dt.datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an RFC3339 string")
    text = value.replace("Z", "+00:00")
    dt = _dt.datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("naive timestamp is not permitted")
    return dt.astimezone(_dt.timezone.utc)


@dataclass(frozen=True)
class ValidatedSnapshot:
    """A validated supplied snapshot, ready for fact extraction."""

    kind: str
    schema_version: str
    tenant_id: str
    subject_ref: str
    source_id: str
    source_kind: str
    adapter_version: str
    captured_at: _dt.datetime
    valid_until: _dt.datetime
    facts: Mapping[str, Any]
    policy_ref: str
    integrity_digest: str


def validate_supplied_snapshot(
    snapshot: Mapping[str, Any],
    *,
    kind: str,
    request: AdapterRequest,
    require_action_binding: bool = False,
) -> Tuple[Optional[ValidatedSnapshot], Optional[AdapterFailureCode]]:
    """Validate a supplied snapshot. Returns ``(validated, None)`` or ``(None, code)``.

    Fails closed with a structured failure code; never raises for expected data
    problems and never yields a positive signal on failure.
    """
    expected_schema = SNAPSHOT_SCHEMAS.get(kind)
    if not isinstance(snapshot, Mapping):
        return None, AdapterFailureCode.SOURCE_SCHEMA_INVALID
    if snapshot.get("schema_version") != expected_schema:
        return None, AdapterFailureCode.SOURCE_SCHEMA_INVALID
    tenant_id = snapshot.get("tenant_id")
    if not tenant_id or tenant_id != request.tenant_id:
        return None, AdapterFailureCode.SOURCE_IDENTITY_MISMATCH
    subject_ref = snapshot.get("subject_ref")
    if not isinstance(subject_ref, str) or not subject_ref:
        return None, AdapterFailureCode.SOURCE_SCHEMA_INVALID
    source_id = snapshot.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        return None, AdapterFailureCode.SOURCE_SCHEMA_INVALID
    adapter_version = snapshot.get("adapter_version")
    if not isinstance(adapter_version, str) or not adapter_version:
        return None, AdapterFailureCode.SOURCE_SCHEMA_INVALID
    try:
        captured_at = _parse_ts(snapshot.get("captured_at"))
        valid_until = _parse_ts(snapshot.get("valid_until"))
    except ValueError:
        return None, AdapterFailureCode.SOURCE_SCHEMA_INVALID
    facts = snapshot.get("facts")
    if not isinstance(facts, Mapping):
        return None, AdapterFailureCode.SOURCE_SCHEMA_INVALID
    # Integrity digest (if supplied) must recompute.
    supplied_digest = snapshot.get("integrity_digest")
    if supplied_digest is not None and supplied_digest != snapshot_digest(snapshot):
        return None, AdapterFailureCode.SOURCE_SCHEMA_INVALID
    # Freshness: an expired snapshot fails closed.
    if valid_until < request.collection_time:
        return None, AdapterFailureCode.SOURCE_DATA_STALE
    # Action/authorization binding, when required by the source policy.
    if require_action_binding:
        bound = snapshot.get("action_fingerprint")
        if bound != request.prepared_action_fingerprint:
            return None, AdapterFailureCode.ARTIFACT_IDENTITY_MISMATCH
    validated = ValidatedSnapshot(
        kind=kind, schema_version=expected_schema, tenant_id=tenant_id,
        subject_ref=subject_ref, source_id=source_id,
        source_kind=snapshot.get("source_kind", kind), adapter_version=adapter_version,
        captured_at=captured_at, valid_until=valid_until, facts=facts,
        policy_ref=snapshot.get("policy_ref", ""), integrity_digest=supplied_digest or "")
    return validated, None


def failed_result(
    *, adapter_id: str, adapter_version: str, source_kind: str,
    request: AdapterRequest, code: AdapterFailureCode,
) -> AdapterResult:
    """Build a FAILED, fact-free adapter result (fail closed)."""
    return AdapterResult(
        adapter=AdapterIdentity(adapter_id=adapter_id, adapter_version=adapter_version,
                                source_kind=source_kind),
        source=AdapterSourceIdentity(source_id="", source_kind=source_kind),
        requested_signal_types=request.requested_signal_types,
        collected_facts=(),
        captured_at=request.collection_time, valid_until=request.collection_time,
        fetch_status=AdapterFetchStatus.FAILED, failure_codes=(code,),
        provenance=ProvenanceMetadata(
            adapter_id=adapter_id, adapter_version=adapter_version, source_id="",
            source_kind=source_kind, endpoint_class="supplied-snapshot",
            registry_projection_version="", source_response_fingerprint=""))


def build_result(
    *, validated: ValidatedSnapshot, adapter_id: str, request: AdapterRequest,
    facts: Tuple[CollectedSignalFact, ...], registry_version: str,
) -> AdapterResult:
    """Build an OK adapter result from a validated snapshot + extracted facts."""
    from .models import source_response_fingerprint
    response_fp = source_response_fingerprint({
        "kind": validated.kind, "subject_ref": validated.subject_ref,
        "facts": {k: str(v) for k, v in sorted(validated.facts.items())}})
    return AdapterResult(
        adapter=AdapterIdentity(adapter_id=adapter_id,
                                adapter_version=validated.adapter_version,
                                source_kind=validated.source_kind),
        source=AdapterSourceIdentity(source_id=validated.source_id,
                                     source_kind=validated.source_kind),
        requested_signal_types=request.requested_signal_types,
        collected_facts=facts,
        captured_at=validated.captured_at, valid_until=validated.valid_until,
        fetch_status=AdapterFetchStatus.OK, failure_codes=(),
        provenance=ProvenanceMetadata(
            adapter_id=adapter_id, adapter_version=validated.adapter_version,
            source_id=validated.source_id, source_kind=validated.source_kind,
            endpoint_class="supplied-snapshot", registry_projection_version=registry_version,
            source_response_fingerprint=response_fp))


__all__ = [
    "SNAPSHOT_SCHEMAS", "IDENTITY_ALLOWED_FACT_KEYS", "DOMAIN_SNAPSHOT",
    "snapshot_digest", "validate_supplied_snapshot", "ValidatedSnapshot",
    "failed_result", "build_result",
]
