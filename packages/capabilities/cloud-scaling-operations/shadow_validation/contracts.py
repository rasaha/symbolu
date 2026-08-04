"""Evidence and decision contracts for the read-only shadow-validation harness.

These types define the *shadow* boundary. A :class:`ShadowDecision` is always a
proposal: it carries ``execution_mode == SHADOW``, ``execution_status ==
NOT_EXECUTED`` and ``proposed_only is True``. Nothing in this package converts a
shadow decision into a live execution request — that requires the separately
invoked, separately authorized controlled-execution API of the operations package.

Every artifact emitted by this harness is labelled as fake/local fixture evidence
(:data:`EVIDENCE_CLASS_FIXTURE`) with ``real_environment_observed`` and
``real_cluster_accessed`` both ``False``. This phase never observes a real cluster.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

# Schema version for the shadow-harness evidence model.
SHADOW_SCHEMA_VERSION = "1.0"

# Mandatory labels stamped on every emitted artifact so fixture evidence can never be
# mistaken for a genuine real-environment shadow run.
EVIDENCE_CLASS_FIXTURE = "FAKE_LOCAL_FIXTURE"
NOT_REAL_ENVIRONMENT_EVIDENCE = "NOT_REAL_ENVIRONMENT_EVIDENCE"

# Shadow decisions are always proposals — these are the only permitted values.
EXECUTION_MODE_SHADOW = "SHADOW"
EXECUTION_STATUS_NOT_EXECUTED = "NOT_EXECUTED"

# The only "accepted" authorization result a shadow run may ever produce. There is no
# AUTHORIZED_FOR_LIVE_EXECUTION result in this harness.
AUTHORIZED_FOR_SHADOW_PLAN = "AUTHORIZED_FOR_SHADOW_PLAN"


class Destination(str, Enum):
    """Classes of remote endpoint the transport barrier governs."""

    KUBERNETES = "kubernetes"
    ARGOCD = "argocd"
    METRICS = "metrics"
    WEBHOOK = "webhook"
    OTLP = "otlp"
    GENERIC = "generic"


class StaleClassification(str, Enum):
    FRESH = "FRESH"
    AGE_EXCEEDED = "AGE_EXCEEDED"
    RESOURCE_VERSION_CHANGED = "RESOURCE_VERSION_CHANGED"
    GENERATION_CHANGED = "GENERATION_CHANGED"
    REPLICA_STATE_CHANGED = "REPLICA_STATE_CHANGED"
    HPA_DESIRED_CHANGED = "HPA_DESIRED_CHANGED"
    RESOURCE_DISAPPEARED = "RESOURCE_DISAPPEARED"
    NAMESPACE_UNAVAILABLE = "NAMESPACE_UNAVAILABLE"
    INCOMPLETE = "INCOMPLETE"


class HpaInteraction(str, Enum):
    NO_HPA = "NO_HPA"
    HPA_OBSERVED_COMPATIBLE = "HPA_OBSERVED_COMPATIBLE"
    HPA_OBSERVED_CONFLICT = "HPA_OBSERVED_CONFLICT"
    HPA_BOUNDS_CONFLICT = "HPA_BOUNDS_CONFLICT"
    HPA_STATE_INCOMPLETE = "HPA_STATE_INCOMPLETE"
    NOT_EVALUATED = "NOT_EVALUATED"


# --------------------------------------------------------------------------- #
# Transport
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class TransportDecision:
    """The barrier's verdict for one attempted remote call, made *before* transmit."""

    method: str
    destination_class: str
    redacted_endpoint: str
    allowed: bool
    call_site: str
    timestamp: float
    blocked_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: asdict(self)[k] for k in sorted(asdict(self))}


@dataclass(frozen=True)
class LedgerEntry:
    """One row of the request-method ledger (append-only)."""

    timestamp: float
    destination_class: str
    redacted_endpoint: str
    method: str
    allowed: bool
    blocked: bool
    call_site: str
    fixture_or_real: str = "fixture"
    blocked_reason: Optional[str] = None
    response_status: Optional[int] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: asdict(self)[k] for k in sorted(asdict(self))}


# --------------------------------------------------------------------------- #
# Observations (only fields needed for scaling analysis; never secrets)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class DeploymentObservation:
    cluster_identifier: str
    namespace: str
    resource_kind: str
    resource_name: str
    resource_uid: str
    resource_version: str
    generation: int
    observed_generation: int
    current_replicas: int
    desired_replicas: int
    available_replicas: int
    ready_replicas: int
    updated_replicas: int
    observation_timestamp: float
    conditions: List[Dict[str, str]] = field(default_factory=list)
    cpu_utilization: Optional[float] = None
    memory_utilization: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: asdict(self)[k] for k in sorted(asdict(self))}


# A StatefulSet observation carries the same scaling-relevant shape.
StatefulSetObservation = DeploymentObservation


@dataclass(frozen=True)
class HorizontalPodAutoscalerObservation:
    cluster_identifier: str
    namespace: str
    resource_name: str
    target_kind: str
    target_name: str
    min_replicas: int
    max_replicas: int
    current_replicas: int
    desired_replicas: int
    observation_timestamp: float
    cpu_utilization: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: asdict(self)[k] for k in sorted(asdict(self))}


@dataclass(frozen=True)
class PodSummary:
    namespace: str
    name: str
    phase: str
    ready: bool
    restart_count: int


@dataclass(frozen=True)
class ReplicaSetSummary:
    namespace: str
    name: str
    replicas: int
    ready_replicas: int


@dataclass(frozen=True)
class EventSummary:
    namespace: str
    reason: str
    type: str
    count: int


@dataclass(frozen=True)
class MetricsObservation:
    namespace: str
    resource_name: str
    cpu_utilization: Optional[float]
    memory_utilization: Optional[float]
    observation_timestamp: float


# --------------------------------------------------------------------------- #
# Shadow decision (always a proposal)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ShadowDecision:
    """A proposed-only scaling decision. Never executed by this harness."""

    session_id: str
    observation_id: str
    recommendation_id: str
    decision_id: str
    authorization_test_id: Optional[str]
    cluster_identifier: str
    namespace: str
    resource_kind: str
    resource_name: str
    current_replicas: int
    recommended_replicas: int
    hpa_state: str
    policy_result: str
    staleness_result: str
    authorization_result: str
    proposed_action: str
    not_executed_reason: str
    timestamp: float
    # Invariants — always these values for a shadow decision.
    execution_mode: str = EXECUTION_MODE_SHADOW
    execution_status: str = EXECUTION_STATUS_NOT_EXECUTED
    proposed_only: bool = True

    def __post_init__(self) -> None:
        # Fail closed if anyone tries to build a non-shadow / executed decision.
        if self.execution_mode != EXECUTION_MODE_SHADOW:
            raise ValueError("ShadowDecision.execution_mode must be SHADOW")
        if self.execution_status != EXECUTION_STATUS_NOT_EXECUTED:
            raise ValueError("ShadowDecision.execution_status must be NOT_EXECUTED")
        if self.proposed_only is not True:
            raise ValueError("ShadowDecision.proposed_only must be True")

    def to_dict(self) -> Dict[str, Any]:
        return {k: asdict(self)[k] for k in sorted(asdict(self))}


def stable_hash(obj: Any) -> str:
    """Deterministic sha256 over a JSON-serializable object (sorted keys)."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


__all__ = [
    "SHADOW_SCHEMA_VERSION",
    "EVIDENCE_CLASS_FIXTURE",
    "NOT_REAL_ENVIRONMENT_EVIDENCE",
    "EXECUTION_MODE_SHADOW",
    "EXECUTION_STATUS_NOT_EXECUTED",
    "AUTHORIZED_FOR_SHADOW_PLAN",
    "Destination",
    "StaleClassification",
    "HpaInteraction",
    "TransportDecision",
    "LedgerEntry",
    "DeploymentObservation",
    "StatefulSetObservation",
    "HorizontalPodAutoscalerObservation",
    "PodSummary",
    "ReplicaSetSummary",
    "EventSummary",
    "MetricsObservation",
    "ShadowDecision",
    "stable_hash",
]
