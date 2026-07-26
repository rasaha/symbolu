"""H5 validation tooling (application-local, validation-only)."""
from __future__ import annotations

from .audit_completeness import AuditCompletenessScore, score_case
from .composition import ValidationEnv, build_validation_env
from .fairness import FairnessReport, analyze, counterfactual_invariance
from .lifecycle import CaseRun, CaseSpec, run_lifecycle
from .metrics import cohort_metrics
from .pilot import build_cohort, run_pilot

__all__ = [
    "build_validation_env", "ValidationEnv", "CaseSpec", "CaseRun", "run_lifecycle",
    "build_cohort", "run_pilot", "cohort_metrics", "analyze", "FairnessReport",
    "counterfactual_invariance", "score_case", "AuditCompletenessScore",
]
