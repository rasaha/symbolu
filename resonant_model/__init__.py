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
  dataset     - Synthetic role-filler binding dataset generator
  heads       - Model A (softmax baseline) and Model B (resonance interference)
  evaluator   - Evaluation harness with accuracy and failure-type tracking
  statistics  - Significance testing and distance/distractor analysis
"""

from resonant_model.dataset import BindingDataset, BindingExample
from resonant_model.heads import SoftmaxBindingHead, ResonanceBindingHead
from resonant_model.evaluator import BindingEvaluator, EvaluationResult
from resonant_model.statistics import BindingStatistics, ComparisonReport

__all__ = [
    "BindingDataset",
    "BindingExample",
    "SoftmaxBindingHead",
    "ResonanceBindingHead",
    "BindingEvaluator",
    "EvaluationResult",
    "BindingStatistics",
    "ComparisonReport",
]
