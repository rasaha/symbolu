"""Phase 12 - Access control.

Enforces, at read time, the governance rules from REVIEWER_GOVERNANCE_PROTOCOL.md:
  * role-scoped   - a reviewer only reaches artifacts assigned to them,
  * tenant-scoped - a reviewer only reaches their own tenant's artifacts,
  * stage-scoped  - at Stage A a reviewer gets the blinded view only (never the system result),
  * isolation     - a reviewer can never read another reviewer's label.

Every decision is a deny-by-default check. A denied access raises AccessDenied - it never silently
degrades to a partial view. Deterministic, stdlib-only. No enforcement of policy outcomes happens here;
this only governs who may read what.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from reviewer_ready_pilot import review_interface

_BLINDED_FIELDS = review_interface._BLINDED_FIELDS


class AccessDenied(Exception):
    pass


class AccessController:
    def __init__(self, assignment_plan: Dict[str, Any], tenant_of: Dict[str, str]):
        """`assignment_plan`: AssignmentPlan.as_dict(). `tenant_of`: reviewer_id -> tenant."""
        self._assigned: Dict[str, Set[str]] = {}
        for a in assignment_plan.get("assignments", []):
            for rid in a["reviewer_ids"]:
                self._assigned.setdefault(rid, set()).add(a["artifact_id"])
        self._tenant_of = dict(tenant_of)

    def can_access(self, reviewer_id: str, artifact_id: str) -> bool:
        return artifact_id in self._assigned.get(reviewer_id, set())

    def assigned_artifacts(self, reviewer_id: str) -> List[str]:
        return sorted(self._assigned.get(reviewer_id, set()))

    def blinded_view(self, reviewer_id: str, artifact: Dict[str, Any]) -> Dict[str, Any]:
        """Stage A read: blinded metadata only, and only for an assigned artifact."""
        if not self.can_access(reviewer_id, artifact["artifact_id"]):
            raise AccessDenied(f"{reviewer_id} not assigned {artifact['artifact_id']}")
        return {k: artifact.get(k) for k in _BLINDED_FIELDS if k in artifact}

    def system_result(self, reviewer_id: str, artifact_id: str, stage_a_locked: bool,
                      result: Dict[str, Any]) -> Dict[str, Any]:
        """Stage B read: the system result, only after this reviewer's Stage A is locked."""
        if not self.can_access(reviewer_id, artifact_id):
            raise AccessDenied(f"{reviewer_id} not assigned {artifact_id}")
        if not stage_a_locked:
            raise AccessDenied("system result withheld until Stage A is locked (blinding)")
        return dict(result)

    def read_other_label(self, reviewer_id: str, other_reviewer_id: str) -> None:
        """Reviewers can NEVER read another reviewer's label. Always denied."""
        raise AccessDenied("reviewer labels are isolated; cross-reviewer reads are forbidden")

    def cross_tenant(self, reviewer_id: str, artifact_tenant: str) -> bool:
        """True only if the reviewer's tenant matches the artifact's tenant."""
        return self._tenant_of.get(reviewer_id) == artifact_tenant
