"""Operations configuration and target-safety policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .contracts import ExecutionMode


@dataclass(frozen=True)
class TargetPolicy:
    """Allowlists and bounds that constrain what may ever be mutated.

    Wildcards and empty namespaces are rejected by default; production live mutation
    requires explicit cluster/namespace/resource allowlisting.
    """

    allowed_clusters: Tuple[str, ...] = ()
    allowed_namespaces: Tuple[str, ...] = ()
    allowed_resources: Tuple[str, ...] = ()
    allow_wildcard: bool = False
    max_replica_delta: int = 5
    min_replicas: int = 1
    max_replicas: int = 100
    max_observation_age_seconds: float = 120.0

    def _match(self, value: str, allowed: Tuple[str, ...]) -> bool:
        if not value or value.strip() != value:
            return False
        if value in ("*", "all", "any"):
            return self.allow_wildcard
        if not allowed:
            return False  # empty allowlist => nothing allowed (fail closed)
        return value in allowed

    def cluster_allowed(self, cluster: str) -> bool:
        return self._match(cluster, self.allowed_clusters)

    def namespace_allowed(self, namespace: str) -> bool:
        return self._match(namespace, self.allowed_namespaces)

    def resource_allowed(self, resource: str) -> bool:
        return self._match(resource, self.allowed_resources)


@dataclass(frozen=True)
class OperationsConfig:
    """Top-level configuration for the controlled executor.

    ``mode`` defaults to DRY_RUN — LIVE must be selected explicitly.
    """

    mode: ExecutionMode = ExecutionMode.DRY_RUN
    target_policy: TargetPolicy = field(default_factory=TargetPolicy)
    # LIVE preconditions
    require_audit_sink: bool = True
    require_readiness: bool = True
    cooldown_seconds: float = 60.0
    rate_limit_per_minute: int = 6
    max_concurrent_executions: int = 1
    # ArgoCD / TLS
    argocd_allowed_base_urls: Tuple[str, ...] = ()
    allow_insecure_tls: bool = False   # rejected in LIVE regardless
    request_timeout_seconds: float = 10.0
    max_retries: int = 2
    # Auto-approval is only ever permitted to drive DRY_RUN / SIMULATION.
    allow_auto_approval_in_nonlive: bool = True

    def is_live(self) -> bool:
        return self.mode == ExecutionMode.LIVE

    def mutation_permitted(self) -> bool:
        """Only LIVE mutates real infrastructure."""
        return self.mode == ExecutionMode.LIVE


__all__ = ["OperationsConfig", "TargetPolicy"]
