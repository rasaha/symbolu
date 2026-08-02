"""Operator health + readiness.

Health covers operator, durable-store, and integrity state; readiness gates whether
the pilot may run an evaluation now. Readiness is false whenever the kill switch is
active, the pilot is not ACTIVE, config is invalid, store integrity failed, a
required adapter is unavailable, or the execution-disabled invariant is missing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from ..adapters.registry import AdapterRegistryProjection
from ..persistence.sqlite import DurableShadowStore
from .config import PilotDeploymentConfig
from .lifecycle import PilotLifecycleStatus


class PilotHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"


@dataclass(frozen=True)
class PilotHealth:
    status: PilotHealthStatus
    checks: Tuple[Tuple[str, str], ...] = ()
    execution_status: str = "DISABLED"


@dataclass(frozen=True)
class PilotReadiness:
    ready: bool
    reasons: Tuple[str, ...] = ()
    execution_status: str = "DISABLED"


def compute_health(
    *,
    store: Optional[DurableShadowStore],
    registry: Optional[AdapterRegistryProjection],
    lifecycle_status: PilotLifecycleStatus,
    recent_source_failure_rate: float = 0.0,
    integrity_ok: bool = True,
) -> PilotHealth:
    checks = []
    if not integrity_ok:
        checks.append(("event_chain_integrity", "FAIL"))
        return PilotHealth(PilotHealthStatus.INTEGRITY_FAILURE, tuple(checks))
    store_ok = store is not None and store.health_check().get("ok", False)
    checks.append(("durable_store", "PASS" if store_ok else "FAIL"))
    checks.append(("adapter_registry", "PASS" if registry is not None else "FAIL"))
    checks.append(("execution_disabled", "PASS"))
    if lifecycle_status is PilotLifecycleStatus.INTEGRITY_FAILURE:
        return PilotHealth(PilotHealthStatus.INTEGRITY_FAILURE, tuple(checks))
    if not store_ok or registry is None:
        return PilotHealth(PilotHealthStatus.UNHEALTHY, tuple(checks))
    if recent_source_failure_rate > 0.5:
        checks.append(("recent_source_failures", "WARN"))
        return PilotHealth(PilotHealthStatus.DEGRADED, tuple(checks))
    return PilotHealth(PilotHealthStatus.HEALTHY, tuple(checks))


def compute_readiness(
    *,
    config_valid: bool,
    lifecycle_status: PilotLifecycleStatus,
    kill_switch_active: bool,
    store_integrity_ok: bool,
    required_adapter_available: bool,
    execution_disabled: bool = True,
) -> PilotReadiness:
    reasons = []
    if kill_switch_active:
        reasons.append("kill_switch_active")
    if lifecycle_status is not PilotLifecycleStatus.ACTIVE:
        reasons.append(f"lifecycle_not_active:{lifecycle_status.value}")
    if not config_valid:
        reasons.append("config_invalid")
    if not store_integrity_ok:
        reasons.append("store_integrity_failed")
    if not required_adapter_available:
        reasons.append("required_adapter_unavailable")
    if not execution_disabled:
        reasons.append("execution_disabled_invariant_missing")
    return PilotReadiness(ready=not reasons, reasons=tuple(reasons))


__all__ = ["PilotHealthStatus", "PilotHealth", "PilotReadiness",
           "compute_health", "compute_readiness"]
