"""
Phase-14: Character Deriver (Varna-Based)
=========================================

Derives cross-layer "character" propensities from phonemic structure
using the Varna Bridge Map (Sanskrit Varna Mala) instead of arbitrary heuristics.

This uses the actual phoneme-meaning mappings from:
    /docs/data/varna_bridge_map_v1.json

Each phoneme has a "bridge meaning" (e.g., ka=hope_pressure, ga=action_pressure)
which maps to ontological layers through semantic analysis.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "phase13_sandbox"))

from k1_schema import OntologicalLayer
from phoneme_extractor import PhonemeAnalysis

from varna_bridge import (
    VarnaBridgeMap,
    load_varna_bridge_map,
    arpabet_to_varna,
    get_bridge_propensities,
    BRIDGE_MEANING_TO_LAYER,
)


# =============================================================================
# Character Profile (same structure as original)
# =============================================================================

@dataclass(frozen=True)
class CharacterProfile:
    """
    Cross-layer character propensity profile.

    Represents how strongly a word resonates with each ontological layer
    based on its phonemic structure (via Varna bridge meanings).
    """
    word: str
    primary_layer: OntologicalLayer
    propensities: Dict[str, float]            # Layer name → propensity (0.0-1.0)
    dominant_secondary: OntologicalLayer
    varna_influences: Dict[str, float]        # Varna sound → contribution
    bridge_meanings: Tuple[str, ...]          # Bridge meanings from phonemes
    profile_hash: str

    def get_propensity(self, layer: OntologicalLayer) -> float:
        """Get propensity for a specific layer."""
        return self.propensities.get(layer.value, 0.0)

    def get_top_layers(self, n: int = 3) -> Tuple[Tuple[OntologicalLayer, float], ...]:
        """Get top N layers by propensity."""
        sorted_props = sorted(
            [(OntologicalLayer(k), v) for k, v in self.propensities.items()],
            key=lambda x: x[1],
            reverse=True
        )
        return tuple(sorted_props[:n])

    def get_resonance_layers(self, threshold: float = 0.5) -> Tuple[OntologicalLayer, ...]:
        """Get layers with propensity above threshold."""
        return tuple(
            OntologicalLayer(k) for k, v in self.propensities.items()
            if v >= threshold
        )


def compute_profile_hash(word: str, propensities: Dict[str, float]) -> str:
    """Compute deterministic hash for profile."""
    sorted_props = sorted(propensities.items())
    content = f"{word.lower()}|" + "|".join(f"{k}:{v:.3f}" for k, v in sorted_props)
    return hashlib.sha256(content.encode()).hexdigest()[:12]


# =============================================================================
# Varna-Based Character Deriver
# =============================================================================

@dataclass
class VarnaCharacterDeriver:
    """
    Derives cross-layer character profiles using Varna bridge meanings.

    Instead of arbitrary phoneme-category heuristics, this uses the
    Sanskrit Varna Mala mappings where each sound has a specific
    bridge meaning (e.g., ka=hope_pressure, ga=action_pressure).
    """
    _varna_map: VarnaBridgeMap

    def derive(
        self,
        analysis: PhonemeAnalysis,
        primary_layer: OntologicalLayer
    ) -> CharacterProfile:
        """
        Derive character profile from phonemic analysis using Varna meanings.

        Args:
            analysis: PhonemeAnalysis from phoneme extractor
            primary_layer: Primary layer from layer assigner

        Returns:
            CharacterProfile with cross-layer propensities based on Varna
        """
        phonemes = analysis.phonemes
        total_phonemes = len(phonemes)

        # Accumulate layer propensities from each phoneme's Varna meaning
        layer_scores: Dict[OntologicalLayer, float] = {
            layer: 0.0 for layer in OntologicalLayer
        }

        varna_contributions: Dict[str, float] = {}
        bridge_meanings_found: list = []

        for i, phoneme in enumerate(phonemes):
            # Convert ARPABET to Varna
            varna_sound = arpabet_to_varna(phoneme)
            if not varna_sound:
                continue

            # Get Varna entry
            entry = self._varna_map.get_entry(varna_sound)
            if not entry:
                continue

            # Record bridge meaning
            if entry.bridge_meaning:
                bridge_meanings_found.append(entry.bridge_meaning)

            # Get propensities for this Varna sound's bridge meaning
            propensities = get_bridge_propensities(entry.bridge_meaning)

            # Position weighting: initial phonemes have more impact
            position_weight = 1.3 if i == 0 else (1.1 if i == total_phonemes - 1 else 1.0)

            # Add to layer scores
            for layer, prop in propensities.items():
                layer_scores[layer] += prop * position_weight

            # Track Varna contribution
            varna_contributions[varna_sound] = (
                varna_contributions.get(varna_sound, 0.0) + position_weight
            )

        # Normalize scores to 0.0-1.0
        if total_phonemes > 0 and any(layer_scores.values()):
            max_score = max(layer_scores.values())
            if max_score > 0:
                propensities = {
                    layer.value: min(1.0, score / max_score)
                    for layer, score in layer_scores.items()
                }
            else:
                propensities = {layer.value: 0.5 for layer in OntologicalLayer}
        else:
            propensities = {layer.value: 0.5 for layer in OntologicalLayer}

        # Boost primary layer (it was assigned for good reason)
        propensities[primary_layer.value] = min(
            1.0,
            propensities.get(primary_layer.value, 0.5) * 1.1
        )

        # Find dominant secondary layer
        secondary_scores = [
            (layer, score) for layer, score in propensities.items()
            if layer != primary_layer.value
        ]
        if secondary_scores:
            dominant_secondary = OntologicalLayer(
                max(secondary_scores, key=lambda x: x[1])[0]
            )
        else:
            dominant_secondary = primary_layer

        # Normalize Varna contributions
        total_contrib = sum(varna_contributions.values()) or 1.0
        varna_influences = {
            varna: contrib / total_contrib
            for varna, contrib in varna_contributions.items()
        }

        profile_hash = compute_profile_hash(analysis.word, propensities)

        return CharacterProfile(
            word=analysis.word,
            primary_layer=primary_layer,
            propensities=propensities,
            dominant_secondary=dominant_secondary,
            varna_influences=varna_influences,
            bridge_meanings=tuple(bridge_meanings_found),
            profile_hash=profile_hash,
        )

    def derive_batch(
        self,
        analyses: Tuple[PhonemeAnalysis, ...],
        assignments: Tuple[OntologicalLayer, ...]
    ) -> Tuple[CharacterProfile, ...]:
        """Derive character profiles for multiple words."""
        if len(analyses) != len(assignments):
            raise ValueError("Analyses and assignments must have same length")
        return tuple(
            self.derive(a, l) for a, l in zip(analyses, assignments)
        )


# =============================================================================
# Factory Functions
# =============================================================================

_cached_varna_map: Optional[VarnaBridgeMap] = None


def create_varna_deriver() -> VarnaCharacterDeriver:
    """Create character deriver using Varna bridge map."""
    global _cached_varna_map
    if _cached_varna_map is None:
        _cached_varna_map = load_varna_bridge_map()
    return VarnaCharacterDeriver(_varna_map=_cached_varna_map)


# =============================================================================
# Comparison Utility
# =============================================================================

def compare_characters(
    profile1: CharacterProfile,
    profile2: CharacterProfile
) -> float:
    """
    Compute similarity between two character profiles.

    Returns cosine similarity (0.0-1.0) of propensity vectors.
    """
    layers = [layer.value for layer in OntologicalLayer]

    vec1 = [profile1.propensities.get(l, 0.0) for l in layers]
    vec2 = [profile2.propensities.get(l, 0.0) for l in layers]

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    mag1 = sum(a * a for a in vec1) ** 0.5
    mag2 = sum(b * b for b in vec2) ** 0.5

    if mag1 == 0 or mag2 == 0:
        return 0.0

    return dot_product / (mag1 * mag2)


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    "CharacterProfile",
    "VarnaCharacterDeriver",
    "create_varna_deriver",
    "compare_characters",
    "compute_profile_hash",
]
