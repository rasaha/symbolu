"""Chitta-Vṛtti Evaluation Harness.

Provides infrastructure to quantify the impact of Chitta-Vṛtti
metacognition on reasoning quality.

Key components:
- EvaluationSample: Single evaluation data point
- GroundTruthCollector: Collect labeled samples during inference
- MetricsComputer: Compute calibration, detection, correlation metrics
- EvaluationHarness: Run full evaluation pipeline
- EvaluationReport: Generate human-readable reports
"""

from agentic.chitta_vritti.evaluation.types import (
    EvaluationSample,
    EvaluationBatch,
    CalibrationResult,
    DetectionResult,
    CorrelationResult,
    EvaluationReport,
)
from agentic.chitta_vritti.evaluation.collector import GroundTruthCollector
from agentic.chitta_vritti.evaluation.metrics import MetricsComputer
from agentic.chitta_vritti.evaluation.harness import EvaluationHarness

__all__ = [
    # Types
    "EvaluationSample",
    "EvaluationBatch",
    "CalibrationResult",
    "DetectionResult",
    "CorrelationResult",
    "EvaluationReport",
    # Components
    "GroundTruthCollector",
    "MetricsComputer",
    "EvaluationHarness",
]
