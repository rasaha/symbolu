"""DecisionCase repository (port + in-memory adapter).

The store is append-only and versioned. Case snapshots, recommendations,
decisions, overrides, and review tasks are never overwritten or deleted; every
material change appends a new record. History and supersession chains are fully
reconstructable. Repository access alone confers no authority — authorization is
enforced in the service layer.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..decisions.case import DecisionCase
from ..decisions.decision import DecisionRecord
from ..decisions.override import OverrideRecord
from ..decisions.recommendation import RecommendationRecord
from ..decisions.review import ReviewTask
from ..errors import (
    CaseVersionNotFoundError,
    DecisionCaseNotFoundError,
    RecommendationNotFoundError,
    ReviewTaskNotFoundError,
    VersionConflictError,
)


@runtime_checkable
class DecisionCaseRepository(Protocol):
    # cases (append-only version chain)
    def create_case(self, case: DecisionCase) -> DecisionCase: ...
    def save_case_version(self, case: DecisionCase) -> DecisionCase: ...
    def get_case(self, case_id: str) -> DecisionCase: ...
    def get_case_version(self, case_id: str, version: int) -> DecisionCase: ...
    def get_case_history(self, case_id: str) -> tuple[DecisionCase, ...]: ...
    def list_cases(self, tenant_id: str) -> tuple[DecisionCase, ...]: ...
    # recommendations (append-only, immutable)
    def add_recommendation(self, rec: RecommendationRecord) -> RecommendationRecord: ...
    def get_recommendation(self, recommendation_id: str) -> RecommendationRecord: ...
    def list_recommendations(self, case_id: str) -> tuple[RecommendationRecord, ...]: ...
    # decisions (append-only, immutable)
    def record_decision(self, dec: DecisionRecord) -> DecisionRecord: ...
    def get_decision(self, decision_id: str) -> DecisionRecord: ...
    def list_decisions(self, case_id: str) -> tuple[DecisionRecord, ...]: ...
    # overrides (append-only, immutable)
    def record_override(self, ovr: OverrideRecord) -> OverrideRecord: ...
    def list_overrides(self, case_id: str) -> tuple[OverrideRecord, ...]: ...
    # review tasks (append-only revisions; latest wins)
    def add_review_task(self, task: ReviewTask) -> ReviewTask: ...
    def save_review_task(self, task: ReviewTask) -> ReviewTask: ...
    def get_review_task(self, task_id: str) -> ReviewTask: ...
    def list_review_tasks(self, case_id: str) -> tuple[ReviewTask, ...]: ...


class InMemoryDecisionCaseRepository:
    def __init__(self) -> None:
        self._cases: dict[str, list[DecisionCase]] = {}
        self._recs: dict[str, RecommendationRecord] = {}
        self._recs_by_case: dict[str, list[RecommendationRecord]] = {}
        self._decisions: dict[str, DecisionRecord] = {}
        self._decisions_by_case: dict[str, list[DecisionRecord]] = {}
        self._overrides_by_case: dict[str, list[OverrideRecord]] = {}
        self._reviews: dict[str, list[ReviewTask]] = {}  # task_id -> revisions
        self._reviews_by_case: dict[str, set[str]] = {}

    # --- cases ------------------------------------------------------------
    def create_case(self, case: DecisionCase) -> DecisionCase:
        if case.decision_case_id in self._cases:
            raise VersionConflictError(
                f"case '{case.decision_case_id}' already exists")
        self._cases[case.decision_case_id] = [case]
        return case

    def save_case_version(self, case: DecisionCase) -> DecisionCase:
        chain = self._cases.get(case.decision_case_id)
        if chain is None:
            raise DecisionCaseNotFoundError(
                f"case '{case.decision_case_id}' not found")
        chain.append(case)
        return case

    def get_case(self, case_id: str) -> DecisionCase:
        chain = self._cases.get(case_id)
        if not chain:
            raise DecisionCaseNotFoundError(f"case '{case_id}' not found")
        return max(chain, key=lambda c: c.version)

    def get_case_version(self, case_id: str, version: int) -> DecisionCase:
        for c in self._cases.get(case_id, ()):
            if c.version == version:
                return c
        raise CaseVersionNotFoundError(
            f"case '{case_id}' has no version {version}")

    def get_case_history(self, case_id: str) -> tuple[DecisionCase, ...]:
        chain = self._cases.get(case_id)
        if not chain:
            raise DecisionCaseNotFoundError(f"case '{case_id}' not found")
        return tuple(sorted(chain, key=lambda c: c.version))

    def list_cases(self, tenant_id: str) -> tuple[DecisionCase, ...]:
        latest = [self.get_case(cid) for cid in self._cases]
        return tuple(sorted(
            (c for c in latest if c.tenant_id == tenant_id),
            key=lambda c: c.decision_case_id))

    # --- recommendations --------------------------------------------------
    def add_recommendation(self, rec: RecommendationRecord) -> RecommendationRecord:
        if rec.recommendation_id in self._recs:
            raise VersionConflictError(
                f"recommendation '{rec.recommendation_id}' already exists; "
                "recommendations are immutable")
        self._recs[rec.recommendation_id] = rec
        self._recs_by_case.setdefault(rec.decision_case_id, []).append(rec)
        return rec

    def get_recommendation(self, recommendation_id: str) -> RecommendationRecord:
        rec = self._recs.get(recommendation_id)
        if rec is None:
            raise RecommendationNotFoundError(
                f"recommendation '{recommendation_id}' not found")
        return rec

    def list_recommendations(self, case_id: str) -> tuple[RecommendationRecord, ...]:
        return tuple(self._recs_by_case.get(case_id, ()))

    # --- decisions --------------------------------------------------------
    def record_decision(self, dec: DecisionRecord) -> DecisionRecord:
        if dec.decision_id in self._decisions:
            raise VersionConflictError(
                f"decision '{dec.decision_id}' already exists; decisions are immutable")
        self._decisions[dec.decision_id] = dec
        self._decisions_by_case.setdefault(dec.decision_case_id, []).append(dec)
        return dec

    def get_decision(self, decision_id: str) -> DecisionRecord:
        dec = self._decisions.get(decision_id)
        if dec is None:
            raise DecisionCaseNotFoundError(f"decision '{decision_id}' not found")
        return dec

    def list_decisions(self, case_id: str) -> tuple[DecisionRecord, ...]:
        return tuple(self._decisions_by_case.get(case_id, ()))

    # --- overrides --------------------------------------------------------
    def record_override(self, ovr: OverrideRecord) -> OverrideRecord:
        self._overrides_by_case.setdefault(ovr.decision_case_id, []).append(ovr)
        return ovr

    def list_overrides(self, case_id: str) -> tuple[OverrideRecord, ...]:
        return tuple(self._overrides_by_case.get(case_id, ()))

    # --- review tasks -----------------------------------------------------
    def add_review_task(self, task: ReviewTask) -> ReviewTask:
        if task.task_id in self._reviews:
            raise VersionConflictError(
                f"review task '{task.task_id}' already exists")
        self._reviews[task.task_id] = [task]
        self._reviews_by_case.setdefault(task.decision_case_id, set()).add(task.task_id)
        return task

    def save_review_task(self, task: ReviewTask) -> ReviewTask:
        revisions = self._reviews.get(task.task_id)
        if revisions is None:
            raise ReviewTaskNotFoundError(f"review task '{task.task_id}' not found")
        revisions.append(task)
        return task

    def get_review_task(self, task_id: str) -> ReviewTask:
        revisions = self._reviews.get(task_id)
        if not revisions:
            raise ReviewTaskNotFoundError(f"review task '{task_id}' not found")
        return max(revisions, key=lambda t: t.revision)

    def list_review_tasks(self, case_id: str) -> tuple[ReviewTask, ...]:
        task_ids = self._reviews_by_case.get(case_id, set())
        return tuple(sorted(
            (self.get_review_task(tid) for tid in task_ids),
            key=lambda t: t.created_at))
