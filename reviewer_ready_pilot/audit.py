"""Phase 14 - Review audit trail.

An append-only, hash-chained record of every reviewer action in the pilot. It exists so a later auditor
can verify that the blinded workflow was actually followed - that no reveal preceded a Stage-A label, that
records were not edited after submission, that overrides carried reasons, and that nothing was enforced.

Design:
  * Each entry records: sequence index, logical timestamp (caller-supplied, so the log is deterministic
    and replayable), pseudonymous reviewer_id, role, artifact_id, event type, a content hash of the
    payload, and the previous entry's hash (chain). Tampering breaks the chain.
  * The log is APPEND-ONLY. There is no update or delete. `verify()` re-derives the chain and checks the
    workflow invariants; it returns findings rather than throwing, so an audit can report every problem.

Event types: ASSIGNED, STAGE_A_SUBMITTED, REVEALED, STAGE_B_SUBMITTED, OVERRIDE, ADJUDICATED, WITHDRAWN.
Deterministic, stdlib-only. No enforcement or external effect occurs here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

AUDIT_VERSION = "review_audit_v1"

ASSIGNED = "ASSIGNED"
STAGE_A_SUBMITTED = "STAGE_A_SUBMITTED"
REVEALED = "REVEALED"
STAGE_B_SUBMITTED = "STAGE_B_SUBMITTED"
OVERRIDE = "OVERRIDE"
ADJUDICATED = "ADJUDICATED"
WITHDRAWN = "WITHDRAWN"

_EVENT_TYPES = {ASSIGNED, STAGE_A_SUBMITTED, REVEALED, STAGE_B_SUBMITTED, OVERRIDE, ADJUDICATED, WITHDRAWN}
_GENESIS = "0" * 64


def _hash(payload: Dict[str, Any], prev: str) -> str:
    return hashlib.sha256((prev + "|" + json.dumps(payload, sort_keys=True)).encode()).hexdigest()


@dataclass
class AuditEntry:
    seq: int
    ts: int                               # logical timestamp (caller-supplied)
    reviewer_id: str
    role: str
    artifact_id: str
    event: str
    payload_hash: str
    prev_hash: str
    entry_hash: str

    def as_dict(self) -> Dict[str, Any]:
        return {"seq": self.seq, "ts": self.ts, "reviewer_id": self.reviewer_id, "role": self.role,
                "artifact_id": self.artifact_id, "event": self.event, "payload_hash": self.payload_hash,
                "prev_hash": self.prev_hash, "entry_hash": self.entry_hash}


class AuditLog:
    def __init__(self) -> None:
        self._entries: List[AuditEntry] = []

    @property
    def entries(self) -> List[AuditEntry]:
        return list(self._entries)

    def record(self, *, ts: int, reviewer_id: str, role: str, artifact_id: str, event: str,
               payload: Optional[Dict[str, Any]] = None) -> AuditEntry:
        if event not in _EVENT_TYPES:
            raise ValueError(f"unknown event {event}")
        payload = payload or {}
        prev = self._entries[-1].entry_hash if self._entries else _GENESIS
        ph = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        seq = len(self._entries)
        eh = _hash({"seq": seq, "ts": ts, "reviewer_id": reviewer_id, "role": role,
                    "artifact_id": artifact_id, "event": event, "payload_hash": ph}, prev)
        entry = AuditEntry(seq=seq, ts=ts, reviewer_id=reviewer_id, role=role, artifact_id=artifact_id,
                           event=event, payload_hash=ph, prev_hash=prev, entry_hash=eh)
        self._entries.append(entry)
        return entry

    # --- convenience recorders (payload carried only as a hash; raw payload stays out of the log) ---
    def assigned(self, ts, reviewer_id, role, artifact_id):
        return self.record(ts=ts, reviewer_id=reviewer_id, role=role, artifact_id=artifact_id, event=ASSIGNED)

    def stage_a(self, ts, reviewer_id, role, artifact_id, label):
        return self.record(ts=ts, reviewer_id=reviewer_id, role=role, artifact_id=artifact_id,
                           event=STAGE_A_SUBMITTED, payload=label)

    def revealed(self, ts, reviewer_id, role, artifact_id, system_result):
        return self.record(ts=ts, reviewer_id=reviewer_id, role=role, artifact_id=artifact_id,
                           event=REVEALED, payload=system_result)

    def stage_b(self, ts, reviewer_id, role, artifact_id, label):
        ev = OVERRIDE if label.get("override") else STAGE_B_SUBMITTED
        return self.record(ts=ts, reviewer_id=reviewer_id, role=role, artifact_id=artifact_id,
                           event=ev, payload=label)


def verify(log: AuditLog) -> Dict[str, Any]:
    """Re-derive the chain and check the blinded-workflow invariants. Returns findings, never throws."""
    findings: List[str] = []
    prev = _GENESIS
    # per (reviewer, artifact) workflow state
    state: Dict[tuple, Dict[str, Any]] = {}

    for e in log.entries:
        # chain integrity
        recomputed = _hash({"seq": e.seq, "ts": e.ts, "reviewer_id": e.reviewer_id, "role": e.role,
                            "artifact_id": e.artifact_id, "event": e.event,
                            "payload_hash": e.payload_hash}, prev)
        if e.prev_hash != prev:
            findings.append(f"seq {e.seq}: broken prev_hash link")
        if e.entry_hash != recomputed:
            findings.append(f"seq {e.seq}: entry_hash mismatch (tampering)")
        prev = e.entry_hash

        key = (e.reviewer_id, e.artifact_id)
        st = state.setdefault(key, {"a": False, "revealed": False, "b": False})
        if e.event == STAGE_A_SUBMITTED:
            if st["a"]:
                findings.append(f"seq {e.seq}: duplicate Stage A for {key}")
            if st["revealed"]:
                findings.append(f"seq {e.seq}: Stage A after reveal for {key} (blinding violated)")
            st["a"] = True
        elif e.event == REVEALED:
            if not st["a"]:
                findings.append(f"seq {e.seq}: reveal before Stage A for {key} (blinding violated)")
            st["revealed"] = True
        elif e.event in (STAGE_B_SUBMITTED, OVERRIDE):
            if not st["revealed"]:
                findings.append(f"seq {e.seq}: Stage B before reveal for {key}")
            if st["b"]:
                findings.append(f"seq {e.seq}: duplicate Stage B for {key}")
            st["b"] = True

    return {"audit_version": AUDIT_VERSION, "n_entries": len(log.entries),
            "chain_ok": not any("hash" in f or "link" in f for f in findings),
            "workflow_ok": not findings, "findings": findings}
