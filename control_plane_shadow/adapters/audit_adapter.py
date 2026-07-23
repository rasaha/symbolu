"""Audit adapter (Phase 5). Wraps the prior track's append-only hash-chained Audit
(control_plane.audit.Audit). Every component decision becomes one append-only record; the chain
is tamper-evident (invariant 11) and trace completeness is checkable (invariant 20). Supports an
`available` flag so partial-degradation scenarios can exercise audit-failure handling.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from control_plane.audit import Audit
from control_plane_shadow.adapters.base import AdapterHealth, ShadowAdapter


class AuditAdapter(ShadowAdapter):
    component = "Audit"
    source_version = "control_plane_audit_v1"

    def __init__(self, available: bool = True, path: Optional[str] = None):
        self.audit = Audit(path)
        self._available = available

    def health(self) -> AdapterHealth:
        return AdapterHealth(self.component, available=self._available, determinism="deterministic",
                             live_call_risk=False, real_action_risk=False,
                             source_version=self.source_version, adapter_version=self.adapter_version,
                             capabilities=["append_only", "hash_chain", "trace_completeness"])

    def record(self, **kw) -> bool:
        if not self._available:
            return False
        self.audit.record(**kw)
        return True

    def verify(self) -> bool:
        return self.audit.verify()

    def trace(self, trace_id: str) -> List[Dict[str, Any]]:
        return self.audit.trace(trace_id)

    def trace_complete(self, trace_id: str):
        return self.audit.trace_complete(trace_id)
