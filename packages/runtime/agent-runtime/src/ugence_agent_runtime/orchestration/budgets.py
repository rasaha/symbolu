"""H22-D — the shared portfolio budget coordinator (reserve-before-execute).

This is *orchestration* budget, not billing infrastructure: a small, generic, typed ledger over
named numeric dimensions (e.g. ``token_units``, ``model_cost``, ``external_api_calls``,
``compute_units`` — the names are the caller's, not hardcoded cloud-provider assumptions) that
lets several concurrent workflow quanta share one budget **without oversubscribing it**.

The key invariant (Section 17): a concurrent quantum must not begin merely because *current
consumed* is below the limit — two quanta each individually affordable can together exceed the
remaining budget. So H22-D **reserves** a quantum's declared maximum requirement *before* it is
admitted, and a later quantum sees that reservation as unavailable. Accounting keeps four
quantities per dimension, with ``available = limit - consumed - reserved``:

    limit     configured ceiling (unconfigured dimension ⇒ unconstrained)
    consumed  settled, irreversible usage of completed quanta
    reserved  held for in-flight quanta (released or settled at their stable boundary)
    available what a new reservation may draw on

H22-D never invents an estimate: a workflow declares a :class:`BudgetRequirement` (or an injected
estimator supplies one). It also never fabricates provider usage — with no runtime usage
telemetry in this release, settlement uses the documented **conservative rule**: charge the full
reservation as consumed (never under-charge), and mark the actual as unavailable. All values are
finite and non-negative; a NaN/±Inf/negative fails **closed**.
"""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Tuple


def _validate_amounts(amounts: Mapping[str, float], *, what: str) -> Dict[str, float]:
    """Return a validated copy: keys non-empty strings, values finite and >= 0. Fail closed."""
    out: Dict[str, float] = {}
    for dim, val in amounts.items():
        if not dim or not isinstance(dim, str):
            raise ValueError(f"{what}: dimension name must be a non-empty string")
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"{what}: {dim!r} amount must be numeric")
        if not math.isfinite(val) or val < 0:
            raise ValueError(f"{what}: {dim!r} amount must be finite and non-negative (got {val!r})")
        out[dim] = float(val)
    return out


@dataclass(frozen=True)
class PortfolioBudget:
    """A configured ceiling per named budget dimension (generic; no billing semantics).

    A dimension absent from ``limits`` is **unconstrained** — the coordinator only gates what
    you configure. Limits are finite and non-negative (a zero limit means "no headroom", not
    "unlimited")."""

    limits: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "limits", _validate_amounts(self.limits, what="PortfolioBudget.limits"))

    def to_dict(self) -> Dict[str, float]:
        return dict(sorted(self.limits.items()))


@dataclass(frozen=True)
class BudgetRequirement:
    """A workflow's declared maximum budget requirement for one quantum, per dimension.

    Supplied by the workflow/application (or an injected estimator) — H22-D consumes it and never
    computes its own estimate. Amounts are finite and non-negative."""

    amounts: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "amounts", _validate_amounts(self.amounts, what="BudgetRequirement"))

    @property
    def is_empty(self) -> bool:
        return not any(v > 0 for v in self.amounts.values())

    def to_dict(self) -> Dict[str, float]:
        return dict(sorted(self.amounts.items()))


class BudgetEstimateExceeded(Exception):
    """Raised when settlement is asked to charge *measured* usage greater than the amount that
    was reserved for a quantum.

    The reservation is the workflow's declared maximum requirement; measured usage above it means
    the declared estimate was wrong. Rather than silently clamp (which would let the ledger claim
    ``consumed <= limit`` by discarding real usage), settlement fails **closed** and surfaces the
    overrun explicitly, so a mis-declared estimate can never be hidden."""

    def __init__(self, instance_id: str, dimension: str, actual: float, reserved: float) -> None:
        self.instance_id = instance_id
        self.dimension = dimension
        self.actual = actual
        self.reserved = reserved
        super().__init__(
            f"settled actual usage {actual!r} exceeds the reservation {reserved!r} for "
            f"dimension {dimension!r} of {instance_id!r} (declared budget estimate exceeded)"
        )


@dataclass(frozen=True)
class BudgetShortfall:
    """A structured, audit-friendly explanation of why a reservation was refused (Section 55).

    Names the first dimension (in deterministic sorted order) whose request exceeded what was
    available, with the exact requested and available quantities."""

    instance_id: str
    dimension: str
    requested: float
    available: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "reason": "BUDGET_UNAVAILABLE",
            "instance_id": self.instance_id,
            "budget_dimension": self.dimension,
            "requested": self.requested,
            "available": self.available,
        }


@dataclass(frozen=True)
class BudgetSettlement:
    """The immutable record of settling (or releasing) one quantum's reservation.

    ``charged`` is what became irreversible ``consumed`` per dimension; ``released`` is what was
    returned to ``available``; ``actual_known`` is ``False`` whenever the conservative rule was
    applied (no runtime usage telemetry), so an audit reader never mistakes a conservative charge
    for a measured one."""

    instance_id: str
    charged: Dict[str, float]
    released: Dict[str, float]
    actual_known: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "charged": dict(sorted(self.charged.items())),
            "released": dict(sorted(self.released.items())),
            "actual_known": self.actual_known,
        }


class BudgetCoordinator:
    """A shared, reserve-before-execute budget ledger for one portfolio.

    Driven from the single admission/reconciliation thread; a lock guards every mutation so a
    concurrent reconciliation release is always safe and two quanta can never race the ledger
    into oversubscription. Reservations are transient — at a stable portfolio checkpoint boundary
    ``reserved`` is expected to be zero (an H22-D validation invariant); only ``limits`` and
    ``consumed`` are durable."""

    def __init__(self, budget: Optional[PortfolioBudget] = None) -> None:
        self._lock = threading.Lock()
        self._budget = budget or PortfolioBudget()
        self._consumed: Dict[str, float] = {d: 0.0 for d in self._budget.limits}
        self._reserved: Dict[str, float] = {d: 0.0 for d in self._budget.limits}
        # instance_id -> the amounts reserved for its in-flight quantum.
        self._holds: Dict[str, Dict[str, float]] = {}

    # -- accounting reads ---------------------------------------------------
    @property
    def has_limits(self) -> bool:
        """True when at least one budget dimension is configured with a limit. When ``False`` the
        coordinator gates nothing, so an *undeclared* budget requirement is harmless; when
        ``True`` an undeclared requirement must fail closed (it could draw on a shared limit)."""
        return bool(self._budget.limits)

    def limit(self, dimension: str) -> Optional[float]:
        """The configured limit for ``dimension`` (``None`` if unconstrained)."""
        return self._budget.limits.get(dimension)

    def consumed(self, dimension: str) -> float:
        with self._lock:
            return self._consumed.get(dimension, 0.0)

    def reserved(self, dimension: str) -> float:
        with self._lock:
            return self._reserved.get(dimension, 0.0)

    def available(self, dimension: str) -> Optional[float]:
        """``limit - consumed - reserved`` for a constrained dimension; ``None`` if unconstrained."""
        lim = self._budget.limits.get(dimension)
        if lim is None:
            return None
        with self._lock:
            return lim - self._consumed.get(dimension, 0.0) - self._reserved.get(dimension, 0.0)

    def _available_locked(self, dimension: str) -> Optional[float]:
        lim = self._budget.limits.get(dimension)
        if lim is None:
            return None
        return lim - self._consumed.get(dimension, 0.0) - self._reserved.get(dimension, 0.0)

    # -- reservation --------------------------------------------------------
    def reserve(
        self, instance_id: str, requirement: BudgetRequirement
    ) -> Tuple[bool, Optional[BudgetShortfall]]:
        """Atomically reserve a quantum's full requirement, or reserve nothing.

        All-or-none across dimensions: every *constrained* dimension the requirement names must
        have ``requested <= available``; an unconstrained dimension always fits. If any dimension
        falls short, **nothing** is reserved and ``(False, shortfall)`` is returned (the first
        shortfall in sorted-dimension order, for determinism). Reserving for an ``instance_id``
        that already holds a reservation raises (per-workflow exclusivity is enforced upstream)."""
        with self._lock:
            if instance_id in self._holds:
                raise ValueError(
                    f"budget reservation for {instance_id!r} already active (a workflow may not "
                    "hold two concurrent reservations)"
                )
            for dim in sorted(requirement.amounts):
                need = requirement.amounts[dim]
                if need <= 0:
                    continue
                avail = self._available_locked(dim)
                if avail is None:
                    continue  # unconstrained dimension
                if need > avail:
                    return False, BudgetShortfall(
                        instance_id=instance_id, dimension=dim, requested=need, available=avail
                    )
            # Commit: record the hold and add to reserved (atomic — all dimensions together).
            hold = {d: v for d, v in requirement.amounts.items() if v > 0}
            for dim, need in hold.items():
                if dim in self._reserved:
                    self._reserved[dim] += need
            self._holds[instance_id] = hold
            return True, None

    def settle(
        self, instance_id: str, actual: Optional[Mapping[str, float]] = None
    ) -> BudgetSettlement:
        """Settle a quantum's reservation into ``consumed`` and release the hold.

        When no actual is supplied, the full reservation is charged (the conservative rule —
        never under-charge; ``actual_known=False`` records that no measurement occurred). When an
        actual IS supplied it is charged as-is, but a measured value **greater than** the
        reservation fails **closed** with :class:`BudgetEstimateExceeded` rather than being
        silently clamped — so the ledger never claims ``consumed <= limit`` by discarding real
        usage, and a mis-declared estimate is surfaced, not hidden. With a well-declared estimate
        (actual <= reserved) this charges the actual and releases the unused remainder, keeping
        ``0 <= consumed <= limit``. Settling a workflow with no active hold is a fail-safe no-op."""
        actual_amounts = None
        if actual is not None:
            actual_amounts = _validate_amounts(actual, what="settle actual")
        with self._lock:
            hold = self._holds.pop(instance_id, None)
            if hold is None:
                return BudgetSettlement(instance_id, {}, {}, actual_known=actual is not None)
            # Fail closed on any overrun BEFORE mutating the ledger, so a rejected settlement
            # leaves the reservation intact (the caller can release it explicitly). An overrun is
            # measured usage above the reservation for a reserved dimension, OR any positive usage
            # in a dimension that had NO reservation (an effective reservation of zero) — the
            # latter must not be silently ignored.
            if actual_amounts is not None:
                for dim, a in actual_amounts.items():
                    reserved_amt = hold.get(dim, 0.0)
                    if a > reserved_amt:
                        self._holds[instance_id] = hold  # restore — nothing was changed
                        raise BudgetEstimateExceeded(instance_id, dim, a, reserved_amt)
            charged: Dict[str, float] = {}
            released: Dict[str, float] = {}
            for dim, reserved_amt in hold.items():
                charge = reserved_amt if actual_amounts is None else actual_amounts.get(dim, 0.0)
                charged[dim] = charge
                released[dim] = reserved_amt - charge
                if dim in self._reserved:
                    self._reserved[dim] -= reserved_amt  # release the whole hold
                    if dim in self._consumed:
                        self._consumed[dim] += charge      # charge (actual <= reserved, or full)
            return BudgetSettlement(instance_id, charged, released, actual_known=actual is not None)

    def release(self, instance_id: str) -> bool:
        """Release a reservation WITHOUT consuming any of it (fail-safe, idempotent).

        Used when a quantum did not consume its estimate — a governance HOLD/ESCALATE/BLOCK (no
        provider call), a no-op, a cancellation, or a worker infrastructure failure. Returns
        ``True`` iff a hold was released. No leaked reservation can permanently block the
        portfolio."""
        with self._lock:
            hold = self._holds.pop(instance_id, None)
            if hold is None:
                return False
            for dim, amt in hold.items():
                if dim in self._reserved:
                    self._reserved[dim] = max(0.0, self._reserved[dim] - amt)
            return True

    # -- inspection / durability -------------------------------------------
    def active_instance_ids(self) -> Tuple[str, ...]:
        with self._lock:
            return tuple(self._holds.keys())

    @property
    def has_active_reservations(self) -> bool:
        with self._lock:
            return bool(self._holds)

    def budget_state(self) -> Dict[str, object]:
        """The durable slice for a portfolio checkpoint: limits + consumed only.

        ``reserved`` and per-instance holds are transient and deliberately excluded; a checkpoint
        is committed only at a stable boundary where they are empty."""
        with self._lock:
            return {
                "limits": dict(sorted(self._budget.limits.items())),
                "consumed": dict(sorted((d, v) for d, v in self._consumed.items())),
            }

    @classmethod
    def restore(cls, state: Mapping[str, object]) -> "BudgetCoordinator":
        """Rebuild a coordinator from durable ``{limits, consumed}`` (H22-D recovery).

        Reservations start empty (they never survive a stable boundary). Validates fail-closed:
        finite non-negative values and ``0 <= consumed <= limit`` for every constrained
        dimension; a corrupt slice raises."""
        limits = _validate_amounts(dict(state.get("limits", {})), what="restore limits")  # type: ignore[arg-type]
        consumed = _validate_amounts(dict(state.get("consumed", {})), what="restore consumed")  # type: ignore[arg-type]
        for dim, used in consumed.items():
            lim = limits.get(dim)
            if lim is not None and used > lim:
                raise ValueError(
                    f"restore: consumed {used!r} exceeds limit {lim!r} for dimension {dim!r}"
                )
        coord = cls(PortfolioBudget(limits))
        with coord._lock:
            for dim, used in consumed.items():
                coord._consumed[dim] = used
                coord._reserved.setdefault(dim, 0.0)
        return coord
