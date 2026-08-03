"""Assessment workspace repository (port + in-memory adapter).

Append-only and version-aware: workspace status transitions create new immutable
versions; the working artifacts (bindings, exclusions, observations, missing
records, conflicts) accumulate in append-only sub-stores keyed by workspace_id.
No destructive deletion.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..assessments.evidence_binding import EvidenceBinding, ExcludedEvidenceRecord
from ..assessments.missing_evidence import MissingEvidenceRecord
from ..assessments.observation import Observation
from ..assessments.workspace import AssessmentWorkspace
from ..errors import AssessmentWorkspaceNotFoundError, VersionConflictError
from ..rubrics.conflicts import Conflict


@runtime_checkable
class AssessmentWorkspaceRepository(Protocol):
    def create_workspace(self, w: AssessmentWorkspace) -> AssessmentWorkspace: ...
    def get_workspace(self, workspace_id: str) -> AssessmentWorkspace: ...
    def save_workspace_version(self, w: AssessmentWorkspace) -> AssessmentWorkspace: ...
    def list_workspaces(self, tenant_id: str) -> tuple[AssessmentWorkspace, ...]: ...
    def history(self, workspace_id: str) -> tuple[AssessmentWorkspace, ...]: ...
    def add_binding(self, b: EvidenceBinding) -> EvidenceBinding: ...
    def list_bindings(self, workspace_id: str) -> tuple[EvidenceBinding, ...]: ...
    def add_excluded(self, r: ExcludedEvidenceRecord) -> ExcludedEvidenceRecord: ...
    def list_excluded(self, workspace_id: str) -> tuple[ExcludedEvidenceRecord, ...]: ...
    def add_observation(self, o: Observation) -> Observation: ...
    def list_observations(self, workspace_id: str) -> tuple[Observation, ...]: ...
    def add_missing(self, m: MissingEvidenceRecord) -> MissingEvidenceRecord: ...
    def list_missing(self, workspace_id: str) -> tuple[MissingEvidenceRecord, ...]: ...
    def add_conflict(self, c: Conflict, workspace_id: str) -> Conflict: ...
    def list_conflicts(self, workspace_id: str) -> tuple[Conflict, ...]: ...


class InMemoryAssessmentWorkspaceRepository:
    def __init__(self) -> None:
        self._versions: dict[str, list[AssessmentWorkspace]] = {}
        self._bindings: dict[str, list[EvidenceBinding]] = {}
        self._excluded: dict[str, list[ExcludedEvidenceRecord]] = {}
        self._observations: dict[str, list[Observation]] = {}
        self._missing: dict[str, list[MissingEvidenceRecord]] = {}
        self._conflicts: dict[str, list[Conflict]] = {}

    def create_workspace(self, w: AssessmentWorkspace) -> AssessmentWorkspace:
        if w.workspace_id in self._versions:
            raise VersionConflictError(f"workspace '{w.workspace_id}' already exists")
        if w.version != 1:
            raise VersionConflictError("initial workspace must be version 1")
        self._versions[w.workspace_id] = [w]
        return w

    def get_workspace(self, workspace_id: str) -> AssessmentWorkspace:
        snaps = self._versions.get(workspace_id)
        if not snaps:
            raise AssessmentWorkspaceNotFoundError(f"workspace '{workspace_id}' not found")
        return snaps[-1]

    def save_workspace_version(self, w: AssessmentWorkspace) -> AssessmentWorkspace:
        snaps = self._versions.get(w.workspace_id)
        if not snaps:
            raise AssessmentWorkspaceNotFoundError(f"workspace '{w.workspace_id}' not found")
        if w.version != snaps[-1].version + 1:
            raise VersionConflictError(
                f"workspace '{w.workspace_id}' expected version {snaps[-1].version + 1}")
        snaps.append(w)
        return w

    def list_workspaces(self, tenant_id: str) -> tuple[AssessmentWorkspace, ...]:
        return tuple(sorted(
            (snaps[-1] for snaps in self._versions.values()
             if snaps[-1].tenant_id == tenant_id),
            key=lambda w: w.workspace_id))

    def history(self, workspace_id: str) -> tuple[AssessmentWorkspace, ...]:
        return tuple(self._versions.get(workspace_id, ()))

    # --- append-only sub-stores -------------------------------------------
    def add_binding(self, b: EvidenceBinding) -> EvidenceBinding:
        self._bindings.setdefault(b.workspace_id, []).append(b)
        return b

    def list_bindings(self, workspace_id: str) -> tuple[EvidenceBinding, ...]:
        return tuple(self._bindings.get(workspace_id, ()))

    def add_excluded(self, r: ExcludedEvidenceRecord) -> ExcludedEvidenceRecord:
        self._excluded.setdefault(r.workspace_id, []).append(r)
        return r

    def list_excluded(self, workspace_id: str) -> tuple[ExcludedEvidenceRecord, ...]:
        return tuple(self._excluded.get(workspace_id, ()))

    def add_observation(self, o: Observation) -> Observation:
        self._observations.setdefault(o.workspace_id, []).append(o)
        return o

    def list_observations(self, workspace_id: str) -> tuple[Observation, ...]:
        return tuple(self._observations.get(workspace_id, ()))

    def add_missing(self, m: MissingEvidenceRecord) -> MissingEvidenceRecord:
        self._missing.setdefault(m.workspace_id, []).append(m)
        return m

    def list_missing(self, workspace_id: str) -> tuple[MissingEvidenceRecord, ...]:
        return tuple(self._missing.get(workspace_id, ()))

    def add_conflict(self, c: Conflict, workspace_id: str) -> Conflict:
        self._conflicts.setdefault(workspace_id, []).append(c)
        return c

    def list_conflicts(self, workspace_id: str) -> tuple[Conflict, ...]:
        return tuple(self._conflicts.get(workspace_id, ()))

    def get_binding(self, workspace_id: str, binding_id: str) -> Optional[EvidenceBinding]:
        for b in self._bindings.get(workspace_id, ()):
            if b.binding_id == binding_id:
                return b
        return None
