"""Immutable record envelope + workflow-event models for the durable store."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

from . import integrity
from .schema import STORE_SCHEMA_VERSION
from .serialization import _normalize_scalar, serialize


def _ts(value) -> str:
    if isinstance(value, str):
        return value
    return _normalize_scalar(value)


@dataclass(frozen=True)
class RecordEnvelope:
    """An immutable, content-addressed envelope around one canonical payload."""

    record_id: str
    record_type: str
    schema_version: str
    tenant_id: str
    workflow_id: str
    workflow_revision_id: str
    created_at: str
    canonical_payload: Mapping[str, Any]
    payload_fingerprint: str
    envelope_fingerprint: str
    previous_record_fingerprint: Optional[str] = None

    @classmethod
    def build(
        cls,
        *,
        record_id: str,
        record_type: str,
        tenant_id: str,
        workflow_id: str,
        workflow_revision_id: str,
        created_at,
        payload: Any,
        previous_record_fingerprint: Optional[str] = None,
        schema_version: str = STORE_SCHEMA_VERSION,
    ) -> "RecordEnvelope":
        canonical = serialize(payload)
        created = _ts(created_at)
        pfp = integrity.payload_fingerprint(canonical)
        efp = integrity.envelope_fingerprint(
            record_id=record_id, record_type=record_type, schema_version=schema_version,
            tenant_id=tenant_id, workflow_id=workflow_id,
            workflow_revision_id=workflow_revision_id, created_at=created, payload_fp=pfp,
            previous_record_fingerprint=previous_record_fingerprint)
        return cls(
            record_id=record_id, record_type=record_type, schema_version=schema_version,
            tenant_id=tenant_id, workflow_id=workflow_id,
            workflow_revision_id=workflow_revision_id, created_at=created,
            canonical_payload=canonical, payload_fingerprint=pfp,
            envelope_fingerprint=efp, previous_record_fingerprint=previous_record_fingerprint)

    def recompute_and_verify(self) -> bool:
        """Recompute payload + envelope fingerprints and compare to stored values."""
        pfp = integrity.payload_fingerprint(self.canonical_payload)
        if pfp != self.payload_fingerprint:
            return False
        efp = integrity.envelope_fingerprint(
            record_id=self.record_id, record_type=self.record_type,
            schema_version=self.schema_version, tenant_id=self.tenant_id,
            workflow_id=self.workflow_id, workflow_revision_id=self.workflow_revision_id,
            created_at=self.created_at, payload_fp=pfp,
            previous_record_fingerprint=self.previous_record_fingerprint)
        return efp == self.envelope_fingerprint


@dataclass(frozen=True)
class WorkflowEventRecord:
    """An immutable, hash-linked workflow-event journal entry."""

    event_id: str
    tenant_id: str
    workflow_id: str
    workflow_revision_id: str
    previous_event_fingerprint: str
    from_state: str
    to_state: str
    event_type: str
    referenced_record_ids: Tuple[str, ...]
    occurred_at: str
    event_fingerprint: str

    @classmethod
    def build(
        cls,
        *,
        event_id: str,
        tenant_id: str,
        workflow_id: str,
        workflow_revision_id: str,
        previous_event_fingerprint: str,
        from_state: str,
        to_state: str,
        event_type: str,
        referenced_record_ids: Tuple[str, ...],
        occurred_at,
    ) -> "WorkflowEventRecord":
        occ = _ts(occurred_at)
        efp = integrity.event_fingerprint(
            event_id=event_id, tenant_id=tenant_id, workflow_id=workflow_id,
            workflow_revision_id=workflow_revision_id,
            previous_event_fingerprint=previous_event_fingerprint,
            from_state=from_state, to_state=to_state, event_type=event_type,
            referenced_record_ids=referenced_record_ids, occurred_at=occ)
        return cls(
            event_id=event_id, tenant_id=tenant_id, workflow_id=workflow_id,
            workflow_revision_id=workflow_revision_id,
            previous_event_fingerprint=previous_event_fingerprint, from_state=from_state,
            to_state=to_state, event_type=event_type,
            referenced_record_ids=tuple(referenced_record_ids), occurred_at=occ,
            event_fingerprint=efp)

    def recompute(self) -> str:
        return integrity.event_fingerprint(
            event_id=self.event_id, tenant_id=self.tenant_id, workflow_id=self.workflow_id,
            workflow_revision_id=self.workflow_revision_id,
            previous_event_fingerprint=self.previous_event_fingerprint,
            from_state=self.from_state, to_state=self.to_state, event_type=self.event_type,
            referenced_record_ids=self.referenced_record_ids, occurred_at=self.occurred_at)


__all__ = ["RecordEnvelope", "WorkflowEventRecord"]
