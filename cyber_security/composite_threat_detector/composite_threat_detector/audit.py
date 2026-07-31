"""Append-only audit log: raw evidence + lifecycle + governance events (§5).

Risk weight decays; **raw evidence and finding provenance do not**. This log is
append-only and hash-chained (tamper-evident). It retains, independent of active
risk state:

* ``RAW_EVIDENCE``   — every ingested event's identity + digest + ordering signals,
  so a past finding can be reconstructed after its active weight has decayed;
* ``LIFECYCLE``      — assembly open/close/expire/supersede transitions;
* ``ASSEMBLY_RESET`` — an administrative reset (an immutable record; reset never
  deletes history);
* ``EVICTION`` / ``OVERLOAD`` — resource-governance actions (§7).

Nothing here is ever mutated or removed. ``reset`` at the ledger level clears
*active* state only; this record survives.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import digest

RAW_EVIDENCE = "RAW_EVIDENCE"
LIFECYCLE = "LIFECYCLE"
ASSEMBLY_RESET = "ASSEMBLY_RESET"
EVICTION = "EVICTION"
OVERLOAD = "OVERLOAD"


@dataclass(frozen=True)
class AuditEvent:
    seq: int
    kind: str
    tenant_id: str
    assembly_key: str
    event_id: str
    prev_digest: str
    record_digest: str
    detail: dict

    def to_dict(self) -> dict:
        return {
            "seq": self.seq, "kind": self.kind, "tenant_id": self.tenant_id,
            "assembly_key": self.assembly_key, "event_id": self.event_id,
            "prev_digest": self.prev_digest, "record_digest": self.record_digest,
            "detail": self.detail,
        }


class AuditLog:
    """Append-only, hash-chained, never-deleting audit record."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._last_digest = "sha-256:" + "0" * 64

    def append(self, kind: str, *, tenant_id: str = "", assembly_key: str = "",
               event_id: str = "", detail: dict | None = None) -> AuditEvent:
        detail = detail or {}
        body = {"seq": len(self._events), "kind": kind, "tenant_id": tenant_id,
                "assembly_key": assembly_key, "event_id": event_id,
                "prev_digest": self._last_digest, "detail": detail}
        rec_digest = digest(body, domain="CTD-AUDIT")
        ev = AuditEvent(seq=len(self._events), kind=kind, tenant_id=tenant_id,
                        assembly_key=assembly_key, event_id=event_id,
                        prev_digest=self._last_digest, record_digest=rec_digest,
                        detail=detail)
        self._events.append(ev)
        self._last_digest = rec_digest
        return ev

    def __len__(self) -> int:
        return len(self._events)

    def all(self) -> list[AuditEvent]:
        return list(self._events)

    def for_assembly(self, tenant_id: str, assembly_key: str) -> list[AuditEvent]:
        return [e for e in self._events
                if e.tenant_id == tenant_id and e.assembly_key == assembly_key]

    def verify_chain(self) -> bool:
        """Recompute the hash chain; True if untampered."""
        prev = "sha-256:" + "0" * 64
        for e in self._events:
            body = {"seq": e.seq, "kind": e.kind, "tenant_id": e.tenant_id,
                    "assembly_key": e.assembly_key, "event_id": e.event_id,
                    "prev_digest": prev, "detail": e.detail}
            if digest(body, domain="CTD-AUDIT") != e.record_digest:
                return False
            prev = e.record_digest
        return True
