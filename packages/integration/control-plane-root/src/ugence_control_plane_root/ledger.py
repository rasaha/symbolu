"""The audit ledger: append one entry, return the reference naming it.

**The act, in full.** ``append`` takes a :class:`~.entry.LedgerEntry` at the instant
its caller supplied, writes it into that tenant's hash-linked chain, and returns an
``AuditReference`` pointing at it. Nothing else. The ledger does not read entries
back for interpretation, does not decide anything about them, and does not know what
any ``kind`` means.

**It unifies nothing.** Seven audit stores already exist and none of them is *the*
audit service (``ugence_governance_contracts.contracts.audit:9-13``). This is an
eighth store — deliberately — and G4's ``AuditReference`` stays the only thing that
correlates across them. No existing store is read, migrated, mirrored or changed.
A root that absorbed them would be doing the migration G4 explicitly refused.

**The shape is storygraph's, copied.** SQLite, WAL, append-only enforced by UPDATE
and DELETE triggers rather than convention, hash-linked per tenant, schema-versioned
(``packages/capabilities/storygraph/src/ugence_storygraph/durable_audit.py``). It is
copied and never imported, exactly as decision D-3 of the sequencing ADR already
ruled for Policy Authority's registry. Tamper-**evident**: the chain detects
modification. It is not tamper-proof and this package never says otherwise.
"""

from __future__ import annotations

import sqlite3
from typing import Optional, Protocol, runtime_checkable

from ._canon import canonical_bytes, domain_digest, iso, require_nonempty
from .entry import GENESIS_DIGEST, LedgerEntry
from .errors import ContractViolation, LedgerIntegrityError, SchemaVersionMismatch
from .version import SCHEMA_VERSION

__all__ = ["AuditLedger", "AuditReferenceFactory", "StoredEntry", "STORE_REF"]

#: What an ``AuditReference`` names as the store it points into. One value, fixed:
#: a reference whose ``store_ref`` varied per deployment could not be correlated.
STORE_REF = "ugence_control_plane_root:audit_ledger"


@runtime_checkable
class AuditReferenceFactory(Protocol):
    """The seam by which governance-contracts is **injected, never imported**.

    The root composes packages; it does not depend on them. A composition root that
    imported the contract package would be one import away from importing a
    capability, and the boundary test that forbids it would have nothing to catch.
    So the caller supplies the type, and ``tests/test_boundaries.py`` asserts this
    module names it nowhere.
    """

    def __call__(self, *, tenant_id: str, store_ref: str, entry_ref: str,
                 entry_digest: str, correlation_id: str = "",
                 recorded_at: object = None): ...


class StoredEntry:
    """One row as it was written: the entry, its place in the chain, its digests."""

    __slots__ = ("seq", "entry", "prev_digest", "record_digest")

    def __init__(self, seq: int, entry: LedgerEntry, prev_digest: str,
                 record_digest: str) -> None:
        self.seq = seq
        self.entry = entry
        self.prev_digest = prev_digest
        self.record_digest = record_digest

    @property
    def entry_ref(self) -> str:
        """How an ``AuditReference`` locates this row inside this store."""

        return f"{self.entry.tenant_id}/{self.seq}"

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (f"StoredEntry(seq={self.seq}, kind={self.entry.kind!r}, "
                f"record_digest={self.record_digest[:12]}…)")


class AuditLedger:
    """A durable, append-only, per-tenant hash-linked store. Reference-grade."""

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    # -- schema ------------------------------------------------------------ #
    def _init_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ledger_entries (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                tenant_seq INTEGER NOT NULL,
                kind TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                recorded_by TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                content_digest TEXT NOT NULL,
                prev_digest TEXT NOT NULL,
                record_digest TEXT NOT NULL,
                UNIQUE (tenant_id, tenant_seq)
            )
        """)
        # Append-only by construction, not by convention: the database itself
        # refuses the two statements that would rewrite history.
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS ledger_no_update
            BEFORE UPDATE ON ledger_entries
            BEGIN SELECT RAISE(ABORT, 'ledger_entries is append-only'); END
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS ledger_no_delete
            BEFORE DELETE ON ledger_entries
            BEGIN SELECT RAISE(ABORT, 'ledger_entries is append-only'); END
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tenant_seq ON ledger_entries "
            "(tenant_id, tenant_seq)")
        cursor.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                       (SCHEMA_VERSION,))
        self._conn.commit()
        stored = self.schema_version()
        if stored != SCHEMA_VERSION:
            raise SchemaVersionMismatch(
                f"store at {self.path!r} is schema {stored!r}, this package writes "
                f"{SCHEMA_VERSION!r}; refused rather than migrated")

    def schema_version(self) -> str:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return row[0] if row else ""

    # -- the act ----------------------------------------------------------- #
    def append(self, entry: LedgerEntry, *, reference_factory: AuditReferenceFactory):
        """Append one entry to its tenant's chain; return the reference naming it.

        ``reference_factory`` is governance-contracts' ``AuditReference``, injected.
        This package never imports it — see :class:`AuditReferenceFactory`.
        """

        if not isinstance(entry, LedgerEntry):
            raise ContractViolation("append.entry must be a LedgerEntry")
        if not callable(reference_factory):
            raise ContractViolation("append.reference_factory must be callable")

        # BEGIN IMMEDIATE: the read of the chain head and the write that extends it
        # are one transaction, so two concurrent appends cannot fork a tenant chain.
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            tenant_seq, prev_digest = self._head(entry.tenant_id)
            content = entry.content_digest()
            record_digest = domain_digest("control_plane_root.chain", {
                "tenant_id": entry.tenant_id, "tenant_seq": tenant_seq,
                "prev_digest": prev_digest, "content_digest": content,
            })
            self._conn.execute(
                "INSERT INTO ledger_entries (tenant_id, tenant_seq, kind, recorded_at,"
                " recorded_by, correlation_id, payload_json, content_digest,"
                " prev_digest, record_digest) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (entry.tenant_id, tenant_seq, entry.kind,
                 iso(entry.recorded_at, "recorded_at"), entry.recorded_by,
                 entry.correlation_id,
                 canonical_bytes(entry.payload).decode("utf-8"),
                 content, prev_digest, record_digest))
            seq = int(self._conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        except Exception:
            self._conn.rollback()
            raise
        self._conn.commit()

        stored = StoredEntry(seq, entry, prev_digest, record_digest)
        return reference_factory(
            tenant_id=entry.tenant_id, store_ref=STORE_REF,
            entry_ref=stored.entry_ref, entry_digest=record_digest,
            correlation_id=entry.correlation_id,
            recorded_at=entry.recorded_at)

    def _head(self, tenant_id: str) -> tuple[int, str]:
        tenant = require_nonempty(tenant_id, "tenant_id")
        row = self._conn.execute(
            "SELECT tenant_seq, record_digest FROM ledger_entries WHERE tenant_id=? "
            "ORDER BY tenant_seq DESC LIMIT 1", (tenant,)).fetchone()
        if row is None:
            return 0, GENESIS_DIGEST
        return int(row[0]) + 1, row[1]

    # -- reading, for verification only ------------------------------------ #
    def entry_count(self, *, tenant_id: Optional[str] = None) -> int:
        if tenant_id is None:
            row = self._conn.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM ledger_entries WHERE tenant_id=?",
                (require_nonempty(tenant_id, "tenant_id"),)).fetchone()
        return int(row[0])

    def verify_chain(self, *, tenant_id: str) -> bool:
        """Recompute one tenant's chain. ``True`` means it agrees with itself.

        Tamper-**evident**, not tamper-proof: a chain that verifies says nobody
        edited a row in place, never that the entries are true or that whoever
        wrote them was entitled to.
        """

        tenant = require_nonempty(tenant_id, "tenant_id")
        expected_prev, expected_seq = GENESIS_DIGEST, 0
        for row in self._conn.execute(
                "SELECT tenant_seq, content_digest, prev_digest, record_digest "
                "FROM ledger_entries WHERE tenant_id=? ORDER BY tenant_seq", (tenant,)):
            tenant_seq, content, prev, record = row
            if int(tenant_seq) != expected_seq or prev != expected_prev:
                raise LedgerIntegrityError(
                    f"tenant {tenant!r} chain breaks at position {expected_seq}")
            recomputed = domain_digest("control_plane_root.chain", {
                "tenant_id": tenant, "tenant_seq": int(tenant_seq),
                "prev_digest": prev, "content_digest": content})
            if recomputed != record:
                raise LedgerIntegrityError(
                    f"tenant {tenant!r} entry {tenant_seq} does not match its digest")
            expected_prev, expected_seq = record, expected_seq + 1
        return True

    def close(self) -> None:
        self._conn.close()
