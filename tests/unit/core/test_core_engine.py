"""
Symbol-U Core v3.0 - Core Engine Tests
======================================
Unit tests for core data models and active module imports.

Phase 0 Cleanup: CoreInterface and CorePipeline facade tests have been removed
because the facades themselves were removed (all methods were NotImplementedError).
See test_phase0_cleanup.py for Phase 0 verification tests.
"""

import pytest
from typing import Any, Dict, List, Optional

# Import data models (still active)
from symbolu.core.models import (
    SMIResult,
    BhavaState,
    EntropyState,
    RecursionState,
    CandidateResponse,
    AnalysisResult,
    WordAnalysis,
    SyllableAnalysis,
    DeliveryMode,
)


# =============================================================================
# Data Model Tests
# =============================================================================


class TestSMIResultModel:
    """Tests for SMIResult dataclass."""

    def test_smi_result_creation_with_defaults(self) -> None:
        """Test SMIResult creation with default values."""
        result = SMIResult()
        assert result.smi == 0.0
        assert result.inner_kosha == 0
        assert result.outer_ontology == 0
        assert result.components == {}
        assert result.interpretation == ""

    def test_smi_result_creation_with_all_fields(self) -> None:
        """Test SMIResult creation with all fields specified."""
        result = SMIResult(
            smi=0.75,
            inner_kosha=3,
            outer_ontology=7,
            components={"alpha": 0.5, "beta": 0.3},
            interpretation="High coherence state"
        )
        assert result.smi == 0.75
        assert result.inner_kosha == 3
        assert result.outer_ontology == 7
        assert result.components == {"alpha": 0.5, "beta": 0.3}
        assert result.interpretation == "High coherence state"

    def test_smi_result_deterministic_creation(self) -> None:
        """Test that creating the same SMIResult twice yields identical results."""
        params = {"smi": 0.5, "inner_kosha": 2, "outer_ontology": 5}
        result1 = SMIResult(**params)
        result2 = SMIResult(**params)
        assert result1 == result2


class TestBhavaStateModel:
    """Tests for BhavaState dataclass."""

    def test_bhava_state_creation_with_defaults(self) -> None:
        """Test BhavaState creation with default values."""
        state = BhavaState()
        assert state.timestamp == 0.0
        assert len(state.vritti_distribution) == 5
        assert all(v == 0.2 for v in state.vritti_distribution)
        assert len(state.aspect_weights) == 10
        assert all(w == 0.1 for w in state.aspect_weights)
        assert isinstance(state.entropy, EntropyState)
        assert state.stability_score == 0.0

    def test_bhava_state_creation_with_custom_values(self) -> None:
        """Test BhavaState creation with custom values."""
        state = BhavaState(
            timestamp=1234567890.0,
            vritti_distribution=[0.1, 0.2, 0.3, 0.25, 0.15],
            aspect_weights=[0.05] * 10,
            stability_score=0.85
        )
        assert state.timestamp == 1234567890.0
        assert state.vritti_distribution == [0.1, 0.2, 0.3, 0.25, 0.15]
        assert state.stability_score == 0.85


class TestEntropyStateModel:
    """Tests for EntropyState dataclass."""

    def test_entropy_state_creation_with_defaults(self) -> None:
        """Test EntropyState creation with default values."""
        entropy = EntropyState()
        assert entropy.H_dim == 0.0
        assert entropy.H_guna == 0.0
        assert entropy.H_kosha == 0.0
        assert entropy.H_combined == 0.0

    def test_entropy_state_creation_with_custom_values(self) -> None:
        """Test EntropyState creation with custom values."""
        entropy = EntropyState(
            H_dim=0.5,
            H_guna=0.3,
            H_kosha=0.4,
            H_combined=0.6
        )
        assert entropy.H_dim == 0.5
        assert entropy.H_guna == 0.3
        assert entropy.H_kosha == 0.4
        assert entropy.H_combined == 0.6


class TestRecursionStateModel:
    """Tests for RecursionState dataclass."""

    def test_recursion_state_creation_with_defaults(self) -> None:
        """Test RecursionState creation with default values."""
        state = RecursionState()
        assert state.iteration == 0
        assert state.max_iterations == 10
        assert state.converged is False
        assert state.states == []
        assert state.diagnostics == {}

    def test_recursion_state_creation_with_custom_values(self) -> None:
        """Test RecursionState creation with custom values."""
        bhava_states = [BhavaState(), BhavaState()]
        state = RecursionState(
            iteration=5,
            max_iterations=20,
            converged=True,
            states=bhava_states,
            diagnostics={"reason": "threshold_reached"}
        )
        assert state.iteration == 5
        assert state.max_iterations == 20
        assert state.converged is True
        assert len(state.states) == 2
        assert state.diagnostics["reason"] == "threshold_reached"


class TestWordAnalysisModel:
    """Tests for WordAnalysis dataclass."""

    def test_word_analysis_creation(self) -> None:
        """Test WordAnalysis creation."""
        analysis = WordAnalysis(
            word="hello",
            ontology_layer=5,
            inner_kosha=2,
            outer_ontology=7,
            smi=0.65
        )
        assert analysis.word == "hello"
        assert analysis.ontology_layer == 5
        assert analysis.inner_kosha == 2
        assert analysis.outer_ontology == 7
        assert analysis.smi == 0.65

    def test_word_analysis_with_syllables(self) -> None:
        """Test WordAnalysis with syllable data."""
        syllables = [
            SyllableAnalysis(syllable="hel", consonant="h", vowel="e", kosha_id=2),
            SyllableAnalysis(syllable="lo", consonant="l", vowel="o", kosha_id=3)
        ]
        analysis = WordAnalysis(word="hello", syllables=syllables)
        assert len(analysis.syllables) == 2
        assert analysis.syllables[0].syllable == "hel"


class TestSyllableAnalysisModel:
    """Tests for SyllableAnalysis dataclass."""

    def test_syllable_analysis_creation(self) -> None:
        """Test SyllableAnalysis creation."""
        syllable = SyllableAnalysis(
            syllable="ka",
            consonant="k",
            vowel="a",
            kosha_id=3,
            vritti_distribution=[0.2, 0.2, 0.2, 0.2, 0.2]
        )
        assert syllable.syllable == "ka"
        assert syllable.consonant == "k"
        assert syllable.vowel == "a"
        assert syllable.kosha_id == 3


class TestAnalysisResultModel:
    """Tests for AnalysisResult dataclass."""

    def test_analysis_result_creation_minimal(self) -> None:
        """Test AnalysisResult creation with minimal fields."""
        result = AnalysisResult(text="Test input")
        assert result.text == "Test input"
        assert result.words == []
        assert result.average_smi == 0.0
        assert result.bhava_state is None
        assert result.entropy is None
        assert result.delivery_mode is None
        assert result.recommendations == []
        assert result.diagnostics == {}

    def test_analysis_result_creation_full(self) -> None:
        """Test AnalysisResult creation with all fields."""
        bhava = BhavaState()
        entropy = EntropyState()
        words = [WordAnalysis(word="test")]
        result = AnalysisResult(
            text="Full test",
            words=words,
            average_smi=0.75,
            bhava_state=bhava,
            entropy=entropy,
            delivery_mode=DeliveryMode.FULL_DELIVERY,
            recommendations=["Recommend A"],
            diagnostics={"status": "complete"}
        )
        assert result.text == "Full test"
        assert len(result.words) == 1
        assert result.average_smi == 0.75
        assert result.bhava_state is not None
        assert result.delivery_mode == DeliveryMode.FULL_DELIVERY


class TestDeliveryModeEnum:
    """Tests for DeliveryMode enum."""

    def test_delivery_mode_values(self) -> None:
        """Test all DeliveryMode enum values exist."""
        assert DeliveryMode.SWEET_RESONANCE.value == "sweet_resonance"
        assert DeliveryMode.INVERSE_JOLT.value == "inverse_jolt"
        assert DeliveryMode.SYMBOLIC_METAPHOR.value == "symbolic_metaphor"
        assert DeliveryMode.DEFER.value == "defer"
        assert DeliveryMode.MIRROR_PREVIEW.value == "mirror_preview"
        assert DeliveryMode.MIRROR_CAUTION.value == "mirror_caution"
        assert DeliveryMode.FULL_DELIVERY.value == "full_delivery"


# =============================================================================
# Module Import Tests
# =============================================================================


class TestCoreModuleImports:
    """Tests to verify core module imports work correctly."""

    def test_core_package_import(self) -> None:
        """Test that core package can be imported."""
        from symbolu import core
        assert core is not None

    def test_core_models_import(self) -> None:
        """Test that core.models can be imported."""
        from symbolu.core import models
        assert models is not None
        assert hasattr(models, 'SMIResult')
        assert hasattr(models, 'BhavaState')
        assert hasattr(models, 'EntropyState')
        assert hasattr(models, 'AnalysisResult')
        assert hasattr(models, 'CandidateResponse')

    def test_core_stitching_import(self) -> None:
        """Test that core.stitching package can be imported."""
        from symbolu.core import stitching
        assert stitching is not None

    def test_core_no_longer_exports_facades(self) -> None:
        """Test that core no longer exports dead facades."""
        from symbolu import core
        assert not hasattr(core, 'CoreInterface')
        assert not hasattr(core, 'CorePipeline')
