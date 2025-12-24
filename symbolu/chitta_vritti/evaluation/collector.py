"""Ground truth collection for Chitta-Vṛtti evaluation.

Provides infrastructure to capture Chitta-Vṛtti outputs during inference
and link them to ground truth labels for later analysis.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Optional, Any, Callable

from symbolu.chitta_vritti.types import ChittaVrittiResult, ChittaVrittiInputs
from symbolu.chitta_vritti.evaluation.types import (
    EvaluationSample,
    EvaluationBatch,
    OutcomeLabel,
    ErrorType,
)


class GroundTruthCollector:
    """Collects Chitta-Vṛtti outputs and links to ground truth.

    Usage:
        collector = GroundTruthCollector(batch_id="experiment_001")

        # During inference
        result = engine.compute(inputs)
        sample_id = collector.record(inputs, result)

        # After verification (manual or automated)
        collector.label(sample_id, OutcomeLabel.CORRECT)

        # Save for analysis
        collector.save("results.json")
    """

    def __init__(
        self,
        batch_id: Optional[str] = None,
        description: str = "",
        auto_hash: bool = True,
    ) -> None:
        """Initialize collector.

        Args:
            batch_id: Unique identifier for this collection batch
            description: Human-readable description of the batch
            auto_hash: Whether to automatically hash inputs for tracking
        """
        self._batch = EvaluationBatch(
            batch_id=batch_id or f"batch_{uuid.uuid4().hex[:8]}",
            description=description,
        )
        self._auto_hash = auto_hash
        self._sample_index: dict[str, EvaluationSample] = {}

    def record(
        self,
        inputs: ChittaVrittiInputs,
        result: ChittaVrittiResult,
        metadata: Optional[dict] = None,
        output_summary: str = "",
    ) -> str:
        """Record a Chitta-Vṛtti computation for later evaluation.

        Args:
            inputs: The inputs used for computation
            result: The Chitta-Vṛtti result
            metadata: Optional metadata about the input context
            output_summary: Optional summary of the system output

        Returns:
            sample_id: Unique identifier for this sample (use for labeling)
        """
        sample_id = f"sample_{uuid.uuid4().hex[:12]}"

        # Hash inputs for reproducibility tracking
        input_hash = ""
        if self._auto_hash:
            input_hash = self._hash_inputs(inputs)

        sample = EvaluationSample(
            sample_id=sample_id,
            timestamp=datetime.now(),
            coherence=result.coherence,
            fractures=dict(result.fractures),
            vritti=dict(result.vritti),
            score=result.score,
            dominant_vritti=result.dominant_vritti,
            fast_path_used=result.fast_path_used,
            input_hash=input_hash,
            input_metadata=metadata or {},
            output_summary=output_summary,
        )

        self._batch.add_sample(sample)
        self._sample_index[sample_id] = sample

        return sample_id

    def label(
        self,
        sample_id: str,
        outcome: OutcomeLabel,
        error_type: ErrorType = ErrorType.NONE,
        error_description: str = "",
        confidence: float = 1.0,
    ) -> bool:
        """Add ground truth label to a recorded sample.

        Args:
            sample_id: The sample identifier returned by record()
            outcome: The ground truth outcome
            error_type: Type of error if outcome is INCORRECT
            error_description: Human-readable error description
            confidence: Confidence in the label (0-1)

        Returns:
            True if sample was found and labeled
        """
        if sample_id not in self._sample_index:
            return False

        sample = self._sample_index[sample_id]

        # Create new sample with updated labels (samples are frozen)
        updated = EvaluationSample(
            sample_id=sample.sample_id,
            timestamp=sample.timestamp,
            coherence=sample.coherence,
            fractures=sample.fractures,
            vritti=sample.vritti,
            score=sample.score,
            dominant_vritti=sample.dominant_vritti,
            fast_path_used=sample.fast_path_used,
            input_hash=sample.input_hash,
            input_metadata=sample.input_metadata,
            outcome=outcome,
            error_type=error_type,
            error_description=error_description,
            confidence_in_label=confidence,
            output_summary=sample.output_summary,
        )

        # Replace in batch and index
        for i, s in enumerate(self._batch.samples):
            if s.sample_id == sample_id:
                self._batch.samples[i] = updated
                break
        self._sample_index[sample_id] = updated

        return True

    def label_batch(
        self,
        labeler: Callable[[EvaluationSample], tuple[OutcomeLabel, ErrorType, str]],
    ) -> int:
        """Apply a labeling function to all unlabeled samples.

        Args:
            labeler: Function that takes a sample and returns (outcome, error_type, description)

        Returns:
            Number of samples labeled
        """
        labeled_count = 0
        for sample in self._batch.samples:
            if not sample.is_labeled():
                outcome, error_type, description = labeler(sample)
                if self.label(sample.sample_id, outcome, error_type, description):
                    labeled_count += 1
        return labeled_count

    def get_batch(self) -> EvaluationBatch:
        """Get the current evaluation batch."""
        return self._batch

    def get_sample(self, sample_id: str) -> Optional[EvaluationSample]:
        """Get a specific sample by ID."""
        return self._sample_index.get(sample_id)

    def stats(self) -> dict[str, Any]:
        """Get collection statistics."""
        labeled = self._batch.labeled_samples()
        correct = self._batch.correct_samples()
        errors = self._batch.error_samples()

        return {
            "batch_id": self._batch.batch_id,
            "total_samples": len(self._batch),
            "labeled_samples": len(labeled),
            "unlabeled_samples": len(self._batch) - len(labeled),
            "correct_count": len(correct),
            "error_count": len(errors),
            "accuracy": len(correct) / max(1, len(labeled)),
            "label_coverage": len(labeled) / max(1, len(self._batch)),
        }

    def save(self, filepath: str) -> None:
        """Save the batch to a JSON file."""
        self._batch.save(filepath)

    @classmethod
    def load(cls, filepath: str) -> "GroundTruthCollector":
        """Load a collector from a saved batch file."""
        batch = EvaluationBatch.load(filepath)
        collector = cls(batch_id=batch.batch_id, description=batch.description)
        collector._batch = batch
        collector._sample_index = {s.sample_id: s for s in batch.samples}
        return collector

    def _hash_inputs(self, inputs: ChittaVrittiInputs) -> str:
        """Create a hash of inputs for tracking."""
        components = []

        # Hash each representation if present
        if inputs.phonemic_rep is not None:
            components.append(f"p:{inputs.phonemic_rep.tobytes().hex()[:16]}")
        if inputs.semantic_rep is not None:
            components.append(f"s:{inputs.semantic_rep.tobytes().hex()[:16]}")
        if inputs.structural_rep is not None:
            components.append(f"t:{inputs.structural_rep.tobytes().hex()[:16]}")
        if inputs.temporal_rep is not None:
            components.append(f"m:{inputs.temporal_rep.tobytes().hex()[:16]}")

        # Add signals
        components.append(f"e:{inputs.entropy:.4f}")
        components.append(f"m:{inputs.motion:.4f}")
        components.append(f"c:{inputs.confidence:.4f}")

        combined = "|".join(components)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def clear(self) -> None:
        """Clear all collected samples."""
        self._batch = EvaluationBatch(
            batch_id=self._batch.batch_id,
            description=self._batch.description,
        )
        self._sample_index.clear()


class AutoLabeler:
    """Automated labeling strategies for ground truth collection.

    Provides common automated labeling approaches when ground truth
    can be verified programmatically.
    """

    @staticmethod
    def from_verification_function(
        verify_fn: Callable[[str, dict], bool],
    ) -> Callable[[EvaluationSample], tuple[OutcomeLabel, ErrorType, str]]:
        """Create labeler from a verification function.

        Args:
            verify_fn: Function(output_summary, metadata) -> is_correct

        Returns:
            Labeler function for use with collector.label_batch()
        """

        def labeler(
            sample: EvaluationSample,
        ) -> tuple[OutcomeLabel, ErrorType, str]:
            try:
                is_correct = verify_fn(sample.output_summary, sample.input_metadata)
                if is_correct:
                    return OutcomeLabel.CORRECT, ErrorType.NONE, ""
                else:
                    return OutcomeLabel.INCORRECT, ErrorType.OTHER, "Verification failed"
            except Exception as e:
                return OutcomeLabel.UNKNOWN, ErrorType.NONE, f"Verification error: {e}"

        return labeler

    @staticmethod
    def from_score_threshold(
        threshold: float = 0.7,
    ) -> Callable[[EvaluationSample], tuple[OutcomeLabel, ErrorType, str]]:
        """Create labeler that uses CV score as proxy for correctness.

        This is a WEAK labeler - only use for initial exploration,
        not for final evaluation (would be circular reasoning).

        Args:
            threshold: Score threshold for "correct" classification

        Returns:
            Labeler function
        """

        def labeler(
            sample: EvaluationSample,
        ) -> tuple[OutcomeLabel, ErrorType, str]:
            if sample.score >= threshold:
                return OutcomeLabel.CORRECT, ErrorType.NONE, ""
            else:
                return (
                    OutcomeLabel.INCORRECT,
                    ErrorType.OTHER,
                    f"Score {sample.score:.3f} below threshold {threshold}",
                )

        return labeler
