"""LIVE gating (ADR 5D, D-3) and blast-radius narrowing (D-4).

The effective mode is resolved per act from the deployment's requested mode and the
proven posture. ``LIVE`` survives only when every precondition holds; any absence resolves
to ``DRY_RUN`` and never to ``SIMULATION``, because a simulation against a fake would look
like a decision about the real target. The executor's ``TargetPolicy`` is narrowed to the
grant's role and never widened beyond the deployment's own config.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from ugence_cloud_scaling_operations.config import OperationsConfig, TargetPolicy
from ugence_cloud_scaling_operations.contracts import ExecutionMode

from .mapping import OpsTarget

__all__ = ["LivePosture", "resolve_effective_mode", "narrow_target_policy"]


@dataclass(frozen=True)
class LivePosture:
    """Each fact the seam proved (or failed to prove) about its dependencies for this act."""

    production_application: bool
    production_ledger: bool
    production_grant_store: bool
    production_broker: bool
    non_reference_grant_handle: bool
    backend_injected: bool
    readiness_required: bool

    def missing(self) -> tuple[str, ...]:
        return tuple(name for name, held in (
            ("production Risk Authority application", self.production_application),
            ("production-mode execution ledger", self.production_ledger),
            ("production-authoritative grant store", self.production_grant_store),
            ("production-authoritative broker", self.production_broker),
            ("non-reference grant handle", self.non_reference_grant_handle),
            ("injected backend", self.backend_injected),
            ("readiness required", self.readiness_required),
        ) if not held)


def resolve_effective_mode(requested: ExecutionMode, posture: LivePosture
                           ) -> tuple[ExecutionMode, tuple[str, ...]]:
    """``LIVE`` only with every precondition; any absence resolves to ``DRY_RUN``."""

    if requested is not ExecutionMode.LIVE:
        return requested, ()
    missing = posture.missing()
    if missing:
        return ExecutionMode.DRY_RUN, tuple(f"LIVE precondition absent: {m}" for m in missing)
    return ExecutionMode.LIVE, ()


def _narrow_list(role_value: str, configured: tuple[str, ...]) -> tuple[str, ...]:
    """The role's one value, if the deployment's allowlist admits it or is unset; else nothing."""

    if not configured or role_value in configured:
        return (role_value,)
    return ()


def narrow_target_policy(config: OperationsConfig, target: OpsTarget, *, max_magnitude: int,
                         max_delta: int) -> TargetPolicy:
    """Ceilings from the role, never above config; allowlists to the role's one target."""

    base = config.target_policy
    return replace(
        base,
        allowed_clusters=_narrow_list(target.cluster, base.allowed_clusters),
        allowed_namespaces=_narrow_list(target.namespace, base.allowed_namespaces),
        allowed_resources=_narrow_list(target.resource, base.allowed_resources),
        allow_wildcard=False,
        max_replica_delta=min(base.max_replica_delta, max_delta),
        max_replicas=min(base.max_replicas, max_magnitude),
    )
