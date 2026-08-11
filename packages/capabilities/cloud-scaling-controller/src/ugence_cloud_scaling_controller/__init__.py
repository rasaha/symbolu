"""Ugence Cloud Scaling Controller — independent, advisory scaling capability.

Coherence-aware adaptive control for cloud infrastructure. Consumes normalized
workload/infrastructure observations and produces explainable, deterministic
scaling *recommendations*. Provider-neutral and advisory-only: this package never
scales infrastructure, calls a cloud API, or authorizes a change.

Core equation (unchanged from the verified controller)::

    Action_t = d_t * G_t * P_t * S_t

    P_t = sigmoid(k_r * R_t - k_m * M_t + b_p)          # plasticity gate
    G_t = clip(G_base * f_phase * f_coh, G_min, G_max)  # adaptive gain
    d_t = exp(-k_dv * V_excess - k_dc * U_t)            # damping
    S_t = weighted pressure from normalized metrics     # signal

Public API (deliberately small):
    CloudScalingController  — stable package facade (observation -> recommendation)
    Controller              — low-level compatibility control API
    InfraControllerConfig   — controller configuration
    ScalingObservation      — input contract
    ScalingRecommendation   — output contract
    ActionResult            — low-level controller result
    evaluate                — one-shot convenience function
    __version__
"""

from .version import __version__
from .config import InfraControllerConfig
from .controller import Controller, ActionResult
from .contracts import (
    ScalingObservation,
    ScalingRecommendation,
    ScalingExecutor,
    ExecutionReceipt,
    ContractError,
    SCHEMA_VERSION,
)
from .api import CloudScalingController, evaluate

# Phase 1: Canonical Capacity Intelligence — provider-neutral observation representation,
# explicit normalization/projection, and immutable recommendation evidence built AROUND
# the unchanged controller. Additive and pure-stdlib; the decision kernel is untouched.
from . import canonical
from .canonical import (
    CanonicalCapacityState,
    CapacitySubject,
    Measurement,
    Unit,
    ObservationProvenance,
    ObservationSourceType,
    NormalizationPolicy,
    NormalizationMethod,
    ControllerProjection,
    project_to_scaling_observation,
    CapacityDecisionEvidence,
    recommend_with_evidence,
    CapacityObservationSource,
)

__all__ = [
    "CloudScalingController",
    "Controller",
    "InfraControllerConfig",
    "ScalingObservation",
    "ScalingRecommendation",
    "ScalingExecutor",
    "ExecutionReceipt",
    "ContractError",
    "ActionResult",
    "evaluate",
    "SCHEMA_VERSION",
    "__version__",
    # Phase 1 canonical capacity intelligence (additive)
    "canonical",
    "CanonicalCapacityState",
    "CapacitySubject",
    "Measurement",
    "Unit",
    "ObservationProvenance",
    "ObservationSourceType",
    "NormalizationPolicy",
    "NormalizationMethod",
    "ControllerProjection",
    "project_to_scaling_observation",
    "CapacityDecisionEvidence",
    "recommend_with_evidence",
    "CapacityObservationSource",
]
