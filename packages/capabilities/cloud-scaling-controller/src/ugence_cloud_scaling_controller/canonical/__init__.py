"""Canonical Capacity Intelligence — Phase 1 (observation → normalization/projection →
recommendation evidence).

This subpackage adds a provider-neutral representation of the operational world around
the existing Cloud Scaling Controller, WITHOUT changing the controller's advisory-only
authority, provider neutrality, or five-signal decision algorithm:

    Provider / Monitoring Source
              ↓
    CanonicalCapacityState          (rich, immutable, versioned observation)
              ↓
    Normalization / Projection      (explicit, deterministic, policy-driven)
              ↓
    existing ScalingObservation
              ↓
    existing CloudScalingController (unchanged decision kernel)
              ↓
    ScalingRecommendation  +  CapacityDecisionEvidence  (immutable, digest-identified)

Phase 1 owns observation representation, normalization/projection, and recommendation
evidence. It does NOT own — and this layer never performs — risk evaluation, authority,
authorization, action-gate enforcement, actuation, or effect verification. The evidence
digest is a stable content identity for a future, separately governed risk-authority
integration package to reference; it is not a signature, verdict, or authorization.

Everything here is pure-stdlib (no cloud SDK, no network, no new runtime dependency) and
imports only this package's own contracts/config/api.
"""

from __future__ import annotations

from .serialization import (
    NAMESPACE,
    DIGEST_PREFIX,
    CanonicalizationError,
    canonical_json,
    canonical_bytes,
    content_digest,
)
from .measurement import MeasurementError, Unit, Measurement, measure
from .identity import SubjectError, CapacitySubject
from .provenance import (
    ProvenanceError,
    ObservationSourceType,
    ObservationProvenance,
)
from .state import (
    CANONICAL_STATE_SCHEMA_VERSION,
    SUPPORTED_CANONICAL_STATE_SCHEMA_VERSIONS,
    VALID_TIME_PHASES,
    StateError,
    WorkloadState,
    PerformanceState,
    InfrastructureState,
    CapacityState,
    ReliabilityState,
    DeploymentState,
    EconomicsState,
    TopologyState,
    ForecastObservation,
    CanonicalCapacityState,
)
from .normalization import (
    NORMALIZATION_POLICY_SCHEMA_VERSION,
    NormalizationError,
    NormalizationMethod,
    NormalizationPolicy,
    NormalizedSignal,
    normalize_signal,
)
from .projection import (
    PROJECTION_SCHEMA_VERSION,
    CONTROLLER_SIGNALS,
    ProjectionError,
    ControllerProjection,
    project_to_scaling_observation,
)
from .evidence import (
    EVIDENCE_SCHEMA_VERSION,
    CONTROLLER_OBSERVATION_SCHEMA_VERSION,
    AUTHORITY_CLASS_ADVISORY,
    EXECUTION_CAPABILITY_NONE,
    DIGEST_EXCLUDED_FIELDS,
    EvidenceError,
    CapacityDecisionEvidence,
    build_capacity_decision_evidence,
    recommend_with_evidence,
)
from .sources import (
    CapacityObservationSource,
    FixtureObservationSource,
    ReplayObservationSource,
)

__all__ = [
    # serialization
    "NAMESPACE", "DIGEST_PREFIX", "CanonicalizationError",
    "canonical_json", "canonical_bytes", "content_digest",
    # measurement
    "MeasurementError", "Unit", "Measurement", "measure",
    # identity
    "SubjectError", "CapacitySubject",
    # provenance
    "ProvenanceError", "ObservationSourceType", "ObservationProvenance",
    # state
    "CANONICAL_STATE_SCHEMA_VERSION", "SUPPORTED_CANONICAL_STATE_SCHEMA_VERSIONS",
    "VALID_TIME_PHASES", "StateError",
    "WorkloadState", "PerformanceState", "InfrastructureState", "CapacityState",
    "ReliabilityState", "DeploymentState", "EconomicsState", "TopologyState",
    "ForecastObservation", "CanonicalCapacityState",
    # normalization
    "NORMALIZATION_POLICY_SCHEMA_VERSION", "NormalizationError", "NormalizationMethod",
    "NormalizationPolicy", "NormalizedSignal", "normalize_signal",
    # projection
    "PROJECTION_SCHEMA_VERSION", "CONTROLLER_SIGNALS", "ProjectionError",
    "ControllerProjection", "project_to_scaling_observation",
    # evidence
    "EVIDENCE_SCHEMA_VERSION", "CONTROLLER_OBSERVATION_SCHEMA_VERSION",
    "AUTHORITY_CLASS_ADVISORY", "EXECUTION_CAPABILITY_NONE", "DIGEST_EXCLUDED_FIELDS",
    "EvidenceError", "CapacityDecisionEvidence", "build_capacity_decision_evidence",
    "recommend_with_evidence",
    # sources
    "CapacityObservationSource", "FixtureObservationSource", "ReplayObservationSource",
]
