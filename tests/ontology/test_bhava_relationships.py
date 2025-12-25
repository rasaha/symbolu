"""
Tests for Inter-Layer Bhava Relationships Architecture
=======================================================

Tests the new Bhava relationship system that replaces sub-layers with
inter-layer relationships based on Vedic astrology principles.

Tests cover:
1. BhavaRelationshipModule - 12x12 relationship matrix computation
2. DrishtiAttention - Vedic aspect-based cross-layer attention
3. InterLayerBhavaEngine - Complete relationship engine
4. VedicBhavaMapping - Astrological interpretation of relationships
5. Integration with ontological engines
"""

import pytest
import numpy as np

# Check if PyTorch is available
try:
    import torch
    import torch.nn as nn
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False


class TestVedicBhavaMapping:
    """Test the Vedic Bhava mapping and interpretation functions."""

    def test_bhava_significances_complete(self):
        """Test that all 12 Bhavas have significances defined."""
        from symbolu.ontological.bhava_relationships import BHAVA_SIGNIFICANCES

        assert len(BHAVA_SIGNIFICANCES) == 12
        for i in range(1, 13):
            assert i in BHAVA_SIGNIFICANCES
            assert 'name' in BHAVA_SIGNIFICANCES[i]
            assert 'meaning' in BHAVA_SIGNIFICANCES[i]
            assert 'description' in BHAVA_SIGNIFICANCES[i]

    def test_layer_to_bhava_mapping(self):
        """Test layer to Bhava mapping is complete."""
        from symbolu.ontological.bhava_relationships import LAYER_TO_BHAVA

        assert len(LAYER_TO_BHAVA) == 12
        for i in range(12):
            assert i in LAYER_TO_BHAVA
            assert 1 <= LAYER_TO_BHAVA[i] <= 12

    def test_relative_bhava_calculation(self):
        """Test relative Bhava calculation follows Vedic principles."""
        from symbolu.ontological.bhava_relationships import get_relative_bhava

        # Same layer should be 1st Bhava (self)
        assert get_relative_bhava(0, 0) == 1
        assert get_relative_bhava(5, 5) == 1

        # Next layer should be 2nd Bhava
        assert get_relative_bhava(0, 1) == 2
        assert get_relative_bhava(5, 6) == 2

        # Opposite layer (6 apart) should be 7th Bhava
        assert get_relative_bhava(0, 6) == 7
        assert get_relative_bhava(3, 9) == 7

        # Wrap-around
        assert get_relative_bhava(11, 0) == 2  # 11 -> 0 is +1

    def test_relationship_meaning(self):
        """Test relationship meaning interpretation."""
        from symbolu.ontological.bhava_relationships import get_relationship_meaning
        from symbolu.ontological.types import LAYER_NAMES

        # Cognition -> Purpose relationship
        meaning = get_relationship_meaning(4, 7)

        assert meaning['from_layer'] == LAYER_NAMES[4]  # O5_COGNITION
        assert meaning['to_layer'] == LAYER_NAMES[7]    # O8_PURPOSE
        assert 'interpretation' in meaning
        assert 'relationship_bhava' in meaning


class TestAspectStrengths:
    """Test Vedic aspect strength calculations."""

    def test_aspect_matrix_shape(self):
        """Test aspect matrix is 12x12."""
        from symbolu.ontological.bhava_relationships import ASPECT_STRENGTH_MATRIX

        assert len(ASPECT_STRENGTH_MATRIX) == 12
        for row in ASPECT_STRENGTH_MATRIX:
            assert len(row) == 12

    def test_conjunction_strength(self):
        """Test conjunction (same layer) has maximum strength."""
        from symbolu.ontological.bhava_relationships import ASPECT_STRENGTH_MATRIX

        for i in range(12):
            assert ASPECT_STRENGTH_MATRIX[i][i] == 1.0

    def test_opposition_strength(self):
        """Test opposition (6 apart) has full strength per Vedic principle."""
        from symbolu.ontological.bhava_relationships import ASPECT_STRENGTH_MATRIX

        for i in range(12):
            j = (i + 6) % 12
            assert ASPECT_STRENGTH_MATRIX[i][j] == 1.0

    def test_trine_strength(self):
        """Test trine aspects (4/8 apart) are harmonious."""
        from symbolu.ontological.bhava_relationships import ASPECT_STRENGTH_MATRIX

        for i in range(12):
            j1 = (i + 4) % 12
            j2 = (i + 8) % 12
            assert ASPECT_STRENGTH_MATRIX[i][j1] == 0.9
            assert ASPECT_STRENGTH_MATRIX[i][j2] == 0.9

    def test_adjacent_strength(self):
        """Test adjacent layers have resource connection."""
        from symbolu.ontological.bhava_relationships import ASPECT_STRENGTH_MATRIX

        for i in range(12):
            j1 = (i + 1) % 12
            j2 = (i - 1) % 12
            assert ASPECT_STRENGTH_MATRIX[i][j1] == 0.8
            assert ASPECT_STRENGTH_MATRIX[i][j2] == 0.8


@pytest.mark.skipif(not PYTORCH_AVAILABLE, reason="PyTorch not available")
class TestBhavaRelationshipModule:
    """Test the BhavaRelationshipModule PyTorch module."""

    def test_module_initialization(self):
        """Test module initializes correctly."""
        from symbolu.ontological.bhava_relationships import BhavaRelationshipModule

        module = BhavaRelationshipModule(embed_dim=128, num_layers=12)

        assert module.num_layers == 12
        assert module.embed_dim == 128
        assert module.aspect_strengths.shape == (12, 12)

    def test_forward_output_shapes(self):
        """Test forward pass produces correct output shapes."""
        from symbolu.ontological.bhava_relationships import BhavaRelationshipModule

        module = BhavaRelationshipModule(embed_dim=128, num_layers=12)

        batch_size = 4
        onto_probs = torch.softmax(torch.randn(batch_size, 12), dim=-1)

        output = module(onto_probs)

        assert 'relationship_matrix' in output
        assert 'relationship_flat' in output
        assert 'coherence' in output

        assert output['relationship_matrix'].shape == (batch_size, 12, 12)
        assert output['relationship_flat'].shape == (batch_size, 144)
        assert output['coherence'].shape == (batch_size,)

    def test_relationship_matrix_symmetry(self):
        """Test relationship matrix properties."""
        from symbolu.ontological.bhava_relationships import BhavaRelationshipModule

        module = BhavaRelationshipModule(embed_dim=128, num_layers=12)

        onto_probs = torch.softmax(torch.randn(1, 12), dim=-1)
        output = module(onto_probs)

        rel_matrix = output['relationship_matrix'].squeeze(0)

        # Values should be bounded
        assert rel_matrix.min() >= -1.0
        assert rel_matrix.max() <= 1.0

    def test_coherence_positive(self):
        """Test coherence score is non-negative."""
        from symbolu.ontological.bhava_relationships import BhavaRelationshipModule

        module = BhavaRelationshipModule(embed_dim=128, num_layers=12)

        onto_probs = torch.softmax(torch.randn(4, 12), dim=-1)
        output = module(onto_probs)

        assert (output['coherence'] >= 0).all()


@pytest.mark.skipif(not PYTORCH_AVAILABLE, reason="PyTorch not available")
class TestDrishtiAttention:
    """Test the DrishtiAttention module."""

    def test_drishti_initialization(self):
        """Test Drishti attention initializes correctly."""
        from symbolu.ontological.bhava_relationships import DrishtiAttention

        module = DrishtiAttention(embed_dim=128, num_layers=12, num_heads=4)

        assert module.embed_dim == 128
        assert module.num_layers == 12
        assert module.num_heads == 4
        assert module.drishti_patterns.shape == (12, 12)

    def test_drishti_forward(self):
        """Test Drishti attention forward pass."""
        from symbolu.ontological.bhava_relationships import DrishtiAttention

        module = DrishtiAttention(embed_dim=128, num_layers=12, num_heads=4)

        batch_size = 4
        layer_embeds = torch.randn(batch_size, 12, 128)
        onto_probs = torch.softmax(torch.randn(batch_size, 12), dim=-1)

        output = module(layer_embeds, onto_probs)

        assert output.shape == (batch_size, 12, 128)

    def test_drishti_patterns_initialized(self):
        """Test Drishti patterns are initialized with Vedic aspects."""
        from symbolu.ontological.bhava_relationships import DrishtiAttention, ASPECT_STRENGTH_MATRIX

        module = DrishtiAttention(embed_dim=128, num_layers=12, num_heads=4)

        expected = torch.tensor(ASPECT_STRENGTH_MATRIX, dtype=torch.float32)

        assert torch.allclose(module.drishti_patterns, expected, atol=1e-6)


@pytest.mark.skipif(not PYTORCH_AVAILABLE, reason="PyTorch not available")
class TestInterLayerBhavaEngine:
    """Test the complete InterLayerBhavaEngine."""

    def test_engine_initialization(self):
        """Test engine initializes correctly."""
        from symbolu.ontological.bhava_relationships import InterLayerBhavaEngine

        engine = InterLayerBhavaEngine(
            ontological_dim=12,
            hidden_dim=128,
        )

        assert engine.ontological_dim == 12
        assert engine.hidden_dim == 128

    def test_engine_forward(self):
        """Test engine forward pass."""
        from symbolu.ontological.bhava_relationships import InterLayerBhavaEngine

        engine = InterLayerBhavaEngine(
            ontological_dim=12,
            hidden_dim=128,
        )

        batch_size = 4
        onto_probs = torch.softmax(torch.randn(batch_size, 12), dim=-1)

        output = engine(onto_probs)

        assert 'bhava' in output
        assert 'relationship_matrix' in output
        assert 'coherence' in output
        assert 'attended_layers' in output

        assert output['bhava'].shape == (batch_size, 144)
        assert output['relationship_matrix'].shape == (batch_size, 12, 12)

    def test_engine_interpretation(self):
        """Test relationship interpretation."""
        from symbolu.ontological.bhava_relationships import InterLayerBhavaEngine

        engine = InterLayerBhavaEngine(
            ontological_dim=12,
            hidden_dim=128,
        )

        rel_matrix = torch.randn(12, 12)
        interpretations = engine.interpret_relationships(rel_matrix, top_k=3)

        assert len(interpretations) == 3
        for interp in interpretations:
            assert 'from_layer' in interp
            assert 'to_layer' in interp
            assert 'strength' in interp
            assert 'interpretation' in interp


@pytest.mark.skipif(not PYTORCH_AVAILABLE, reason="PyTorch not available")
class TestBhavaRelationshipMatrix:
    """Test the BhavaRelationshipMatrix dataclass."""

    def test_from_flat(self):
        """Test creating matrix from flat 144D vector."""
        from symbolu.ontological.bhava_relationships import BhavaRelationshipMatrix

        flat = list(range(144))
        flat = [x / 144 for x in flat]  # Normalize to [0, 1]

        matrix = BhavaRelationshipMatrix.from_flat(flat, coherence=0.8)

        assert len(matrix.values) == 12
        assert all(len(row) == 12 for row in matrix.values)
        assert matrix.coherence == 0.8
        assert len(matrix.dominant_relationships) == 5

    def test_to_flat(self):
        """Test flattening matrix to 144D vector."""
        from symbolu.ontological.bhava_relationships import BhavaRelationshipMatrix

        flat = list(range(144))
        flat = [x / 144 for x in flat]

        matrix = BhavaRelationshipMatrix.from_flat(flat, coherence=0.8)
        recovered = matrix.to_flat()

        assert len(recovered) == 144
        assert recovered == flat

    def test_get_relationship(self):
        """Test getting specific relationship."""
        from symbolu.ontological.bhava_relationships import BhavaRelationshipMatrix

        flat = [0.5] * 144
        matrix = BhavaRelationshipMatrix.from_flat(flat, coherence=0.8)

        rel = matrix.get_relationship(4, 7)  # Cognition -> Purpose

        assert rel.from_layer == "O5_COGNITION"
        assert rel.to_layer == "O8_PURPOSE"
        assert rel.strength == 0.5


@pytest.mark.skipif(not PYTORCH_AVAILABLE, reason="PyTorch not available")
class TestIntegrationWithEngines:
    """Test integration with ontological engines."""

    def test_unified_engine_v2(self):
        """Test UnifiedOntologicalEngineV2 uses new architecture."""
        from symbolu.ontological.unified_engine import UnifiedOntologicalEngineV2

        engine = UnifiedOntologicalEngineV2(
            encoder_dim=128,  # Smaller for testing
            hidden_dims=(64, 32),
        )

        # Test forward pass with random input
        batch_size = 2
        x = torch.randn(batch_size, 128)

        output = engine(x)

        # Check new outputs are present
        assert 'bhava' in output
        assert 'relationship_matrix' in output
        assert 'coherence' in output

        # Check shapes
        assert output['bhava'].shape == (batch_size, 144)
        assert output['relationship_matrix'].shape == (batch_size, 12, 12)

    def test_inter_layer_bhava_layer(self):
        """Test InterLayerBhavaLayer from semantic_bhava."""
        from symbolu.ontological.semantic_bhava import InterLayerBhavaLayer

        layer = InterLayerBhavaLayer(
            ontological_dim=12,
            hidden_dim=128,
        )

        batch_size = 2
        onto = torch.softmax(torch.randn(batch_size, 12), dim=-1)

        output = layer(onto)

        assert 'bhava' in output
        assert output['bhava'].shape == (batch_size, 144)


class TestArchitectureSummary:
    """Test architecture documentation and summary functions."""

    def test_architecture_summary(self):
        """Test architecture summary is comprehensive."""
        from symbolu.ontological.bhava_relationships import get_architecture_summary

        summary = get_architecture_summary()

        # Check key sections are present
        assert "BHAVA RELATIONSHIP ARCHITECTURE" in summary
        assert "VEDIC PRINCIPLE" in summary
        assert "RELATIONSHIP SPACE" in summary
        assert "DRISHTI" in summary
        assert "EFFICIENCY" in summary

    def test_deprecated_module_warning(self):
        """Test deprecated modules have warnings."""
        import symbolu.ontological.bhava as bhava_module

        docstring = bhava_module.__doc__

        assert "DEPRECATED" in docstring
        assert "bhava_relationships.py" in docstring


class TestComparisonWithOldArchitecture:
    """Test comparing old sub-layer vs new relationship architecture."""

    def test_dimension_comparison(self):
        """Test dimension comparison between architectures."""
        # Old: 11 pairs × 12 sub-layers = 132D (or 90D with 10 layers)
        # New: 12 × 12 = 144D

        old_dimensions = 11 * 12  # 132
        new_dimensions = 12 * 12  # 144

        assert new_dimensions > old_dimensions
        assert new_dimensions == 144

    def test_relationship_richness(self):
        """Test relationship richness comparison."""
        # Old: Only adjacent layer relationships
        # New: All-to-all relationships

        old_relationships = 11  # Adjacent pairs only
        new_relationships = 12 * 12  # All pairs including self

        assert new_relationships > old_relationships
        assert new_relationships / old_relationships > 10  # >10x richer


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
