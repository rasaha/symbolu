"""In-memory repository adapters for development and tests.

These are the reference implementations of the repository ports. They enforce
uniqueness, immutability (no overwrite of an existing version), version-conflict
detection, and — for decisions — one binding decision per evaluation stage. The
audit store is strictly append/read-only.

No production database is included in this phase.
"""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

from ..domain.audit import AuditEvent
from ..domain.decision import Decision
from ..domain.evaluation import CandidateEvaluation
from ..domain.evidence import NormalizedEvidence
from ..domain.recommendation import Recommendation
from ..domain.workflow import CandidateWorkflow
from ..errors import (
    DuplicateDecisionError,
    RecordNotFoundError,
    VersionConflictError,
)

T = TypeVar("T")


class _VersionedStore(Generic[T]):
    """Backing store keyed by (logical id -> {version -> record}).

    Adding an (id, version) that already exists is a version conflict, which
    enforces immutability: a stored record can never be silently overwritten.
    """

    def __init__(
        self,
        id_of: Callable[[T], str],
        version_of: Callable[[T], int],
        label: str,
    ) -> None:
        self._id_of = id_of
        self._version_of = version_of
        self._label = label
        self._data: dict[str, dict[int, T]] = {}

    def add(self, record: T) -> T:
        rid = self._id_of(record)
        version = self._version_of(record)
        versions = self._data.setdefault(rid, {})
        if version in versions:
            raise VersionConflictError(
                f"{self._label} '{rid}' version {version} already exists; "
                "immutable records cannot be overwritten"
            )
        versions[version] = record
        return record

    def get(self, rid: str) -> T:
        versions = self._data.get(rid)
        if not versions:
            raise RecordNotFoundError(f"{self._label} '{rid}' not found")
        latest = max(versions)
        return versions[latest]

    def get_version(self, rid: str, version: int) -> T:
        versions = self._data.get(rid)
        if not versions or version not in versions:
            raise RecordNotFoundError(
                f"{self._label} '{rid}' version {version} not found"
            )
        return versions[version]

    def exists(self, rid: str) -> bool:
        return rid in self._data

    def values_latest(self) -> tuple[T, ...]:
        return tuple(self.get(rid) for rid in self._data)


class InMemoryEvidenceRepository:
    def __init__(self) -> None:
        self._store: _VersionedStore[NormalizedEvidence] = _VersionedStore(
            lambda r: r.evidence_id, lambda r: r.version, "evidence"
        )

    def add(self, record: NormalizedEvidence) -> NormalizedEvidence:
        return self._store.add(record)

    def get(self, evidence_id: str) -> NormalizedEvidence:
        return self._store.get(evidence_id)

    def get_version(self, evidence_id: str, version: int) -> NormalizedEvidence:
        return self._store.get_version(evidence_id, version)

    def exists(self, evidence_id: str) -> bool:
        return self._store.exists(evidence_id)


class InMemoryEvaluationRepository:
    def __init__(self) -> None:
        self._store: _VersionedStore[CandidateEvaluation] = _VersionedStore(
            lambda r: r.evaluation_id, lambda r: r.version, "evaluation"
        )

    def add(self, record: CandidateEvaluation) -> CandidateEvaluation:
        return self._store.add(record)

    def get(self, evaluation_id: str) -> CandidateEvaluation:
        return self._store.get(evaluation_id)

    def get_version(self, evaluation_id: str, version: int) -> CandidateEvaluation:
        return self._store.get_version(evaluation_id, version)

    def exists(self, evaluation_id: str) -> bool:
        return self._store.exists(evaluation_id)


class InMemoryRecommendationRepository:
    def __init__(self) -> None:
        self._store: _VersionedStore[Recommendation] = _VersionedStore(
            lambda r: r.recommendation_id, lambda r: r.version, "recommendation"
        )

    def add(self, record: Recommendation) -> Recommendation:
        return self._store.add(record)

    def get(self, recommendation_id: str) -> Recommendation:
        return self._store.get(recommendation_id)

    def exists(self, recommendation_id: str) -> bool:
        return self._store.exists(recommendation_id)


class InMemoryDecisionRepository:
    """Decision store with a one-decision-per-evaluation-stage guard.

    A binding decision is unique per evaluation. Superseding a decision is an
    explicit later-phase workflow and is intentionally not permitted here.
    """

    def __init__(self) -> None:
        self._store: _VersionedStore[Decision] = _VersionedStore(
            lambda r: r.decision_id, lambda r: r.version, "decision"
        )
        self._by_evaluation: dict[str, str] = {}

    def add(self, record: Decision) -> Decision:
        existing = self._by_evaluation.get(record.evaluation_id)
        if existing is not None and existing != record.decision_id:
            raise DuplicateDecisionError(
                f"a binding decision ('{existing}') already exists for evaluation "
                f"'{record.evaluation_id}'"
            )
        stored = self._store.add(record)
        self._by_evaluation[record.evaluation_id] = record.decision_id
        return stored

    def get(self, decision_id: str) -> Decision:
        return self._store.get(decision_id)

    def exists(self, decision_id: str) -> bool:
        return self._store.exists(decision_id)

    def get_for_evaluation(self, evaluation_id: str) -> Decision | None:
        decision_id = self._by_evaluation.get(evaluation_id)
        return self._store.get(decision_id) if decision_id else None


class InMemoryWorkflowRepository:
    """Workflow store with optimistic-concurrency version checking."""

    def __init__(self) -> None:
        self._data: dict[str, CandidateWorkflow] = {}

    def save(self, record: CandidateWorkflow) -> CandidateWorkflow:
        current = self._data.get(record.candidate_id)
        if current is None:
            if record.version != 1:
                raise VersionConflictError(
                    f"initial workflow for '{record.candidate_id}' must be version 1"
                )
        else:
            if record.version != current.version + 1:
                raise VersionConflictError(
                    f"workflow '{record.candidate_id}' expected version "
                    f"{current.version + 1}, got {record.version}"
                )
        self._data[record.candidate_id] = record
        return record

    def get(self, candidate_id: str) -> CandidateWorkflow:
        record = self._data.get(candidate_id)
        if record is None:
            raise RecordNotFoundError(f"workflow '{candidate_id}' not found")
        return record

    def exists(self, candidate_id: str) -> bool:
        return candidate_id in self._data


class InMemoryAuditRepository:
    """Strictly append/read-only audit log.

    There is no update or delete operation by construction — the only mutation
    is :meth:`append`.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        return event

    def list_by_entity(self, entity_id: str) -> tuple[AuditEvent, ...]:
        return tuple(
            sorted(
                (e for e in self._events if e.entity_id == entity_id),
                key=lambda e: (e.timestamp, self._events.index(e)),
            )
        )

    def list_by_correlation(self, correlation_id: str) -> tuple[AuditEvent, ...]:
        return tuple(
            sorted(
                (e for e in self._events if e.correlation_id == correlation_id),
                key=lambda e: (e.timestamp, self._events.index(e)),
            )
        )

    def all(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)
