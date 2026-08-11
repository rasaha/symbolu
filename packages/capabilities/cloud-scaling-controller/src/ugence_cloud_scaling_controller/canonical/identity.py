"""Provider-neutral subject / scope identity for canonical capacity observations.

A :class:`CapacitySubject` names *what was observed* using only provider-neutral
references, with unambiguous equality and serialization semantics. It carries the
minimum identity needed to avoid ambiguity (a workload identifier is required); tenant,
resource, environment, cluster, region and zone are optional but, when present, are part
of the subject's stable identity and content digest.

Scope fields are never inferred from an untrusted display name — a caller supplies them
explicitly. No provider-specific resource class (an ARN, an Azure resourceId, a GCP
self-link) appears here; mapping those provider identifiers onto this neutral subject is
the job of a future, separately governed integration/adapter package, documented in the
Phase-1 ADR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


class SubjectError(ValueError):
    """Raised when a subject/scope reference is ambiguous or malformed (fail closed)."""


def _opt_str(name: str, value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SubjectError(f"{name} must be a string, got {type(value).__name__}")
    if value == "":
        raise SubjectError(f"{name} must be a non-empty string if provided")
    return value


@dataclass(frozen=True)
class CapacitySubject:
    """Immutable, provider-neutral identity of an observed workload.

    Required:
        workload_id: Stable identifier of the workload/deployment being observed.

    Optional (part of identity + digest when present):
        tenant_id: Tenant / namespace owner, if the repository's scope model requires it.
        resource_id: Resource / deployment identifier distinct from the workload.
        environment: Logical environment (e.g. ``prod``/``staging``) — opaque string.
        cluster: Logical compute domain / cluster identifier.
        region, zone: Geographic placement when known.
    """

    workload_id: str
    tenant_id: Optional[str] = None
    resource_id: Optional[str] = None
    environment: Optional[str] = None
    cluster: Optional[str] = None
    region: Optional[str] = None
    zone: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.workload_id, str) or self.workload_id == "":
            raise SubjectError("workload_id is required and must be a non-empty string")
        for name in ("tenant_id", "resource_id", "environment", "cluster", "region", "zone"):
            _opt_str(name, getattr(self, name))

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "workload_id": self.workload_id,
            "tenant_id": self.tenant_id,
            "resource_id": self.resource_id,
            "environment": self.environment,
            "cluster": self.cluster,
            "region": self.region,
            "zone": self.zone,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "CapacitySubject":
        if not isinstance(data, dict):
            raise SubjectError("subject must be a mapping")
        known = {"workload_id", "tenant_id", "resource_id", "environment",
                 "cluster", "region", "zone"}
        unknown = set(data) - known
        if unknown:
            raise SubjectError(f"unknown subject field(s): {sorted(unknown)}")
        if "workload_id" not in data:
            raise SubjectError("subject requires 'workload_id'")
        return cls(
            workload_id=data["workload_id"],
            tenant_id=data.get("tenant_id"),
            resource_id=data.get("resource_id"),
            environment=data.get("environment"),
            cluster=data.get("cluster"),
            region=data.get("region"),
            zone=data.get("zone"),
        )


__all__ = ["SubjectError", "CapacitySubject"]
