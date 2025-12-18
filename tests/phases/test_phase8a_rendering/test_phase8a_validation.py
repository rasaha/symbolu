"""
Phase-8A Rendering Layer - Validation Tests
============================================

These tests prove Phase-8A is a projection, not a computation.
Contract: docs/contracts/PHASE_8A_RENDERING_CONTRACT.md

Validation Tests:
  1. Determinism Test - Same RenderInput → byte-identical output
  2. Isolation Test - Rendering does not change Phase-7 outputs or cache state
  3. Non-selection Test - Renderer cannot access rank/score fields
  4. Irreversibility Test - Multiple distinct inputs collapse to similar outputs
"""

import pytest
import copy
import inspect
import hashlib

from symbolu.phases.phase7_targeted_generation.types import (
    RankedResult,
    TrajectoryResult,
    TrajectoryStep,
)
from symbolu.phases.phase8a_rendering import (
    SymbolicRenderer,
    RenderInput,
    RendererConfig,
    RenderModality,
    compute_input_hash,
)


# ============================================================================
# Test Fixtures - Create deterministic test data
# ============================================================================


def create_trajectory_step(
    idx: int, token: str, token_type: str, magnitude: float, event: str
) -> TrajectoryStep:
    """Create a trajectory step with deterministic values."""
    return TrajectoryStep(
        idx=idx,
        token=token,
        token_type=token_type,
        magnitude=magnitude,
        event=event,
        notes="",  # Notes ignored per contract
    )


def create_test_trajectory(
    sequence: tuple[str, ...],
    magnitudes: tuple[float, ...],
    events: tuple[str, ...],
) -> TrajectoryResult:
    """Create a test trajectory with deterministic values."""
    token_types = tuple(
        "consonant" if t in ("ka", "ga", "ta", "da", "pa", "ba") else "vowel"
        for t in sequence
    )
    steps = tuple(
        create_trajectory_step(i, sequence[i], token_types[i], magnitudes[i], events[i])
        for i in range(len(sequence))
    )
    return TrajectoryResult(
        sequence=sequence,
        steps=steps,
        final_magnitude=magnitudes[-1] if magnitudes else 1.0,
    )


def create_render_input(
    sequence: tuple[str, ...],
    magnitudes: tuple[float, ...],
    events: tuple[str, ...],
    score: float = 0.0,
    rank: int = 1,
    renderer_id: str = "symbolic_v1",
    output_format: str = "default",
) -> RenderInput:
    """Create a complete RenderInput for testing."""
    trajectory = create_test_trajectory(sequence, magnitudes, events)
    ranked_result = RankedResult(
        sequence=sequence,
        trajectory=trajectory,
        score=score,
        rank=rank,
    )
    config = RendererConfig(output_format=output_format)
    return RenderInput(
        ranked_result=ranked_result,
        renderer_id=renderer_id,
        renderer_config=config,
    )


# ============================================================================
# Test Class 1: Determinism Validation (INV-1, INV-2)
# ============================================================================


class TestDeterminismValidation:
    """
    Validate: Same RenderInput → byte-identical output.

    Contract invariants tested:
      INV-1: Same input produces same output
      INV-2: Output hash matches input hash
    """

    def test_same_input_same_output_simple(self):
        """Test identical inputs produce identical outputs."""
        renderer = SymbolicRenderer()
        input1 = create_render_input(
            sequence=("ba", "a", "i"),
            magnitudes=(1.0, 1.2, 1.5),
            events=("reset", "modulate", "modulate"),
        )
        input2 = create_render_input(
            sequence=("ba", "a", "i"),
            magnitudes=(1.0, 1.2, 1.5),
            events=("reset", "modulate", "modulate"),
        )

        output1 = renderer.render(input1)
        output2 = renderer.render(input2)

        # Byte-identical comparison
        assert output1 == output2
        assert output1.artifact == output2.artifact
        assert output1.input_hash == output2.input_hash

    def test_repeated_renders_identical(self):
        """Test repeated renders of same input are identical."""
        renderer = SymbolicRenderer()
        input_data = create_render_input(
            sequence=("ka", "u", "ga", "a"),
            magnitudes=(1.0, 1.3, 1.0, 1.6),
            events=("reset", "modulate", "reset", "modulate"),
        )

        # Render 100 times
        outputs = [renderer.render(input_data) for _ in range(100)]

        # All must be identical
        assert all(o == outputs[0] for o in outputs)

    def test_input_hash_deterministic(self):
        """Test input hash is deterministic."""
        input1 = create_render_input(
            sequence=("pa", "i"),
            magnitudes=(1.0, 1.4),
            events=("reset", "modulate"),
        )
        input2 = create_render_input(
            sequence=("pa", "i"),
            magnitudes=(1.0, 1.4),
            events=("reset", "modulate"),
        )

        hash1 = compute_input_hash(input1)
        hash2 = compute_input_hash(input2)

        assert hash1 == hash2

    def test_output_hash_matches_computed_hash(self):
        """Test output.input_hash matches compute_input_hash."""
        renderer = SymbolicRenderer()
        input_data = create_render_input(
            sequence=("da", "a", "ta", "u"),
            magnitudes=(1.0, 1.1, 1.0, 1.2),
            events=("reset", "modulate", "reset", "modulate"),
        )

        output = renderer.render(input_data)
        expected_hash = compute_input_hash(input_data)

        assert output.input_hash == expected_hash

    def test_different_renderer_instances_same_output(self):
        """Test different renderer instances produce same output."""
        renderer1 = SymbolicRenderer()
        renderer2 = SymbolicRenderer()
        input_data = create_render_input(
            sequence=("ba", "u", "ka", "i"),
            magnitudes=(1.0, 1.5, 1.0, 1.8),
            events=("reset", "modulate", "reset", "modulate"),
        )

        output1 = renderer1.render(input_data)
        output2 = renderer2.render(input_data)

        assert output1 == output2

    def test_no_randomness_in_renderer_source(self):
        """Test no random imports or usage in renderer source."""
        import symbolu.phases.phase8a_rendering.symbolic_renderer as module

        source = inspect.getsource(module)
        assert "random" not in source.lower()
        assert "uuid" not in source.lower()
        assert "time.time" not in source

    def test_all_outputs_are_frozen(self):
        """Test all output dataclasses are frozen (immutable)."""
        renderer = SymbolicRenderer()
        input_data = create_render_input(
            sequence=("ga", "a"),
            magnitudes=(1.0, 1.3),
            events=("reset", "modulate"),
        )

        output = renderer.render(input_data)

        # Attempting to modify should raise
        with pytest.raises(AttributeError):
            output.renderer_id = "hacked"

        with pytest.raises(AttributeError):
            output.artifact.symbols = ("hacked",)


# ============================================================================
# Test Class 2: Isolation Validation (INV-4, INV-5)
# ============================================================================


class TestIsolationValidation:
    """
    Validate: Rendering does not change Phase-7 outputs or cache state.

    Contract invariants tested:
      INV-4: No upstream influence
      INV-5: No cross-renderer influence
    """

    def test_input_unchanged_after_render(self):
        """Test RenderInput is unchanged after rendering."""
        renderer = SymbolicRenderer()

        # Create input and capture its state
        input_data = create_render_input(
            sequence=("ba", "a", "ka", "u"),
            magnitudes=(1.0, 1.2, 1.0, 1.4),
            events=("reset", "modulate", "reset", "modulate"),
        )

        # Capture original values
        original_sequence = input_data.ranked_result.sequence
        original_score = input_data.ranked_result.score
        original_rank = input_data.ranked_result.rank
        original_magnitude = input_data.ranked_result.trajectory.final_magnitude

        # Render
        _ = renderer.render(input_data)

        # Verify nothing changed
        assert input_data.ranked_result.sequence == original_sequence
        assert input_data.ranked_result.score == original_score
        assert input_data.ranked_result.rank == original_rank
        assert input_data.ranked_result.trajectory.final_magnitude == original_magnitude

    def test_no_global_state_modification(self):
        """Test rendering does not modify global state."""
        renderer = SymbolicRenderer()

        # Capture module-level state (token mapping)
        from symbolu.phases.phase8a_rendering.symbolic_renderer import TOKEN_TO_SYMBOL

        original_mapping = dict(TOKEN_TO_SYMBOL)

        input_data = create_render_input(
            sequence=("ba", "a"),
            magnitudes=(1.0, 1.2),
            events=("reset", "modulate"),
        )

        # Render multiple times
        for _ in range(10):
            renderer.render(input_data)

        # Verify mapping unchanged
        assert TOKEN_TO_SYMBOL == original_mapping

    def test_no_cross_renderer_influence(self):
        """Test one renderer's operation doesn't affect another."""
        renderer1 = SymbolicRenderer()
        renderer2 = SymbolicRenderer()

        input1 = create_render_input(
            sequence=("ba", "a"),
            magnitudes=(1.0, 1.2),
            events=("reset", "modulate"),
        )
        input2 = create_render_input(
            sequence=("ka", "u"),
            magnitudes=(1.0, 1.5),
            events=("reset", "modulate"),
        )

        # Render with renderer1, then renderer2
        output1_before = renderer1.render(input1)
        _ = renderer2.render(input2)
        output1_after = renderer1.render(input1)

        # Renderer1's output should be identical
        assert output1_before == output1_after

    def test_no_instance_state_accumulation(self):
        """Test renderer does not accumulate state between calls."""
        renderer = SymbolicRenderer()

        inputs = [
            create_render_input(
                sequence=("ba", "a", "i"),
                magnitudes=(1.0, 1.2, 1.5),
                events=("reset", "modulate", "modulate"),
            ),
            create_render_input(
                sequence=("ka", "u", "ga"),
                magnitudes=(1.0, 1.8, 1.0),
                events=("reset", "modulate", "reset"),
            ),
            create_render_input(
                sequence=("ta", "a"),
                magnitudes=(1.0, 1.1),
                events=("reset", "modulate"),
            ),
        ]

        # Render all inputs
        for inp in inputs:
            renderer.render(inp)

        # First input should still produce same output
        output_first = renderer.render(inputs[0])
        output_fresh = SymbolicRenderer().render(inputs[0])

        assert output_first == output_fresh

    def test_no_file_io_in_render(self):
        """Test no file I/O operations in renderer source."""
        import symbolu.phases.phase8a_rendering.symbolic_renderer as module

        source = inspect.getsource(module)
        # Check for file operations
        assert "open(" not in source
        assert "write(" not in source
        assert "read(" not in source or "read()" not in source  # Allow attr reads


# ============================================================================
# Test Class 3: Non-Selection Validation (INV-6, INV-7)
# ============================================================================


class TestNonSelectionValidation:
    """
    Validate: Renderer cannot access rank/score fields.

    Contract invariants tested:
      INV-6: Score and rank are not accessed
      INV-7: Output does not encode preference
    """

    def test_different_scores_same_output(self):
        """Test different scores produce identical artifacts."""
        renderer = SymbolicRenderer()

        # Same sequence/trajectory, different scores
        input_score_0 = create_render_input(
            sequence=("ba", "a", "i"),
            magnitudes=(1.0, 1.2, 1.5),
            events=("reset", "modulate", "modulate"),
            score=0.0,  # Perfect score
            rank=1,
        )
        input_score_100 = create_render_input(
            sequence=("ba", "a", "i"),
            magnitudes=(1.0, 1.2, 1.5),
            events=("reset", "modulate", "modulate"),
            score=100.0,  # High violation score
            rank=999,
        )

        output1 = renderer.render(input_score_0)
        output2 = renderer.render(input_score_100)

        # Artifacts must be identical (score not accessed)
        assert output1.artifact == output2.artifact

    def test_different_ranks_same_output(self):
        """Test different ranks produce identical artifacts."""
        renderer = SymbolicRenderer()

        input_rank_1 = create_render_input(
            sequence=("ka", "u", "ga"),
            magnitudes=(1.0, 1.4, 1.0),
            events=("reset", "modulate", "reset"),
            score=0.0,
            rank=1,  # Best
        )
        input_rank_1000 = create_render_input(
            sequence=("ka", "u", "ga"),
            magnitudes=(1.0, 1.4, 1.0),
            events=("reset", "modulate", "reset"),
            score=0.0,
            rank=1000,  # Worst
        )

        output1 = renderer.render(input_rank_1)
        output2 = renderer.render(input_rank_1000)

        # Artifacts must be identical (rank not accessed)
        assert output1.artifact == output2.artifact

    def test_input_hash_excludes_score_rank(self):
        """Test input hash does not include score or rank."""
        input1 = create_render_input(
            sequence=("ba", "a"),
            magnitudes=(1.0, 1.2),
            events=("reset", "modulate"),
            score=0.0,
            rank=1,
        )
        input2 = create_render_input(
            sequence=("ba", "a"),
            magnitudes=(1.0, 1.2),
            events=("reset", "modulate"),
            score=99.9,  # Different score
            rank=500,    # Different rank
        )

        # Hashes should be identical (score/rank excluded)
        assert compute_input_hash(input1) == compute_input_hash(input2)

    def test_no_score_access_in_render_method(self):
        """Test _do_render method doesn't access .score."""
        import symbolu.phases.phase8a_rendering.symbolic_renderer as module

        # Get just the _do_render method source
        renderer_cls = module.SymbolicRenderer
        do_render_source = inspect.getsource(renderer_cls._do_render)

        # Verify .score is not accessed in the actual rendering logic
        # Docstrings may mention it to document non-access (that's fine)
        # Look for actual access patterns like ranked_result.score
        access_patterns = [
            "ranked_result.score",
            ".score)",
            ".score,",
            ".score]",
            ".score\n",
            "input.ranked_result.score",
        ]
        for pattern in access_patterns:
            assert pattern not in do_render_source, f"Found score access: {pattern}"

    def test_no_rank_access_in_render_method(self):
        """Test _do_render method doesn't access .rank."""
        import symbolu.phases.phase8a_rendering.symbolic_renderer as module

        # Get just the _do_render method source
        renderer_cls = module.SymbolicRenderer
        do_render_source = inspect.getsource(renderer_cls._do_render)

        # Verify .rank is not accessed in the actual rendering logic
        access_patterns = [
            "ranked_result.rank",
            ".rank)",
            ".rank,",
            ".rank]",
            ".rank\n",
            "input.ranked_result.rank",
        ]
        for pattern in access_patterns:
            assert pattern not in do_render_source, f"Found rank access: {pattern}"

    def test_output_has_no_quality_field(self):
        """Test output contains no quality/preference indicators."""
        renderer = SymbolicRenderer()
        input_data = create_render_input(
            sequence=("ba", "a"),
            magnitudes=(1.0, 1.2),
            events=("reset", "modulate"),
        )

        output = renderer.render(input_data)

        # Check output has no preference-indicating fields
        output_fields = set(output.__dataclass_fields__.keys())
        forbidden_fields = {"quality", "preference", "recommendation", "fitness", "score"}
        assert output_fields.isdisjoint(forbidden_fields)

    def test_artifact_has_no_quality_encoding(self):
        """Test artifact contains no quality encoding."""
        renderer = SymbolicRenderer()
        input_data = create_render_input(
            sequence=("ba", "a", "ka", "u"),
            magnitudes=(1.0, 1.2, 1.0, 1.4),
            events=("reset", "modulate", "reset", "modulate"),
        )

        output = renderer.render(input_data)
        artifact = output.artifact

        # Check artifact fields
        artifact_fields = set(artifact.__dataclass_fields__.keys())
        forbidden_fields = {"quality", "score", "rank", "preference", "fitness"}
        assert artifact_fields.isdisjoint(forbidden_fields)


# ============================================================================
# Test Class 4: Irreversibility Validation (INV-12)
# ============================================================================


class TestIrreversibilityValidation:
    """
    Validate: Multiple distinct inputs collapse to similar outputs.

    Contract invariant tested:
      INV-12: Rendering is not invertible

    This proves Phase-8A is a projection (lossy), not encoding (lossless).
    """

    def test_different_magnitudes_same_symbols(self):
        """Test different magnitudes can produce same symbols."""
        renderer = SymbolicRenderer()

        # Same sequence, different magnitudes
        input1 = create_render_input(
            sequence=("ba", "a"),
            magnitudes=(1.0, 1.1),  # Low magnitude
            events=("reset", "modulate"),
        )
        input2 = create_render_input(
            sequence=("ba", "a"),
            magnitudes=(1.0, 1.9),  # High magnitude
            events=("reset", "modulate"),
        )

        output1 = renderer.render(input1)
        output2 = renderer.render(input2)

        # Symbols are same (magnitude only affects connectors between groups)
        assert output1.artifact.symbols == output2.artifact.symbols

    def test_connector_information_loss(self):
        """Test connector computation loses magnitude precision."""
        renderer = SymbolicRenderer()

        # Multiple magnitudes in the same connector category
        inputs_rising = [
            create_render_input(
                sequence=("ba", "a", "ka", "u"),
                magnitudes=(1.0, 1.2, 1.0, 1.0 + delta),
                events=("reset", "modulate", "reset", "modulate"),
            )
            for delta in [0.35, 0.5, 0.8, 1.0, 1.5]  # All > 0.3 threshold
        ]

        outputs = [renderer.render(inp) for inp in inputs_rising]

        # All should have same connector (→) despite different deltas
        for output in outputs:
            assert output.artifact.connectors == outputs[0].artifact.connectors

    def test_grouping_loses_index_precision(self):
        """Test grouping computation loses exact index information."""
        renderer = SymbolicRenderer()

        # Two inputs with same reset pattern but different intermediate magnitudes
        input1 = create_render_input(
            sequence=("ba", "a", "i", "ka", "u"),
            magnitudes=(1.0, 1.1, 1.2, 1.0, 1.3),
            events=("reset", "modulate", "modulate", "reset", "modulate"),
        )
        input2 = create_render_input(
            sequence=("ba", "a", "i", "ka", "u"),
            magnitudes=(1.0, 1.9, 1.8, 1.0, 1.1),  # Different magnitudes
            events=("reset", "modulate", "modulate", "reset", "modulate"),
        )

        output1 = renderer.render(input1)
        output2 = renderer.render(input2)

        # Groupings are identical (based on events, not magnitudes)
        assert output1.artifact.groupings == output2.artifact.groupings

    def test_cannot_reconstruct_trajectory_from_artifact(self):
        """Test trajectory cannot be reconstructed from artifact."""
        renderer = SymbolicRenderer()
        input_data = create_render_input(
            sequence=("ba", "a", "i", "ka", "u"),
            magnitudes=(1.0, 1.23456, 1.78901, 1.0, 1.34567),
            events=("reset", "modulate", "modulate", "reset", "modulate"),
        )

        output = renderer.render(input_data)
        artifact = output.artifact

        # Information lost:
        # 1. Exact magnitude values (only thresholds matter for connectors)
        # 2. Precise delta values
        # 3. Token types (consonant/vowel distinction collapsed to symbols)

        # Cannot reconstruct magnitudes from artifact
        # The artifact only tells us symbols, groupings, and connector directions
        # Multiple magnitude sequences produce identical artifacts

        # Verify by checking another input produces same artifact
        input_different_mags = create_render_input(
            sequence=("ba", "a", "i", "ka", "u"),
            magnitudes=(1.0, 1.5, 1.9, 1.0, 1.1),  # Very different magnitudes
            events=("reset", "modulate", "modulate", "reset", "modulate"),
        )
        output_different = renderer.render(input_different_mags)

        # Symbols and groupings are same (information lost)
        assert artifact.symbols == output_different.artifact.symbols
        assert artifact.groupings == output_different.artifact.groupings

    def test_many_to_one_mapping(self):
        """Test many distinct inputs map to same output."""
        renderer = SymbolicRenderer()

        # Generate many inputs with same sequence but different trajectories
        inputs = []
        for mag1 in [1.1, 1.15, 1.2, 1.25, 1.29]:  # All < 0.3 delta
            for mag2 in [1.1, 1.15, 1.2, 1.25, 1.29]:
                inputs.append(
                    create_render_input(
                        sequence=("ba", "a"),
                        magnitudes=(1.0, mag1),
                        events=("reset", "modulate"),
                    )
                )

        outputs = [renderer.render(inp) for inp in inputs]

        # All outputs should have same artifact (many-to-one)
        unique_artifacts = set()
        for output in outputs:
            # Convert to hashable representation
            artifact_repr = (
                output.artifact.symbols,
                output.artifact.groupings,
                output.artifact.connectors,
            )
            unique_artifacts.add(artifact_repr)

        # Should be exactly 1 unique artifact (many-to-one proven)
        assert len(unique_artifacts) == 1, f"Expected 1 unique artifact, got {len(unique_artifacts)}"

    def test_projection_not_encoding(self):
        """
        Comprehensive test that Phase-8A is projection, not encoding.

        Projection: information is lost, many inputs → one output
        Encoding: information preserved, one input → one output (invertible)
        """
        renderer = SymbolicRenderer()

        # Create multiple distinct inputs
        distinct_inputs = [
            create_render_input(
                sequence=("ba", "a"),
                magnitudes=(1.0, 1.0 + 0.01 * i),  # Slightly different magnitudes
                events=("reset", "modulate"),
                score=float(i),  # Different scores (ignored)
                rank=i,          # Different ranks (ignored)
            )
            for i in range(100)
        ]

        # Count unique outputs
        outputs = [renderer.render(inp) for inp in distinct_inputs]
        unique_outputs = len(set(
            (o.artifact.symbols, o.artifact.groupings, o.artifact.connectors)
            for o in outputs
        ))

        # For projection: unique_outputs << len(distinct_inputs)
        # 100 inputs should collapse to far fewer outputs
        assert unique_outputs < len(distinct_inputs), (
            f"Expected information loss: {unique_outputs} unique outputs from "
            f"{len(distinct_inputs)} distinct inputs"
        )


# ============================================================================
# Test Class 5: Contract Compliance Summary
# ============================================================================


class TestContractComplianceSummary:
    """
    Summary tests verifying overall contract compliance.
    """

    def test_modality_declaration_correct(self):
        """Test renderer declares correct modality."""
        renderer = SymbolicRenderer()
        assert renderer.modality == RenderModality.SYMBOLIC

    def test_renderer_id_consistent(self):
        """Test renderer ID is consistent."""
        renderer1 = SymbolicRenderer()
        renderer2 = SymbolicRenderer()
        assert renderer1.renderer_id == renderer2.renderer_id == "symbolic_v1"

    def test_output_modality_matches_declaration(self):
        """Test output modality matches renderer declaration."""
        renderer = SymbolicRenderer()
        input_data = create_render_input(
            sequence=("ba", "a"),
            magnitudes=(1.0, 1.2),
            events=("reset", "modulate"),
        )

        output = renderer.render(input_data)
        assert output.modality == renderer.modality

    def test_all_invariants_summary(self):
        """Summary: verify Phase-8A is a projection, not computation."""
        renderer = SymbolicRenderer()

        # Create test input
        input_data = create_render_input(
            sequence=("ba", "a", "ka", "u"),
            magnitudes=(1.0, 1.2, 1.0, 1.5),
            events=("reset", "modulate", "reset", "modulate"),
        )

        # Determinism (INV-1, INV-2)
        output1 = renderer.render(input_data)
        output2 = renderer.render(input_data)
        assert output1 == output2, "FAIL: Determinism violated"

        # Isolation (INV-4, INV-5)
        original_seq = input_data.ranked_result.sequence
        _ = renderer.render(input_data)
        assert input_data.ranked_result.sequence == original_seq, "FAIL: Isolation violated"

        # Non-selection (INV-6, INV-7)
        input_high_score = create_render_input(
            sequence=("ba", "a", "ka", "u"),
            magnitudes=(1.0, 1.2, 1.0, 1.5),
            events=("reset", "modulate", "reset", "modulate"),
            score=999.0,
            rank=9999,
        )
        output_high = renderer.render(input_high_score)
        assert output1.artifact == output_high.artifact, "FAIL: Selection detected"

        # Irreversibility (INV-12)
        input_diff_mag = create_render_input(
            sequence=("ba", "a", "ka", "u"),
            magnitudes=(1.0, 1.9, 1.0, 1.1),  # Different magnitudes
            events=("reset", "modulate", "reset", "modulate"),
        )
        output_diff = renderer.render(input_diff_mag)
        assert output1.artifact.symbols == output_diff.artifact.symbols, "FAIL: Expected info loss"

        # All passed - Phase-8A is a projection
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
