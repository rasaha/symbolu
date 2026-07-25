"""Repository protocols (ports).

Services depend on these Protocols, not on concrete adapters, so persistence is
injectable. This phase ships only in-memory adapters (see :mod:`.in_memory`); a
production database is a later phase.

Contract shared by the versioned record repositories:

* IDs are unique per (logical id, version).
* Immutable records cannot be overwritten — re-adding the same (id, version)
  raises :class:`~ai_hiring.errors.VersionConflictError`.
* Revisions are stored as new versions; ``get`` returns the latest version.

The audit repository is deliberately append/read-only: it exposes no update or
delete operation.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.audit import AuditEvent
from ..domain.decision import Decision
from ..domain.evaluation import CandidateEvaluation
from ..domain.evidence import NormalizedEvidence
from ..domain.recommendation import Recommendation
from ..domain.workflow import CandidateWorkflow


@runtime_checkable
class EvidenceRepository(Protocol):
    def add(self, record: NormalizedEvidence) -> NormalizedEvidence: ...
    def get(self, evidence_id: str) -> NormalizedEvidence: ...
    def get_version(self, evidence_id: str, version: int) -> NormalizedEvidence: ...
    def exists(self, evidence_id: str) -> bool: ...


@runtime_checkable
class EvaluationRepository(Protocol):
    def add(self, record: CandidateEvaluation) -> CandidateEvaluation: ...
    def get(self, evaluation_id: str) -> CandidateEvaluation: ...
    def get_version(self, evaluation_id: str, version: int) -> CandidateEvaluation: ...
    def exists(self, evaluation_id: str) -> bool: ...


@runtime_checkable
class RecommendationRepository(Protocol):
    def add(self, record: Recommendation) -> Recommendation: ...
    def get(self, recommendation_id: str) -> Recommendation: ...
    def exists(self, recommendation_id: str) -> bool: ...


@runtime_checkable
class DecisionRepository(Protocol):
    def add(self, record: Decision) -> Decision: ...
    def get(self, decision_id: str) -> Decision: ...
    def exists(self, decision_id: str) -> bool: ...
    def get_for_evaluation(self, evaluation_id: str) -> Decision | None: ...


@runtime_checkable
class WorkflowRepository(Protocol):
    def save(self, record: CandidateWorkflow) -> CandidateWorkflow: ...
    def get(self, candidate_id: str) -> CandidateWorkflow: ...
    def exists(self, candidate_id: str) -> bool: ...


# AuditRepository extracted to the DGM kernel in Phase 5B; re-exported here.
from decision_governance.audit.repository import AuditRepository  # noqa: F401,E402
