"""Unified audit trace (Phase 5). Immutable event records (not just a final summary) + a deterministic
replay signature. Supports redacted and full internal views. No wall-clock: latency is in deterministic
units, timestamps come from the request. Stdlib-only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

AUDIT_VERSION = "gip_audit_v1"

# fields redacted in the operator (non-internal) view
_REDACT = {"source_repr", "transformed_repr"}


@dataclass
class AuditEvent:
    trace_id: str
    seq: int
    stage: str
    component_version: str
    disposition: str
    shadow_outcome: str
    reason_codes: List[str] = field(default_factory=list)
    source_repr: Dict[str, Any] = field(default_factory=dict)
    transformed_repr: Dict[str, Any] = field(default_factory=dict)
    semantic_loss: List[str] = field(default_factory=list)
    missing_metadata: List[str] = field(default_factory=list)
    claim_refs: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    action_refs: List[str] = field(default_factory=list)
    latency_units: int = 0
    cumulative_latency_units: int = 0
    estimated_cost_usd: float = 0.0
    error: str = ""


@dataclass
class AuditTrace:
    trace_id: str
    parent_trace: str = ""
    request_snapshot: Dict[str, Any] = field(default_factory=dict)
    source_artifact_hashes: Dict[str, str] = field(default_factory=dict)
    component_versions: Dict[str, str] = field(default_factory=dict)
    policy_versions: Dict[str, str] = field(default_factory=dict)
    events: List[AuditEvent] = field(default_factory=list)
    final_shadow_disposition: str = ""
    human_review_state: str = "not_required"
    replay_signature: str = ""

    def add(self, ev: AuditEvent) -> None:
        ev.seq = len(self.events)
        ev.cumulative_latency_units = sum(e.latency_units for e in self.events) + ev.latency_units
        self.events.append(ev)

    def finalize(self, final: str) -> None:
        self.final_shadow_disposition = final
        self.replay_signature = self.compute_signature()

    def compute_signature(self) -> str:
        """Deterministic signature over the DECISION-BEARING content (not latency/cost), so replay can
        detect decision drift independent of instrumentation."""
        payload = {
            "trace_id": self.trace_id,
            "request": self.request_snapshot,
            "events": [{"stage": e.stage, "disposition": e.disposition,
                        "shadow_outcome": e.shadow_outcome, "reason_codes": e.reason_codes,
                        "semantic_loss": e.semantic_loss} for e in self.events],
            "final": self.final_shadow_disposition,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def view(self, internal: bool = False) -> Dict[str, Any]:
        d = asdict(self)
        if not internal:
            for ev in d["events"]:
                for k in _REDACT:
                    ev[k] = "<redacted>"
        return d

    def audit_complete(self) -> bool:
        """A complete audit has an event per attempted stage, a final disposition, and a signature."""
        return bool(self.events) and bool(self.final_shadow_disposition) and bool(self.replay_signature)


def artifact_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]
