"""
Rule-Based Renderer Snapshot Tests
====================================

Snapshot tests for FusionRenderer (deterministic rule-based rendering).

Tests cover all four rendering modes:
1. MINIMAL - practical layer only
2. STANDARD - all three layers
3. SYMBOLIC - symbolic expanded, practical condensed
4. REGULATED - compliance-safe, minimal metaphors

Snapshots ensure:
- Deterministic output across runs
- Mode-specific layer structure preserved
- Metadata correctly propagated
- No unexpected changes in rendering logic

Usage:
    pytest renderer/tests/test_rule_based_renderer_snapshots.py -v

    # Regenerate snapshots:
    REGENERATE_SNAPSHOTS=1 pytest renderer/tests/test_rule_based_renderer_snapshots.py -v

Version: 1.0
"""

import sys
import json
import pytest
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, "/home/user/symbolu")

from symbolu.mechanical.renderer.fusion_renderer import (
    FusionRenderer,
    FusionOutput,
    RenderMode,
    Domain
)

from symbolu.renderer.tests.snapshot_utils import assert_snapshot


# ============================================================================
# SNAPSHOT PATHS
# ============================================================================

SNAPSHOT_DIR = Path(__file__).parent.parent / "snapshots"

SNAPSHOT_PATHS = {
    "minimal": SNAPSHOT_DIR / "rule_based_minimal.snap",
    "standard": SNAPSHOT_DIR / "rule_based_standard.snap",
    "symbolic": SNAPSHOT_DIR / "rule_based_symbolic.snap",
    "regulated": SNAPSHOT_DIR / "rule_based_regulated.snap",
}


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def synthetic_fusion_output() -> FusionOutput:
    """
    Create synthetic FusionEngine output for snapshot testing.

    Structure mirrors the task specification:
    - symbolic: themes of growth and tension
    - practical: facts about user request
    - mirror_truth: contradictions between fear and desire

    Uses fixed values to ensure deterministic output:
    - No timestamps or random IDs
    - Static session/user identifiers
    - Fixed channel weights
    """
    return FusionOutput(
        query="What should I focus on in my life?",
        merged_response="Consider exploring both growth and stability paths.",
        hrm_content={
            # Symbolic layer source - themes and reasoning
            "reasoning": "The user seeks understanding because their path feels uncertain. Therefore, exploring alternatives provides clarity. This represents a growth vs stability tension.",
            "themes": ["growth", "tension"],
            "archetypes": ["seeker", "builder"]
        },
        lcm_content={
            # Practical layer source - facts and clarity
            "content": "User requested help. The situation involves decision-making. Multiple paths are available. Assessment is recommended.",
            "clarity_score": 0.85
        },
        moe_content={
            # Expert layer - constraints and procedures
            "content": "First, assess current state. Then, identify priorities. Finally, create action plan.",
            "domain": "life_guidance",
            "constraints": ["limited time", "competing priorities"],
            "procedures": ["self-assessment", "goal-setting", "action-planning"]
        },
        channel_weights={"hrm": 0.40, "lcm": 0.35, "moe": 0.25},
        conflict_resolution=[
            {
                "source1": "hrm",
                "source2": "moe",
                "type": "fear vs desire",
                "resolution": "weighted_blend"
            }
        ],
        metadata={
            # Fixed metadata for deterministic output
            "session_id": "snapshot-test-session",
            "user_id": "snapshot-test-user",
            "entropy": 0.42
        }
    )


def render_to_deterministic_string(output) -> str:
    """
    Convert RenderedOutput to a deterministic string representation.

    Removes timestamp field to ensure deterministic comparison.
    Uses sorted JSON keys for consistent ordering.

    Args:
        output: RenderedOutput from FusionRenderer

    Returns:
        Deterministic JSON string representation
    """
    output_dict = output.to_dict()

    # Remove non-deterministic fields
    output_dict.pop("render_timestamp", None)

    # Convert to sorted JSON for deterministic output
    return json.dumps(output_dict, indent=2, sort_keys=True, ensure_ascii=False)


# ============================================================================
# SNAPSHOT TESTS
# ============================================================================

class TestRuleBasedRendererSnapshots:
    """Snapshot tests for each FusionRenderer mode."""

    def test_minimal_mode_snapshot(self, synthetic_fusion_output):
        """
        TEST 1: Minimal mode snapshot.

        MINIMAL mode returns only the practical layer.
        - Symbolic layer: None
        - Practical layer: Key facts, constraints, actions
        - Mirror-truth layer: None
        """
        renderer = FusionRenderer(mode=RenderMode.MINIMAL)
        output = renderer.render(synthetic_fusion_output)

        # Verify mode is correct
        assert output.mode == "minimal"
        assert output.symbolic_layer is None
        assert output.practical_layer is not None
        assert output.mirror_truth_layer is None

        # Convert to deterministic string and compare snapshot
        rendered_string = render_to_deterministic_string(output)
        assert_snapshot(rendered_string, SNAPSHOT_PATHS["minimal"])

    def test_standard_mode_snapshot(self, synthetic_fusion_output):
        """
        TEST 2: Standard mode snapshot.

        STANDARD mode returns all three layers.
        - Symbolic layer: Theme, archetype, causal patterns
        - Practical layer: Key facts, constraints, procedures
        - Mirror-truth layer: Contradictions, tensions, alignment
        """
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(synthetic_fusion_output)

        # Verify mode is correct
        assert output.mode == "standard"
        assert output.symbolic_layer is not None
        assert output.practical_layer is not None
        assert output.mirror_truth_layer is not None

        # Convert to deterministic string and compare snapshot
        rendered_string = render_to_deterministic_string(output)
        assert_snapshot(rendered_string, SNAPSHOT_PATHS["standard"])

    def test_symbolic_mode_snapshot(self, synthetic_fusion_output):
        """
        TEST 3: Symbolic mode snapshot.

        SYMBOLIC mode expands symbolic layer and condenses practical.
        - Symbolic layer: Expanded with full depth
        - Practical layer: Condensed (max 2 facts, 1 action)
        - Mirror-truth layer: Full
        """
        renderer = FusionRenderer(mode=RenderMode.SYMBOLIC)
        output = renderer.render(synthetic_fusion_output)

        # Verify mode is correct
        assert output.mode == "symbolic"
        assert output.symbolic_layer is not None
        assert output.practical_layer is not None
        assert output.mirror_truth_layer is not None

        # Verify practical layer is condensed
        assert len(output.practical_layer.key_facts) <= 2
        assert len(output.practical_layer.actionable_items) <= 1

        # Convert to deterministic string and compare snapshot
        rendered_string = render_to_deterministic_string(output)
        assert_snapshot(rendered_string, SNAPSHOT_PATHS["symbolic"])

    def test_regulated_mode_snapshot(self, synthetic_fusion_output):
        """
        TEST 4: Regulated mode snapshot.

        REGULATED mode minimizes metaphors and maintains factual content.
        - Symbolic layer: Simplified (no metaphors)
        - Practical layer: Prioritized (highest weight)
        - Mirror-truth layer: Minimal

        Note: is_regulated flag is determined by domain (FINANCE, MEDICAL, LEGAL),
        not by mode. REGULATED mode applies rendering rules regardless of domain.
        """
        renderer = FusionRenderer(mode=RenderMode.REGULATED, domain=Domain.FINANCE)
        output = renderer.render(synthetic_fusion_output)

        # Verify mode is correct
        assert output.mode == "regulated"
        assert output.symbolic_layer is not None
        assert output.practical_layer is not None
        assert output.mirror_truth_layer is not None

        # Verify regulated domain flag (set because we use FINANCE domain)
        assert output.metadata.get("is_regulated") is True

        # Convert to deterministic string and compare snapshot
        rendered_string = render_to_deterministic_string(output)
        assert_snapshot(rendered_string, SNAPSHOT_PATHS["regulated"])


# ============================================================================
# METADATA PRESERVATION TESTS
# ============================================================================

class TestSnapshotMetadataPreservation:
    """Tests ensuring metadata is preserved correctly in snapshots."""

    def test_original_metadata_preserved_in_all_modes(self, synthetic_fusion_output):
        """Verify original metadata (session_id, user_id) preserved across modes."""
        for mode in RenderMode:
            renderer = FusionRenderer(mode=mode)
            output = renderer.render(synthetic_fusion_output)

            # Original metadata must be preserved
            assert output.metadata["session_id"] == "snapshot-test-session"
            assert output.metadata["user_id"] == "snapshot-test-user"
            assert output.metadata["entropy"] == 0.42

    def test_rendering_metadata_added_in_all_modes(self, synthetic_fusion_output):
        """Verify rendering metadata is added correctly."""
        for mode in RenderMode:
            renderer = FusionRenderer(mode=mode)
            output = renderer.render(synthetic_fusion_output)

            # Rendering metadata must be added
            assert "render_mode" in output.metadata
            assert "render_domain" in output.metadata
            assert "layer_weights" in output.metadata
            assert output.metadata["render_mode"] == mode.value


# ============================================================================
# DETERMINISM VERIFICATION
# ============================================================================

class TestSnapshotDeterminism:
    """Tests verifying snapshot outputs are fully deterministic."""

    def test_multiple_renders_produce_identical_output(self, synthetic_fusion_output):
        """Multiple renders of same input must produce identical snapshot strings."""
        for mode in RenderMode:
            renderer = FusionRenderer(mode=mode)

            output1 = renderer.render(synthetic_fusion_output)
            output2 = renderer.render(synthetic_fusion_output)

            string1 = render_to_deterministic_string(output1)
            string2 = render_to_deterministic_string(output2)

            assert string1 == string2, f"Mode {mode.value} produced non-deterministic output"

    def test_different_instances_produce_identical_output(self, synthetic_fusion_output):
        """Different renderer instances must produce identical outputs."""
        for mode in RenderMode:
            renderer1 = FusionRenderer(mode=mode)
            renderer2 = FusionRenderer(mode=mode)

            output1 = renderer1.render(synthetic_fusion_output)
            output2 = renderer2.render(synthetic_fusion_output)

            string1 = render_to_deterministic_string(output1)
            string2 = render_to_deterministic_string(output2)

            assert string1 == string2, f"Mode {mode.value} varied between instances"


# ============================================================================
# LAYER STRUCTURE TESTS
# ============================================================================

class TestSnapshotLayerStructure:
    """Tests verifying layer structure consistency."""

    def test_symbolic_layer_structure_in_snapshot(self, synthetic_fusion_output):
        """Symbolic layer should have consistent structure for snapshotting."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(synthetic_fusion_output)

        symbolic = output.symbolic_layer
        assert symbolic is not None

        # Required fields
        assert hasattr(symbolic, "theme")
        assert hasattr(symbolic, "archetype")
        assert hasattr(symbolic, "causal_patterns")
        assert hasattr(symbolic, "meaning_vectors")
        assert hasattr(symbolic, "dominant_channel")
        assert hasattr(symbolic, "reasoning_depth")

    def test_practical_layer_structure_in_snapshot(self, synthetic_fusion_output):
        """Practical layer should have consistent structure for snapshotting."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(synthetic_fusion_output)

        practical = output.practical_layer
        assert practical is not None

        # Required fields
        assert hasattr(practical, "key_facts")
        assert hasattr(practical, "constraints")
        assert hasattr(practical, "procedures")
        assert hasattr(practical, "coherence_score")
        assert hasattr(practical, "domain")
        assert hasattr(practical, "actionable_items")

    def test_mirror_truth_layer_structure_in_snapshot(self, synthetic_fusion_output):
        """Mirror-truth layer should have consistent structure for snapshotting."""
        renderer = FusionRenderer(mode=RenderMode.STANDARD)
        output = renderer.render(synthetic_fusion_output)

        mirror = output.mirror_truth_layer
        assert mirror is not None

        # Required fields
        assert hasattr(mirror, "contradictions")
        assert hasattr(mirror, "entropy_measures")
        assert hasattr(mirror, "tensions")
        assert hasattr(mirror, "alignment_score")
        assert hasattr(mirror, "stability_indicator")
        assert hasattr(mirror, "reflection")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
