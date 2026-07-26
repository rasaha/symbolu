"""In-memory repositories for H1 hiring product entities.

Reference adapters for requisitions, job definitions, candidates, applications,
and evidence intake. They enforce the same contract as the existing versioned
stores — unique (logical id, version), immutability (no overwrite → version
conflict), latest-version reads — and add:

* ``history(id)`` for full, ordered version reconstruction;
* duplicate-application detection scoped by (tenant, candidate, requisition);
* collected-evidence-type coverage per application for readiness checks.

Protocols are defined so services depend on ports, not concrete adapters. No
production database is included in this phase.
"""

from __future__ import annotations

from typing import Callable, Generic, Optional, Protocol, TypeVar, runtime_checkable

from ..candidates.candidate import Candidate
from ..errors import (
    ApplicationNotFoundError,
    CandidateNotFoundError,
    EvidenceIntakeNotFoundError,
    JobDefinitionNotFoundError,
    RequisitionNotFoundError,
    VersionConflictError,
)
from ..hiring_applications.application import Application
from ..hiring_applications.status import APPLICATION_ACTIVE_STATUSES
from ..intake.intake import EvidenceIntakeItem
from ..requisitions.job_definition import JobDefinition
from ..requisitions.requisition import JobRequisition

T = TypeVar("T")


class _VersionedStore(Generic[T]):
    """(logical id -> {version -> record}) with immutability + history."""

    def __init__(
        self,
        *,
        id_of: Callable[[T], str],
        version_of: Callable[[T], int],
        not_found: Callable[[str], Exception],
        label: str,
    ) -> None:
        self._id_of = id_of
        self._version_of = version_of
        self._not_found = not_found
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
            raise self._not_found(rid)
        return versions[max(versions)]

    def get_version(self, rid: str, version: int) -> T:
        versions = self._data.get(rid) or {}
        if version not in versions:
            raise self._not_found(f"{rid}@v{version}")
        return versions[version]

    def exists(self, rid: str) -> bool:
        return rid in self._data

    def history(self, rid: str) -> tuple[T, ...]:
        versions = self._data.get(rid)
        if not versions:
            raise self._not_found(rid)
        return tuple(versions[v] for v in sorted(versions))

    def latest_records(self) -> tuple[T, ...]:
        return tuple(vs[max(vs)] for vs in self._data.values() if vs)


# --- Protocols --------------------------------------------------------------
@runtime_checkable
class RequisitionRepository(Protocol):
    def add(self, record: JobRequisition) -> JobRequisition: ...
    def get(self, requisition_id: str) -> JobRequisition: ...
    def get_version(self, requisition_id: str, version: int) -> JobRequisition: ...
    def exists(self, requisition_id: str) -> bool: ...
    def history(self, requisition_id: str) -> tuple[JobRequisition, ...]: ...


@runtime_checkable
class JobDefinitionRepository(Protocol):
    def add(self, record: JobDefinition) -> JobDefinition: ...
    def get(self, job_definition_id: str) -> JobDefinition: ...
    def exists(self, job_definition_id: str) -> bool: ...
    def history(self, job_definition_id: str) -> tuple[JobDefinition, ...]: ...


@runtime_checkable
class CandidateRepository(Protocol):
    def add(self, record: Candidate) -> Candidate: ...
    def get(self, candidate_id: str) -> Candidate: ...
    def exists(self, candidate_id: str) -> bool: ...
    def history(self, candidate_id: str) -> tuple[Candidate, ...]: ...


@runtime_checkable
class ApplicationRepository(Protocol):
    def add(self, record: Application) -> Application: ...
    def get(self, application_id: str) -> Application: ...
    def exists(self, application_id: str) -> bool: ...
    def history(self, application_id: str) -> tuple[Application, ...]: ...
    def active_exists(self, tenant_id: str, candidate_id: str, requisition_id: str) -> bool: ...


@runtime_checkable
class EvidenceIntakeRepository(Protocol):
    def add(self, record: EvidenceIntakeItem) -> EvidenceIntakeItem: ...
    def get(self, intake_id: str) -> EvidenceIntakeItem: ...
    def exists(self, intake_id: str) -> bool: ...
    def history(self, intake_id: str) -> tuple[EvidenceIntakeItem, ...]: ...
    def items_for_application(self, application_id: str) -> tuple[EvidenceIntakeItem, ...]: ...
    def evidence_types_for_application(self, application_id: str) -> frozenset[str]: ...


# --- In-memory adapters -----------------------------------------------------
class InMemoryRequisitionRepository:
    def __init__(self) -> None:
        self._s: _VersionedStore[JobRequisition] = _VersionedStore(
            id_of=lambda r: r.requisition_id, version_of=lambda r: r.version,
            not_found=lambda k: RequisitionNotFoundError(f"requisition '{k}' not found"),
            label="requisition")

    def add(self, record): return self._s.add(record)
    def get(self, requisition_id): return self._s.get(requisition_id)
    def get_version(self, requisition_id, version): return self._s.get_version(requisition_id, version)
    def exists(self, requisition_id): return self._s.exists(requisition_id)
    def history(self, requisition_id): return self._s.history(requisition_id)


class InMemoryJobDefinitionRepository:
    def __init__(self) -> None:
        self._s: _VersionedStore[JobDefinition] = _VersionedStore(
            id_of=lambda r: r.job_definition_id, version_of=lambda r: r.version,
            not_found=lambda k: JobDefinitionNotFoundError(f"job definition '{k}' not found"),
            label="job_definition")

    def add(self, record): return self._s.add(record)
    def get(self, job_definition_id): return self._s.get(job_definition_id)
    def get_version(self, job_definition_id, version): return self._s.get_version(job_definition_id, version)
    def exists(self, job_definition_id): return self._s.exists(job_definition_id)
    def history(self, job_definition_id): return self._s.history(job_definition_id)


class InMemoryCandidateRepository:
    def __init__(self) -> None:
        self._s: _VersionedStore[Candidate] = _VersionedStore(
            id_of=lambda r: r.candidate_id, version_of=lambda r: r.version,
            not_found=lambda k: CandidateNotFoundError(f"candidate '{k}' not found"),
            label="candidate")

    def add(self, record): return self._s.add(record)
    def get(self, candidate_id): return self._s.get(candidate_id)
    def get_version(self, candidate_id, version): return self._s.get_version(candidate_id, version)
    def exists(self, candidate_id): return self._s.exists(candidate_id)
    def history(self, candidate_id): return self._s.history(candidate_id)


class InMemoryApplicationRepository:
    def __init__(self) -> None:
        self._s: _VersionedStore[Application] = _VersionedStore(
            id_of=lambda r: r.application_id, version_of=lambda r: r.version,
            not_found=lambda k: ApplicationNotFoundError(f"application '{k}' not found"),
            label="application")

    def add(self, record): return self._s.add(record)
    def get(self, application_id): return self._s.get(application_id)
    def get_version(self, application_id, version): return self._s.get_version(application_id, version)
    def exists(self, application_id): return self._s.exists(application_id)
    def history(self, application_id): return self._s.history(application_id)

    def active_exists(self, tenant_id: str, candidate_id: str, requisition_id: str) -> bool:
        for app in self._s.latest_records():
            if (app.tenant_id == tenant_id
                    and app.candidate_id == candidate_id
                    and app.requisition_id == requisition_id
                    and app.status in APPLICATION_ACTIVE_STATUSES):
                return True
        return False


class InMemoryEvidenceIntakeRepository:
    def __init__(self) -> None:
        self._s: _VersionedStore[EvidenceIntakeItem] = _VersionedStore(
            id_of=lambda r: r.intake_id, version_of=lambda r: r.version,
            not_found=lambda k: EvidenceIntakeNotFoundError(f"evidence intake '{k}' not found"),
            label="evidence_intake")

    def add(self, record): return self._s.add(record)
    def get(self, intake_id): return self._s.get(intake_id)
    def get_version(self, intake_id, version): return self._s.get_version(intake_id, version)
    def exists(self, intake_id): return self._s.exists(intake_id)
    def history(self, intake_id): return self._s.history(intake_id)

    def items_for_application(self, application_id: str) -> tuple[EvidenceIntakeItem, ...]:
        return tuple(i for i in self._s.latest_records() if i.application_id == application_id)

    def evidence_types_for_application(self, application_id: str) -> frozenset[str]:
        return frozenset(i.evidence_type for i in self.items_for_application(application_id))
