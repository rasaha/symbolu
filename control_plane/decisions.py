"""Canonical append-only Decision Record with hash chaining + audit log (Phase 6).

Supports deterministic replay, causal tracing, independent evaluation, conflict investigation,
audit reconstruction, and redacted external review. No raw prompt/response by default.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DecisionRecord:
    decision_id: str
    request_id: str
    trace_id: str
    component: str
    component_version: str
    decision_type: str
    output_state: str
    reason_codes: List[str] = field(default_factory=list)
    input_ref: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    evidence_timestamps: List[float] = field(default_factory=list)
    policy_version: str = ""
    registry_version: str = ""
    confidence: Optional[float] = None
    human_authority_ref: Optional[str] = None
    override_status: str = "none"          # none | applied
    override_actor: Optional[str] = None
    override_rationale: Optional[str] = None
    latency_ms: float = 0.0
    projected_cost_usd: float = 0.0
    observed_cost_usd: float = 0.0
    selected_candidate: Optional[str] = None
    excluded_candidates: List[str] = field(default_factory=list)
    assertion_disposition: Optional[str] = None
    action_disposition: Optional[str] = None
    execution_outcome: Optional[str] = None
    prior_record_hash: str = ""
    record_hash: str = ""


_SECRETS = ("api_key", "authorization", "token", "secret", "password", "bearer")


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: ("<redacted>" if any(s in str(k).lower() for s in _SECRETS) else _redact(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def _hash(payload: Dict[str, Any], prior: str) -> str:
    body = dict(payload)
    body.pop("record_hash", None)
    body["prior_record_hash"] = prior
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


class AuditLog:
    """Append-only hash-chained decision log. Aborts (raises) on write failure."""

    def __init__(self, path: Optional[str] = None):
        self.path = path
        self.records: List[Dict[str, Any]] = []
        self._last_hash = ""
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)

    def append(self, rec: DecisionRecord) -> DecisionRecord:
        rec.prior_record_hash = self._last_hash
        payload = _redact(asdict(rec))
        rec.record_hash = _hash(payload, self._last_hash)
        payload["record_hash"] = rec.record_hash
        if self.path:
            try:
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(payload, sort_keys=True) + "\n")
            except OSError as e:
                raise IOError(f"AUDIT_CHAIN write failure: {e}")
        self.records.append(payload)
        self._last_hash = rec.record_hash
        return rec

    def verify_chain(self) -> bool:
        prior = ""
        for p in self.records:
            expect = _hash(p, prior)
            if expect != p["record_hash"] or p["prior_record_hash"] != prior:
                return False
            prior = p["record_hash"]
        return True

    def trace(self, trace_id: str) -> List[Dict[str, Any]]:
        return [p for p in self.records if p["trace_id"] == trace_id]
