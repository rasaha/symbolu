"""H22-D — logical resource claims, the conflict matrix, and the reservation coordinator.

A **resource claim** is how a workflow declares, *before* its H22-A quantum runs, the logical
resources that quantum will touch and how. It is a portfolio-coordination requirement, **not**
application authority:

    a WRITE claim on ``crm/customer/123`` means "do not run another *conflicting* workflow
    quantum concurrently with mine" — it does NOT mean "I am authorized to update customer 123".

Authorization for the actual action still crosses the unchanged governance → exact-action →
provider boundary *below* H22, inside ``advance_workflow``. H22-D never turns a resource
reservation into permission.

## Scope / non-claims

Resource coordination here is **portfolio-local**: it prevents two workflows *in this one
in-process coordinator* from running conflicting quanta at the same time. It is NOT a
distributed lock and does not protect an external resource from an independent process outside
this coordinator. A deployment that needs cross-process resource exclusion must supply that
separately; this module never implies it (see ``docs/AGENT_RUNTIME_H22D_CONCURRENCY.md``).

## Conflict matrix (fixed, documented, exhaustively tested)

The *only* compatible pair is ``READ + READ``. Everything else conflicts:

    READ  + READ       compatible
    READ  + WRITE      conflict
    WRITE + WRITE      conflict
    EXCLUSIVE + any    conflict   (including EXCLUSIVE + EXCLUSIVE and EXCLUSIVE + READ)
    UNKNOWN + any      conflict   (fail-closed: an undeclared/unknown resource is never
                                   assumed compatible with anything, including another UNKNOWN)

Compatibility is never inferred dynamically from payloads; it is exactly this matrix.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Optional, Tuple


class ResourceMode(str, Enum):
    """How a workflow quantum intends to touch a logical resource.

    Kept deliberately small. ``UNKNOWN`` exists only so an undeclared/unresolvable resource can
    be represented and handled **fail-closed** (it conflicts with everything) rather than being
    silently assumed compatible."""

    READ = "READ"
    WRITE = "WRITE"
    EXCLUSIVE = "EXCLUSIVE"
    UNKNOWN = "UNKNOWN"


# Conservative escalation strength for normalizing several modes on the SAME resource key within
# ONE workflow (higher wins). UNKNOWN is strongest so a single undeclared claim keeps the whole
# key fail-closed; EXCLUSIVE beats WRITE beats READ.
_MODE_STRENGTH: Dict[ResourceMode, int] = {
    ResourceMode.READ: 1,
    ResourceMode.WRITE: 2,
    ResourceMode.EXCLUSIVE: 3,
    ResourceMode.UNKNOWN: 4,
}


def modes_conflict(a: ResourceMode, b: ResourceMode) -> bool:
    """Return ``True`` iff two modes on the *same* resource key cannot run concurrently.

    The exhaustive matrix collapses to one rule: only ``READ + READ`` is compatible. Any WRITE,
    EXCLUSIVE, or UNKNOWN on either side conflicts (UNKNOWN is fail-closed)."""
    return not (a is ResourceMode.READ and b is ResourceMode.READ)


@dataclass(frozen=True)
class ResourceClaim:
    """One workflow's logical claim on one resource: a ``resource_key`` and a ``mode``.

    ``resource_key`` is an opaque, application-supplied logical identifier (e.g.
    ``"crm/customer/123"``). H22-D never parses it, never discovers rows, and never assigns
    meaning to its structure — it only compares keys for equality and modes via the matrix."""

    resource_key: str
    mode: ResourceMode = ResourceMode.WRITE

    def __post_init__(self) -> None:
        if not self.resource_key or not isinstance(self.resource_key, str):
            raise ValueError("ResourceClaim.resource_key must be a non-empty string")
        if not isinstance(self.mode, ResourceMode):
            raise ValueError("ResourceClaim.mode must be a ResourceMode")

    def to_dict(self) -> Dict[str, str]:
        return {"resource_key": self.resource_key, "mode": self.mode.value}


def normalize_claims(claims: Iterable[ResourceClaim]) -> Tuple[ResourceClaim, ...]:
    """Deduplicate a workflow's own claims by resource key, escalating conservatively.

    Two claims on the same ``resource_key`` are never treated as independent resources: they
    collapse to a single claim carrying the **strongest** mode (``UNKNOWN`` > ``EXCLUSIVE`` >
    ``WRITE`` > ``READ``) — so ``R READ`` + ``R WRITE`` resolves to ``R WRITE`` and any
    ``R UNKNOWN`` keeps ``R`` fail-closed. The result is ordered by ``resource_key`` so a claim
    set has a single deterministic canonical form."""
    strongest: Dict[str, ResourceMode] = {}
    for c in claims:
        if not isinstance(c, ResourceClaim):
            raise ValueError("claims must be ResourceClaim instances")
        cur = strongest.get(c.resource_key)
        if cur is None or _MODE_STRENGTH[c.mode] > _MODE_STRENGTH[cur]:
            strongest[c.resource_key] = c.mode
    return tuple(
        ResourceClaim(resource_key=k, mode=strongest[k]) for k in sorted(strongest)
    )


@dataclass(frozen=True)
class ResourceConflict:
    """A structured, audit-friendly explanation of why one claim could not be reserved.

    Answers "why was B deferred?" precisely: the ``resource_key`` contended, the mode B
    requested, the mode already held, and the ``holder`` workflow whose live reservation
    conflicts."""

    instance_id: str
    resource_key: str
    requested_mode: str
    existing_mode: str
    holder: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "reason": "RESOURCE_CONFLICT",
            "instance_id": self.instance_id,
            "resource_key": self.resource_key,
            "requested_mode": self.requested_mode,
            "existing_mode": self.existing_mode,
            "conflicts_with": self.holder,
        }


class ResourceCoordinator:
    """Tracks the resource reservations of the workflows whose quanta are currently in flight.

    Reservations are **transient**: they exist only for the duration of a batch of concurrent
    quanta and are released the moment each quantum reaches a stable boundary. The coordinator is
    driven exclusively from the single admission/reconciliation thread; a lock still guards every
    mutation so a defensive release from a reconciliation path is always safe. It holds no
    persistent ownership of a resource across workflow lifetimes — at a stable portfolio
    checkpoint boundary the coordinator is expected to be empty (an H22-D validation invariant).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # instance_id -> its normalized, currently-reserved claims, in insertion order.
        self._held: Dict[str, Tuple[ResourceClaim, ...]] = {}

    def check(
        self, instance_id: str, claims: Iterable[ResourceClaim]
    ) -> Optional[ResourceConflict]:
        """Return the first :class:`ResourceConflict` a claim set would hit against currently-held
        reservations (excluding ``instance_id``'s own), or ``None`` if fully compatible.

        Deterministic: normalized claims are scanned in ``resource_key`` order against holders in
        reservation (insertion) order, so the same state always yields the same first conflict."""
        normalized = normalize_claims(claims)
        with self._lock:
            return self._first_conflict_locked(instance_id, normalized)

    def _first_conflict_locked(
        self, instance_id: str, normalized: Tuple[ResourceClaim, ...]
    ) -> Optional[ResourceConflict]:
        for claim in normalized:
            for holder, held in self._held.items():
                if holder == instance_id:
                    continue
                for hc in held:
                    if hc.resource_key == claim.resource_key and modes_conflict(claim.mode, hc.mode):
                        return ResourceConflict(
                            instance_id=instance_id,
                            resource_key=claim.resource_key,
                            requested_mode=claim.mode.value,
                            existing_mode=hc.mode.value,
                            holder=holder,
                        )
        return None

    def reserve(
        self, instance_id: str, claims: Iterable[ResourceClaim]
    ) -> Tuple[bool, Optional[ResourceConflict]]:
        """Atomically reserve a workflow's entire claim set, or reserve nothing.

        All-or-none: the full normalized claim set is validated against current reservations
        first; if *any* claim conflicts, **nothing** is reserved and ``(False, conflict)`` is
        returned. Otherwise every normalized claim is recorded together and ``(True, None)`` is
        returned. Reserving for an ``instance_id`` that already holds a reservation is a
        programming error (H22-D enforces per-workflow exclusivity upstream) and raises."""
        normalized = normalize_claims(claims)
        with self._lock:
            if instance_id in self._held:
                raise ValueError(
                    f"resource reservation for {instance_id!r} already active (a workflow may "
                    "not hold two concurrent reservations)"
                )
            conflict = self._first_conflict_locked(instance_id, normalized)
            if conflict is not None:
                return False, conflict
            self._held[instance_id] = normalized  # atomic: all claims recorded together
            return True, None

    def release(self, instance_id: str) -> bool:
        """Release a workflow's reservation. Idempotent and fail-safe: releasing a workflow that
        holds nothing is a no-op returning ``False`` (never raises), so a leaked reservation can
        always be reclaimed and no cleanup path can wedge the portfolio."""
        with self._lock:
            return self._held.pop(instance_id, None) is not None

    # -- read-only inspection ----------------------------------------------
    def active_instance_ids(self) -> Tuple[str, ...]:
        with self._lock:
            return tuple(self._held.keys())

    def active_claims(self, instance_id: str) -> Tuple[ResourceClaim, ...]:
        with self._lock:
            return self._held.get(instance_id, ())

    @property
    def is_empty(self) -> bool:
        """True when no reservation is held — the expected state at a stable checkpoint boundary."""
        with self._lock:
            return not self._held
