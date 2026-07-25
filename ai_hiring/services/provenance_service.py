"""Provenance service — lineage and version-history reconstruction.

Read-only reconstruction over the provenance and lineage repositories:
* full transformation history for a version,
* the version ancestry chain for an evidence id,
* the lineage DAG for an evidence id.

No mutation, scoring, or interpretation.
"""

from __future__ import annotations

from ..normalization.lineage import LineageGraph
from ..normalization.models import Provenance, TransformationStep
from ..repositories.evidence_artifacts import LineageRepository, ProvenanceRepository


class ProvenanceService:
    def __init__(
        self,
        provenance_repository: ProvenanceRepository,
        lineage_repository: LineageRepository,
    ) -> None:
        self._prov = provenance_repository
        self._lineage = lineage_repository

    def versions(self, evidence_id: str) -> tuple[Provenance, ...]:
        """All provenance versions for an evidence id, oldest first."""
        return self._prov.versions_of(evidence_id)

    def ancestry(self, evidence_id: str) -> tuple[int, ...]:
        """The ordered version chain (e.g. (1, 2, 3))."""
        return tuple(p.version for p in self._prov.versions_of(evidence_id))

    def transformation_history(
        self, evidence_id: str, version: int
    ) -> tuple[TransformationStep, ...]:
        """The recorded transformation steps for a specific version."""
        for prov in self._prov.versions_of(evidence_id):
            if prov.version == version:
                return prov.transformation_history
        return ()

    def lineage(self, evidence_id: str) -> LineageGraph:
        """The reconstructable lineage DAG for an evidence id."""
        return LineageGraph(nodes=self._lineage.for_evidence(evidence_id))
