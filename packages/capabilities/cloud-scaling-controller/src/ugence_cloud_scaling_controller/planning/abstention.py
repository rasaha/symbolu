"""Typed abstention reasons for shadow capacity-action recommendation (Phase 3).

An abstention is a *first-class, evidence-producing* Phase-3 output: when the
authoritative evidence needed to choose a capacity action is missing, stale, contradictory,
or ambiguous, the recommender declines to recommend rather than fabricate a plan. Every
reason here is a stable, machine-readable enum value so a downstream reader can aggregate
abstentions by cause.

These reasons name why a recommendation was *not* produced. They are descriptive capacity
intelligence only — never a risk verdict, an authorization, or an execution signal. Phase 3
never collapses a typed domain failure into a generic exception or a generic abstention.
"""

from __future__ import annotations

from enum import Enum

RECOMMENDATION_STATUS_RECOMMENDED = "recommended"
RECOMMENDATION_STATUS_ABSTAINED = "abstained"


class RecommendationAbstentionReason(str, Enum):
    """Stable, typed reasons the recommender declines to produce a capacity action."""

    # --- forecast evidence ---------------------------------------------------------
    MISSING_FORECAST = "missing_forecast"
    EXPIRED_FORECAST = "expired_forecast"
    UNSUPPORTED_FORECAST_TARGET = "unsupported_forecast_target"
    INSUFFICIENT_FORECAST_CONFIDENCE = "insufficient_forecast_confidence"
    FORECAST_ABSTAINED = "forecast_abstained"

    # --- canonical state -----------------------------------------------------------
    MISSING_CANONICAL_STATE = "missing_canonical_state"
    MISSING_CURRENT_CAPACITY = "missing_current_capacity"
    SUBJECT_SCOPE_MISMATCH = "subject_scope_mismatch"

    # --- topology ------------------------------------------------------------------
    MISSING_TOPOLOGY = "missing_topology"
    STALE_TOPOLOGY = "stale_topology"
    DEPENDENCY_CYCLE = "dependency_cycle"
    CONFLICTING_DEPENDENCY_EVIDENCE = "conflicting_dependency_evidence"
    MISSING_DEPENDENCY_CAPACITY = "missing_dependency_capacity"

    # --- cost ----------------------------------------------------------------------
    MISSING_COST_EVIDENCE = "missing_cost_evidence"
    INCOMPATIBLE_COST_EVIDENCE = "incompatible_cost_evidence"
    STALE_COST_EVIDENCE = "stale_cost_evidence"
    CURRENCY_MISMATCH = "currency_mismatch"

    # --- constraints ---------------------------------------------------------------
    MISSING_CONSTRAINTS = "missing_constraints"
    QUOTA_CONFLICT = "quota_conflict"
    COOLDOWN_ACTIVE = "cooldown_active"
    NO_FEASIBLE_ACTION = "no_feasible_action"

    # --- selection -----------------------------------------------------------------
    AMBIGUOUS_BEST_PLAN = "ambiguous_best_plan"
    UNSUPPORTED_RESOURCE_TYPE = "unsupported_resource_type"

    # --- integrity / temporal ------------------------------------------------------
    NON_FINITE_INPUT = "non_finite_input"
    FUTURE_DATA_LEAKAGE = "future_data_leakage"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"


__all__ = [
    "RECOMMENDATION_STATUS_RECOMMENDED",
    "RECOMMENDATION_STATUS_ABSTAINED",
    "RecommendationAbstentionReason",
]
