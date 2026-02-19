"""
Resonant Model - Binding Benchmark Suite
==========================================

Synthetic benchmark for evaluating role-filler binding under interference.

Tests whether an interference-based resonance head outperforms a standard
softmax head at maintaining correct role assignments under:
  - Distractor names
  - Long separation distance
  - Nested clauses
  - Multiple agents/patients

Modules:
  dataset        - Synthetic role-filler binding dataset generator
  heads          - Model A (softmax baseline) and Model B (resonance interference)
  evaluator      - Evaluation harness with accuracy and failure-type tracking
  statistics     - Significance testing and distance/distractor analysis
  pass_criteria  - Three-tier behavioral pass gate (minimal/strong/breakthrough)
  diagnostics    - Interference cross-term validation (6-step analysis)
"""

from resonant_model.dataset import BindingDataset, BindingExample
from resonant_model.heads import SoftmaxBindingHead, ResonanceBindingHead
from resonant_model.evaluator import BindingEvaluator, EvaluationResult
from resonant_model.statistics import BindingStatistics, ComparisonReport
from resonant_model.pass_criteria import PassCriteria, PassResult, PassTier
from resonant_model.diagnostics import ValidationReport, run_validation

__all__ = [
    "BindingDataset",
    "BindingExample",
    "SoftmaxBindingHead",
    "ResonanceBindingHead",
    "BindingEvaluator",
    "EvaluationResult",
    "BindingStatistics",
    "ComparisonReport",
    "PassCriteria",
    "PassResult",
    "PassTier",
    "ValidationReport",
    "run_validation",
]
