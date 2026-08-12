"""Dependency- and cost-aware Capacity Planning — Phase 3 (shadow / advisory only).

This additive, pure-stdlib leaf subpackage answers, in SHADOW mode only:

    Given the Phase-2 forecast, service dependencies, operating constraints and cost
    evidence, what is the best capacity ACTION — and why?

Architecture (nothing here executes, authorizes, or verifies an effect)::

    CapacityForecastEvidence (Phase 2)
        +  DependencyTopology (supplied dependency evidence)
        +  CostBook (supplied, exact-money cost evidence)
        +  OperatingConstraints (hard, non-compensatory limits)
        +  RecommendationPolicy (explicit, versioned weights + thresholds)
              ↓  recommend_capacity_action  (deterministic, clock-free, fail-closed)
        bounded candidate generation (always incl. NO_CHANGE)
              ↓  hard-constraint filtering  (BEFORE scoring; non-compensatory)
              ↓  dependency + cost evaluation, explicit policy scoring
    CapacityActionRecommendation   (selected plan + alternatives + typed rejections,
                                    self-revalidating, sha256 content-identity digest)
              OR
    RecommendationAbstention       (a typed, first-class abstention)

Boundary: a RECOMMENDATION is descriptive capacity intelligence. It is NOT an authorization,
a risk evaluation, an ActionGate decision, or an execution instruction. Every recommendation
and abstention carries ``advisory_only=True``, ``shadow_only=True``, ``actuation_performed=
False`` (recommendations also assert ``authorization_performed=False`` and ``effect_verified=
False``), ``authority_class=ADVISORY``, ``execution_capability=NONE``. This layer imports no
Risk Authority (Phase 4), no ActionGate / provider execution (Phase 5), and no effect
verification / learning (Phase 6); it performs no network / subprocess / credential / LLM
activity and adds no runtime dependency.

Maturity: the recommendation policy is a deterministic BASELINE verified for implementation
correctness only. Economic optimality, predictive quality, and production effectiveness are
NOT established (ECONOMIC_OPTIMALITY_NOT_ESTABLISHED, PREDICTIVE_QUALITY_NOT_ESTABLISHED,
PRODUCTION_EFFECTIVENESS_NOT_ESTABLISHED). No recommendation is authorized or executed here.
"""

from __future__ import annotations

from .abstention import (
    RECOMMENDATION_STATUS_ABSTAINED,
    RECOMMENDATION_STATUS_RECOMMENDED,
    RecommendationAbstentionReason,
)
from .topology import (
    DEPENDENCY_EDGE_SCHEMA_VERSION,
    DEPENDENCY_TOPOLOGY_SCHEMA_VERSION,
    DependencyEdge,
    DependencyKind,
    DependencyTopology,
    TopologyError,
)
from .cost import (
    COST_BOOK_SCHEMA_VERSION,
    COST_EVIDENCE_SCHEMA_VERSION,
    CostBasis,
    CostBook,
    CostError,
    CostEvidence,
    Money,
)
from .constraints import (
    OPERATING_CONSTRAINTS_SCHEMA_VERSION,
    ConstraintError,
    ConstraintViolationKind,
    OperatingConstraints,
)
from .candidates import (
    CANDIDATE_PLAN_SCHEMA_VERSION,
    MAX_CANDIDATES,
    ActionKind,
    CandidateActionPlan,
    CandidateError,
    ResourceChange,
    generate_candidates,
)
from .policy import (
    RECOMMENDATION_POLICY_SCHEMA_VERSION,
    SCORE_BREAKDOWN_SCHEMA_VERSION,
    FEATURE_NAMES,
    PolicyError,
    RecommendationPolicy,
    ScoreBreakdown,
)
from .scoring import (
    PLANNING_TARGET,
    EvaluationContext,
    ScoringError,
    build_context,
    compute_features,
    evaluate_feasibility,
    plan_cost_delta_minor,
    primary_capacity_dependency,
    score_candidate,
)
from .recommendation import (
    EVALUATED_CANDIDATE_SCHEMA_VERSION,
    RECOMMENDATION_ABSTENTION_SCHEMA_VERSION,
    RECOMMENDATION_SCHEMA_VERSION,
    CapacityActionRecommendation,
    EvaluatedCandidate,
    RecommendationAbstention,
    RecommendationError,
)
from .pipeline import (
    PipelineError,
    RecommendationOutcome,
    recommend_capacity_action,
)

__all__ = [
    # abstention
    "RECOMMENDATION_STATUS_ABSTAINED", "RECOMMENDATION_STATUS_RECOMMENDED",
    "RecommendationAbstentionReason",
    # topology
    "DEPENDENCY_EDGE_SCHEMA_VERSION", "DEPENDENCY_TOPOLOGY_SCHEMA_VERSION",
    "DependencyEdge", "DependencyKind", "DependencyTopology", "TopologyError",
    # cost
    "COST_BOOK_SCHEMA_VERSION", "COST_EVIDENCE_SCHEMA_VERSION", "CostBasis", "CostBook",
    "CostError", "CostEvidence", "Money",
    # constraints
    "OPERATING_CONSTRAINTS_SCHEMA_VERSION", "ConstraintError", "ConstraintViolationKind",
    "OperatingConstraints",
    # candidates
    "CANDIDATE_PLAN_SCHEMA_VERSION", "MAX_CANDIDATES", "ActionKind", "CandidateActionPlan",
    "CandidateError", "ResourceChange", "generate_candidates",
    # policy
    "RECOMMENDATION_POLICY_SCHEMA_VERSION", "SCORE_BREAKDOWN_SCHEMA_VERSION", "FEATURE_NAMES",
    "PolicyError", "RecommendationPolicy", "ScoreBreakdown",
    # scoring
    "PLANNING_TARGET", "EvaluationContext", "ScoringError", "build_context",
    "compute_features", "evaluate_feasibility", "plan_cost_delta_minor",
    "primary_capacity_dependency", "score_candidate",
    # recommendation
    "EVALUATED_CANDIDATE_SCHEMA_VERSION", "RECOMMENDATION_ABSTENTION_SCHEMA_VERSION",
    "RECOMMENDATION_SCHEMA_VERSION", "CapacityActionRecommendation", "EvaluatedCandidate",
    "RecommendationAbstention", "RecommendationError",
    # pipeline (the shadow / advisory entry point)
    "PipelineError", "RecommendationOutcome", "recommend_capacity_action",
]
