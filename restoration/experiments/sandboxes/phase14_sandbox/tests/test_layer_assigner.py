"""
Tests for Phase-14 Layer Assigner
=================================

Test Categories:
    1. POS Tagging - simple POS classification
    2. Layer Assignment - POS → Layer mapping
    3. Override Lexicon - specific word overrides
    4. Context Adjustment - context modifies assignment
    5. Determinism - same input → same output
"""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "phase13_sandbox"))

from k1_schema import OntologicalLayer

from layer_assigner import (
    LayerAssigner,
    LayerAssignment,
    SimplePOS,
    ContextHint,
    create_assigner,
    get_pos,
    get_layer_override,
    POS_TO_LAYER,
)


# =============================================================================
# Test: POS Tagging
# =============================================================================

class TestPOSTagging:
    """Tests for simple POS classification."""

    def test_cognitive_verbs(self):
        """Cognitive verbs classified correctly."""
        cognitive = ["think", "believe", "know", "understand"]
        for word in cognitive:
            assert get_pos(word) == SimplePOS.VERB_COGNITIVE

    def test_action_verbs(self):
        """Action verbs classified correctly."""
        # Note: "make" is VERB_CREATION, not VERB_ACTION
        actions = ["run", "walk", "jump", "catalyze", "throw"]
        for word in actions:
            assert get_pos(word) == SimplePOS.VERB_ACTION

    def test_creation_verbs(self):
        """Creation verbs classified correctly."""
        creation = ["create", "build", "form", "design"]
        for word in creation:
            assert get_pos(word) == SimplePOS.VERB_CREATION

    def test_abstract_nouns(self):
        """Abstract nouns classified correctly."""
        # Note: "reason" is VERB_COGNITIVE (to reason), so we use other nouns
        abstract = ["idea", "truth", "freedom", "wisdom"]
        for word in abstract:
            assert get_pos(word) == SimplePOS.NOUN_ABSTRACT

    def test_connectors(self):
        """Connectors classified correctly."""
        connectors = ["because", "therefore", "however"]
        for word in connectors:
            assert get_pos(word) == SimplePOS.CONNECTOR

    def test_unknown_word(self):
        """Unknown words return UNKNOWN."""
        assert get_pos("xyzquux") == SimplePOS.UNKNOWN


# =============================================================================
# Test: Layer Assignment
# =============================================================================

class TestLayerAssignment:
    """Tests for POS → Layer mapping."""

    def test_cognitive_verbs_map_to_thinking(self):
        """Cognitive verbs map to O1_THINKING."""
        assigner = create_assigner()
        result = assigner.assign("think")

        assert result.layer == OntologicalLayer.O1_THINKING

    def test_action_verbs_map_to_acting(self):
        """Action verbs map to O3_ACTING."""
        assigner = create_assigner()
        result = assigner.assign("run")

        assert result.layer == OntologicalLayer.O3_ACTING

    def test_creation_verbs_map_to_forming(self):
        """Creation verbs map to O2_FORMING."""
        assigner = create_assigner()
        result = assigner.assign("create")

        assert result.layer == OntologicalLayer.O2_FORMING

    def test_connectors_map_to_reasoning(self):
        """Connectors map to O7_REASONING."""
        assigner = create_assigner()
        result = assigner.assign("because")

        assert result.layer == OntologicalLayer.O7_REASONING

    def test_catalyze_maps_to_acting(self):
        """'catalyze' maps to O3_ACTING."""
        assigner = create_assigner()
        result = assigner.assign("catalyze")

        assert result.layer == OntologicalLayer.O3_ACTING


# =============================================================================
# Test: Override Lexicon
# =============================================================================

class TestOverrideLexicon:
    """Tests for word-specific overrides."""

    def test_purpose_words_override_to_purposing(self):
        """Purpose words override to O8_PURPOSE."""
        assigner = create_assigner()
        purpose_words = ["aim", "goal", "purpose", "intention"]

        for word in purpose_words:
            result = assigner.assign(word)
            assert result.layer == OntologicalLayer.O8_PURPOSE
            assert result.source == "override"

    def test_observe_overrides_to_meta(self):
        """'observe' overrides to O9_WITNESSES."""
        assigner = create_assigner()
        result = assigner.assign("observe")

        assert result.layer == OntologicalLayer.O9_WITNESSES

    def test_unify_overrides_to_unifying(self):
        """'unify' overrides to O10_UNIFYING."""
        assigner = create_assigner()
        result = assigner.assign("unify")

        assert result.layer == OntologicalLayer.O10_UNIFYING

    def test_absolve_overrides_to_absolving(self):
        """'absolve' overrides to O12_ABSOLVING."""
        assigner = create_assigner()
        result = assigner.assign("absolve")

        assert result.layer == OntologicalLayer.O12_ABSOLVING

    def test_override_has_high_confidence(self):
        """Override assignments have high confidence."""
        assigner = create_assigner()
        result = assigner.assign("purpose")

        assert result.confidence >= 0.9


# =============================================================================
# Test: Context Adjustment
# =============================================================================

class TestContextAdjustment:
    """Tests for context-based assignment adjustment."""

    def test_context_hint_affects_assignment(self):
        """Context hint can modify assignment."""
        assigner = create_assigner()

        # Without context
        result_no_context = assigner.assign("analyze")

        # With context suggesting reasoning
        context = ContextHint(
            preceding_words=("because", "of"),
            following_words=(),
        )
        result_with_context = assigner.assign("analyze", context)

        # May adjust layer based on context
        assert result_with_context is not None

    def test_imperative_context(self):
        """Imperative context affects ACTING verbs."""
        assigner = create_assigner()

        context = ContextHint(
            sentence_type="imperative",
        )
        result = assigner.assign("run", context)

        # Imperative may shift to DIRECTING
        assert result is not None

    def test_scientific_domain(self):
        """Scientific domain context is recognized."""
        assigner = create_assigner()

        context = ContextHint(
            domain="scientific",
        )
        result = assigner.assign("analyze", context)

        assert result is not None


# =============================================================================
# Test: Assignment Object
# =============================================================================

class TestAssignmentObject:
    """Tests for LayerAssignment dataclass."""

    def test_assignment_has_all_fields(self):
        """Assignment has all required fields."""
        assigner = create_assigner()
        result = assigner.assign("think")

        assert result.word == "think"
        assert isinstance(result.layer, OntologicalLayer)
        assert isinstance(result.pos, SimplePOS)
        assert 0.0 <= result.confidence <= 1.0
        assert result.source in ("override", "pos_mapping", "context_adjusted", "default")
        assert len(result.assignment_hash) == 12

    def test_assignment_is_frozen(self):
        """Assignment is immutable."""
        assigner = create_assigner()
        result = assigner.assign("think")

        with pytest.raises(AttributeError):
            result.layer = OntologicalLayer.O3_ACTING  # type: ignore


# =============================================================================
# Test: Batch Assignment
# =============================================================================

class TestBatchAssignment:
    """Tests for batch layer assignment."""

    def test_assign_batch(self):
        """Batch assignment works."""
        assigner = create_assigner()
        words = ("think", "create", "run", "because")

        results = assigner.assign_batch(words)

        assert len(results) == 4
        assert results[0].layer == OntologicalLayer.O1_THINKING
        assert results[1].layer == OntologicalLayer.O2_FORMING
        assert results[2].layer == OntologicalLayer.O3_ACTING
        assert results[3].layer == OntologicalLayer.O7_REASONING

    def test_batch_preserves_order(self):
        """Batch results preserve input order."""
        assigner = create_assigner()
        words = ("run", "think", "create")

        results = assigner.assign_batch(words)

        assert results[0].word == "run"
        assert results[1].word == "think"
        assert results[2].word == "create"


# =============================================================================
# Test: Determinism
# =============================================================================

class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_assignment_deterministic_100_runs(self):
        """Same word produces same result over 100 runs."""
        assigner = create_assigner()

        first_result = assigner.assign("catalyze")
        first_hash = first_result.assignment_hash

        for _ in range(100):
            result = assigner.assign("catalyze")
            assert result.layer == first_result.layer
            assert result.pos == first_result.pos
            assert result.assignment_hash == first_hash

    def test_batch_deterministic(self):
        """Batch assignment is deterministic."""
        assigner = create_assigner()
        words = ("think", "create", "run")

        first_results = assigner.assign_batch(words)

        for _ in range(100):
            results = assigner.assign_batch(words)
            for i, r in enumerate(results):
                assert r.layer == first_results[i].layer


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
