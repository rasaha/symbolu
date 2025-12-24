"""Tests for training data validator."""

import pytest
from symbolu.training.schemas import (
    IntentLabel,
    QueryIntentPair,
    ParaphrasePair,
    TrainingDataset,
)
from symbolu.training.scripts.validate import (
    DataValidator,
    ValidationResult,
    validate_training_data,
)


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_valid_result(self):
        """Should create a valid result."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["Minor warning"],
            stats={"count": 100},
        )
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1

    def test_invalid_result(self):
        """Should create an invalid result."""
        result = ValidationResult(
            is_valid=False,
            errors=["Major error"],
            warnings=[],
            stats={},
        )
        assert result.is_valid is False
        assert len(result.errors) == 1

    def test_str_representation(self):
        """Should have readable string representation."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            stats={"total": 10},
        )
        output = str(result)
        assert "VALID" in output
        assert "total: 10" in output


class TestDataValidator:
    """Tests for DataValidator."""

    def _create_valid_intent_pairs(self, count: int = 150):
        """Create valid intent pairs for testing."""
        pairs = []
        intents = list(IntentLabel)
        for i in range(count):
            pairs.append(QueryIntentPair(
                query=f"Test query number {i} with some content",
                intent=intents[i % len(intents)],
                confidence=0.9,
            ))
        return pairs

    def _create_valid_paraphrase_pairs(self, count: int = 150):
        """Create valid paraphrase pairs for testing."""
        pairs = []
        for i in range(count):
            pairs.append(ParaphrasePair(
                query_a=f"Query A number {i}",
                query_b=f"Query B number {i}",
                similar=i % 2 == 0,
                similarity_score=0.9 if i % 2 == 0 else 0.1,
            ))
        return pairs

    def test_validate_valid_dataset(self):
        """Should pass validation for valid dataset."""
        validator = DataValidator(
            min_intent_pairs=100,
            min_paraphrase_pairs=100,
        )
        dataset = TrainingDataset(
            name="test",
            version="1.0",
            intent_pairs=self._create_valid_intent_pairs(150),
            paraphrase_pairs=self._create_valid_paraphrase_pairs(150),
        )
        result = validator.validate_dataset(dataset)
        assert result.is_valid is True

    def test_fail_too_few_intent_pairs(self):
        """Should fail with too few intent pairs."""
        validator = DataValidator(min_intent_pairs=100)
        result = validator.validate_intent_pairs([
            QueryIntentPair(query="Test", intent=IntentLabel.GENERAL)
        ])
        assert result.is_valid is False
        assert any("Too few" in e for e in result.errors)

    def test_fail_empty_queries(self):
        """Should fail with empty queries."""
        validator = DataValidator(min_intent_pairs=1)
        result = validator.validate_intent_pairs([
            QueryIntentPair(query="", intent=IntentLabel.GENERAL),
            QueryIntentPair(query="Valid", intent=IntentLabel.GENERAL),
        ])
        assert result.is_valid is False
        assert any("empty queries" in e for e in result.errors)

    def test_warn_duplicate_queries(self):
        """Should warn about duplicate queries."""
        validator = DataValidator(min_intent_pairs=2)
        result = validator.validate_intent_pairs([
            QueryIntentPair(query="Same query", intent=IntentLabel.GENERAL),
            QueryIntentPair(query="Same Query", intent=IntentLabel.REASONING),
        ])
        assert any("duplicate" in w for w in result.warnings)

    def test_warn_imbalanced_intents(self):
        """Should warn about imbalanced intent distribution."""
        validator = DataValidator(
            min_intent_pairs=100,
            max_imbalance_ratio=2.0,
        )
        # Create highly imbalanced data
        pairs = []
        pairs.extend([
            QueryIntentPair(query=f"General {i}", intent=IntentLabel.GENERAL)
            for i in range(90)
        ])
        pairs.extend([
            QueryIntentPair(query=f"Reasoning {i}", intent=IntentLabel.REASONING)
            for i in range(10)
        ])
        result = validator.validate_intent_pairs(pairs)
        assert any("imbalance" in w.lower() for w in result.warnings)

    def test_validate_paraphrase_pairs(self):
        """Should validate paraphrase pairs correctly."""
        validator = DataValidator(min_paraphrase_pairs=100)
        pairs = self._create_valid_paraphrase_pairs(150)
        result = validator.validate_paraphrase_pairs(pairs)
        assert result.is_valid is True

    def test_fail_empty_paraphrase_queries(self):
        """Should fail with empty paraphrase queries."""
        validator = DataValidator(min_paraphrase_pairs=1)
        result = validator.validate_paraphrase_pairs([
            ParaphrasePair(query_a="", query_b="Valid", similar=True),
        ])
        assert result.is_valid is False
        assert any("empty" in e for e in result.errors)

    def test_warn_identical_pairs(self):
        """Should warn about identical paraphrase pairs."""
        validator = DataValidator(min_paraphrase_pairs=1)
        result = validator.validate_paraphrase_pairs([
            ParaphrasePair(query_a="Same", query_b="same", similar=True),
            ParaphrasePair(query_a="Different A", query_b="Different B", similar=True),
        ])
        assert any("identical" in w for w in result.warnings)

    def test_warn_inconsistent_scores(self):
        """Should warn about inconsistent similarity scores."""
        validator = DataValidator(min_paraphrase_pairs=1)
        result = validator.validate_paraphrase_pairs([
            # Similar pair with low score - inconsistent
            ParaphrasePair(query_a="A", query_b="B", similar=True, similarity_score=0.2),
        ])
        assert any("inconsistent" in w for w in result.warnings)

    def test_check_overlap(self):
        """Should detect overlap between train and test sets."""
        validator = DataValidator()
        train = [
            QueryIntentPair(query="Shared query", intent=IntentLabel.GENERAL),
            QueryIntentPair(query="Train only", intent=IntentLabel.GENERAL),
        ]
        test = [
            QueryIntentPair(query="Shared query", intent=IntentLabel.GENERAL),
            QueryIntentPair(query="Test only", intent=IntentLabel.GENERAL),
        ]
        count, overlaps = validator.check_overlap(train, test)
        assert count == 1
        assert "shared query" in overlaps


class TestConvenienceFunction:
    """Tests for validate_training_data function."""

    def test_validate_training_data(self):
        """Should validate training data using convenience function."""
        intent_pairs = [
            QueryIntentPair(query=f"Query {i}", intent=IntentLabel.GENERAL)
            for i in range(150)
        ]
        para_pairs = [
            ParaphrasePair(query_a=f"A {i}", query_b=f"B {i}", similar=True)
            for i in range(150)
        ]
        result = validate_training_data(
            intent_pairs=intent_pairs,
            paraphrase_pairs=para_pairs,
            name="test",
            version="1.0",
        )
        assert isinstance(result, ValidationResult)
        assert result.stats["dataset_name"] == "test"
