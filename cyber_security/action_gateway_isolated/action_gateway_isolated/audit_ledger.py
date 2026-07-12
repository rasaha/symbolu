"""Durable append-only audit ledger with a SEPARATE checkpoint signer.

Two roles are cryptographically distinct:
  * WRITER (the broker) appends hash-chained records to a SQLite ledger whose
    file is readable only by the broker user; UPDATE/DELETE are blocked by
    triggers.
  * CHECKPOINT SIGNER holds the Ed25519 *checkpoint* private key (separate
    custody, not held by the agent, gateway, or even the broker in the isolated
    deployment) and signs the chain head. Verifiers use the checkpoint PUBLIC
    key only.

Therefore a compromised agent or gateway (no ledger file access, no checkpoint
key) can neither rewrite history nor forge a checkpoint; truncation below a signed
head is detected because the externally-held checkpoint no longer matches.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from . import crypto


def _h(prev: str, payload: dict) -> str:
    return hashlib.sha256((prev + json.dumps(payload, sort_keys=True)).encode()).hexdigest()


class AuditLedger:
    def __init__(self, db_path: str):
        self.path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init(self):
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS records(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, prev_hash TEXT, payload TEXT,
                record_hash TEXT NOT NULL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS checkpoints(
                head_seq INTEGER, head_hash TEXT, signed_at TEXT, signature TEXT)""")
            # WORM: block in-place rewrite / deletion of committed records
            c.execute("""CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON records
                BEGIN SELECT RAISE(ABORT,'append-only'); END""")
            c.execute("""CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON records
                BEGIN SELECT RAISE(ABORT,'append-only'); END""")

    def append(self, payload: dict) -> str:
        with self._conn() as c:
            row = c.execute("SELECT record_hash FROM records ORDER BY seq DESC LIMIT 1").fetchone()
            prev = row[0] if row else "genesis"
            rh = _h(prev, payload)
            c.execute("INSERT INTO records(prev_hash, payload, record_hash) VALUES(?,?,?)",
                      (prev, json.dumps(payload, sort_keys=True), rh))
        return rh

    def head(self):
        with self._conn() as c:
            row = c.execute("SELECT seq, record_hash FROM records ORDER BY seq DESC LIMIT 1").fetchone()
            return (row[0], row[1]) if row else (0, "genesis")

    def verify_chain(self) -> bool:
        with self._conn() as c:
            prev = "genesis"
            for seq, ph, payload, rh in c.execute(
                    "SELECT seq, prev_hash, payload, record_hash FROM records ORDER BY seq"):
                if ph != prev or _h(prev, json.loads(payload)) != rh:
                    return False
                prev = rh
        return True

    # ---- checkpoint signer role (separate key custody) ----

    def sign_checkpoint(self, checkpoint_sk, *, at: str) -> dict:
        seq, hh = self.head()
        body = {"head_seq": seq, "head_hash": hh}
        sig = crypto.sign(checkpoint_sk, body)
        with self._conn() as c:
            c.execute("INSERT INTO checkpoints(head_seq, head_hash, signed_at, signature) "
                      "VALUES(?,?,?,?)", (seq, hh, at, sig))
        return {**body, "signature": sig}

    def latest_checkpoint(self):
        with self._conn() as c:
            row = c.execute("SELECT head_seq, head_hash, signature FROM checkpoints "
                            "ORDER BY rowid DESC LIMIT 1").fetchone()
            return {"head_seq": row[0], "head_hash": row[1], "signature": row[2]} if row else None

    def verify_against_checkpoint(self, keyring) -> dict:
        """Verify chain integrity + the checkpoint signature + no truncation."""
        chain_ok = self.verify_chain()
        cp = self.latest_checkpoint()
        if cp is None:
            return {"intact": chain_ok, "checkpoint": None, "truncated": False}
        sig_ok = keyring.verify("checkpoint", {"head_seq": cp["head_seq"],
                                               "head_hash": cp["head_hash"]}, cp["signature"])
        seq, hh = self.head()
        # truncation: current head is behind the last signed checkpoint
        truncated = seq < cp["head_seq"]
        # or the record at the checkpointed seq no longer hashes to head_hash
        with self._conn() as c:
            row = c.execute("SELECT record_hash FROM records WHERE seq=?", (cp["head_seq"],)).fetchone()
        mismatch = row is None or row[0] != cp["head_hash"]
        return {"intact": chain_ok and sig_ok and not truncated and not mismatch,
                "chain_ok": chain_ok, "checkpoint_sig_ok": sig_ok,
                "truncated": truncated or mismatch, "head_seq": seq,
                "checkpoint_seq": cp["head_seq"]}
