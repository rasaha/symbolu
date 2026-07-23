"""Audit facade (Phase 10). Thin wrapper over the append-only hash-chained AuditLog in
decisions.py, plus helpers the orchestrator uses to build records and verify trace
completeness (invariant 20). Audit owns the chain; no other component writes it.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from control_plane.decisions import AuditLog, DecisionRecord
from control_plane.failure_codes import Failure


class Audit:
    def __init__(self, path: Optional[str] = None):
        self.log = AuditLog(path)
        self._counter = 0

    def record(self, *, request_id: str, trace_id: str, component: str, component_version: str,
               decision_type: str, output_state: str, reason_codes: Optional[List[str]] = None,
               input_ref: str = "", evidence_refs: Optional[List[str]] = None,
               policy_version: str = "", registry_version: str = "", **extra) -> DecisionRecord:
        self._counter += 1
        rec = DecisionRecord(
            decision_id=f"{trace_id}:{self._counter:03d}", request_id=request_id, trace_id=trace_id,
            component=component, component_version=component_version, decision_type=decision_type,
            output_state=output_state, reason_codes=list(reason_codes or []), input_ref=input_ref,
            evidence_refs=list(evidence_refs or []), policy_version=policy_version,
            registry_version=registry_version,
            **{k: v for k, v in extra.items() if k in DecisionRecord.__dataclass_fields__})
        return self.log.append(rec)

    def verify(self) -> bool:
        return self.log.verify_chain()

    def trace(self, trace_id: str) -> List[Dict]:
        return self.log.trace(trace_id)

    def trace_complete(self, trace_id: str) -> Optional[Failure]:
        """Invariant 20: a trace must end in exactly one terminal record and verify clean."""
        recs = self.trace(trace_id)
        if not recs:
            return Failure.TRACE_INCOMPLETE
        if not self.verify():
            return Failure.AUDIT_CHAIN_BROKEN
        return None
