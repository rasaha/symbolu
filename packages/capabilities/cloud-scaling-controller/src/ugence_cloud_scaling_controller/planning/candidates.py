"""Candidate capacity-action plans and BOUNDED candidate generation.

A candidate is a *proposed* capacity action — one or more coordinated resource changes.
Candidate generation is deliberately bounded: Phase 3 enumerates a small, explicit set of
plans (NO_CHANGE plus a few step-aligned scale targets, optionally paired with one
coordinated dependency change) rather than searching an unbounded combinatorial space.
NO_CHANGE is always present as the mandatory safe baseline.

A ``CandidateActionPlan`` records only WHAT would change (target subject, current and
proposed capacity, timing) and the coarse ``action_kind``. Derived, comparison-relevant
quantities — estimated cost delta, forecast coverage, dependency impact, and the policy
score — are computed during evaluation (see :mod:`.scoring`) and recorded on an
``EvaluatedCandidate``, never baked into the candidate itself (so a candidate cannot carry a
forged, self-serving cost or score).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ..canonical.identity import CapacitySubject
from ..canonical.serialization import content_digest

CANDIDATE_PLAN_SCHEMA_VERSION = "capacity-candidate-plan-1"

MAX_CANDIDATES = 32  # hard bound on generated candidates (no unbounded optimizer)


class CandidateError(ValueError):
    """Raised when a candidate plan is internally inconsistent (fail closed)."""


class ActionKind(str, Enum):
    """The coarse shape of a candidate capacity action."""

    NO_CHANGE = "no_change"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    COORDINATED = "coordinated"


@dataclass(frozen=True)
class ResourceChange:
    """A proposed change to one resource/subject's capacity (integer capacity units)."""

    subject: CapacitySubject
    current_capacity: int
    proposed_capacity: int
    role: str = "primary"

    def __post_init__(self) -> None:
        if not isinstance(self.subject, CapacitySubject):
            raise CandidateError("resource change subject must be a CapacitySubject")
        for name in ("current_capacity", "proposed_capacity"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise CandidateError(f"{name} must be an int >= 0")
        if self.role not in ("primary", "dependency"):
            raise CandidateError("role must be 'primary' or 'dependency'")

    @property
    def delta(self) -> int:
        return self.proposed_capacity - self.current_capacity

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject.to_canonical_dict(),
            "current_capacity": self.current_capacity,
            "proposed_capacity": self.proposed_capacity,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ResourceChange":
        if not isinstance(data, Mapping):
            raise CandidateError("resource change must be a mapping")
        known = {"subject", "current_capacity", "proposed_capacity", "role"}
        unknown = set(data) - known
        if unknown:
            raise CandidateError(f"unknown resource change field(s): {sorted(unknown)}")
        for req in ("subject", "current_capacity", "proposed_capacity"):
            if req not in data:
                raise CandidateError(f"resource change requires '{req}'")
        return cls(
            subject=CapacitySubject.from_dict(data["subject"]),
            current_capacity=data["current_capacity"],
            proposed_capacity=data["proposed_capacity"],
            role=data.get("role", "primary"),
        )


@dataclass(frozen=True)
class CandidateActionPlan:
    """A bounded, immutable candidate action: one or more coordinated resource changes."""

    plan_id: str
    action_kind: ActionKind
    changes: Tuple[ResourceChange, ...]
    timing_seconds: float = 0.0
    label: str = ""
    schema_version: str = CANDIDATE_PLAN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.plan_id, str) or self.plan_id == "":
            raise CandidateError("plan_id must be a non-empty string")
        if not isinstance(self.action_kind, ActionKind):
            raise CandidateError("action_kind must be an ActionKind")
        if not isinstance(self.changes, tuple):
            object.__setattr__(self, "changes", tuple(self.changes))
        if not self.changes:
            raise CandidateError("a candidate plan requires at least one resource change")
        roles = [c.role for c in self.changes]
        if roles.count("primary") != 1:
            raise CandidateError("a candidate plan requires exactly one 'primary' change")
        # No duplicate subjects in a single plan.
        seen = set()
        for c in self.changes:
            if not isinstance(c, ResourceChange):
                raise CandidateError("every change must be a ResourceChange")
            key = tuple(sorted(c.subject.to_canonical_dict().items()))
            if key in seen:
                raise CandidateError("duplicate subject within a candidate plan")
            seen.add(key)
        if isinstance(self.timing_seconds, bool) or not isinstance(self.timing_seconds, (int, float)):
            raise CandidateError("timing_seconds must be a real number")
        if self.timing_seconds < 0:
            raise CandidateError("timing_seconds must be >= 0")

        primary = self.primary_change
        nonzero = [c for c in self.changes if c.delta != 0]
        if self.action_kind is ActionKind.NO_CHANGE:
            if nonzero:
                raise CandidateError("NO_CHANGE must have zero net change on every resource")
        elif self.action_kind is ActionKind.SCALE_UP:
            if primary.delta <= 0:
                raise CandidateError("SCALE_UP requires primary proposed > current")
            if len(nonzero) != 1:
                raise CandidateError("SCALE_UP changes exactly the primary resource")
        elif self.action_kind is ActionKind.SCALE_DOWN:
            if primary.delta >= 0:
                raise CandidateError("SCALE_DOWN requires primary proposed < current")
            if len(nonzero) != 1:
                raise CandidateError("SCALE_DOWN changes exactly the primary resource")
        else:  # COORDINATED
            if primary.delta == 0:
                raise CandidateError("COORDINATED requires a non-zero primary change")
            if len(nonzero) < 2:
                raise CandidateError("COORDINATED requires >= 2 changed resources")

    @property
    def primary_change(self) -> ResourceChange:
        for c in self.changes:
            if c.role == "primary":
                return c
        raise CandidateError("no primary change")  # unreachable after validation

    @property
    def dependency_changes(self) -> Tuple[ResourceChange, ...]:
        return tuple(c for c in self.changes if c.role == "dependency")

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "action_kind": self.action_kind.value,
            "changes": [c.to_canonical_dict() for c in self.changes],
            "timing_seconds": self.timing_seconds,
            "label": self.label,
        }

    def digest(self) -> str:
        return content_digest("capacity_candidate_plan", self.schema_version, self.to_canonical_dict())

    @classmethod
    def from_dict(cls, data: Any) -> "CandidateActionPlan":
        if not isinstance(data, Mapping):
            raise CandidateError("candidate plan must be a mapping")
        known = {"schema_version", "plan_id", "action_kind", "changes", "timing_seconds", "label"}
        unknown = set(data) - known
        if unknown:
            raise CandidateError(f"unknown candidate plan field(s): {sorted(unknown)}")
        for req in ("plan_id", "action_kind", "changes"):
            if req not in data:
                raise CandidateError(f"candidate plan requires '{req}'")
        try:
            action_kind = ActionKind(data["action_kind"])
        except ValueError as exc:
            raise CandidateError(f"unsupported action_kind: {data['action_kind']!r}") from exc
        changes_raw = data["changes"]
        if not isinstance(changes_raw, (list, tuple)):
            raise CandidateError("changes must be a list")
        return cls(
            plan_id=data["plan_id"],
            action_kind=action_kind,
            changes=tuple(ResourceChange.from_dict(c) for c in changes_raw),
            timing_seconds=data.get("timing_seconds", 0.0),
            label=data.get("label", ""),
            schema_version=data.get("schema_version", CANDIDATE_PLAN_SCHEMA_VERSION),
        )


def _no_change_plan(subject: CapacitySubject, current: int) -> CandidateActionPlan:
    return CandidateActionPlan(
        plan_id="no_change",
        action_kind=ActionKind.NO_CHANGE,
        changes=(ResourceChange(subject, current, current, role="primary"),),
        label="hold at current capacity",
    )


def generate_candidates(
    subject: CapacitySubject,
    current_capacity: int,
    required_capacity: int,
    *,
    allowed_step: int,
    min_capacity: int,
    max_capacity: int,
    dependency: Optional[CapacitySubject] = None,
    dependency_current: Optional[int] = None,
    dependency_required: Optional[int] = None,
) -> Tuple[CandidateActionPlan, ...]:
    """Enumerate a small, explicit, step-aligned candidate set (always incl. NO_CHANGE).

    The set contains: NO_CHANGE; a step-down toward ``required_capacity`` when the forecast
    permits a reduction; step-up targets between current and the required capacity (clamped
    to ``[min_capacity, max_capacity]`` and rounded UP to the nearest ``allowed_step``); and,
    when a coordinated dependency change is supplied, a COORDINATED plan pairing the primary
    scale-up target with the dependency's required capacity. The number of candidates is
    bounded by :data:`MAX_CANDIDATES`."""
    if isinstance(current_capacity, bool) or not isinstance(current_capacity, int) or current_capacity < 0:
        raise CandidateError("current_capacity must be an int >= 0")
    if isinstance(required_capacity, bool) or not isinstance(required_capacity, int) or required_capacity < 0:
        raise CandidateError("required_capacity must be an int >= 0")
    if allowed_step < 1:
        raise CandidateError("allowed_step must be >= 1")

    plans: List[CandidateActionPlan] = [_no_change_plan(subject, current_capacity)]

    def _aligned_targets() -> List[int]:
        targets = set()
        lo = max(min_capacity, 0)
        hi = max_capacity
        # Step-aligned targets from current toward the required capacity, inclusive of a
        # target that first meets/exceeds required_capacity.
        if required_capacity > current_capacity:
            n = current_capacity
            while n < hi and n < required_capacity + allowed_step:
                n += allowed_step
                if lo <= n <= hi:
                    targets.add(n)
                if len(targets) >= MAX_CANDIDATES:
                    break
        elif required_capacity < current_capacity:
            n = current_capacity
            while n > lo and n > required_capacity - allowed_step:
                n -= allowed_step
                if lo <= n <= hi:
                    targets.add(n)
                if len(targets) >= MAX_CANDIDATES:
                    break
        # Also always offer the clamped required capacity itself if in-range and aligned.
        if lo <= required_capacity <= hi:
            targets.add(required_capacity)
        targets.discard(current_capacity)
        return sorted(targets)

    for target in _aligned_targets():
        if len(plans) >= MAX_CANDIDATES:
            break
        kind = ActionKind.SCALE_UP if target > current_capacity else ActionKind.SCALE_DOWN
        primary = ResourceChange(subject, current_capacity, target, role="primary")
        plans.append(CandidateActionPlan(
            plan_id=f"{kind.value}_to_{target}",
            action_kind=kind,
            changes=(primary,),
            label=f"{kind.value} primary to {target}",
        ))

        # Coordinated variant: pair a primary scale-up with the dependency's required change.
        if (kind is ActionKind.SCALE_UP and dependency is not None
                and dependency_current is not None and dependency_required is not None
                and dependency_required != dependency_current
                and len(plans) < MAX_CANDIDATES):
            dep_change = ResourceChange(dependency, dependency_current, dependency_required,
                                        role="dependency")
            plans.append(CandidateActionPlan(
                plan_id=f"coordinated_{target}_dep_{dependency_required}",
                action_kind=ActionKind.COORDINATED,
                changes=(primary, dep_change),
                label=f"scale primary to {target} and dependency to {dependency_required}",
            ))

    return tuple(plans[:MAX_CANDIDATES])


__all__ = [
    "CANDIDATE_PLAN_SCHEMA_VERSION",
    "MAX_CANDIDATES",
    "CandidateError",
    "ActionKind",
    "ResourceChange",
    "CandidateActionPlan",
    "generate_candidates",
]
