"""Benchmark evaluators — expectation layer, oracle, fairness, invariants, paired."""
from __future__ import annotations

from .expectation import ScenarioExpectation, derive
from .oracle import Judgement, classify, judge
from .fairness import FairnessCheck, check_fairness, fairness_passed
from .invariants import InvariantResult, check_invariants, invariants_passed
from .paired import paired_analysis

__all__ = [
    "derive", "ScenarioExpectation", "judge", "classify", "Judgement",
    "check_fairness", "FairnessCheck", "fairness_passed",
    "check_invariants", "InvariantResult", "invariants_passed", "paired_analysis",
]
