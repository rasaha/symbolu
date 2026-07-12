"""Immutable audit record + append-only hash chain (spec §14).

Tamper-EVIDENT given a protected audit key. NOT tamper-proof external storage
and NOT a blockchain — no such claim is made.
"""

from __future__ import annotations

from typing import Any

from . import canon_profile as cp
from . import hashing, jcs, signing
from .errors import AuditChainError


def build_audit_record(
    *, action_hash: str, decision: str, dispositive_rules: list, policy_hash: str,
    evidence_hashes: list, approval_hashes: list, applied_constraints: dict | None,
    timestamps: dict, execution_token_hash: str | None = None,
    execution_result_hash: str | None = None,
    algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID,
) -> dict:
    payload: dict[str, Any] = {
        "action_hash": action_hash,
        "decision": decision,
        "dispositive_rules": dispositive_rules,
        "policy_hash": policy_hash,
        "evidence_hashes": sorted(evidence_hashes),
        "approval_hashes": sorted(approval_hashes),
        "applied_constraints": applied_constraints,
        "timestamps": timestamps,
        "execution_token_hash": execution_token_hash,
        "execution_result_hash": execution_result_hash,
        "canonicalization_version": cp.CANONICALIZATION_VERSION,
        "envelope_schema_version": cp.ENVELOPE_SCHEMA_VERSION,
        "hash_algorithm_id": algorithm_id,
    }
    rec_hash = hashing.domain_digest("AUDIT_RECORD", jcs.canonicalize(payload), algorithm_id=algorithm_id)
    return {"payload": payload, "audit_record_hash": rec_hash, "hash_algorithm_id": algorithm_id,
            "signature": signing.sign("audit", rec_hash)}


def verify_record(record: dict) -> bool:
    algo = record["hash_algorithm_id"]
    rec_hash = hashing.domain_digest("AUDIT_RECORD", jcs.canonicalize(record["payload"]), algorithm_id=algo)
    if rec_hash != record["audit_record_hash"]:
        return False
    return signing.verify("audit", rec_hash, record["signature"])


class AuditChain:
    """Append-only, hash-chained audit log (in-memory reference)."""

    def __init__(self, chain_id: str, *, algorithm_id: str = cp.DEFAULT_HASH_ALGORITHM_ID):
        self.chain_id = chain_id
        self.algorithm_id = algorithm_id
        genesis_payload = {"genesis": True, "chain_id": chain_id,
                           "canonicalization_version": cp.CANONICALIZATION_VERSION}
        self.genesis = hashing.domain_digest("AUDIT_CHAIN", jcs.canonicalize(genesis_payload),
                                             algorithm_id=algorithm_id)
        self.records: list[dict] = []
        self.chain: list[str] = [self.genesis]

    def append(self, record: dict) -> str:
        if not verify_record(record):
            raise AuditChainError("record failed self-verification before append")
        prev = self.chain[-1]
        new = hashing.raw_chain_hash(prev, record["audit_record_hash"], algorithm_id=self.algorithm_id)
        self.records.append(record)
        self.chain.append(new)
        return new

    def head(self) -> str:
        return self.chain[-1]

    def verify(self) -> bool:
        """Recompute the whole chain; True iff intact (tamper detection)."""
        cur = self.genesis
        for rec in self.records:
            if not verify_record(rec):
                return False
            cur = hashing.raw_chain_hash(cur, rec["audit_record_hash"], algorithm_id=self.algorithm_id)
        return cur == self.chain[-1]

    def locate_tamper(self) -> int | None:
        """Return the index of the first tampered record, or None if intact."""
        cur = self.genesis
        for i, rec in enumerate(self.records):
            expected = self.chain[i + 1]
            if not verify_record(rec):
                return i
            cur = hashing.raw_chain_hash(cur, rec["audit_record_hash"], algorithm_id=self.algorithm_id)
            if cur != expected:
                return i
        return None
