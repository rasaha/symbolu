"""Canonical cloud envelopes (V2 §5). Reuses the frozen ACP core identity.

CloudWorldState / CloudActionCandidate / CloudOperationalEvidence are the cloud
analogues of the robotics envelopes. They REUSE ``identity.identity`` +
``normalize_float`` + the ACP error hierarchy unchanged — only the fields are
domain-specific. Grounded in the repository's ``cloud_controller`` (K8s deployment
scaling) — see ``ACP_CLOUD_DOMAIN_MODEL.md``.

Fail loudly on ambiguous units, missing identities, stale data, malformed
manifests, or unsupported operations.

Stdlib-only.
"""
from __future__ import annotations

import types
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Tuple

from ..errors import SchemaValidationError
from ..identity import identity, normalize_float

_DOMAIN_STATE = "cloud_world_state"
_DOMAIN_CAND = "cloud_action_candidate"
_DOMAIN_EVID = "cloud_operational_evidence"


class CloudOperation(str, Enum):
    SCALE = "SCALE"                 # change replica count
    ROLLOUT = "ROLLOUT"            # new manifest/image rollout
    CONFIG_UPDATE = "CONFIG_UPDATE"
    DELETE = "DELETE"             # destructive
    ROLLBACK = "ROLLBACK"


class CloudValidity(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    EVALUATOR_FAILED = "EVALUATOR_FAILED"
    MISSING = "MISSING"


@dataclass(frozen=True)
class CloudWorldState:
    """Immutable cluster/deployment snapshot; ``version`` == content identity."""
    cluster: str
    namespace: str
    deployment: str
    resource_version: str          # K8s resourceVersion (CAS token)
    generation: int                # deployment.metadata.generation
    desired_replicas: int
    current_replicas: int
    available_replicas: int
    readiness_plasticity: float    # cloud_controller readiness signal [0,1]
    active_rollback_watches: int
    seconds_since_last_action: float
    dependency_healthy: bool
    freeze_active: bool            # from cloud_controller BlackoutWindow
    observation_time_s: float
    extensions: Mapping[str, str] = field(default_factory=dict)
    provenance: str = field(default="", metadata={"identity": False})

    def __post_init__(self) -> None:
        for f in ("cluster", "namespace", "deployment", "resource_version"):
            if not getattr(self, f):
                raise SchemaValidationError(f"{f} must be non-empty")
        for f in ("generation", "desired_replicas", "current_replicas",
                  "available_replicas", "active_rollback_watches"):
            if getattr(self, f) < 0:
                raise SchemaValidationError(f"{f} must be >= 0")
        for f in ("readiness_plasticity", "seconds_since_last_action",
                  "observation_time_s"):
            normalize_float(getattr(self, f), field=f"CloudWorldState.{f}")
        ext = dict(self.extensions)
        for k, v in ext.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise SchemaValidationError("extensions must be str->str")
        object.__setattr__(self, "extensions", types.MappingProxyType(ext))

    @property
    def version(self) -> str:
        return identity(self, domain=_DOMAIN_STATE)


@dataclass(frozen=True)
class CloudActionCandidate:
    """A proposed cloud operation (e.g. scale N->M)."""
    candidate_id: str
    operation: CloudOperation
    namespace: str
    deployment: str
    current_replicas: int
    desired_replicas: int          # target for SCALE (== current for non-scale)
    manifest_digest: str           # for ROLLOUT/CONFIG_UPDATE ("" if N/A)
    rollback_ref: str              # rollback artifact id ("" if none)
    rollout_strategy: str          # e.g. "RollingUpdate" / "Recreate"
    max_unavailable: int
    max_surge: int
    timeout_s: float
    origin_state_version: str
    metadata: Mapping[str, str] = field(default_factory=dict)
    provenance: str = field(default="", metadata={"identity": False})

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.deployment or not self.namespace:
            raise SchemaValidationError("candidate_id/deployment/namespace required")
        if not isinstance(self.operation, CloudOperation):
            raise SchemaValidationError("operation must be CloudOperation")
        if not self.origin_state_version:
            raise SchemaValidationError("origin_state_version required")
        for f in ("current_replicas", "desired_replicas", "max_unavailable", "max_surge"):
            if getattr(self, f) < 0:
                raise SchemaValidationError(f"{f} must be >= 0")
        normalize_float(self.timeout_s, field="CloudActionCandidate.timeout_s")
        m = dict(self.metadata)
        for k, v in m.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise SchemaValidationError("metadata must be str->str")
        object.__setattr__(self, "metadata", types.MappingProxyType(m))

    @property
    def blast_radius(self) -> int:
        """Replicas affected. SCALE: |delta|; DELETE: all current; else surge."""
        if self.operation is CloudOperation.SCALE:
            return abs(self.desired_replicas - self.current_replicas)
        if self.operation is CloudOperation.DELETE:
            return self.current_replicas
        return max(self.max_surge, self.max_unavailable, 1)

    @property
    def is_destructive(self) -> bool:
        return self.operation is CloudOperation.DELETE

    @property
    def identity(self) -> str:
        return identity(self, domain=_DOMAIN_CAND)


@dataclass(frozen=True)
class CloudOperationalEvidence:
    """Deterministic operational-safety evidence for one candidate."""
    candidate_identity: str
    state_version: str
    evaluator: str
    evaluator_version: str
    observation_time_s: float
    freshness_s: float
    validity: CloudValidity
    readiness_ok: Optional[bool] = None
    readiness_status: Optional[str] = None
    capacity_margin_replicas: Optional[int] = None
    rollback_available: Optional[bool] = None
    blast_radius: Optional[int] = None
    freeze_active: Optional[bool] = None
    dependency_healthy: Optional[bool] = None
    reason_codes: Tuple[str, ...] = ()
    note: str = field(default="", metadata={"identity": False})

    def __post_init__(self) -> None:
        if not self.candidate_identity or not self.state_version:
            raise SchemaValidationError("candidate_identity/state_version required")
        if not isinstance(self.validity, CloudValidity):
            raise SchemaValidationError("validity must be CloudValidity")
        normalize_float(self.observation_time_s, field="observation_time_s")
        normalize_float(self.freshness_s, field="freshness_s")
        if self.freshness_s < 0:
            raise SchemaValidationError("freshness_s must be >= 0")
        if not isinstance(self.reason_codes, tuple):
            raise SchemaValidationError("reason_codes must be a tuple")

    @property
    def is_usable(self) -> bool:
        return self.validity is CloudValidity.VALID

    @property
    def identity(self) -> str:
        return identity(self, domain=_DOMAIN_EVID)
