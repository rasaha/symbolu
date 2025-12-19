"""
Test Suite for Phase-11A Evaluation Harness
=============================================

This test suite verifies:
    - Harness does not mutate generator inputs
    - Only one dimension changes per experiment
    - Records are immutable
    - No forbidden imports
    - Harness can be run repeatedly with identical results given same seeds

This test suite does NOT:
    - Test semantic quality
    - Validate output correctness
    - Judge output appropriateness
"""

from __future__ import annotations

import ast
import copy
import hashlib
import sys
from pathlib import Path
from typing import List, Set

import pytest

# Import harness components
from phase11a_evaluation_harness import (
    # Version
    PHASE11A_VERSION,
    # Constants
    INTENTS,
    ONTOLOGICAL_LAYER_ORDER,
    PPV_DIMENSION_ORDER,
    PPV_VALUE_MIN,
    PPV_VALUE_MAX,
    TEMPERATURE_VALUES,
    # Enums
    OntologicalLayer,
    PPVDimension,
    TemperatureLevel,
    RenderMode,
    # Configuration
    ExperimentConfig,
    # Output Records
    Phase11OutputRecord,
    # Signals
    DifferentiationSignals,
    StabilitySignals,
    # Generator
    MockPhase11Generator,
    # Variation Generator
    VariationMatrixGenerator,
    # Harness
    Phase11AEvaluationHarness,
    # Summary
    EvaluationSummary,
    # Functions
    compute_output_hash,
    compute_lexical_signature,
    capture_output,
    compute_differentiation_signals,
    compute_stability_signals,
    compute_evaluation_summary,
)


# =============================================================================
# Test Constants
# =============================================================================

class TestConstants:
    """Test that constants are properly defined."""

    def test_intents_are_frozen(self) -> None:
        """Verify INTENTS is a tuple (immutable)."""
        assert isinstance(INTENTS, tuple)
        assert len(INTENTS) == 3
        assert "EXPRESS_LOSS" in INTENTS
        assert "EXPRESS_RESOLVE" in INTENTS
        assert "EXPRESS_CURIOSITY" in INTENTS

    def test_ontological_layers_count(self) -> None:
        """Verify exactly 10 ontological layers."""
        assert len(ONTOLOGICAL_LAYER_ORDER) == 10
        assert len(OntologicalLayer) == 10

    def test_ppv_dimensions_count(self) -> None:
        """Verify exactly 8 PPV dimensions."""
        assert len(PPV_DIMENSION_ORDER) == 8
        assert len(PPVDimension) == 8

    def test_ppv_value_bounds(self) -> None:
        """Verify PPV value bounds are 0-7."""
        assert PPV_VALUE_MIN == 0
        assert PPV_VALUE_MAX == 7

    def test_temperature_levels(self) -> None:
        """Verify temperature levels are defined."""
        assert len(TEMPERATURE_VALUES) == 3
        assert TemperatureLevel.LOW in TEMPERATURE_VALUES
        assert TemperatureLevel.MID in TEMPERATURE_VALUES
        assert TemperatureLevel.HIGH in TEMPERATURE_VALUES
        assert all(0.0 <= v <= 1.0 for v in TEMPERATURE_VALUES.values())


# =============================================================================
# Test Input Immutability
# =============================================================================

class TestInputImmutability:
    """Test that harness does not mutate generator inputs."""

    def test_experiment_config_is_frozen(self) -> None:
        """Verify ExperimentConfig is immutable."""
        config = ExperimentConfig(
            intent="EXPRESS_LOSS",
            ontological_path=(OntologicalLayer.FORMING,),
            ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
            temperature=0.5,
            mode=RenderMode.GOVERNED,
            variation_axis="test",
            variation_index=0,
        )

        # Attempt to modify should raise
        with pytest.raises(AttributeError):
            config.intent = "MODIFIED"  # type: ignore

        with pytest.raises(AttributeError):
            config.temperature = 0.9  # type: ignore

    def test_output_record_is_frozen(self) -> None:
        """Verify Phase11OutputRecord is immutable."""
        record = Phase11OutputRecord(
            intent="EXPRESS_LOSS",
            ontological_path=("FORMING",),
            ppv_vector=(3, 3, 3, 3, 3, 3, 3, 3),
            temperature=0.5,
            mode="governed",
            output_hash="a" * 64,
            output_length=100,
            lexical_signature=("token1", "token2"),
            config_hash="b" * 64,
            run_index=0,
        )

        # Attempt to modify should raise
        with pytest.raises(AttributeError):
            record.intent = "MODIFIED"  # type: ignore

        with pytest.raises(AttributeError):
            record.output_length = 999  # type: ignore

    def test_generator_does_not_mutate_config(self) -> None:
        """Verify generator does not modify input configuration."""
        config = ExperimentConfig(
            intent="EXPRESS_LOSS",
            ontological_path=(OntologicalLayer.FORMING, OntologicalLayer.THINKING),
            ppv_values=(1, 2, 3, 4, 5, 6, 7, 0),
            temperature=0.3,
            mode=RenderMode.GOVERNED,
            variation_axis="test",
            variation_index=0,
        )

        # Take snapshot of config hash before
        hash_before = config.config_hash()

        # Run generator
        generator = MockPhase11Generator(seed=42)
        _ = generator.generate(config)

        # Config should be unchanged
        hash_after = config.config_hash()
        assert hash_before == hash_after

    def test_harness_does_not_mutate_config(self) -> None:
        """Verify harness does not modify input configuration."""
        config = ExperimentConfig(
            intent="EXPRESS_RESOLVE",
            ontological_path=(OntologicalLayer.DIRECTING,),
            ppv_values=(0, 0, 0, 0, 7, 7, 7, 7),
            temperature=0.8,
            mode=RenderMode.OPEN,
            variation_axis="test",
            variation_index=0,
        )

        # Take snapshot
        intent_before = config.intent
        path_before = config.ontological_path
        ppv_before = config.ppv_values
        temp_before = config.temperature
        mode_before = config.mode

        # Run through harness
        harness = Phase11AEvaluationHarness(seed=42)
        _ = harness.run_experiment(config)

        # Verify unchanged
        assert config.intent == intent_before
        assert config.ontological_path == path_before
        assert config.ppv_values == ppv_before
        assert config.temperature == temp_before
        assert config.mode == mode_before


# =============================================================================
# Test Single Dimension Variation
# =============================================================================

class TestSingleDimensionVariation:
    """Test that only one dimension changes per experiment."""

    def test_path_variations_only_change_path(self) -> None:
        """Verify path variations only change ontological_path."""
        generator = VariationMatrixGenerator()
        configs = generator.generate_path_variations("EXPRESS_LOSS")

        # All should have same PPV, temperature, mode
        first = configs[0]
        for config in configs[1:]:
            assert config.ppv_values == first.ppv_values
            assert config.temperature == first.temperature
            assert config.mode == first.mode
            assert config.intent == first.intent

        # Paths should differ
        paths = [c.ontological_path for c in configs]
        assert len(set(paths)) > 1  # At least some different paths

    def test_ppv_variations_only_change_ppv(self) -> None:
        """Verify PPV variations only change ppv_values."""
        generator = VariationMatrixGenerator()
        configs = generator.generate_ppv_variations("EXPRESS_RESOLVE")

        # All should have same path, temperature, mode
        first = configs[0]
        for config in configs[1:]:
            assert config.ontological_path == first.ontological_path
            assert config.temperature == first.temperature
            assert config.mode == first.mode
            assert config.intent == first.intent

        # PPV should differ
        ppv_sets = [c.ppv_values for c in configs]
        assert len(set(ppv_sets)) > 1  # At least some different PPV

    def test_ppv_single_dimension_change(self) -> None:
        """Verify each PPV variation changes exactly one dimension."""
        generator = VariationMatrixGenerator()
        configs = generator.generate_ppv_variations("EXPRESS_CURIOSITY")

        baseline = generator.DEFAULT_PPV

        for config in configs:
            # Count how many dimensions differ from baseline
            differences = sum(
                1 for a, b in zip(baseline, config.ppv_values) if a != b
            )
            # Should be exactly 0 or 1 difference
            assert differences <= 1, (
                f"Expected at most 1 dimension change, got {differences}: "
                f"baseline={baseline}, config={config.ppv_values}"
            )

    def test_temperature_variations_only_change_temp(self) -> None:
        """Verify temperature variations only change temperature."""
        generator = VariationMatrixGenerator()
        configs = generator.generate_temperature_variations("EXPRESS_LOSS")

        # All should have same path, PPV, mode
        first = configs[0]
        for config in configs[1:]:
            assert config.ontological_path == first.ontological_path
            assert config.ppv_values == first.ppv_values
            assert config.mode == first.mode
            assert config.intent == first.intent

        # Temperatures should differ
        temps = [c.temperature for c in configs]
        assert len(set(temps)) > 1

    def test_mode_variations_only_change_mode(self) -> None:
        """Verify mode variations only change mode."""
        generator = VariationMatrixGenerator()
        configs = generator.generate_mode_variations("EXPRESS_RESOLVE")

        # All should have same path, PPV, temperature
        first = configs[0]
        for config in configs[1:]:
            assert config.ontological_path == first.ontological_path
            assert config.ppv_values == first.ppv_values
            assert config.temperature == first.temperature
            assert config.intent == first.intent

        # Modes should differ
        modes = [c.mode for c in configs]
        assert RenderMode.GOVERNED in modes
        assert RenderMode.OPEN in modes


# =============================================================================
# Test Record Immutability
# =============================================================================

class TestRecordImmutability:
    """Test that all records are immutable after creation."""

    def test_differentiation_signals_frozen(self) -> None:
        """Verify DifferentiationSignals is immutable."""
        signals = DifferentiationSignals(
            unique_hash_count=5,
            total_output_count=10,
            hash_uniqueness_ratio=0.5,
            min_length=50,
            max_length=100,
            length_range=50,
            common_tokens=("a", "b"),
            variable_tokens=("c", "d"),
            token_overlap_ratio=0.5,
            variation_axis="test",
        )

        with pytest.raises(AttributeError):
            signals.unique_hash_count = 999  # type: ignore

    def test_stability_signals_frozen(self) -> None:
        """Verify StabilitySignals is immutable."""
        signals = StabilitySignals(
            config_hash="a" * 64,
            run_count=5,
            unique_output_hashes=1,
            all_hashes_identical=True,
            mode="governed",
        )

        with pytest.raises(AttributeError):
            signals.run_count = 999  # type: ignore

    def test_evaluation_summary_frozen(self) -> None:
        """Verify EvaluationSummary is immutable."""
        summary = EvaluationSummary(
            total_experiments=100,
            total_unique_outputs=50,
            path_variations_unique_ratio=0.8,
            ppv_variations_unique_ratio=0.6,
            temperature_variations_unique_ratio=0.9,
            mode_variations_unique_ratio=1.0,
            governed_mode_deterministic=True,
            open_mode_deterministic=True,
        )

        with pytest.raises(AttributeError):
            summary.total_experiments = 999  # type: ignore

    def test_captured_records_are_immutable(self) -> None:
        """Verify records captured by harness are immutable."""
        harness = Phase11AEvaluationHarness(seed=42)

        config = ExperimentConfig(
            intent="EXPRESS_LOSS",
            ontological_path=(OntologicalLayer.FORMING,),
            ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
            temperature=0.5,
            mode=RenderMode.GOVERNED,
            variation_axis="test",
            variation_index=0,
        )

        record = harness.run_experiment(config)

        # Record should be immutable
        with pytest.raises(AttributeError):
            record.output_length = 999  # type: ignore


# =============================================================================
# Test Forbidden Imports
# =============================================================================

class TestForbiddenImports:
    """Test that no forbidden imports are used."""

    FORBIDDEN_MODULES = {
        # ML/NLP
        "sklearn",
        "scikit-learn",
        "torch",
        "pytorch",
        "tensorflow",
        "keras",
        "transformers",
        "spacy",
        "nltk",
        "gensim",
        # Embeddings
        "sentence_transformers",
        "openai",
        "anthropic",
        # Probability models
        "scipy.stats",
        "statsmodels",
    }

    def test_no_forbidden_imports_in_harness(self) -> None:
        """Verify harness file has no forbidden imports."""
        harness_path = Path(__file__).parent / "phase11a_evaluation_harness.py"
        source = harness_path.read_text()

        # Parse AST
        tree = ast.parse(source)

        # Extract all imports
        imports: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        # Check for forbidden modules
        forbidden_found = imports & self.FORBIDDEN_MODULES
        assert not forbidden_found, (
            f"Forbidden imports found: {forbidden_found}"
        )

    def test_no_random_import_unless_seeded(self) -> None:
        """Verify random is not imported or is properly seeded."""
        harness_path = Path(__file__).parent / "phase11a_evaluation_harness.py"
        source = harness_path.read_text()

        # Check if random is imported
        if "import random" in source or "from random" in source:
            # If random is imported, verify it's seeded
            assert "seed" in source.lower(), (
                "random module imported but no seeding mechanism found"
            )

    def test_no_datetime_import(self) -> None:
        """Verify no datetime/time imports (non-determinism source)."""
        harness_path = Path(__file__).parent / "phase11a_evaluation_harness.py"
        source = harness_path.read_text()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in ("datetime", "time"), (
                        f"Forbidden time module imported: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert node.module.split(".")[0] not in ("datetime", "time"), (
                        f"Forbidden time module imported: {node.module}"
                    )


# =============================================================================
# Test Determinism / Repeatability
# =============================================================================

class TestDeterminism:
    """Test that harness produces identical results with same seeds."""

    def test_same_seed_same_output(self) -> None:
        """Verify same seed produces identical output."""
        config = ExperimentConfig(
            intent="EXPRESS_LOSS",
            ontological_path=(OntologicalLayer.FORMING, OntologicalLayer.THINKING),
            ppv_values=(3, 4, 5, 6, 3, 4, 5, 6),
            temperature=0.5,
            mode=RenderMode.GOVERNED,
            variation_axis="test",
            variation_index=0,
        )

        # Run with same seed multiple times
        outputs: List[str] = []
        for _ in range(5):
            generator = MockPhase11Generator(seed=12345)
            output = generator.generate(config)
            outputs.append(output)

        # All outputs should be identical
        assert len(set(outputs)) == 1, (
            f"Expected identical outputs, got {len(set(outputs))} unique"
        )

    def test_harness_repeatability(self) -> None:
        """Verify harness produces identical records with same seed."""
        config = ExperimentConfig(
            intent="EXPRESS_RESOLVE",
            ontological_path=(OntologicalLayer.DIRECTING,),
            ppv_values=(0, 1, 2, 3, 4, 5, 6, 7),
            temperature=0.3,
            mode=RenderMode.OPEN,
            variation_axis="test",
            variation_index=0,
        )

        # Run harness twice with same seed
        harness1 = Phase11AEvaluationHarness(seed=99999)
        record1 = harness1.run_experiment(config)

        harness2 = Phase11AEvaluationHarness(seed=99999)
        record2 = harness2.run_experiment(config)

        # Records should be identical
        assert record1.output_hash == record2.output_hash
        assert record1.output_length == record2.output_length
        assert record1.lexical_signature == record2.lexical_signature

    def test_governed_mode_is_deterministic(self) -> None:
        """Verify GOVERNED mode is always deterministic."""
        harness = Phase11AEvaluationHarness(seed=42)

        config = ExperimentConfig(
            intent="EXPRESS_CURIOSITY",
            ontological_path=(OntologicalLayer.REASONING,),
            ppv_values=(5, 5, 5, 5, 5, 5, 5, 5),
            temperature=0.5,
            mode=RenderMode.GOVERNED,
            variation_axis="determinism_check",
            variation_index=0,
        )

        stability = harness.run_determinism_check(config, run_count=10)

        # GOVERNED mode should be deterministic
        assert stability.all_hashes_identical, (
            f"GOVERNED mode not deterministic: {stability.unique_output_hashes} unique hashes"
        )

    def test_config_hash_is_deterministic(self) -> None:
        """Verify config hash is deterministic."""
        config1 = ExperimentConfig(
            intent="EXPRESS_LOSS",
            ontological_path=(OntologicalLayer.FORMING,),
            ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
            temperature=0.5,
            mode=RenderMode.GOVERNED,
            variation_axis="test",
            variation_index=0,
        )

        config2 = ExperimentConfig(
            intent="EXPRESS_LOSS",
            ontological_path=(OntologicalLayer.FORMING,),
            ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
            temperature=0.5,
            mode=RenderMode.GOVERNED,
            variation_axis="test",
            variation_index=0,
        )

        assert config1.config_hash() == config2.config_hash()


# =============================================================================
# Test Output Differentiation
# =============================================================================

class TestOutputDifferentiation:
    """Test that structural variation produces differentiated outputs."""

    def test_different_intents_produce_different_outputs(self) -> None:
        """Verify different intents produce different outputs."""
        generator = MockPhase11Generator(seed=42)

        outputs = []
        for intent in INTENTS:
            config = ExperimentConfig(
                intent=intent,
                ontological_path=(OntologicalLayer.FORMING,),
                ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
                temperature=0.5,
                mode=RenderMode.GOVERNED,
                variation_axis="intent",
                variation_index=0,
            )
            output = generator.generate(config)
            outputs.append(output)

        # All outputs should be different
        unique_outputs = set(outputs)
        assert len(unique_outputs) == len(INTENTS), (
            f"Expected {len(INTENTS)} unique outputs, got {len(unique_outputs)}"
        )

    def test_different_paths_produce_different_outputs(self) -> None:
        """Verify different ontological paths produce different outputs."""
        generator = MockPhase11Generator(seed=42)

        outputs = []
        for layer in ONTOLOGICAL_LAYER_ORDER[:5]:  # Test first 5 layers
            config = ExperimentConfig(
                intent="EXPRESS_LOSS",
                ontological_path=(layer,),
                ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
                temperature=0.5,
                mode=RenderMode.GOVERNED,
                variation_axis="path",
                variation_index=0,
            )
            output = generator.generate(config)
            outputs.append(output)

        # Most outputs should be different
        unique_outputs = set(outputs)
        assert len(unique_outputs) > 1, "Paths should produce different outputs"

    def test_different_ppv_produces_different_outputs(self) -> None:
        """Verify different PPV values produce different outputs."""
        generator = MockPhase11Generator(seed=42)

        outputs = []
        for ppv_val in [0, 3, 7]:  # Test min, mid, max
            ppv = tuple([ppv_val] * 8)
            config = ExperimentConfig(
                intent="EXPRESS_LOSS",
                ontological_path=(OntologicalLayer.FORMING,),
                ppv_values=ppv,
                temperature=0.5,
                mode=RenderMode.GOVERNED,
                variation_axis="ppv",
                variation_index=0,
            )
            output = generator.generate(config)
            outputs.append(output)

        # Different PPV should produce different outputs
        unique_outputs = set(outputs)
        assert len(unique_outputs) > 1, "PPV should affect outputs"

    def test_different_temps_produce_different_outputs(self) -> None:
        """Verify different temperatures produce different outputs."""
        generator = MockPhase11Generator(seed=42)

        outputs = []
        for temp in TEMPERATURE_VALUES.values():
            config = ExperimentConfig(
                intent="EXPRESS_LOSS",
                ontological_path=(OntologicalLayer.FORMING,),
                ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
                temperature=temp,
                mode=RenderMode.GOVERNED,
                variation_axis="temperature",
                variation_index=0,
            )
            output = generator.generate(config)
            outputs.append(output)

        # Different temps should produce different outputs
        unique_outputs = set(outputs)
        assert len(unique_outputs) > 1, "Temperature should affect outputs"

    def test_different_modes_produce_different_outputs(self) -> None:
        """Verify different modes produce different outputs."""
        generator = MockPhase11Generator(seed=42)

        outputs = []
        for mode in [RenderMode.GOVERNED, RenderMode.OPEN]:
            config = ExperimentConfig(
                intent="EXPRESS_LOSS",
                ontological_path=(OntologicalLayer.FORMING,),
                ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
                temperature=0.5,
                mode=mode,
                variation_axis="mode",
                variation_index=0,
            )
            output = generator.generate(config)
            outputs.append(output)

        # Different modes should produce different outputs
        unique_outputs = set(outputs)
        assert len(unique_outputs) == 2, "Modes should affect outputs"


# =============================================================================
# Test Signal Computation
# =============================================================================

class TestSignalComputation:
    """Test that signal computation is correct."""

    def test_differentiation_signals_compute_correctly(self) -> None:
        """Verify differentiation signals are computed correctly."""
        # Create test records with known properties
        records = [
            Phase11OutputRecord(
                intent="EXPRESS_LOSS",
                ontological_path=("FORMING",),
                ppv_vector=(3, 3, 3, 3, 3, 3, 3, 3),
                temperature=0.5,
                mode="governed",
                output_hash="a" * 64,
                output_length=100,
                lexical_signature=("common", "unique1"),
                config_hash="x" * 64,
                run_index=0,
            ),
            Phase11OutputRecord(
                intent="EXPRESS_LOSS",
                ontological_path=("FORMING",),
                ppv_vector=(3, 3, 3, 3, 3, 3, 3, 3),
                temperature=0.5,
                mode="governed",
                output_hash="b" * 64,  # Different hash
                output_length=150,  # Different length
                lexical_signature=("common", "unique2"),  # Partially different
                config_hash="y" * 64,
                run_index=1,
            ),
        ]

        signals = compute_differentiation_signals(records, "test")

        assert signals.unique_hash_count == 2
        assert signals.total_output_count == 2
        assert signals.hash_uniqueness_ratio == 1.0
        assert signals.min_length == 100
        assert signals.max_length == 150
        assert signals.length_range == 50
        assert "common" in signals.common_tokens
        assert "unique1" in signals.variable_tokens or "unique2" in signals.variable_tokens

    def test_stability_signals_detect_determinism(self) -> None:
        """Verify stability signals correctly detect determinism."""
        # Records with identical hashes
        records = [
            Phase11OutputRecord(
                intent="EXPRESS_LOSS",
                ontological_path=("FORMING",),
                ppv_vector=(3, 3, 3, 3, 3, 3, 3, 3),
                temperature=0.5,
                mode="governed",
                output_hash="same" * 16,  # Same hash
                output_length=100,
                lexical_signature=("a", "b"),
                config_hash="cfg" + "0" * 61,
                run_index=i,
            )
            for i in range(5)
        ]

        signals = compute_stability_signals(records, "cfg" + "0" * 61, "governed")

        assert signals.run_count == 5
        assert signals.unique_output_hashes == 1
        assert signals.all_hashes_identical is True

    def test_stability_signals_detect_non_determinism(self) -> None:
        """Verify stability signals correctly detect non-determinism."""
        # Records with different hashes
        records = [
            Phase11OutputRecord(
                intent="EXPRESS_LOSS",
                ontological_path=("FORMING",),
                ppv_vector=(3, 3, 3, 3, 3, 3, 3, 3),
                temperature=0.5,
                mode="open",
                output_hash=str(i) * 64,  # Different hashes
                output_length=100,
                lexical_signature=("a", "b"),
                config_hash="cfg" + "0" * 61,
                run_index=i,
            )
            for i in range(5)
        ]

        signals = compute_stability_signals(records, "cfg" + "0" * 61, "open")

        assert signals.run_count == 5
        assert signals.unique_output_hashes == 5
        assert signals.all_hashes_identical is False


# =============================================================================
# Test Full Harness Integration
# =============================================================================

class TestHarnessIntegration:
    """Test full harness integration."""

    def test_full_evaluation_runs(self) -> None:
        """Verify full evaluation runs without error."""
        harness = Phase11AEvaluationHarness(seed=42)

        # Run full evaluation
        results = harness.run_full_evaluation(determinism_runs=2)

        # Verify structure
        assert len(results) == len(INTENTS)
        for intent in INTENTS:
            assert intent in results
            assert "ontological_path" in results[intent]
            assert "ppv_dimension" in results[intent]
            assert "temperature" in results[intent]
            assert "mode" in results[intent]

    def test_harness_captures_records(self) -> None:
        """Verify harness captures output records."""
        harness = Phase11AEvaluationHarness(seed=42)

        config = ExperimentConfig(
            intent="EXPRESS_LOSS",
            ontological_path=(OntologicalLayer.FORMING,),
            ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
            temperature=0.5,
            mode=RenderMode.GOVERNED,
            variation_axis="test",
            variation_index=0,
        )

        harness.run_experiment(config)

        assert len(harness.output_records) == 1
        assert harness.output_records[0].intent == "EXPRESS_LOSS"

    def test_harness_clear_works(self) -> None:
        """Verify harness clear removes all stored data."""
        harness = Phase11AEvaluationHarness(seed=42)

        # Run some experiments
        config = ExperimentConfig(
            intent="EXPRESS_LOSS",
            ontological_path=(OntologicalLayer.FORMING,),
            ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
            temperature=0.5,
            mode=RenderMode.GOVERNED,
            variation_axis="test",
            variation_index=0,
        )
        harness.run_experiment(config)

        assert len(harness.output_records) > 0

        # Clear
        harness.clear()

        assert len(harness.output_records) == 0
        assert len(harness.differentiation_signals) == 0
        assert len(harness.stability_signals) == 0

    def test_evaluation_summary_computes(self) -> None:
        """Verify evaluation summary computes from harness results."""
        harness = Phase11AEvaluationHarness(seed=42)
        harness.run_full_evaluation(determinism_runs=2)

        summary = compute_evaluation_summary(harness)

        assert summary.total_experiments > 0
        assert summary.total_unique_outputs > 0
        assert 0.0 <= summary.path_variations_unique_ratio <= 1.0
        assert 0.0 <= summary.ppv_variations_unique_ratio <= 1.0


# =============================================================================
# Test Lexical Signature
# =============================================================================

class TestLexicalSignature:
    """Test lexical signature computation."""

    def test_lexical_signature_is_sorted(self) -> None:
        """Verify lexical signature is sorted."""
        text = "zebra apple banana"
        signature = compute_lexical_signature(text)

        assert signature == ("apple", "banana", "zebra")

    def test_lexical_signature_is_unique(self) -> None:
        """Verify lexical signature contains unique tokens only."""
        text = "word word word"
        signature = compute_lexical_signature(text)

        assert signature == ("word",)

    def test_lexical_signature_whitespace_only(self) -> None:
        """Verify lexical signature handles whitespace tokenization."""
        text = "a b c"
        signature = compute_lexical_signature(text)

        assert len(signature) == 3
        assert "a" in signature


# =============================================================================
# Test Config Validation
# =============================================================================

class TestConfigValidation:
    """Test configuration validation."""

    def test_invalid_intent_rejected(self) -> None:
        """Verify empty intent is rejected."""
        with pytest.raises(ValueError, match="intent"):
            ExperimentConfig(
                intent="",
                ontological_path=(OntologicalLayer.FORMING,),
                ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
                temperature=0.5,
                mode=RenderMode.GOVERNED,
                variation_axis="test",
                variation_index=0,
            )

    def test_invalid_ppv_length_rejected(self) -> None:
        """Verify wrong PPV length is rejected."""
        with pytest.raises(ValueError, match="8"):
            ExperimentConfig(
                intent="EXPRESS_LOSS",
                ontological_path=(OntologicalLayer.FORMING,),
                ppv_values=(3, 3, 3),  # Wrong length
                temperature=0.5,
                mode=RenderMode.GOVERNED,
                variation_axis="test",
                variation_index=0,
            )

    def test_invalid_ppv_value_rejected(self) -> None:
        """Verify out-of-range PPV values are rejected."""
        with pytest.raises(ValueError, match="range"):
            ExperimentConfig(
                intent="EXPRESS_LOSS",
                ontological_path=(OntologicalLayer.FORMING,),
                ppv_values=(3, 3, 3, 3, 3, 3, 3, 99),  # 99 out of range
                temperature=0.5,
                mode=RenderMode.GOVERNED,
                variation_axis="test",
                variation_index=0,
            )

    def test_invalid_temperature_rejected(self) -> None:
        """Verify out-of-range temperature is rejected."""
        with pytest.raises(ValueError, match="temperature"):
            ExperimentConfig(
                intent="EXPRESS_LOSS",
                ontological_path=(OntologicalLayer.FORMING,),
                ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
                temperature=1.5,  # Out of range
                mode=RenderMode.GOVERNED,
                variation_axis="test",
                variation_index=0,
            )


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
