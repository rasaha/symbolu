"""Trajectory-policy reader seam (spec §5/D2).

Ownership is ratified: **WorkflowIR / the workflow policy layer owns the policy
*content*.** Risk Authority binds the *reference* (the signed
``trajectory_policy_id`` and threaded ``trajectory_version``); RA-7 only *reads*
the content through this neutral seam. The stdlib-only RA leaf is kept free of
telemetry-specific policy implementation.

RA-7 does not own, author, or mutate trajectory policy. It resolves a
:class:`~.contracts.TrajectoryPolicyRef` to a :class:`TrajectoryPolicy` (the
deterministic, explainable thresholds the evaluator applies). An unresolvable or
unknown-version reference yields ``None`` — the evaluator then produces an
``UNKNOWN`` assessment (never a fabricated escalation; spec §20).

Content integrity: when the deferred, additive ``trajectory_policy_digest``
binding (D2) lands, a reader MAY verify the resolved content against
``ref.digest`` and refuse a mismatch. Until then the reference milestone operates
against the authority-bound ``policy_id`` alone and downgrades to ``UNKNOWN``
where content integrity would matter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Protocol, Tuple, runtime_checkable

from .contracts import TrajectoryPolicyRef

__all__ = [
    "TrajectoryPolicy",
    "TrajectoryPolicyReader",
    "ReferenceTrajectoryPolicyReader",
    "ReferencePolicyRejectedError",
]


class ReferencePolicyRejectedError(RuntimeError):
    """Raised when a reference policy reader is wired into production (F-1)."""


@dataclass(frozen=True)
class TrajectoryPolicy:
    """Deterministic, explainable trajectory-risk thresholds (spec §6/§8/§14).

    This is policy *content*, conceptually owned by WorkflowIR and merely read
    here. Every rule is a plain, auditable comparison — there is **no weighted
    "risk score"** that converts to authority (a hard constraint). Absent /
    ``None`` thresholds disable the corresponding rule (that dimension is simply
    not risk-typed), mirroring the runtime's "unconfigured ⇒ unconstrained"
    posture.

    - ``cumulative_exposure_limits`` — per named dimension (e.g. ``model_cost``),
      the cumulative ceiling above which the trajectory is ``CUMULATIVE_EXPOSURE``.
    - ``near_boundary_fraction`` / ``near_boundary_repeat`` — a per-action amount
      at/above this fraction of its dimension ceiling, occurring at least this many
      times, is ``NEAR_BOUNDARY_REPEAT``.
    - ``retry_loop_threshold`` — retries/failures for one action id at/above this
      count is ``RETRY_LOOP``.
    - ``data_class_order`` — the allowed monotonic data-access-class ranking; a
      regression to a *more* sensitive class than the policy permits (a jump past
      ``max_data_class_rank``) is ``DATA_CLASS_PROGRESSION``.
    - ``context_expansion_limit`` — a context size above this is ``CONTEXT_EXPANSION``.
    """

    policy_id: str
    version: Optional[str] = None
    cumulative_exposure_limits: Mapping[str, float] = field(default_factory=dict)
    near_boundary_fraction: Optional[float] = None
    near_boundary_repeat: Optional[int] = None
    retry_loop_threshold: Optional[int] = None
    data_class_order: Tuple[str, ...] = ()
    max_data_class_rank: Optional[int] = None
    context_expansion_limit: Optional[float] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "cumulative_exposure_limits", dict(self.cumulative_exposure_limits)
        )
        object.__setattr__(self, "data_class_order", tuple(self.data_class_order))

    def data_class_rank(self, data_class: str) -> Optional[int]:
        """Return the ranking of ``data_class`` in the policy order, or ``None``.

        A higher rank == more sensitive. ``None`` means the class is unknown to the
        policy (the evaluator treats an unknown class as non-assessable for the
        progression rule, never as safe-by-default).
        """

        try:
            return self.data_class_order.index(data_class)
        except ValueError:
            return None


@runtime_checkable
class TrajectoryPolicyReader(Protocol):
    """Resolve an authority-bound policy reference to its content (spec §5/D2).

    ``resolve`` returns ``None`` for an unknown ``policy_id`` or a version the
    reader cannot pin — the evaluator then produces ``UNKNOWN`` (never fabricated
    escalation). ``is_reference_reader`` marks a conformance stand-in that
    production composition must refuse (F-1 pattern).
    """

    is_reference_reader: bool

    def resolve(self, ref: TrajectoryPolicyRef) -> Optional[TrajectoryPolicy]:
        ...


class ReferenceTrajectoryPolicyReader:
    """In-memory reference reader over an explicit ``policy_id → TrajectoryPolicy`` map.

    This is NOT the production policy source (WorkflowIR). It resolves only
    policies registered on it, pins the version when the registered policy declares
    one, and returns ``None`` for anything unknown — so unknown / substituted /
    stale-version references deterministically become ``UNKNOWN`` assessments.
    ``is_reference_reader = True`` and production composition refuses it.
    """

    is_reference_reader = True

    def __init__(self, policies: Optional[Mapping[str, TrajectoryPolicy]] = None) -> None:
        self._policies: Dict[str, TrajectoryPolicy] = dict(policies or {})

    def register(self, policy: TrajectoryPolicy) -> None:
        self._policies[policy.policy_id] = policy

    def resolve(self, ref: TrajectoryPolicyRef) -> Optional[TrajectoryPolicy]:
        if ref is None or ref.is_empty():
            return None
        policy = self._policies.get(ref.policy_id)
        if policy is None:
            return None
        # Version pinning: if the reference names a version, it must match the
        # registered policy's version exactly, else the reader cannot pin it.
        if ref.version is not None and policy.version is not None:
            if ref.version != policy.version:
                return None
        return policy
