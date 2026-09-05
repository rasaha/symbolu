"""Appending the receipt linkage to the control-plane audit ledger (HE-1, HE-5).

    THIS MODULE APPENDS ONE ENTRY PER LINKAGE, ONCE. IT DECIDES NOTHING.

Owner ruling HE-1 (``APPEND_FROM_REVIEW_SERVICE_ROOT``): after a GRANT is recorded or
replayed and the instance's next quantum has consumed the approval, the review
service reconstructs the :class:`ReviewLinkage` from the three stores and appends it
to ``ugence_control_plane_root``'s audit ledger as a ``LedgerEntry`` of kind
``governed_review.linkage.v2``. The ledger returns G4's ``AuditReference``; the
service exposes it, and the linkage, on the run-detail read (HE-5).

Two properties are load-bearing:

* **Non-blocking.** Reconstruction refuses (``LinkageError``) until the round trip is
  complete: an approval that is GRANTED but not yet CONSUMED, an instance that has not
  been resumed. That refusal is a typed outcome (``NOT_YET``) and never withholds or
  alters the decision it follows. The linkage is written when it can be, on the next
  submission or the next run-detail read.
* **Idempotent per linkage digest.** A replayed decision or a repeated read never writes
  twice. Before appending, the service asks a :class:`LinkageIndex` whether an entry
  with this linkage digest already exists; the reference implementation reads the
  ledger's own rows, read-only, by the schema version the ledger declares, and refuses a
  ledger at any other schema rather than guessing at its layout.

The service reads no clock: ``recorded_at`` is the injected clock's instant, ``recorded_by``
names the service. Nothing here touches the approval ledger, the durable engine or the
decision path.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from ugence_control_plane_root import SCHEMA_VERSION, AuditLedger, LedgerEntry
from ugence_governance_contracts.api import AuditReference
from ugence_governed_review import LinkageError, ReviewLinkage, reconstruct

from .errors import ContractViolation
from .reader import RunReader

__all__ = [
    "LINKAGE_KIND",
    "LinkageState",
    "LinkageOutcome",
    "LinkageIndex",
    "InMemoryLinkageIndex",
    "LedgerLinkageIndex",
    "LinkageAppender",
    "linkage_view",
]

#: The ``LedgerEntry.kind`` a linkage is appended under (HE-1). Follows the
#: linkage's own version: v2 since AI-D added ``authentication_reference``.
LINKAGE_KIND = "governed_review.linkage.v2"

#: The payload key that carries the linkage's own digest, so the entry can be found
#: again by it. Everything else in the payload is ``ReviewLinkage.to_dict()``.
_DIGEST_KEY = "linkage_digest"


class LinkageState(str, Enum):
    APPENDED = "APPENDED"
    ALREADY_APPENDED = "ALREADY_APPENDED"
    NOT_YET = "NOT_YET"
    LEDGER_UNCONFIGURED = "LEDGER_UNCONFIGURED"
    INSTANCE_UNKNOWN = "INSTANCE_UNKNOWN"


@dataclass(frozen=True)
class LinkageOutcome:
    """What linking did, or why it could not yet. Never an error on the decision path."""

    state: LinkageState
    approval_id: str
    instance_id: str
    task_id: str
    linkage: Optional[ReviewLinkage] = None
    audit_reference: Optional[AuditReference] = None
    reason: str = ""

    @property
    def appended(self) -> bool:
        return self.state in (LinkageState.APPENDED, LinkageState.ALREADY_APPENDED)


@runtime_checkable
class LinkageIndex(Protocol):
    """Answers whether a linkage digest is already in the ledger, and remembers one."""

    def reference_for(self, *, tenant_id: str, linkage_digest: str) -> Optional[AuditReference]: ...

    def remember(self, *, linkage_digest: str, reference: AuditReference) -> None: ...


class InMemoryLinkageIndex:
    """Process-local. For tests and single-process reference composition only: a
    restart forgets it, and a ledger it cannot see may already hold the entry."""

    def __init__(self) -> None:
        self._refs: dict[str, AuditReference] = {}

    def reference_for(self, *, tenant_id: str, linkage_digest: str) -> Optional[AuditReference]:
        ref = self._refs.get(linkage_digest)
        return ref if ref is not None and ref.tenant_id == tenant_id else None

    def remember(self, *, linkage_digest: str, reference: AuditReference) -> None:
        self._refs[linkage_digest] = reference


class LedgerLinkageIndex:
    """Reads the audit ledger's own rows, read-only, to find a linkage by digest.

    The ledger ships no read API by design ("no reconstruction API"); what it does
    ship is a schema-versioned, append-only table whose columns its README documents.
    This index opens that file read-only, refuses any schema version other than the
    one the installed ``ugence_control_plane_root`` declares, and asks one question:
    which row of kind ``governed_review.linkage.v2`` carries this linkage digest. It
    writes nothing and interprets nothing else.
    """

    def __init__(self, path: str, *, store_ref: str) -> None:
        if not isinstance(path, str) or not path or path == ":memory:":
            raise ContractViolation("LedgerLinkageIndex needs the ledger's file path; an "
                                    "in-memory ledger cannot be read from a second connection")
        self._path = path
        self._store_ref = store_ref

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        stored = row[0] if row else ""
        if stored != SCHEMA_VERSION:
            conn.close()
            raise ContractViolation(f"audit ledger at {self._path!r} is schema {stored!r}; this "
                                    f"index reads {SCHEMA_VERSION!r} only")
        return conn

    def reference_for(self, *, tenant_id: str, linkage_digest: str) -> Optional[AuditReference]:
        conn = self._connect()
        try:
            # ``seq`` is the row the ledger's own ``StoredEntry.entry_ref`` names
            # (``<tenant_id>/<seq>``), so the reference rebuilt here equals the one the
            # append returned.
            row = conn.execute(
                "SELECT seq, record_digest, correlation_id, recorded_at FROM ledger_entries "
                "WHERE tenant_id=? AND kind=? AND json_extract(payload_json, '$.' || ?) = ? "
                "ORDER BY tenant_seq LIMIT 1",
                (tenant_id, LINKAGE_KIND, _DIGEST_KEY, linkage_digest)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        seq, record_digest, correlation_id, recorded_at = row
        return AuditReference(tenant_id=tenant_id, store_ref=self._store_ref,
                              entry_ref=f"{tenant_id}/{int(seq)}", entry_digest=record_digest,
                              correlation_id=correlation_id or "",
                              recorded_at=datetime.fromisoformat(recorded_at))

    def remember(self, *, linkage_digest: str, reference: AuditReference) -> None:
        return None  # the ledger row is the memory


class LinkageAppender:
    """Reconstruct a linkage from the three stores and append it, once."""

    def __init__(self, *, ledger: AuditLedger, index: LinkageIndex, reader: RunReader,
                 approvals: Any, tenant_id: str, recorded_by: str) -> None:
        if not isinstance(ledger, AuditLedger):
            raise ContractViolation("ledger must be a control-plane AuditLedger")
        if not isinstance(index, LinkageIndex):
            raise ContractViolation("index must satisfy LinkageIndex")
        if not isinstance(recorded_by, str) or not recorded_by.strip():
            raise ContractViolation("recorded_by must be a non-empty string")
        self._ledger = ledger
        self._index = index
        self._reader = reader
        self._approvals = approvals
        self._tenant = tenant_id
        self._recorded_by = recorded_by.strip()

    def link(self, *, instance_id: str, task_id: str, approval_id: str,
             recorded_at: datetime) -> LinkageOutcome:
        ckpt = self._reader.checkpoint(instance_id)
        if ckpt is None:
            return LinkageOutcome(LinkageState.INSTANCE_UNKNOWN, approval_id, instance_id, task_id,
                                  reason="the instance has no durable state")
        try:
            result = reconstruct(
                self._approvals, tenant_id=self._tenant, instance_id=instance_id, task_id=task_id,
                approval_id=approval_id, events=self._reader.events(instance_id),
                journal=self._reader.journal(instance_id),
                correlation_id=str(ckpt.get("correlation_id") or ""),
            )
        except LinkageError as exc:
            return LinkageOutcome(LinkageState.NOT_YET, approval_id, instance_id, task_id,
                                  reason=str(exc))
        linkage = result.linkage
        digest = linkage.digest()
        existing = self._index.reference_for(tenant_id=self._tenant, linkage_digest=digest)
        if existing is not None:
            return LinkageOutcome(LinkageState.ALREADY_APPENDED, approval_id, instance_id, task_id,
                                  linkage=linkage, audit_reference=existing)
        entry = LedgerEntry(
            tenant_id=self._tenant, kind=LINKAGE_KIND, recorded_at=recorded_at,
            recorded_by=self._recorded_by,
            payload={**linkage.to_dict(), _DIGEST_KEY: digest},
            correlation_id=linkage.correlation_id,
        )
        reference = self._ledger.append(entry, reference_factory=AuditReference)
        self._index.remember(linkage_digest=digest, reference=reference)
        return LinkageOutcome(LinkageState.APPENDED, approval_id, instance_id, task_id,
                              linkage=linkage, audit_reference=reference)


def linkage_view(outcome: Optional[LinkageOutcome]) -> Optional[Mapping[str, Any]]:
    if outcome is None:
        return None
    ref = outcome.audit_reference
    return {
        "state": outcome.state.value,
        "appended": outcome.appended,
        "approval_id": outcome.approval_id,
        "instance_id": outcome.instance_id,
        "task_id": outcome.task_id,
        "linkage_digest": outcome.linkage.digest() if outcome.linkage is not None else None,
        "linkage": outcome.linkage.to_dict() if outcome.linkage is not None else None,
        "audit_reference": None if ref is None else {
            "tenant_id": ref.tenant_id, "store_ref": ref.store_ref, "entry_ref": ref.entry_ref,
            "entry_digest": ref.entry_digest, "correlation_id": ref.correlation_id,
            "recorded_at": ref.recorded_at.isoformat() if ref.recorded_at else None,
        },
        "reason": outcome.reason,
    }
