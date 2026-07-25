"""Benchmark schemas — neutral result, safety taxonomy, failure profiles, dataset."""
from __future__ import annotations

from .result import (
    NOT_APPLICABLE, NOT_PERFORMED, UNKNOWN, StrategyResult)
from .safety import SafetyOutcome, UNSAFE_OUTCOMES
from .failure import (
    FailureProfile, REQUIRED_PROFILES, STRATEGY_COMPONENTS, applies_to)
from .dataset import (
    DOMAIN_NAMES, DatasetIdentity, EnterpriseScenario, load_frozen_dataset, verify_identity)

__all__ = [
    "StrategyResult", "NOT_APPLICABLE", "NOT_PERFORMED", "UNKNOWN",
    "SafetyOutcome", "UNSAFE_OUTCOMES",
    "FailureProfile", "REQUIRED_PROFILES", "STRATEGY_COMPONENTS", "applies_to",
    "EnterpriseScenario", "DatasetIdentity", "load_frozen_dataset", "verify_identity",
    "DOMAIN_NAMES",
]
