"""ACP cloud-operations domain adapter (V2 cross-domain study).

Additive domain layer that REUSES the frozen ACP V1 core (identity, constraints,
selection, decision trace, authorization/revalidation, outcomes) UNCHANGED, and
adds only cloud-specific envelopes, evidence, constraints, and a shadow adapter
for Kubernetes deployment operations.

Stdlib-only: the cloud constraints consume the repository's real, deterministic
``cloud_controller`` policy/readiness/rollback logic (imported lazily inside the
evaluators), never the Kubernetes client. ACP is shadow-only and never actuates.

This package is NOT imported by the ACP core ``__init__``; importing the ACP core
stays production-independent.
"""
from .adapter import (
    BoundedCloudSink,
    CloudShadowAdapter,
    CloudShadowRecord,
    CloudShadowResult,
)
from .composition import (
    AuthorizationVerdict,
    CombinedOutcome,
    CompositionResult,
    compose,
)
from .constraints import (
    CloudConstraintConfig,
    CloudConstraintEvaluator,
    EVALUATOR_NAME,
    EVALUATOR_VERSION,
)
from .envelopes import (
    CloudActionCandidate,
    CloudOperation,
    CloudOperationalEvidence,
    CloudValidity,
    CloudWorldState,
)
from .outcomes import CloudRecommendation, cloud_recommendation, is_permissive

__all__ = [
    "CloudWorldState", "CloudActionCandidate", "CloudOperationalEvidence",
    "CloudOperation", "CloudValidity",
    "CloudConstraintEvaluator", "CloudConstraintConfig",
    "EVALUATOR_NAME", "EVALUATOR_VERSION",
    "CloudRecommendation", "cloud_recommendation", "is_permissive",
    "AuthorizationVerdict", "CombinedOutcome", "CompositionResult", "compose",
    "CloudShadowAdapter", "CloudShadowResult", "CloudShadowRecord",
    "BoundedCloudSink",
]
