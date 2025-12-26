#!/usr/bin/env python3
"""
Tests for Symbol-U Image Generation Module
==========================================

Tests for the image_gen module components:
- Configuration classes
- Layer mapping
- BCVF, USE, SCC engines
- Coherence monitoring
- Integration tests (mock FLUX)
"""

import pytest
import numpy as np
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def mock_torch():
    """Mock torch module for tests."""
    with patch.dict('sys.modules', {'torch': MagicMock()}):
        yield


@pytest.fixture
def sample_layer_states() -> Dict[int, np.ndarray]:
    """Create sample layer states for testing."""
    np.random.seed(42)
    return {
        i: np.random.randn(1, 64, 32, 32).astype(np.float32)
        for i in range(1, 13)
    }


@pytest.fixture
def sample_latents() -> np.ndarray:
    """Create sample latents for testing."""
    np.random.seed(42)
    return np.random.randn(1, 4, 128, 128).astype(np.float32)


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================

class TestConfiguration:
    """Test configuration dataclasses."""

    def test_flux_config_defaults(self):
        """Test FluxConfig default values."""
        from symbolu.image_gen.config import FluxConfig

        config = FluxConfig()

        assert config.model_id == "black-forest-labs/FLUX.1-dev"
        assert config.num_double_blocks == 19
        assert config.num_single_blocks == 38
        assert config.torch_dtype == "bfloat16"

    def test_coherence_config_thresholds(self):
        """Test CoherenceConfig thresholds."""
        from symbolu.image_gen.config import CoherenceConfig

        config = CoherenceConfig()

        assert 0 <= config.coherence_threshold <= 1
        assert config.entropy_threshold > 0
        assert config.min_forward_score >= 0
        assert config.min_backward_score >= 0

    def test_scc_config_normalization(self):
        """Test SCCImageConfig weight normalization."""
        from symbolu.image_gen.config import SCCImageConfig

        config = SCCImageConfig(alpha=1.0, beta=1.0, gamma=1.0, delta=1.0)

        # Weights should be normalized to sum to 1
        total = config.alpha + config.beta + config.gamma + config.delta
        assert abs(total - 1.0) < 0.01

    def test_scc_config_layer_weights(self):
        """Test SCCImageConfig default layer weights."""
        from symbolu.image_gen.config import SCCImageConfig

        config = SCCImageConfig()

        assert config.layer_weights is not None
        assert len(config.layer_weights) == 12
        assert abs(sum(config.layer_weights) - 1.0) < 0.01

    def test_image_gen_config_presets(self):
        """Test ImageGenConfig preset methods."""
        from symbolu.image_gen.config import ImageGenConfig, GenerationMode

        fast_config = ImageGenConfig.fast()
        assert fast_config.mode == GenerationMode.FAST
        assert fast_config.num_inference_steps == 4

        quality_config = ImageGenConfig.quality()
        assert quality_config.mode == GenerationMode.QUALITY
        assert quality_config.num_inference_steps == 50

    def test_coherence_matrix_config(self):
        """Test CoherenceMatrixConfig matrix building."""
        from symbolu.image_gen.config import CoherenceMatrixConfig

        config = CoherenceMatrixConfig()
        matrix = config.build_default_matrix()

        assert len(matrix) == 12
        assert len(matrix[0]) == 12

        # Check diagonal is self_coupling
        for i in range(12):
            assert matrix[i][i] == config.self_coupling

        # Check symmetry
        for i in range(12):
            for j in range(12):
                assert abs(matrix[i][j] - matrix[j][i]) < 0.01


# =============================================================================
# LAYER MAPPER TESTS
# =============================================================================

class TestLayerMapper:
    """Test layer mapping functionality."""

    def test_layer_names(self):
        """Test LAYER_NAMES dictionary."""
        from symbolu.image_gen.layer_mapper import LAYER_NAMES

        assert len(LAYER_NAMES) == 12
        assert LAYER_NAMES[1] == "POTENTIAL"
        assert LAYER_NAMES[12] == "ABSOLVING"

    def test_ontological_layer_enum(self):
        """Test OntologicalLayer enum."""
        from symbolu.image_gen.layer_mapper import OntologicalLayer

        assert OntologicalLayer.POTENTIAL == 1
        assert OntologicalLayer.IDENTITY == 2
        assert OntologicalLayer.ABSOLVING == 12

    def test_layer_mapper_double_blocks(self):
        """Test mapping double blocks to layers."""
        from symbolu.image_gen.layer_mapper import LayerMapper

        mapper = LayerMapper()

        # Early blocks -> early layers
        assert mapper.get_layer_for_double_block(0) in [2, 3]
        assert mapper.get_layer_for_double_block(5) in [3, 4, 5]

        # Late blocks -> later layers
        assert mapper.get_layer_for_double_block(15) in [6, 7]
        assert mapper.get_layer_for_double_block(18) in [7]

    def test_layer_mapper_single_blocks(self):
        """Test mapping single blocks to layers."""
        from symbolu.image_gen.layer_mapper import LayerMapper

        mapper = LayerMapper()

        # Single blocks map to layers 8-11
        assert mapper.get_layer_for_single_block(0) == 8
        assert mapper.get_layer_for_single_block(10) == 9
        assert mapper.get_layer_for_single_block(25) == 10
        assert mapper.get_layer_for_single_block(35) == 11

    def test_layer_block_mapping(self):
        """Test LayerBlockMapping dataclass."""
        from symbolu.image_gen.layer_mapper import LayerBlockMapping, LAYER_CONFIG

        # Check L2 (IDENTITY) configuration
        l2_config = LAYER_CONFIG[2]
        assert l2_config.layer_index == 2
        assert l2_config.layer_name == "IDENTITY"
        assert l2_config.double_block_range is not None

    def test_timestep_to_layer(self):
        """Test timestep to layer mapping."""
        from symbolu.image_gen.layer_mapper import LayerMapper

        mapper = LayerMapper()

        # Early timesteps -> early layers
        early_layer = mapper.timestep_to_layer(0, 28)
        assert early_layer in [2, 3, 4]

        # Late timesteps -> later layers
        late_layer = mapper.timestep_to_layer(27, 28)
        assert late_layer in [10, 11, 12]


# =============================================================================
# BCVF ENGINE TESTS
# =============================================================================

class TestBCVFEngine:
    """Test BCVF image engine."""

    def test_consistency_lagrangian(self):
        """Test Lagrangian computation."""
        from symbolu.image_gen.bcvf_image import ConsistencyLagrangianImage

        lagrangian = ConsistencyLagrangianImage()

        # Perfect scores should give low Lagrangian
        L_perfect = lagrangian.compute_lagrangian(1.0, 1.0)
        assert L_perfect < 0.01

        # Low scores should give high Lagrangian
        L_low = lagrangian.compute_lagrangian(0.3, 0.3)
        assert L_low > L_perfect

        # Inconsistent scores should add penalty
        L_inconsistent = lagrangian.compute_lagrangian(0.9, 0.4)
        L_consistent = lagrangian.compute_lagrangian(0.7, 0.7)
        assert L_inconsistent > L_consistent

    def test_lagrangian_weight(self):
        """Test weight computation from Lagrangian."""
        from symbolu.image_gen.bcvf_image import ConsistencyLagrangianImage

        lagrangian = ConsistencyLagrangianImage()

        # Low Lagrangian -> high weight
        L_low = lagrangian.compute_lagrangian(0.9, 0.9)
        w_high = lagrangian.compute_weight(L_low)

        # High Lagrangian -> low weight
        L_high = lagrangian.compute_lagrangian(0.2, 0.2)
        w_low = lagrangian.compute_weight(L_high)

        assert w_high > w_low
        assert 0 <= w_high <= 1
        assert 0 <= w_low <= 1

    def test_bcvf_score_properties(self):
        """Test BCVFImageScore properties."""
        from symbolu.image_gen.bcvf_image import BCVFImageScore

        # Consistent high scores
        score = BCVFImageScore(
            forward_score=0.85,
            backward_score=0.80,
            lagrangian=0.05,
            consistency_weight=0.9,
        )

        assert score.is_consistent
        assert score.quality_category == "excellent"
        assert score.should_accept

        # Inconsistent scores
        score_inconsistent = BCVFImageScore(
            forward_score=0.9,
            backward_score=0.3,
            lagrangian=0.5,
            consistency_weight=0.4,
        )

        assert not score_inconsistent.is_consistent

    def test_forward_scorer(self, sample_latents):
        """Test forward image scorer."""
        from symbolu.image_gen.bcvf_image import ForwardImageScorer

        scorer = ForwardImageScorer()

        # Test coherence scoring
        coherence = scorer.compute_coherence_score(sample_latents)
        assert 0 <= coherence <= 1

        # Test quality scoring
        quality = scorer.compute_quality_score(sample_latents)
        assert 0 <= quality <= 1

        # Test style consistency
        style = scorer.compute_style_consistency_score(sample_latents)
        assert 0 <= style <= 1

    def test_bcvf_engine_score(self, sample_latents):
        """Test complete BCVF scoring."""
        from symbolu.image_gen.bcvf_image import BCVFImageEngine

        engine = BCVFImageEngine()

        score = engine.score(
            latents=sample_latents,
            prompt="A test prompt",
        )

        assert hasattr(score, 'forward_score')
        assert hasattr(score, 'backward_score')
        assert hasattr(score, 'lagrangian')
        assert hasattr(score, 'consistency_weight')


# =============================================================================
# USE ENGINE TESTS
# =============================================================================

class TestUSEEngine:
    """Test USE phase synchronization engine."""

    def test_phase_extraction(self, sample_layer_states):
        """Test phase extraction from layer states."""
        from symbolu.image_gen.use_image import PhaseExtractor

        extractor = PhaseExtractor(phase_dim=64)

        for layer_idx, state in sample_layer_states.items():
            phase = extractor.extract_phase_from_state(state)
            assert phase is not None
            # Phases should be in [0, 2pi]
            assert np.all(phase >= 0)
            assert np.all(phase <= 2 * np.pi + 0.1)

    def test_phase_correlation(self, sample_layer_states):
        """Test pairwise phase correlation."""
        from symbolu.image_gen.use_image import PhaseExtractor, PhaseCorrelation

        extractor = PhaseExtractor(phase_dim=32)
        phases = extractor.extract_all_phases(sample_layer_states)

        correlator = PhaseCorrelation()

        # Correlation between same phase should be 1
        corr_self = correlator.pairwise_correlation(phases[1], phases[1])
        assert abs(corr_self - 1.0) < 0.01

        # Correlation matrix should be 12x12
        matrix = correlator.compute_correlation_matrix(phases)
        assert matrix.shape == (12, 12)

        # Diagonal should be 1
        for i in range(12):
            assert abs(matrix[i, i] - 1.0) < 0.01

    def test_total_coherence(self, sample_layer_states):
        """Test total coherence computation."""
        from symbolu.image_gen.use_image import USEImageEngine

        engine = USEImageEngine()

        coherence = engine.compute_total_coherence(layer_states=sample_layer_states)

        assert isinstance(coherence, float)
        assert -1 <= coherence <= 1

    def test_phase_synchronization(self, sample_layer_states):
        """Test phase synchronization."""
        from symbolu.image_gen.use_image import USEImageEngine

        engine = USEImageEngine()

        result = engine.synchronize(
            layer_states=sample_layer_states,
            num_steps=3,
        )

        assert hasattr(result, 'initial_coherence')
        assert hasattr(result, 'final_coherence')
        assert hasattr(result, 'improvement')
        assert hasattr(result, 'synchronized_phases')


# =============================================================================
# SCC ENGINE TESTS
# =============================================================================

class TestSCCEngine:
    """Test SCC semantic coherence engine."""

    def test_layer_coherence_components(self, sample_layer_states):
        """Test individual coherence components."""
        from symbolu.image_gen.scc_image import LayerCoherenceComputer

        computer = LayerCoherenceComputer()
        state = sample_layer_states[5]

        # Test semantic consistency
        S = computer.compute_semantic_consistency(state)
        assert 0 <= S <= 1

        # Test entropy
        E = computer.compute_entropy(state)
        assert 0 <= E <= 1

        # Test predictability
        P = computer.compute_predictability(5, state)
        assert 0 <= P <= 1

    def test_layer_coherence_result(self, sample_layer_states):
        """Test per-layer coherence computation."""
        from symbolu.image_gen.scc_image import LayerCoherenceComputer

        computer = LayerCoherenceComputer()

        result = computer.compute_layer_coherence(
            layer_idx=5,
            layer_states=sample_layer_states,
        )

        assert result.layer_index == 5
        assert 0 <= result.coherence <= 1
        assert hasattr(result, 'semantic_consistency')
        assert hasattr(result, 'resonance')
        assert hasattr(result, 'entropy')
        assert hasattr(result, 'predictability')

    def test_global_coherence(self, sample_layer_states):
        """Test global coherence computation."""
        from symbolu.image_gen.scc_image import SCCImageEngine

        engine = SCCImageEngine()

        result = engine.compute_global_coherence(sample_layer_states)

        assert 0 <= result.global_coherence <= 1
        assert hasattr(result, 'layer_results')
        assert hasattr(result, 'weakest_layers')
        assert hasattr(result, 'strongest_layers')

    def test_coherence_issues_diagnosis(self, sample_layer_states):
        """Test issue diagnosis."""
        from symbolu.image_gen.scc_image import SCCImageEngine

        engine = SCCImageEngine()

        issues = engine.diagnose_issues(sample_layer_states, threshold=0.9)

        # With high threshold, should find some issues
        assert isinstance(issues, list)
        for issue in issues:
            assert hasattr(issue, 'layer_index')
            assert hasattr(issue, 'issue_type')
            assert hasattr(issue, 'severity')


# =============================================================================
# COHERENCE MONITOR TESTS
# =============================================================================

class TestCoherenceMonitor:
    """Test coherence monitoring."""

    def test_monitor_initialization(self):
        """Test monitor initialization."""
        from symbolu.image_gen.coherence_monitor import CoherenceMonitor
        from symbolu.image_gen.config import GenerationMode

        monitor = CoherenceMonitor(mode=GenerationMode.BALANCED)

        assert monitor.mode == GenerationMode.BALANCED
        assert monitor.corrections_applied == 0

    def test_timestep_recording(self, sample_layer_states, sample_latents):
        """Test timestep recording."""
        from symbolu.image_gen.coherence_monitor import CoherenceMonitor

        monitor = CoherenceMonitor()
        monitor.set_prompt("A test prompt")

        metrics = monitor.record_timestep(
            timestep=0,
            latents=sample_latents,
            layer_states=sample_layer_states,
        )

        assert metrics.timestep == 0
        assert hasattr(metrics, 'bcvf_forward')
        assert hasattr(metrics, 'bcvf_backward')
        assert hasattr(metrics, 'use_coherence')
        assert hasattr(metrics, 'scc_global')
        assert hasattr(metrics, 'combined_weight')

    def test_coherence_history(self, sample_layer_states, sample_latents):
        """Test coherence history tracking."""
        from symbolu.image_gen.coherence_monitor import CoherenceMonitor

        monitor = CoherenceMonitor()

        # Record multiple timesteps
        for t in range(5):
            monitor.record_timestep(
                timestep=t,
                latents=sample_latents,
                layer_states=sample_layer_states,
            )

        history = monitor.history

        assert history.num_timesteps == 5
        assert history.latest.timestep == 4

        # Test trend detection
        trend = history.get_trend("combined_weight")
        assert trend in ["improving", "declining", "stable"]

    def test_generation_decision(self, sample_layer_states, sample_latents):
        """Test generation decision."""
        from symbolu.image_gen.coherence_monitor import CoherenceMonitor
        from symbolu.image_gen.config import GenerationMode

        monitor = CoherenceMonitor(mode=GenerationMode.BALANCED)
        monitor.set_prompt("Test prompt")

        # Record some timesteps
        for t in range(3):
            monitor.record_timestep(
                timestep=t,
                latents=sample_latents,
                layer_states=sample_layer_states,
            )

        decision = monitor.get_generation_result(
            final_latents=sample_latents,
            final_layer_states=sample_layer_states,
        )

        assert hasattr(decision, 'should_accept')
        assert hasattr(decision, 'confidence')
        assert hasattr(decision, 'category')
        assert hasattr(decision, 'completion_weight')
        assert hasattr(decision, 'recommendations')


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests with mocked FLUX."""

    def test_module_imports(self):
        """Test that all module imports work."""
        from symbolu.image_gen import (
            ImageGenConfig,
            GenerationMode,
            LayerMapper,
            BCVFImageEngine,
            USEImageEngine,
            SCCImageEngine,
            CoherenceMonitor,
            create_bcvf_engine,
            create_use_engine,
            create_scc_engine,
        )

        # All should be importable without error
        assert ImageGenConfig is not None
        assert GenerationMode is not None
        assert LayerMapper is not None

    def test_full_coherence_pipeline(self, sample_layer_states, sample_latents):
        """Test complete coherence pipeline without FLUX."""
        from symbolu.image_gen import (
            BCVFImageEngine,
            USEImageEngine,
            SCCImageEngine,
            CoherenceMonitor,
        )

        prompt = "A majestic mountain landscape"

        # Initialize engines
        bcvf = BCVFImageEngine()
        use = USEImageEngine()
        scc = SCCImageEngine()

        # BCVF scoring
        bcvf_score = bcvf.score(
            latents=sample_latents,
            prompt=prompt,
        )
        assert bcvf_score.forward_score >= 0
        assert bcvf_score.backward_score >= 0

        # USE phase coherence
        phases = use.extract_phases(sample_layer_states)
        use_coherence = use.compute_total_coherence(phases=phases)
        assert -1 <= use_coherence <= 1

        # SCC global coherence
        scc_result = scc.compute_global_coherence(sample_layer_states)
        assert 0 <= scc_result.global_coherence <= 1

        # Monitor integration
        monitor = CoherenceMonitor()
        monitor.set_prompt(prompt)

        metrics = monitor.record_timestep(
            timestep=0,
            latents=sample_latents,
            layer_states=sample_layer_states,
        )

        assert metrics.combined_weight >= 0

    def test_version_and_info(self):
        """Test module version and info functions."""
        from symbolu.image_gen import (
            __version__,
            get_version,
            check_dependencies,
            quick_start_info,
        )

        assert __version__ is not None
        assert get_version() == __version__

        deps = check_dependencies()
        assert isinstance(deps, dict)
        assert "torch" in deps

        info = quick_start_info()
        assert "Symbol-U" in info


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_layer_states(self):
        """Test handling of empty layer states."""
        from symbolu.image_gen.scc_image import SCCImageEngine

        engine = SCCImageEngine()

        result = engine.compute_global_coherence({})

        assert result.global_coherence == 0.0
        assert len(result.layer_results) == 0

    def test_partial_layer_states(self):
        """Test handling of partial layer states."""
        from symbolu.image_gen.scc_image import SCCImageEngine

        engine = SCCImageEngine()

        # Only provide some layers
        partial_states = {
            1: np.random.randn(1, 64, 32, 32),
            5: np.random.randn(1, 64, 32, 32),
            12: np.random.randn(1, 64, 32, 32),
        }

        result = engine.compute_global_coherence(partial_states)

        # Should still work with partial data
        assert 0 <= result.global_coherence <= 1
        assert len(result.layer_results) == 3

    def test_invalid_scores(self):
        """Test handling of out-of-range scores."""
        from symbolu.image_gen.bcvf_image import ConsistencyLagrangianImage

        lagrangian = ConsistencyLagrangianImage()

        # Should handle out-of-range values
        L = lagrangian.compute_lagrangian(1.5, -0.5)
        assert L >= 0  # Lagrangian should be non-negative

    def test_none_inputs(self):
        """Test handling of None inputs."""
        from symbolu.image_gen.bcvf_image import ForwardImageScorer
        from symbolu.image_gen.scc_image import LayerCoherenceComputer

        forward_scorer = ForwardImageScorer()
        coherence = forward_scorer.compute_coherence_score(None)
        assert coherence == 0.7  # Should return default

        layer_computer = LayerCoherenceComputer()
        S = layer_computer.compute_semantic_consistency(None)
        assert S == 0.5  # Should return neutral value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
