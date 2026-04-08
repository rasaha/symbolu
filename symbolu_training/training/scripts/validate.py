"""
Training Data Validator
=======================

Validates training data quality and consistency.
Checks for duplicates, balance, and data integrity.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Set, Tuple
from collections import Counter

from symbolu_training.training.schemas import (
    QueryIntentPair,
    ParaphrasePair,
    TrainingDataset,
    IntentLabel,
)


@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    stats: Dict[str, Any]

    def __str__(self) -> str:
        status = "VALID" if self.is_valid else "INVALID"
        lines = [f"Validation Result: {status}"]

        if self.errors:
            lines.append(f"\nErrors ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  - {error}")

        if self.warnings:
            lines.append(f"\nWarnings ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        lines.append("\nStats:")
        for key, value in self.stats.items():
            lines.append(f"  {key}: {value}")

        return "\n".join(lines)


class DataValidator:
    """
    Validates training data quality.

    Checks:
    - No empty queries
    - No duplicate queries
    - Intent balance (within threshold)
    - Paraphrase pair consistency
    - Minimum dataset size
    """

    def __init__(
        self,
        min_intent_pairs: int = 100,
        min_paraphrase_pairs: int = 100,
        max_imbalance_ratio: float = 5.0,
        min_query_length: int = 3,
        max_query_length: int = 500,
    ):
        """
        Initialize validator with thresholds.

        Args:
            min_intent_pairs: Minimum number of intent pairs required
            min_paraphrase_pairs: Minimum number of paraphrase pairs required
            max_imbalance_ratio: Maximum ratio between largest and smallest class
            min_query_length: Minimum query character length
            max_query_length: Maximum query character length
        """
        self.min_intent_pairs = min_intent_pairs
        self.min_paraphrase_pairs = min_paraphrase_pairs
        self.max_imbalance_ratio = max_imbalance_ratio
        self.min_query_length = min_query_length
        self.max_query_length = max_query_length

    def validate_dataset(self, dataset: TrainingDataset) -> ValidationResult:
        """Validate a complete training dataset."""
        errors: List[str] = []
        warnings: List[str] = []

        # Validate intent pairs
        intent_result = self.validate_intent_pairs(dataset.intent_pairs)
        errors.extend(intent_result.errors)
        warnings.extend(intent_result.warnings)

        # Validate paraphrase pairs
        para_result = self.validate_paraphrase_pairs(dataset.paraphrase_pairs)
        errors.extend(para_result.errors)
        warnings.extend(para_result.warnings)

        # Combined stats
        stats = {
            **intent_result.stats,
            **para_result.stats,
            "dataset_name": dataset.name,
            "dataset_version": dataset.version,
        }

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            stats=stats,
        )

    def validate_intent_pairs(
        self, pairs: List[QueryIntentPair]
    ) -> ValidationResult:
        """Validate intent pairs."""
        errors: List[str] = []
        warnings: List[str] = []

        # Check minimum count
        if len(pairs) < self.min_intent_pairs:
            errors.append(
                f"Too few intent pairs: {len(pairs)} < {self.min_intent_pairs}"
            )

        # Check for empty queries
        empty_count = sum(1 for p in pairs if not p.query or not p.query.strip())
        if empty_count > 0:
            errors.append(f"Found {empty_count} empty queries")

        # Check query lengths
        short_count = sum(
            1 for p in pairs if len(p.query) < self.min_query_length
        )
        long_count = sum(
            1 for p in pairs if len(p.query) > self.max_query_length
        )
        if short_count > 0:
            warnings.append(f"Found {short_count} queries shorter than {self.min_query_length} chars")
        if long_count > 0:
            warnings.append(f"Found {long_count} queries longer than {self.max_query_length} chars")

        # Check for duplicates
        queries = [p.query.lower().strip() for p in pairs]
        duplicates = len(queries) - len(set(queries))
        if duplicates > 0:
            warnings.append(f"Found {duplicates} duplicate queries")

        # Check intent balance
        intent_counts = Counter(p.intent for p in pairs)
        if intent_counts:
            max_count = max(intent_counts.values())
            min_count = min(intent_counts.values())
            if min_count > 0:
                ratio = max_count / min_count
                if ratio > self.max_imbalance_ratio:
                    warnings.append(
                        f"Intent imbalance ratio {ratio:.1f}x exceeds threshold {self.max_imbalance_ratio}x"
                    )

        # Check confidence scores
        low_confidence = sum(1 for p in pairs if p.confidence < 0.5)
        if low_confidence > len(pairs) * 0.1:
            warnings.append(
                f"High proportion of low-confidence labels: {low_confidence}/{len(pairs)}"
            )

        stats = {
            "intent_pairs_total": len(pairs),
            "intent_distribution": {k.value: v for k, v in intent_counts.items()},
            "duplicate_queries": duplicates,
            "empty_queries": empty_count,
            "short_queries": short_count,
            "long_queries": long_count,
            "low_confidence_pairs": low_confidence,
        }

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            stats=stats,
        )

    def validate_paraphrase_pairs(
        self, pairs: List[ParaphrasePair]
    ) -> ValidationResult:
        """Validate paraphrase pairs."""
        errors: List[str] = []
        warnings: List[str] = []

        # Check minimum count
        if len(pairs) < self.min_paraphrase_pairs:
            errors.append(
                f"Too few paraphrase pairs: {len(pairs)} < {self.min_paraphrase_pairs}"
            )

        # Check for empty queries
        empty_count = sum(
            1 for p in pairs
            if not p.query_a or not p.query_a.strip()
            or not p.query_b or not p.query_b.strip()
        )
        if empty_count > 0:
            errors.append(f"Found {empty_count} pairs with empty queries")

        # Check for identical pairs
        identical_count = sum(
            1 for p in pairs
            if p.query_a.lower().strip() == p.query_b.lower().strip()
        )
        if identical_count > 0:
            warnings.append(f"Found {identical_count} pairs with identical queries")

        # Check similar/dissimilar balance
        similar_count = sum(1 for p in pairs if p.similar)
        dissimilar_count = len(pairs) - similar_count
        if similar_count > 0 and dissimilar_count > 0:
            ratio = max(similar_count, dissimilar_count) / min(similar_count, dissimilar_count)
            if ratio > 3.0:
                warnings.append(
                    f"Similar/dissimilar imbalance: {similar_count}/{dissimilar_count}"
                )

        # Check similarity scores consistency
        inconsistent_scores = sum(
            1 for p in pairs
            if (p.similar and p.similarity_score is not None and p.similarity_score < 0.5)
            or (not p.similar and p.similarity_score is not None and p.similarity_score > 0.5)
        )
        if inconsistent_scores > 0:
            warnings.append(
                f"Found {inconsistent_scores} pairs with inconsistent similarity scores"
            )

        stats = {
            "paraphrase_pairs_total": len(pairs),
            "similar_pairs": similar_count,
            "dissimilar_pairs": dissimilar_count,
            "identical_pairs": identical_count,
            "empty_pairs": empty_count,
            "inconsistent_scores": inconsistent_scores,
        }

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            stats=stats,
        )

    def check_overlap(
        self,
        train_pairs: List[QueryIntentPair],
        test_pairs: List[QueryIntentPair],
    ) -> Tuple[int, List[str]]:
        """
        Check for data leakage between train and test sets.

        Returns:
            Tuple of (overlap_count, overlapping_queries)
        """
        train_queries = {p.query.lower().strip() for p in train_pairs}
        test_queries = {p.query.lower().strip() for p in test_pairs}

        overlap = train_queries & test_queries
        return len(overlap), list(overlap)[:10]  # Return first 10


def validate_training_data(
    intent_pairs: List[QueryIntentPair],
    paraphrase_pairs: List[ParaphrasePair],
    name: str = "dataset",
    version: str = "1.0",
) -> ValidationResult:
    """
    Convenience function to validate training data.

    Args:
        intent_pairs: List of query-intent pairs
        paraphrase_pairs: List of paraphrase pairs
        name: Dataset name
        version: Dataset version

    Returns:
        ValidationResult
    """
    dataset = TrainingDataset(
        name=name,
        version=version,
        intent_pairs=intent_pairs,
        paraphrase_pairs=paraphrase_pairs,
    )

    validator = DataValidator()
    return validator.validate_dataset(dataset)
