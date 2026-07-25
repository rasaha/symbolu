"""Assessment repository (port + in-memory adapter).

Finalized assessments are append-only and versioned; supersession appends a new
version referencing the prior one. No destructive deletion; history and
supersession chains are retrievable.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..assessments.assessment import Assessment
from ..errors import AssessmentNotFoundError, VersionConflictError


@runtime_checkable
class AssessmentRepository(Protocol):
    def create_assessment(self, a: Assessment) -> Assessment: ...
    def get_assessment(self, assessment_id: str) -> Assessment: ...
    def list_assessments(self, tenant_id: str) -> tuple[Assessment, ...]: ...
    def get_latest_assessment(self, workspace_id: str) -> Optional[Assessment]: ...
    def get_assessment_history(self, workspace_id: str) -> tuple[Assessment, ...]: ...


class InMemoryAssessmentRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, Assessment] = {}
        self._by_workspace: dict[str, list[Assessment]] = {}

    def create_assessment(self, a: Assessment) -> Assessment:
        if a.assessment_id in self._by_id:
            raise VersionConflictError(
                f"assessment '{a.assessment_id}' already exists; assessments are immutable")
        self._by_id[a.assessment_id] = a
        self._by_workspace.setdefault(a.workspace_id, []).append(a)
        return a

    def get_assessment(self, assessment_id: str) -> Assessment:
        a = self._by_id.get(assessment_id)
        if a is None:
            raise AssessmentNotFoundError(f"assessment '{assessment_id}' not found")
        return a

    def list_assessments(self, tenant_id: str) -> tuple[Assessment, ...]:
        return tuple(sorted(
            (a for a in self._by_id.values() if a.tenant_id == tenant_id),
            key=lambda a: (a.workspace_id, a.version)))

    def get_latest_assessment(self, workspace_id: str) -> Optional[Assessment]:
        chain = self._by_workspace.get(workspace_id)
        if not chain:
            return None
        return max(chain, key=lambda a: a.version)

    def get_assessment_history(self, workspace_id: str) -> tuple[Assessment, ...]:
        return tuple(sorted(self._by_workspace.get(workspace_id, ()),
                            key=lambda a: a.version))
