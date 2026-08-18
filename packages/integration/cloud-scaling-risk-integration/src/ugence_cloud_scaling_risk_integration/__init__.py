"""Ugence Cloud Scaling Risk Integration — Phase 4C adapter.

A **one-way leaf integration**:

    ugence-cloud-scaling-controller ─┐
                                      ├─► ugence-cloud-scaling-risk-integration ─► RiskEvaluationSeam
    ugence-risk-authority ───────────┘        (projection + one seam call; STOPS at
                                               a non-executable SubjectRiskDecision)

Neither the Cloud Scaling Controller nor Risk Authority imports this package: the
controller remains an advisory leaf and Risk Authority remains a stdlib-only leaf.

This package owns **no runtime and no authority**. It holds no policy, no control
catalog, no evidence source, no keys, no credentials, no clock and no execution surface.
It does not issue envelopes, invoke ActionGate, mint credentials, call a cloud provider,
scale anything, verify an effect, or learn from outcomes — Phase 5 and Phase 6 remain
excluded, and no capability toward either is introduced here.

What it does, in order, before Risk Authority is reached at all:

1. establishes the **recommendation authenticity boundary** Phase 4A/4B left open;
2. projects the recommendation into the RA-owned neutral ``SubjectContext``;
3. builds and locally reconciles the full ``context → binding → request`` digest chain;
4. re-checks the recommendation validity window against an **injected trusted clock**.

Read :mod:`~ugence_cloud_scaling_risk_integration.authenticity` for the precise
statement of what Phase 4C proves, what it does not prove, and which upstream trust
assumption remains.
"""

from __future__ import annotations

from .adapter import CloudScalingRiskAdapter, RiskEvaluationSeamPort
from .authenticity import (
    CARRIED_DIGEST_FIELD,
    AuthenticatedAbstention,
    AuthenticatedRecommendation,
    DigestExpectationSource,
    authenticate_controller_output,
)
from .errors import (
    AdapterConfigurationError,
    CloudScalingRiskIntegrationError,
    MissingIndependentDigestError,
    NonExecutableInvariantError,
    ProjectionError,
    RecommendationAuthenticityError,
    RecommendationInputError,
    RecommendationNotYetValidError,
    RecommendationValidityError,
    UnsupportedRecommendationSourceError,
)
from .identifiers import (
    CANONICAL_ACTION_TYPES,
    DOMAIN_CLOUD_SCALING,
    PURPOSE_CAPACITY_ACTION,
    SUBJECT_TYPE_CAPACITY_SUBJECT,
    canonical_action_type,
)
from .outcomes import (
    ADAPTER_OUTCOME_SCHEMA_VERSION,
    AdapterOutcomeStatus,
    AdapterRejectionReason,
    CloudScalingRiskOutcome,
)
from .projection import (
    PROJECTION_SCHEMA_VERSION,
    CapacityRiskSubjectProjection,
    build_idempotency_key,
    project_recommendation,
)
from .version import __version__

__all__ = [
    "__version__",
    # --- production entry point ---
    "CloudScalingRiskAdapter",
    "RiskEvaluationSeamPort",
    # --- deterministic projection ---
    "project_recommendation",
    "build_idempotency_key",
    "CapacityRiskSubjectProjection",
    "PROJECTION_SCHEMA_VERSION",
    # --- authenticity boundary ---
    "authenticate_controller_output",
    "AuthenticatedRecommendation",
    "AuthenticatedAbstention",
    "DigestExpectationSource",
    "CARRIED_DIGEST_FIELD",
    # --- typed outcomes ---
    "CloudScalingRiskOutcome",
    "AdapterOutcomeStatus",
    "AdapterRejectionReason",
    "ADAPTER_OUTCOME_SCHEMA_VERSION",
    # --- D-4 ratified identifiers ---
    "PURPOSE_CAPACITY_ACTION",
    "DOMAIN_CLOUD_SCALING",
    "SUBJECT_TYPE_CAPACITY_SUBJECT",
    "CANONICAL_ACTION_TYPES",
    "canonical_action_type",
    # --- typed errors ---
    "CloudScalingRiskIntegrationError",
    "AdapterConfigurationError",
    "RecommendationInputError",
    "UnsupportedRecommendationSourceError",
    "RecommendationAuthenticityError",
    "MissingIndependentDigestError",
    "RecommendationValidityError",
    "RecommendationNotYetValidError",
    "ProjectionError",
    "NonExecutableInvariantError",
]
