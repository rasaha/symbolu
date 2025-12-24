"""
Symbol-U Core v3.0 - Core Engine Tests
======================================
Unit tests for the high-level Core engine and interfaces:
- CoreInterface (facade for Symbol-U intelligence)
- CorePipeline (main processing pipeline)
- Data models (SMIResult, BhavaState, EntropyState, AnalysisResult, etc.)

Note: Core module contains placeholder implementations that raise NotImplementedError.
These tests verify the interface contracts, model structures, and error handling.
"""

import pytest
from typing import Any, Dict, List, Optional

# Import core interfaces and pipeline
from symbolu.core.interface import CoreInterface
from symbolu.core.pipeline import CorePipeline

# Import data models
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
# Fixtures
# =============================================================================


@pytest.fixture
def core_interface() -> CoreInterface:
    """Create a CoreInterface instance."""
    return CoreInterface()


@pytest.fixture
def core_pipeline() -> CorePipeline:
    """Create a CorePipeline instance."""
    return CorePipeline()


@pytest.fixture
def sample_text() -> str:
    """Sample text for testing."""
    return "Hello world, this is a test."


@pytest.fixture
def sample_context() -> Dict[str, Any]:
    """Sample context dictionary for testing."""
    return {
        "user_intent": "exploration",
        "session_id": "test-session-001",
        "preferences": {"verbosity": "low"},
    }


# =============================================================================
# CoreInterface Tests
# =============================================================================


class TestCoreInterfaceInstantiation:
    """Tests for CoreInterface instantiation."""

    def test_interface_instantiation(self) -> None:
        """Test that CoreInterface can be instantiated."""
        interface = CoreInterface()
        assert interface is not None
        assert isinstance(interface, CoreInterface)

    def test_interface_instantiation_deterministic(self) -> None:
        """Test that multiple instantiations create valid objects."""
        interface1 = CoreInterface()
        interface2 = CoreInterface()
        assert interface1 is not None
        assert interface2 is not None
        assert interface1 is not interface2


class TestCoreInterfaceComputeSMI:
    """Tests for CoreInterface.compute_smi method."""

    def test_compute_smi_raises_not_implemented(
        self, core_interface: CoreInterface, sample_text: str
    ) -> None:
        """Test that compute_smi raises NotImplementedError (placeholder)."""
        with pytest.raises(NotImplementedError):
            core_interface.compute_smi(sample_text)

    def test_compute_smi_with_empty_string_raises_not_implemented(
        self, core_interface: CoreInterface
    ) -> None:
        """Test compute_smi with empty string raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            core_interface.compute_smi("")


class TestCoreInterfaceComputeStitching:
    """Tests for CoreInterface.compute_stitching method."""

    def test_compute_stitching_raises_not_implemented(
        self, core_interface: CoreInterface
    ) -> None:
        """Test that compute_stitching raises NotImplementedError (placeholder)."""
        candidates = [CandidateResponse(text="Test")]
        with pytest.raises(NotImplementedError):
            core_interface.compute_stitching(candidates)

    def test_compute_stitching_with_context_raises_not_implemented(
        self, core_interface: CoreInterface, sample_context: Dict[str, Any]
    ) -> None:
        """Test compute_stitching with context raises NotImplementedError."""
        candidates = [CandidateResponse(text="Test")]
        with pytest.raises(NotImplementedError):
            core_interface.compute_stitching(candidates, context=sample_context)


class TestCoreInterfaceComputeBhava:
    """Tests for CoreInterface.compute_bhava method."""

    def test_compute_bhava_raises_not_implemented(
        self, core_interface: CoreInterface, sample_context: Dict[str, Any]
    ) -> None:
        """Test that compute_bhava raises NotImplementedError (placeholder)."""
        with pytest.raises(NotImplementedError):
            core_interface.compute_bhava(sample_context)


class TestCoreInterfaceComputeEntropy:
    """Tests for CoreInterface.compute_entropy method."""

    def test_compute_entropy_raises_not_implemented(
        self, core_interface: CoreInterface, sample_text: str
    ) -> None:
        """Test that compute_entropy raises NotImplementedError (placeholder)."""
        with pytest.raises(NotImplementedError):
            core_interface.compute_entropy(sample_text)


class TestCoreInterfaceApplyRegulators:
    """Tests for CoreInterface.apply_regulators method."""

    def test_apply_regulators_raises_not_implemented(
        self, core_interface: CoreInterface
    ) -> None:
        """Test that apply_regulators raises NotImplementedError (placeholder)."""
        draft = "Test draft text"
        bhava = BhavaState()
        with pytest.raises(NotImplementedError):
            core_interface.apply_regulators(draft, bhava)


class TestCoreInterfaceDecomposeSyllables:
    """Tests for CoreInterface.decompose_syllables method."""

    def test_decompose_syllables_raises_not_implemented(
        self, core_interface: CoreInterface
    ) -> None:
        """Test that decompose_syllables raises NotImplementedError (placeholder)."""
        with pytest.raises(NotImplementedError):
            core_interface.decompose_syllables("word")


class TestCoreInterfaceMapConsonantToKosha:
    """Tests for CoreInterface.map_consonant_to_kosha method."""

    def test_map_consonant_to_kosha_raises_not_implemented(
        self, core_interface: CoreInterface
    ) -> None:
        """Test that map_consonant_to_kosha raises NotImplementedError (placeholder)."""
        with pytest.raises(NotImplementedError):
            core_interface.map_consonant_to_kosha("k")


class TestCoreInterfaceMapWordToOntology:
    """Tests for CoreInterface.map_word_to_ontology method."""

    def test_map_word_to_ontology_raises_not_implemented(
        self, core_interface: CoreInterface
    ) -> None:
        """Test that map_word_to_ontology raises NotImplementedError (placeholder)."""
        with pytest.raises(NotImplementedError):
            core_interface.map_word_to_ontology("test")


# =============================================================================
# CorePipeline Tests
# =============================================================================


class TestCorePipelineInstantiation:
    """Tests for CorePipeline instantiation."""

    def test_pipeline_instantiation_default(self) -> None:
        """Test that CorePipeline can be instantiated with defaults."""
        pipeline = CorePipeline()
        assert pipeline is not None
        assert isinstance(pipeline, CorePipeline)

    def test_pipeline_instantiation_with_core_interface(self) -> None:
        """Test CorePipeline instantiation with custom CoreInterface."""
        interface = CoreInterface()
        pipeline = CorePipeline(core=interface)
        assert pipeline is not None
        assert isinstance(pipeline, CorePipeline)


class TestCorePipelineAnalyze:
    """Tests for CorePipeline.analyze method."""

    def test_analyze_raises_not_implemented(
        self, core_pipeline: CorePipeline, sample_text: str
    ) -> None:
        """Test that analyze raises NotImplementedError (placeholder)."""
        with pytest.raises(NotImplementedError):
            core_pipeline.analyze(sample_text)

    def test_analyze_with_context_raises_not_implemented(
        self, core_pipeline: CorePipeline, sample_text: str, sample_context: Dict[str, Any]
    ) -> None:
        """Test analyze with context raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            core_pipeline.analyze(sample_text, context=sample_context)


class TestCorePipelineAnalyzeStreaming:
    """Tests for CorePipeline.analyze_streaming method."""

    def test_analyze_streaming_raises_not_implemented(
        self, core_pipeline: CorePipeline, sample_text: str
    ) -> None:
        """Test that analyze_streaming raises NotImplementedError (placeholder)."""
        with pytest.raises(NotImplementedError):
            # Attempt to get first result from generator
            gen = core_pipeline.analyze_streaming(sample_text)
            next(gen)


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

    def test_core_interface_import(self) -> None:
        """Test that core.interface can be imported."""
        from symbolu.core import interface
        assert interface is not None
        assert hasattr(interface, 'CoreInterface')

    def test_core_pipeline_import(self) -> None:
        """Test that core.pipeline can be imported."""
        from symbolu.core import pipeline
        assert pipeline is not None
        assert hasattr(pipeline, 'CorePipeline')

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
