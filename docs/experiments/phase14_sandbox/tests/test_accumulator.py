"""
Tests for Phase-14 Accumulator
==============================

Test Categories:
    1. Recording - observation tracking
    2. Stability - status transitions
    3. Confidence - vote-based confidence
    4. Override - manual corrections
    5. Ledger - operation logging
"""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "phase13_sandbox"))

from k1_schema import OntologicalLayer

from accumulator import (
    Accumulator,
    LedgeredAccumulator,
    WordStats,
    StabilityStatus,
    AccumulatorSnapshot,
    create_accumulator,
    create_ledgered_accumulator,
    MIN_OBSERVATIONS_UNSTABLE,
    MIN_OBSERVATIONS_STABLE,
    CONFIDENCE_STABLE_THRESHOLD,
    CONFIDENCE_CONFLICTED_THRESHOLD,
)


# =============================================================================
# Test: Recording Observations
# =============================================================================

class TestRecording:
    """Tests for observation recording."""

    def test_record_creates_stats(self):
        """Recording creates word stats."""
        acc = create_accumulator()
        stats = acc.record("think", OntologicalLayer.O1_THINKING)

        assert stats.word == "think"
        assert stats.observations == 1

    def test_record_increments_count(self):
        """Recording increments observation count."""
        acc = create_accumulator()

        acc.record("think", OntologicalLayer.O1_THINKING)
        acc.record("think", OntologicalLayer.O1_THINKING)
        acc.record("think", OntologicalLayer.O1_THINKING)

        stats = acc.get_stats("think")
        assert stats.observations == 3

    def test_record_tracks_layer_votes(self):
        """Recording tracks votes per layer."""
        acc = create_accumulator()

        acc.record("think", OntologicalLayer.O1_THINKING)
        acc.record("think", OntologicalLayer.O1_THINKING)
        acc.record("think", OntologicalLayer.O3_ACTING)

        stats = acc.get_stats("think")
        assert stats.layer_votes["O1_THINKING"] == 2
        assert stats.layer_votes["O3_ACTING"] == 1

    def test_record_tracks_source_docs(self):
        """Recording tracks source documents."""
        acc = create_accumulator()

        acc.record("think", OntologicalLayer.O1_THINKING, "doc1")
        acc.record("think", OntologicalLayer.O1_THINKING, "doc2")
        acc.record("think", OntologicalLayer.O1_THINKING, "doc1")  # Duplicate

        stats = acc.get_stats("think")
        assert len(stats.source_documents) == 2

    def test_record_batch(self):
        """Batch recording works."""
        acc = create_accumulator()

        mappings = (
            ("think", OntologicalLayer.O1_THINKING),
            ("run", OntologicalLayer.O3_ACTING),
            ("create", OntologicalLayer.O2_FORMING),
        )
        results = acc.record_batch(mappings, "batch_doc")

        assert len(results) == 3
        assert acc.word_count == 3


# =============================================================================
# Test: Stability Status
# =============================================================================

class TestStability:
    """Tests for stability status transitions."""

    def test_unstable_with_few_observations(self):
        """Words with few observations are UNSTABLE."""
        acc = create_accumulator()

        for _ in range(MIN_OBSERVATIONS_UNSTABLE - 1):
            acc.record("think", OntologicalLayer.O1_THINKING)

        stats = acc.get_stats("think")
        assert stats.get_stability_status() == StabilityStatus.UNSTABLE

    def test_emerging_with_moderate_observations(self):
        """Words with moderate observations are EMERGING."""
        acc = create_accumulator()

        # Add observations but with varying layers
        for i in range(MIN_OBSERVATIONS_UNSTABLE + 5):
            layer = OntologicalLayer.O1_THINKING if i % 2 == 0 else OntologicalLayer.O3_ACTING
            acc.record("think", layer)

        stats = acc.get_stats("think")
        # Should be emerging (not enough observations for stable, confidence < 0.7)
        status = stats.get_stability_status()
        assert status in (StabilityStatus.EMERGING, StabilityStatus.UNSTABLE)

    def test_stable_with_many_consistent_observations(self):
        """Words with many consistent observations are STABLE."""
        acc = create_accumulator()

        # Add 50+ observations with high consistency
        for _ in range(MIN_OBSERVATIONS_STABLE + 10):
            acc.record("think", OntologicalLayer.O1_THINKING)

        stats = acc.get_stats("think")
        assert stats.get_stability_status() == StabilityStatus.STABLE
        assert stats.get_confidence() >= CONFIDENCE_STABLE_THRESHOLD

    def test_conflicted_with_many_inconsistent_observations(self):
        """Words with conflicting mappings are CONFLICTED."""
        acc = create_accumulator()

        # Add 60+ observations split three ways (confidence < 0.5)
        for _ in range(20):
            acc.record("think", OntologicalLayer.O1_THINKING)
        for _ in range(20):
            acc.record("think", OntologicalLayer.O3_ACTING)
        for _ in range(20):
            acc.record("think", OntologicalLayer.O2_FORMING)

        stats = acc.get_stats("think")
        # With 3-way split, max is 20/60 = 0.33, clearly conflicted
        assert stats.get_confidence() < CONFIDENCE_CONFLICTED_THRESHOLD
        assert stats.get_stability_status() == StabilityStatus.CONFLICTED


# =============================================================================
# Test: Confidence
# =============================================================================

class TestConfidence:
    """Tests for confidence calculation."""

    def test_confidence_100_percent(self):
        """All same votes gives 1.0 confidence."""
        acc = create_accumulator()

        for _ in range(10):
            acc.record("think", OntologicalLayer.O1_THINKING)

        stats = acc.get_stats("think")
        assert stats.get_confidence() == 1.0

    def test_confidence_50_percent(self):
        """Half-split votes gives 0.5 confidence."""
        acc = create_accumulator()

        for _ in range(10):
            acc.record("think", OntologicalLayer.O1_THINKING)
        for _ in range(10):
            acc.record("think", OntologicalLayer.O3_ACTING)

        stats = acc.get_stats("think")
        assert stats.get_confidence() == 0.5

    def test_confidence_zero_no_observations(self):
        """No observations gives 0.0 confidence."""
        stats = WordStats(word="unknown")
        assert stats.get_confidence() == 0.0


# =============================================================================
# Test: Dominant Layer
# =============================================================================

class TestDominantLayer:
    """Tests for dominant layer determination."""

    def test_dominant_layer_single(self):
        """Single layer is dominant."""
        acc = create_accumulator()

        for _ in range(10):
            acc.record("think", OntologicalLayer.O1_THINKING)

        stats = acc.get_stats("think")
        assert stats.get_dominant_layer() == OntologicalLayer.O1_THINKING

    def test_dominant_layer_majority(self):
        """Majority layer is dominant."""
        acc = create_accumulator()

        for _ in range(15):
            acc.record("think", OntologicalLayer.O1_THINKING)
        for _ in range(5):
            acc.record("think", OntologicalLayer.O3_ACTING)

        stats = acc.get_stats("think")
        assert stats.get_dominant_layer() == OntologicalLayer.O1_THINKING

    def test_dominant_layer_none_empty(self):
        """No dominant layer for empty stats."""
        stats = WordStats(word="unknown")
        assert stats.get_dominant_layer() is None


# =============================================================================
# Test: Override Mapping
# =============================================================================

class TestOverride:
    """Tests for manual override functionality."""

    def test_override_adds_votes(self):
        """Override adds votes to specified layer."""
        acc = create_accumulator()

        # Initial observations
        for _ in range(10):
            acc.record("ambiguous", OntologicalLayer.O1_THINKING)
        for _ in range(8):
            acc.record("ambiguous", OntologicalLayer.O3_ACTING)

        # Override to ACTING
        acc.override_mapping("ambiguous", OntologicalLayer.O3_ACTING, 100)

        stats = acc.get_stats("ambiguous")
        assert stats.get_dominant_layer() == OntologicalLayer.O3_ACTING

    def test_override_makes_stable(self):
        """Override with enough votes makes word stable."""
        acc = create_accumulator()

        # Start with unstable
        acc.record("new_word", OntologicalLayer.O1_THINKING)

        # Override with many votes
        acc.override_mapping("new_word", OntologicalLayer.O3_ACTING, 100)

        stats = acc.get_stats("new_word")
        assert stats.get_stability_status() == StabilityStatus.STABLE


# =============================================================================
# Test: Retrieval Functions
# =============================================================================

class TestRetrieval:
    """Tests for word retrieval functions."""

    def test_get_all_words(self):
        """get_all_words returns all tracked words."""
        acc = create_accumulator()

        acc.record("think", OntologicalLayer.O1_THINKING)
        acc.record("run", OntologicalLayer.O3_ACTING)
        acc.record("create", OntologicalLayer.O2_FORMING)

        words = acc.get_all_words()
        assert len(words) == 3
        assert "think" in words
        assert "run" in words
        assert "create" in words

    def test_get_words_by_status(self):
        """get_words_by_status filters correctly."""
        acc = create_accumulator()

        # Add stable word
        for _ in range(60):
            acc.record("stable_word", OntologicalLayer.O1_THINKING)

        # Add unstable word
        acc.record("unstable_word", OntologicalLayer.O3_ACTING)

        stable = acc.get_words_by_status(StabilityStatus.STABLE)
        unstable = acc.get_words_by_status(StabilityStatus.UNSTABLE)

        assert "stable_word" in stable
        assert "unstable_word" in unstable

    def test_get_stable_mappings(self):
        """get_stable_mappings returns only stable."""
        acc = create_accumulator()

        for _ in range(60):
            acc.record("stable", OntologicalLayer.O1_THINKING)

        acc.record("unstable", OntologicalLayer.O3_ACTING)

        mappings = acc.get_stable_mappings()
        assert "stable" in mappings
        assert "unstable" not in mappings

    def test_get_layer_vocabulary(self):
        """get_layer_vocabulary returns words for layer."""
        acc = create_accumulator()

        for _ in range(10):
            acc.record("think1", OntologicalLayer.O1_THINKING)
            acc.record("think2", OntologicalLayer.O1_THINKING)
            acc.record("act1", OntologicalLayer.O3_ACTING)

        vocab = acc.get_layer_vocabulary(OntologicalLayer.O1_THINKING)
        assert "think1" in vocab
        assert "think2" in vocab
        assert "act1" not in vocab


# =============================================================================
# Test: Snapshot
# =============================================================================

class TestSnapshot:
    """Tests for accumulator snapshots."""

    def test_snapshot_counts(self):
        """Snapshot has correct counts."""
        acc = create_accumulator()

        # Add stable word
        for _ in range(60):
            acc.record("stable", OntologicalLayer.O1_THINKING)

        # Add unstable word
        acc.record("unstable", OntologicalLayer.O3_ACTING)

        snapshot = acc.snapshot()
        assert snapshot.total_words == 2
        assert snapshot.total_observations == 61
        assert snapshot.stable_count == 1
        assert snapshot.unstable_count == 1

    def test_snapshot_has_hash(self):
        """Snapshot has deterministic hash."""
        acc = create_accumulator()
        acc.record("test", OntologicalLayer.O1_THINKING)

        snapshot = acc.snapshot()
        assert len(snapshot.snapshot_hash) == 16


# =============================================================================
# Test: Ledgered Accumulator
# =============================================================================

class TestLedgeredAccumulator:
    """Tests for ledger recording."""

    def test_ledger_records_operations(self):
        """Operations are recorded in ledger."""
        acc = create_ledgered_accumulator()

        acc.record("think", OntologicalLayer.O1_THINKING)
        acc.record("think", OntologicalLayer.O1_THINKING)

        ledger = acc.get_ledger()
        assert len(ledger) == 2
        assert ledger[0].operation == "RECORD"

    def test_ledger_entry_has_fields(self):
        """Ledger entries have all required fields."""
        acc = create_ledgered_accumulator()

        acc.record("think", OntologicalLayer.O1_THINKING, "doc1")

        entry = acc.get_ledger()[0]
        assert entry.word == "think"
        assert entry.layer == "O1_THINKING"
        assert entry.source_doc == "doc1"
        assert entry.before_observations == 0
        assert entry.after_observations == 1

    def test_override_logged(self):
        """Override operations are logged."""
        acc = create_ledgered_accumulator()

        acc.override_mapping("test", OntologicalLayer.O3_ACTING, 100)

        ledger = acc.get_ledger()
        assert len(ledger) == 1
        assert ledger[0].operation == "OVERRIDE"


# =============================================================================
# Test: Metrics
# =============================================================================

class TestMetrics:
    """Tests for accumulator metrics."""

    def test_metrics_computed(self):
        """Metrics are computed correctly."""
        acc = create_accumulator()

        for _ in range(60):
            acc.record("stable", OntologicalLayer.O1_THINKING)
        acc.record("unstable", OntologicalLayer.O3_ACTING)

        metrics = acc.get_metrics()

        assert metrics["total_words"] == 2
        assert metrics["total_observations"] == 61
        assert metrics["stable_rate"] == 0.5  # 1 of 2 words stable


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
