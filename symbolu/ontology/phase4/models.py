"""
Phase-4 Data Models
===================

Immutable dataclasses for Phase-4 ontology execution outputs.

All models are:
    - Frozen (immutable after construction)
    - Hashable (can be used in sets/dict keys)
    - Serializable (JSON-compatible fields)
"""

from dataclasses import dataclass
from typing import Tuple, FrozenSet


@dataclass(frozen=True)
class VarnaLayerInteraction:
    """
    The output of a Phase-4 (varna, layer) lookup.

    All fields are required. Phase-4 fails if any field is missing
    from the frozen ontology files.

    Attributes:
        varna: The input varna token (e.g., "ka", "a", "sha")
        layer: The input ontological layer (e.g., "O1_ACTING")
        manifestation_positive: Healthy expression when varna interacts with layer
        manifestation_negative: Distorted expression
        distortion_vector: Direction of negative manifestation ("lateral", "downward")
        sublimate_vector: Direction of transcendence ("upward", "terminating")
    """

    varna: str
    layer: str
    manifestation_positive: str
    manifestation_negative: str
    distortion_vector: str
    sublimate_vector: str

    def __post_init__(self) -> None:
        """Validate that all fields are non-empty strings."""
        for field_name in (
            "varna",
            "layer",
            "manifestation_positive",
            "manifestation_negative",
            "distortion_vector",
            "sublimate_vector",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise TypeError(
                    f"Field '{field_name}' must be str, got {type(value).__name__}"
                )
            if not value.strip():
                raise ValueError(f"Field '{field_name}' must not be empty or whitespace")

    def to_dict(self) -> dict:
        """
        Convert to plain dict for serialization.

        Returns:
            Dict with all fields.
        """
        return {
            "varna": self.varna,
            "layer": self.layer,
            "manifestation_positive": self.manifestation_positive,
            "manifestation_negative": self.manifestation_negative,
            "distortion_vector": self.distortion_vector,
            "sublimate_vector": self.sublimate_vector,
        }


@dataclass(frozen=True)
class OntologyValidationReport:
    """
    Report from Phase-4 ontology validation.

    Attributes:
        valid: True if all three frozen files are consistent
        varna_count: Number of varnas in bridge map
        layer_count: Number of layers in ontological layers
        interaction_count: Number of (varna, layer) pairs in interaction map
        missing_varnas_in_interactions: Varnas referenced in interactions but not in bridge map
        missing_layers_in_interactions: Layers referenced in interactions but not in ontological layers
        missing_interactions: (varna, layer) pairs that should exist but don't
        errors: Human-readable error messages
    """

    valid: bool
    varna_count: int
    layer_count: int
    interaction_count: int
    missing_varnas_in_interactions: Tuple[str, ...]
    missing_layers_in_interactions: Tuple[str, ...]
    missing_interactions: Tuple[Tuple[str, str], ...]
    errors: Tuple[str, ...]

    @classmethod
    def success(
        cls,
        varna_count: int,
        layer_count: int,
        interaction_count: int
    ) -> "OntologyValidationReport":
        """
        Create a successful validation report.

        Args:
            varna_count: Number of varnas in bridge map
            layer_count: Number of layers
            interaction_count: Number of interactions

        Returns:
            A valid OntologyValidationReport
        """
        return cls(
            valid=True,
            varna_count=varna_count,
            layer_count=layer_count,
            interaction_count=interaction_count,
            missing_varnas_in_interactions=(),
            missing_layers_in_interactions=(),
            missing_interactions=(),
            errors=(),
        )

    @classmethod
    def failure(
        cls,
        varna_count: int,
        layer_count: int,
        interaction_count: int,
        missing_varnas: Tuple[str, ...] = (),
        missing_layers: Tuple[str, ...] = (),
        missing_interactions: Tuple[Tuple[str, str], ...] = (),
        errors: Tuple[str, ...] = (),
    ) -> "OntologyValidationReport":
        """
        Create a failed validation report.

        Args:
            varna_count: Number of varnas in bridge map
            layer_count: Number of layers
            interaction_count: Number of interactions
            missing_varnas: Varnas in interactions but not in bridge map
            missing_layers: Layers in interactions but not in ontological layers
            missing_interactions: Missing (varna, layer) pairs
            errors: Human-readable error descriptions

        Returns:
            An invalid OntologyValidationReport
        """
        return cls(
            valid=False,
            varna_count=varna_count,
            layer_count=layer_count,
            interaction_count=interaction_count,
            missing_varnas_in_interactions=missing_varnas,
            missing_layers_in_interactions=missing_layers,
            missing_interactions=missing_interactions,
            errors=errors,
        )


@dataclass(frozen=True)
class VarnaInfo:
    """
    Information about a single varna from the bridge map.

    Attributes:
        varna: The varna token (e.g., "ka", "a")
        varna_type: "vowel" or "consonant"
        bridge_meaning: The pre-semantic bridge meaning
        varna_group: For consonants, the varga group (e.g., "ka_varga")
        aspirated: For consonants, whether it's aspirated
    """

    varna: str
    varna_type: str  # "vowel" or "consonant"
    bridge_meaning: str
    varna_group: str  # Empty string for vowels
    aspirated: bool  # False for vowels


@dataclass(frozen=True)
class LayerInfo:
    """
    Information about an ontological layer.

    Attributes:
        layer_id: The layer identifier (e.g., "O1_ACTING")
        experiential_role: The functional description
        kosha_anchor: The ontological sheath mapping
        polarity_tendency: "constructive", "neutral", or "degenerative"
        prev_layer: Previous layer in sequence (None for O1)
        next_layer: Next layer in sequence (None for O10)
    """

    layer_id: str
    experiential_role: str
    kosha_anchor: str
    polarity_tendency: str
    prev_layer: str  # Empty string if None
    next_layer: str  # Empty string if None
