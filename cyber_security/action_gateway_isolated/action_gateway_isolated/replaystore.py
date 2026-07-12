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
            c.execute("""CREATE TABLE IF NOT EXISTS commits(
                action_hash TEXT PRIMARY KEY, committed_at TEXT, result_hash TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS watermarks(
                stream TEXT PRIMARY KEY, seq INTEGER NOT NULL)""")

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

    def finalize_commit(self, action_hash: str, result_hash: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE commits SET result_hash=? WHERE action_hash=?",
                      (result_hash, action_hash))

    def release_commit(self, action_hash: str) -> None:
        """Release a claim that never completed (execution failed before write)."""
        with self._conn() as c:
            c.execute("DELETE FROM commits WHERE action_hash=? AND result_hash IS NULL",
                      (action_hash,))

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
                    "streams": c.execute("SELECT COUNT(*) FROM watermarks").fetchone()[0]}
