"""Durable, transactional replay + single-commit store (SQLite).

Replaces process-local nonce sets. Survives process restart and is shared by
multiple gateway/broker instances (one DB file). Uniqueness is enforced by the
database (UNIQUE constraints + a transactional claim), so:

  * a nonce can be claimed at most once, ever (token/approval/capability replay);
  * an action_hash can be committed at most once (duplicate/parallel commit);
  * sequence watermarks are GLOBAL per (session, stream) — a fresh correlation id
    cannot reset another stream's watermark.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class ReplayStore:
    def __init__(self, db_path: str):
        self.path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")
        return c

    def _init(self):
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS nonces(
                kind TEXT NOT NULL, nonce TEXT NOT NULL, claimed_at TEXT,
                PRIMARY KEY(kind, nonce))""")
            # commits.audit_seq links a finalized mutation to its audit record so
            # commit/audit divergence is detectable (N3). NULL until audited.
            c.execute("""CREATE TABLE IF NOT EXISTS commits(
                action_hash TEXT PRIMARY KEY, committed_at TEXT, result_hash TEXT,
                audit_seq INTEGER)""")
            c.execute("""CREATE TABLE IF NOT EXISTS watermarks(
                stream TEXT PRIMARY KEY, seq INTEGER NOT NULL)""")
            # durable record of RBAC credentials whose single-use teardown did not
            # confirm; the reconciler drains this (N2). resolved_at NULL == open.
            c.execute("""CREATE TABLE IF NOT EXISTS orphans(
                sa TEXT NOT NULL, namespace TEXT NOT NULL, action_hash TEXT,
                detected_at TEXT, detail TEXT, resolved_at TEXT,
                PRIMARY KEY(sa, namespace))""")
            # forward-compatible migration for stores created before audit_seq
            cols = [r[1] for r in c.execute("PRAGMA table_info(commits)").fetchall()]
            if "audit_seq" not in cols:
                c.execute("ALTER TABLE commits ADD COLUMN audit_seq INTEGER")

    def claim_nonce(self, kind: str, nonce: str, *, at: str) -> bool:
        """Return True iff this nonce was previously unused (atomic single-use)."""
        try:
            with self._conn() as c:
                c.execute("INSERT INTO nonces(kind, nonce, claimed_at) VALUES(?,?,?)",
                          (kind, nonce, at))
            return True
        except sqlite3.IntegrityError:
            return False

    def claim_commit(self, action_hash: str, *, at: str) -> bool:
        """Return True iff no prior commit exists for this action (single commit)."""
        try:
            with self._conn() as c:
                c.execute("INSERT INTO commits(action_hash, committed_at) VALUES(?,?)",
                          (action_hash, at))
            return True
        except sqlite3.IntegrityError:
            return False

    def finalize_commit(self, action_hash: str, result_hash: str, audit_seq=None) -> None:
        """Mark the mutation durable and link it to its audit record (N3)."""
        with self._conn() as c:
            c.execute("UPDATE commits SET result_hash=?, audit_seq=? WHERE action_hash=?",
                      (result_hash, audit_seq, action_hash))

    def release_commit(self, action_hash: str) -> None:
        """Release a claim that never completed (execution failed BEFORE any write).

        Guarded on ``result_hash IS NULL`` so a finalized commit can never be
        released — a successful mutation's claim is permanent (N2).
        """
        with self._conn() as c:
            c.execute("DELETE FROM commits WHERE action_hash=? AND result_hash IS NULL",
                      (action_hash,))

    def commit_record(self, action_hash: str):
        with self._conn() as c:
            row = c.execute("SELECT action_hash, committed_at, result_hash, audit_seq "
                            "FROM commits WHERE action_hash=?", (action_hash,)).fetchone()
        if not row:
            return None
        return {"action_hash": row[0], "committed_at": row[1],
                "result_hash": row[2], "audit_seq": row[3]}

    def finalized_commits(self):
        with self._conn() as c:
            return [{"action_hash": r[0], "result_hash": r[1], "audit_seq": r[2]}
                    for r in c.execute("SELECT action_hash, result_hash, audit_seq FROM "
                                       "commits WHERE result_hash IS NOT NULL")]

    # ---- durable orphaned-RBAC ledger (transactional teardown, N2) ----

    def record_orphan(self, sa: str, namespace: str, *, at: str, action_hash="", detail="") -> None:
        with self._conn() as c:
            c.execute("INSERT INTO orphans(sa, namespace, action_hash, detected_at, detail) "
                      "VALUES(?,?,?,?,?) ON CONFLICT(sa, namespace) DO UPDATE SET "
                      "detected_at=excluded.detected_at, detail=excluded.detail, "
                      "resolved_at=NULL", (sa, namespace, action_hash, at, detail))

    def open_orphans(self):
        with self._conn() as c:
            return [{"sa": r[0], "namespace": r[1], "action_hash": r[2], "detail": r[3]}
                    for r in c.execute("SELECT sa, namespace, action_hash, detail FROM "
                                       "orphans WHERE resolved_at IS NULL")]

    def resolve_orphan(self, sa: str, namespace: str, *, at: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE orphans SET resolved_at=? WHERE sa=? AND namespace=?",
                      (at, sa, namespace))

    def advance_sequence(self, stream: str, seq: int) -> bool:
        """Accept a strictly increasing sequence per GLOBAL stream; reject rollback."""
        with self._conn() as c:
            cur = c.execute("SELECT seq FROM watermarks WHERE stream=?", (stream,)).fetchone()
            if cur is not None and seq <= cur[0]:
                return False
            c.execute("INSERT INTO watermarks(stream, seq) VALUES(?,?) "
                      "ON CONFLICT(stream) DO UPDATE SET seq=excluded.seq", (stream, seq))
            return True

    def stats(self) -> dict:
        with self._conn() as c:
            return {"nonces": c.execute("SELECT COUNT(*) FROM nonces").fetchone()[0],
                    "commits": c.execute("SELECT COUNT(*) FROM commits").fetchone()[0],
                    "streams": c.execute("SELECT COUNT(*) FROM watermarks").fetchone()[0],
                    "open_orphans": c.execute(
                        "SELECT COUNT(*) FROM orphans WHERE resolved_at IS NULL").fetchone()[0]}
