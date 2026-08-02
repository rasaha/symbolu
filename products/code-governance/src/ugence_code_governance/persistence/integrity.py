"""Domain-separated content integrity for durable shadow records.

All fingerprints reuse the product-wide ``fingerprints.domain_hash`` (deterministic
domain-separated SHA-256). Fingerprints exclude SQLite row ids, file paths,
insertion order, process ids, object addresses, and hidden current-time values.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from ..fingerprints import domain_hash
from .schema import DOMAIN_ENVELOPE, DOMAIN_EVENT, DOMAIN_PAYLOAD, DOMAIN_BUNDLE


def payload_fingerprint(canonical_payload: Mapping[str, Any]) -> str:
    return domain_hash(DOMAIN_PAYLOAD, canonical_payload)


def envelope_fingerprint(
    *,
    record_id: str,
    record_type: str,
    schema_version: str,
    tenant_id: str,
    workflow_id: str,
    workflow_revision_id: str,
    created_at: str,
    payload_fp: str,
    previous_record_fingerprint: Optional[str],
) -> str:
    return domain_hash(DOMAIN_ENVELOPE, {
        "record_id": record_id,
        "record_type": record_type,
        "schema_version": schema_version,
        "tenant_id": tenant_id,
        "workflow_id": workflow_id,
        "workflow_revision_id": workflow_revision_id,
        "created_at": created_at,
        "payload_fingerprint": payload_fp,
        "previous_record_fingerprint": previous_record_fingerprint,
    })


def event_fingerprint(
    *,
    event_id: str,
    tenant_id: str,
    workflow_id: str,
    workflow_revision_id: str,
    previous_event_fingerprint: str,
    from_state: str,
    to_state: str,
    event_type: str,
    referenced_record_ids,
    occurred_at: str,
) -> str:
    return domain_hash(DOMAIN_EVENT, {
        "event_id": event_id,
        "tenant_id": tenant_id,
        "workflow_id": workflow_id,
        "workflow_revision_id": workflow_revision_id,
        "previous_event_fingerprint": previous_event_fingerprint,
        "from_state": from_state,
        "to_state": to_state,
        "event_type": event_type,
        "referenced_record_ids": sorted(referenced_record_ids),
        "occurred_at": occurred_at,
    })


def bundle_fingerprint(manifest: Mapping[str, Any]) -> str:
    return domain_hash(DOMAIN_BUNDLE, manifest)


__all__ = [
    "payload_fingerprint",
    "envelope_fingerprint",
    "event_fingerprint",
    "bundle_fingerprint",
]
