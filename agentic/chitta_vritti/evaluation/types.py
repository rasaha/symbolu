"""Evaluation data types for Chitta-Vṛtti quantification.

Defines the core data structures used throughout the evaluation harness.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import json
from datetime import datetime


class OutcomeLabel(Enum):
    """Ground truth outcome labels."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"  # Partially correct
    UNKNOWN = "unknown"  # Not yet labeled


class ErrorType(Enum):
    """Classification of error types for analysis."""

    NONE = "none"
    SEMANTIC_MISMATCH = "semantic_mismatch"  # Meaning wrong
    PHONEMIC_ERROR = "phonemic_error"  # Sound/pronunciation wrong
    STRUCTURAL_ERROR = "structural_error"  # Grammar/syntax wrong
    TEMPORAL_ERROR = "temporal_error"  # Timing/sequence wrong
    HALLUCINATION = "hallucination"  # Fabricated content
    OMISSION = "omission"  # Missing information
    OTHER = "other"


@dataclass
class EvaluationSample:
    """Single evaluation data point linking Chitta-Vṛtti output to ground truth.

    Captures everything needed to analyze correlation between
    metacognitive signals and actual reasoning quality.
    """

    # Unique identifier
    sample_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Chitta-Vṛtti outputs (captured at inference time)
    coherence: float = 0.0
    fractures: dict[tuple[str, str], float] = field(default_factory=dict)
    vritti: dict[str, float] = field(default_factory=dict)
    score: float = 0.0
    dominant_vritti: str = ""
    fast_path_used: bool = False

    # Input context (for reproducibility)
    input_hash: str = ""  # Hash of input data
    input_metadata: dict = field(default_factory=dict)

    # Ground truth labels (added post-hoc or via automated verification)
    outcome: OutcomeLabel = OutcomeLabel.UNKNOWN
    error_type: ErrorType = ErrorType.NONE
    error_description: str = ""
    confidence_in_label: float = 1.0  # How confident is the labeler?

    # Optional: actual output for manual review
    output_summary: str = ""

    def __post_init__(self) -> None:
        """Validate sample data."""
        if not 0.0 <= self.coherence <= 1.0:
            raise ValueError(f"coherence must be in [0,1], got {self.coherence}")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0,1], got {self.score}")

    def is_labeled(self) -> bool:
        """Check if this sample has ground truth labels."""
        return self.outcome != OutcomeLabel.UNKNOWN

    def is_correct(self) -> bool:
        """Check if outcome is correct."""
        return self.outcome == OutcomeLabel.CORRECT

    def is_error(self) -> bool:
        """Check if outcome is incorrect."""
        return self.outcome == OutcomeLabel.INCORRECT

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "sample_id": self.sample_id,
            "timestamp": self.timestamp.isoformat(),
            "coherence": self.coherence,
            "fractures": {f"{k[0]},{k[1]}": v for k, v in self.fractures.items()},
            "vritti": self.vritti,
            "score": self.score,
            "dominant_vritti": self.dominant_vritti,
            "fast_path_used": self.fast_path_used,
            "input_hash": self.input_hash,
            "input_metadata": self.input_metadata,
            "outcome": self.outcome.value,
            "error_type": self.error_type.value,
            "error_description": self.error_description,
            "confidence_in_label": self.confidence_in_label,
            "output_summary": self.output_summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationSample":
        """Create from dictionary."""
        fractures = {}
        for k, v in data.get("fractures", {}).items():
            parts = k.split(",")
            if len(parts) == 2:
                fractures[(parts[0], parts[1])] = v

        return cls(
            sample_id=data["sample_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            coherence=data.get("coherence", 0.0),
            fractures=fractures,
            vritti=data.get("vritti", {}),
            score=data.get("score", 0.0),
            dominant_vritti=data.get("dominant_vritti", ""),
            fast_path_used=data.get("fast_path_used", False),
            input_hash=data.get("input_hash", ""),
            input_metadata=data.get("input_metadata", {}),
            outcome=OutcomeLabel(data.get("outcome", "unknown")),
            error_type=ErrorType(data.get("error_type", "none")),
            error_description=data.get("error_description", ""),
            confidence_in_label=data.get("confidence_in_label", 1.0),
            output_summary=data.get("output_summary", ""),
        )


@dataclass
class EvaluationBatch:
    """Collection of evaluation samples for batch analysis."""

    batch_id: str
    samples: list[EvaluationSample] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    description: str = ""

    def add_sample(self, sample: EvaluationSample) -> None:
        """Add a sample to the batch."""
        self.samples.append(sample)

    def labeled_samples(self) -> list[EvaluationSample]:
        """Get only labeled samples."""
        return [s for s in self.samples if s.is_labeled()]

    def correct_samples(self) -> list[EvaluationSample]:
        """Get only correct samples."""
        return [s for s in self.samples if s.is_correct()]

    def error_samples(self) -> list[EvaluationSample]:
        """Get only error samples."""
        return [s for s in self.samples if s.is_error()]

    def __len__(self) -> int:
        return len(self.samples)

    def save(self, filepath: str) -> None:
        """Save batch to JSON file."""
        data = {
            "batch_id": self.batch_id,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "samples": [s.to_dict() for s in self.samples],
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "EvaluationBatch":
        """Load batch from JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)

        batch = cls(
            batch_id=data["batch_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            description=data.get("description", ""),
        )
        batch.samples = [EvaluationSample.from_dict(s) for s in data["samples"]]
        return batch


@dataclass
class CalibrationResult:
    """Results from calibration analysis.

    Measures: P(correct | score > threshold) for various thresholds.
    A well-calibrated system has accuracy matching the score threshold.
    """

    # Threshold → accuracy mapping
    threshold_accuracy: dict[float, float] = field(default_factory=dict)

    # Summary statistics
    expected_calibration_error: float = 0.0  # ECE
    max_calibration_error: float = 0.0  # MCE
    brier_score: float = 0.0  # Mean squared error of predictions

    # Sample counts per bin
    bin_counts: dict[float, int] = field(default_factory=dict)

    def is_well_calibrated(self, tolerance: float = 0.1) -> bool:
        """Check if ECE is within tolerance."""
        return self.expected_calibration_error <= tolerance


@dataclass
class DetectionResult:
    """Results from error detection analysis.

    Measures how well vṛtti signals predict errors.
    """

    # Viparyaya as error detector
    viparyaya_threshold: float = 0.3
    true_positive_rate: float = 0.0  # P(high_viparyaya | error)
    false_positive_rate: float = 0.0  # P(high_viparyaya | correct)
    precision: float = 0.0  # P(error | high_viparyaya)
    recall: float = 0.0  # Same as TPR
    f1_score: float = 0.0

    # ROC analysis
    auc_roc: float = 0.0  # Area under ROC curve

    # Confusion matrix
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    def specificity(self) -> float:
        """True negative rate."""
        return 1.0 - self.false_positive_rate


@dataclass
class CorrelationResult:
    """Results from correlation analysis.

    Measures linear and rank correlations between signals and outcomes.
    """

    # Pearson correlations (linear)
    coherence_vs_correct: float = 0.0
    score_vs_correct: float = 0.0
    viparyaya_vs_error: float = 0.0

    # Spearman correlations (rank-based, more robust)
    coherence_vs_correct_spearman: float = 0.0
    score_vs_correct_spearman: float = 0.0
    viparyaya_vs_error_spearman: float = 0.0

    # P-values for significance
    coherence_pvalue: float = 1.0
    score_pvalue: float = 1.0
    viparyaya_pvalue: float = 1.0

    # Per-vṛtti correlations with error
    vritti_correlations: dict[str, float] = field(default_factory=dict)

    def is_significant(self, alpha: float = 0.05) -> bool:
        """Check if key correlations are statistically significant."""
        return (
            self.coherence_pvalue < alpha
            or self.score_pvalue < alpha
            or self.viparyaya_pvalue < alpha
        )


@dataclass
class EvaluationReport:
    """Complete evaluation report with all metrics."""

    # Identification
    report_id: str
    generated_at: datetime = field(default_factory=datetime.now)
    batch_id: str = ""

    # Sample statistics
    total_samples: int = 0
    labeled_samples: int = 0
    correct_count: int = 0
    error_count: int = 0
    baseline_accuracy: float = 0.0  # Raw accuracy without CV

    # Component results
    calibration: CalibrationResult = field(default_factory=CalibrationResult)
    detection: DetectionResult = field(default_factory=DetectionResult)
    correlation: CorrelationResult = field(default_factory=CorrelationResult)

    # Error type breakdown
    error_distribution: dict[str, int] = field(default_factory=dict)

    # Vṛtti distribution in errors vs correct
    vritti_in_errors: dict[str, float] = field(default_factory=dict)
    vritti_in_correct: dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"=== Chitta-Vṛtti Evaluation Report ===",
            f"Report ID: {self.report_id}",
            f"Generated: {self.generated_at.isoformat()}",
            f"",
            f"--- Sample Statistics ---",
            f"Total samples: {self.total_samples}",
            f"Labeled samples: {self.labeled_samples}",
            f"Correct: {self.correct_count} ({self.correct_count/max(1,self.labeled_samples)*100:.1f}%)",
            f"Errors: {self.error_count} ({self.error_count/max(1,self.labeled_samples)*100:.1f}%)",
            f"",
            f"--- Calibration ---",
            f"Expected Calibration Error: {self.calibration.expected_calibration_error:.3f}",
            f"Max Calibration Error: {self.calibration.max_calibration_error:.3f}",
            f"Brier Score: {self.calibration.brier_score:.3f}",
            f"Well-calibrated: {'Yes' if self.calibration.is_well_calibrated() else 'No'}",
            f"",
            f"--- Error Detection (Viparyaya) ---",
            f"Threshold: {self.detection.viparyaya_threshold}",
            f"True Positive Rate (Recall): {self.detection.true_positive_rate:.3f}",
            f"False Positive Rate: {self.detection.false_positive_rate:.3f}",
            f"Precision: {self.detection.precision:.3f}",
            f"F1 Score: {self.detection.f1_score:.3f}",
            f"AUC-ROC: {self.detection.auc_roc:.3f}",
            f"",
            f"--- Correlations ---",
            f"Coherence vs Correct: {self.correlation.coherence_vs_correct:.3f} (p={self.correlation.coherence_pvalue:.4f})",
            f"Score vs Correct: {self.correlation.score_vs_correct:.3f} (p={self.correlation.score_pvalue:.4f})",
            f"Viparyaya vs Error: {self.correlation.viparyaya_vs_error:.3f} (p={self.correlation.viparyaya_pvalue:.4f})",
            f"Significant: {'Yes' if self.correlation.is_significant() else 'No'}",
        ]

        if self.vritti_in_errors:
            lines.append("")
            lines.append("--- Vṛtti Distribution ---")
            lines.append("Mode        | Errors | Correct | Delta")
            lines.append("------------|--------|---------|------")
            for mode in ["pramana", "viparyaya", "vikalpa", "smrti", "nidra"]:
                err = self.vritti_in_errors.get(mode, 0)
                cor = self.vritti_in_correct.get(mode, 0)
                delta = err - cor
                sign = "+" if delta > 0 else ""
                lines.append(f"{mode:11} | {err:.3f}  | {cor:.3f}   | {sign}{delta:.3f}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "batch_id": self.batch_id,
            "total_samples": self.total_samples,
            "labeled_samples": self.labeled_samples,
            "correct_count": self.correct_count,
            "error_count": self.error_count,
            "baseline_accuracy": self.baseline_accuracy,
            "calibration": {
                "threshold_accuracy": self.calibration.threshold_accuracy,
                "expected_calibration_error": self.calibration.expected_calibration_error,
                "max_calibration_error": self.calibration.max_calibration_error,
                "brier_score": self.calibration.brier_score,
            },
            "detection": {
                "viparyaya_threshold": self.detection.viparyaya_threshold,
                "true_positive_rate": self.detection.true_positive_rate,
                "false_positive_rate": self.detection.false_positive_rate,
                "precision": self.detection.precision,
                "recall": self.detection.recall,
                "f1_score": self.detection.f1_score,
                "auc_roc": self.detection.auc_roc,
            },
            "correlation": {
                "coherence_vs_correct": self.correlation.coherence_vs_correct,
                "score_vs_correct": self.correlation.score_vs_correct,
                "viparyaya_vs_error": self.correlation.viparyaya_vs_error,
            },
            "vritti_in_errors": self.vritti_in_errors,
            "vritti_in_correct": self.vritti_in_correct,
        }
