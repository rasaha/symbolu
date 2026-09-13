"""The one durable home of workflow drafts (owner ruling, Bring Your Workflow phase 3A).

    THIS STORE KEEPS AND READS UNAPPROVED DRAFTS. IT NEVER APPROVES, COMPILES,
    PUBLISHES, EXPORTS, EDITS OR DELETES. ITS ONLY WRITE IS ``save``.

``SqliteWorkflowDrafts`` implements the read-only :class:`WorkflowDraftPort` over a
sqlite file in the studio's seam-5 posture: a plain file path under a writable volume,
no server, no driver, no DSN, no network. It is bound to exactly one tenant at
construction; a read or write naming any other tenant is a typed refusal, never an
empty answer. Records are append-only: a draft is never edited, a revision is a new
draft that ``supersedes`` its predecessor, the lineage is linear, and the supersession
is admitted only by :func:`supersession_refusals`.

No clock is read here. Nothing here can reach the Policy Workflow Compiler, an
approval queue, a runtime or a system of record: the file the composing deployment
owns is the whole of it.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import List, Optional, Tuple

from ._canon import require_nonempty
from .draft import (
    WorkflowDraft,
    draft_from_record,
    draft_record,
    require_admissible_supersession,
)
from .errors import (
    ContractViolation,
    CrossTenantRefused,
    DraftProductionModeError,
    DraftStorageError,
    DuplicateDraftError,
)
from .selectors import lineage, select_for_tenant, superseded_by
from .version import CONTRACT_VERSION

__all__ = ["SqliteWorkflowDrafts", "SCHEMA_VERSION"]

SCHEMA_VERSION = "workflow_drafts.sqlite.v1"

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS drafts ("
    " seq INTEGER PRIMARY KEY AUTOINCREMENT,"
    " draft_id TEXT NOT NULL UNIQUE,"
    " tenant_id TEXT NOT NULL,"
    " workflow_digest TEXT NOT NULL,"
    " supersedes TEXT NOT NULL,"
    " record_digest TEXT NOT NULL,"
    " record_json TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS drafts_tenant ON drafts(tenant_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS drafts_supersedes ON drafts(supersedes) WHERE supersedes <> ''",
    "CREATE TABLE IF NOT EXISTS drafts_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
)


def _is_non_durable(path: str) -> bool:
    return path == ":memory:" or path.startswith("file:")


class SqliteWorkflowDrafts:
    """A tenant-bound, append-only sqlite store satisfying :class:`WorkflowDraftPort`."""

    kind = "SqliteWorkflowDrafts"

    def __init__(self, path: str, *, tenant_id: str, production_mode: bool = False,
                 busy_timeout_ms: int = 5000) -> None:
        self.tenant_id = require_nonempty(tenant_id, "SqliteWorkflowDrafts.tenant_id")
        self.path = require_nonempty(path, "SqliteWorkflowDrafts.path")
        self.production_mode = bool(production_mode)
        if self.production_mode and _is_non_durable(self.path):
            raise DraftProductionModeError(
                "a durable file path is required in production mode; an in-memory or URI "
                "store is refused")
        self._lock = threading.Lock()
        try:
            self._conn: Optional[sqlite3.Connection] = sqlite3.connect(
                self.path, check_same_thread=False, isolation_level=None)
            self._conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
            if not _is_non_durable(self.path):
                self._conn.execute("PRAGMA journal_mode=WAL")
            for statement in _SCHEMA:
                self._conn.execute(statement)
            self._conn.execute(
                "INSERT OR IGNORE INTO drafts_meta(key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,))
            self._conn.execute(
                "INSERT OR IGNORE INTO drafts_meta(key, value) VALUES ('tenant_id', ?)",
                (self.tenant_id,))
            # OR IGNORE leaves an existing file's own version in place, so this reads
            # what the file says rather than what this build would have written.
            self.schema_version = self._conn.execute(
                "SELECT value FROM drafts_meta WHERE key = 'schema_version'").fetchone()[0]
            if self.schema_version != SCHEMA_VERSION:
                self._conn.close()
                self._conn = None
                raise DraftStorageError(
                    f"this drafts file records schema {self.schema_version!r}, which this "
                    f"build does not know; it reads {SCHEMA_VERSION!r}")
            bound = self._conn.execute(
                "SELECT value FROM drafts_meta WHERE key = 'tenant_id'").fetchone()[0]
            if bound != self.tenant_id:
                self._conn.close()
                self._conn = None
                raise CrossTenantRefused(
                    "this drafts file is bound to another tenant; a store is never re-bound")
        except sqlite3.Error as exc:
            raise DraftStorageError(f"cannot open the drafts file: {exc}") from exc

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            raise DraftStorageError("the drafts file is closed")
        return self._conn

    def _require_tenant(self, tenant_id: str) -> None:
        if tenant_id != self.tenant_id:
            raise CrossTenantRefused(
                f"this store is bound to one tenant; a read or write for tenant "
                f"{tenant_id!r} is refused")

    def _rows(self) -> List[WorkflowDraft]:
        try:
            cursor = self._db().execute(
                "SELECT record_json, record_digest FROM drafts WHERE tenant_id = ? ORDER BY seq",
                (self.tenant_id,))
            rows = cursor.fetchall()
        except sqlite3.Error as exc:
            raise DraftStorageError(f"cannot read the drafts file: {exc}") from exc
        out: List[WorkflowDraft] = []
        for record_json, stored_digest in rows:
            draft = draft_from_record(json.loads(record_json))
            if draft.record_digest() != stored_digest:
                raise ContractViolation(
                    f"draft {draft.draft_id} does not match its recorded digest; the record "
                    "was altered outside this package")
            out.append(draft)
        return out

    # -- the one write ----------------------------------------------------- #
    def save(self, draft: WorkflowDraft) -> WorkflowDraft:
        """Append one draft. Refuses a foreign tenant, a duplicate derived id and an
        inadmissible supersession; never edits or deletes."""
        if not isinstance(draft, WorkflowDraft):
            raise ContractViolation("save takes a WorkflowDraft")
        self._require_tenant(draft.tenant_id)
        if draft.record_version != CONTRACT_VERSION:
            raise ContractViolation(f"save takes a {CONTRACT_VERSION} draft")
        with self._lock:
            existing = self._rows()
            by_id = {d.draft_id: d for d in existing}
            if draft.draft_id in by_id:
                raise DuplicateDraftError(
                    f"draft {draft.draft_id} is already recorded; records are never edited")
            predecessor = by_id.get(draft.supersedes) if draft.supersedes else None
            taken = superseded_by(existing)
            require_admissible_supersession(
                draft, predecessor, taken.get(draft.supersedes, "") if draft.supersedes else "")
            record = draft_record(draft)
            try:
                self._db().execute(
                    "INSERT INTO drafts(draft_id, tenant_id, workflow_digest, supersedes, "
                    "record_digest, record_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (draft.draft_id, draft.tenant_id, draft.workflow_digest, draft.supersedes,
                     draft.record_digest(),
                     json.dumps(record, sort_keys=True, separators=(",", ":"))))
            except sqlite3.IntegrityError as exc:
                raise DuplicateDraftError(str(exc)) from exc
            except sqlite3.Error as exc:
                raise DraftStorageError(f"cannot write the drafts file: {exc}") from exc
        return draft

    # -- the WorkflowDraftPort reads ---------------------------------------- #
    def get_draft(self, draft_id: str) -> Optional[WorkflowDraft]:
        with self._lock:
            for draft in self._rows():
                if draft.draft_id == draft_id:
                    return draft
        return None

    def drafts_for_tenant(self, *, tenant_id: str,
                          include_superseded: bool = False) -> Tuple[WorkflowDraft, ...]:
        self._require_tenant(tenant_id)
        with self._lock:
            return select_for_tenant(self._rows(), tenant_id=tenant_id,
                                     include_superseded=include_superseded)

    def lineage_of(self, draft_id: str) -> Tuple[WorkflowDraft, ...]:
        with self._lock:
            return lineage(self._rows(), draft_id)

    def superseded_by(self, draft_id: str) -> str:
        """The successor's id, or ``""`` when the draft is the head of its lineage."""
        with self._lock:
            return superseded_by(self._rows()).get(draft_id, "")

    # -- diagnostics, read-only --------------------------------------------- #
    def count(self) -> int:
        with self._lock:
            return len(self._rows())
