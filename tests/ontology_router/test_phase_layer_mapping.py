"""
Tests for Phase to Ontological Layer Mapping
============================================

Verifies the deterministic mapping from Phase IDs to ontological layers.
"""

import pytest

from symbolu.ontology.layers.ontology_layer import (
    GATED_LAYERS,
    OntologicalLayer,
)
from symbolu.ontology.router.phase_layer_map import (
    PHASE_TO_LAYERS,
    VALID_PHASE_IDS,
    get_layers_for_phase,
    get_phases_for_layer,
    is_valid_phase_id,
)


class TestPhaseToLayerMapping:
    """Tests for the PHASE_TO_LAYERS mapping."""

    def test_all_phases_present(self) -> None:
        """Verify all required phases are in the mapping."""
        required_phases = {"1b", "2", "3", "4", "5", "6", "7", "8", "9"}
        assert required_phases == set(PHASE_TO_LAYERS.keys())

    def test_phase_1b_layers(self) -> None:
        """Phase 1b maps to TAGGING and FORMING."""
        layers = PHASE_TO_LAYERS["1b"]
        assert OntologicalLayer.IDENTITY in layers
        assert OntologicalLayer.STRUCTURE in layers
        assert len(layers) == 2

    def test_phase_2_layers(self) -> None:
        """Phase 2 maps to TAGGING and FORMING."""
        layers = PHASE_TO_LAYERS["2"]
        assert OntologicalLayer.IDENTITY in layers
        assert OntologicalLayer.STRUCTURE in layers
        assert len(layers) == 2

    def test_phase_3_layers(self) -> None:
        """Phase 3 maps to THINKING, REASONING, and DIRECTING."""
        layers = PHASE_TO_LAYERS["3"]
        assert OntologicalLayer.COGNITION in layers
        assert OntologicalLayer.REASONING in layers
        assert OntologicalLayer.AGENCY in layers
        assert len(layers) == 3

    def test_phase_4_layers(self) -> None:
        """Phase 4 maps to ACTING and THINKING."""
        layers = PHASE_TO_LAYERS["4"]
        assert OntologicalLayer.EXECUTION in layers
        assert OntologicalLayer.COGNITION in layers
        assert len(layers) == 2

    def test_phase_5_layers(self) -> None:
        """Phase 5 maps to FORMING and UNIFYING."""
        layers = PHASE_TO_LAYERS["5"]
        assert OntologicalLayer.STRUCTURE in layers
        assert OntologicalLayer.UNIFYING in layers
        assert len(layers) == 2

    def test_phase_6_layers(self) -> None:
        """Phase 6 maps to DIRECTING, META_OBSERVING, and PURPOSING."""
        layers = PHASE_TO_LAYERS["6"]
        assert OntologicalLayer.AGENCY in layers
        assert OntologicalLayer.WITNESSES in layers
        assert OntologicalLayer.PURPOSE in layers
        assert len(layers) == 3

    def test_phase_7_layers(self) -> None:
        """Phase 7 maps to ACTING, DIRECTING, and THINKING."""
        layers = PHASE_TO_LAYERS["7"]
        assert OntologicalLayer.EXECUTION in layers
        assert OntologicalLayer.AGENCY in layers
        assert OntologicalLayer.COGNITION in layers
        assert len(layers) == 3

    def test_phase_8_layers(self) -> None:
        """Phase 8 maps to META_OBSERVING and DIRECTING."""
        layers = PHASE_TO_LAYERS["8"]
        assert OntologicalLayer.WITNESSES in layers
        assert OntologicalLayer.AGENCY in layers
        assert len(layers) == 2

    def test_phase_9_layers(self) -> None:
        """Phase 9 maps to UNIFYING, REASONING, and ABSOLVING."""
        layers = PHASE_TO_LAYERS["9"]
        assert OntologicalLayer.UNIFYING in layers
        assert OntologicalLayer.REASONING in layers
        assert OntologicalLayer.ABSOLVING in layers
        assert len(layers) == 3

    def test_mapping_immutability(self) -> None:
        """Mapping values are frozensets (immutable)."""
        for layers in PHASE_TO_LAYERS.values():
            assert isinstance(layers, frozenset)


class TestGetLayersForPhase:
    """Tests for the get_layers_for_phase function."""

    def test_returns_tuple(self) -> None:
        """Function returns a tuple, not a list or set."""
        layers = get_layers_for_phase("3")
        assert isinstance(layers, tuple)

    def test_deterministic_ordering(self) -> None:
        """Layers are returned in canonical order (by enum value)."""
        layers = get_layers_for_phase("3")
        values = [layer.value for layer in layers]
        assert values == sorted(values)

    def test_invalid_phase_raises_keyerror(self) -> None:
        """Invalid phase ID raises KeyError."""
        with pytest.raises(KeyError) as exc_info:
            get_layers_for_phase("invalid")
        assert "invalid" in str(exc_info.value)

    def test_exclude_gated_by_default(self) -> None:
        """Gated layers (ABSOLVING) are excluded by default."""
        layers = get_layers_for_phase("9", include_gated=False)
        for layer in layers:
            assert layer not in GATED_LAYERS

    def test_include_gated_when_requested(self) -> None:
        """Gated layers are included when include_gated=True."""
        layers = get_layers_for_phase("9", include_gated=True)
        assert OntologicalLayer.ABSOLVING in layers


class TestIsValidPhaseId:
    """Tests for the is_valid_phase_id function."""

    def test_valid_phases(self) -> None:
        """All valid phases return True."""
        for phase_id in VALID_PHASE_IDS:
            assert is_valid_phase_id(phase_id) is True

    def test_invalid_phases(self) -> None:
        """Invalid phases return False."""
        assert is_valid_phase_id("invalid") is False
        assert is_valid_phase_id("0") is False
        assert is_valid_phase_id("10") is False
        assert is_valid_phase_id("") is False


class TestGetPhasesForLayer:
    """Tests for the get_phases_for_layer function."""

    def test_returns_tuple(self) -> None:
        """Function returns a tuple, not a list or set."""
        phases = get_phases_for_layer(OntologicalLayer.COGNITION)
        assert isinstance(phases, tuple)

    def test_deterministic_ordering(self) -> None:
        """Phases are returned in sorted order."""
        phases = get_phases_for_layer(OntologicalLayer.COGNITION)
        assert phases == tuple(sorted(phases))

    def test_thinking_layer_phases(self) -> None:
        """THINKING layer is used by phases 3, 4, and 7."""
        phases = get_phases_for_layer(OntologicalLayer.COGNITION)
        assert "3" in phases
        assert "4" in phases
        assert "7" in phases

    def test_absolving_layer_phases(self) -> None:
        """ABSOLVING layer is only used by phase 9."""
        phases = get_phases_for_layer(OntologicalLayer.ABSOLVING)
        assert phases == ("9",)
