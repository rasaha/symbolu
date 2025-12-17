"""
Phase-14: Varna Bridge Loader
=============================

Loads phoneme-to-meaning mappings from varna_bridge_map_v1.json
and maps bridge meanings to ontological layers.

This replaces the arbitrary heuristics with your actual Varna Mala mappings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "phase13_sandbox"))

from k1_schema import OntologicalLayer


# =============================================================================
# Varna Data Path
# =============================================================================

VARNA_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "varna_bridge_map_v1.json"


# =============================================================================
# Bridge Meaning → Ontological Layer Mapping
# =============================================================================

# Map bridge meanings to primary ontological layer
# These mappings are based on the semantic nature of each bridge meaning

BRIDGE_MEANING_TO_LAYER: Dict[str, OntologicalLayer] = {
    # Vowels
    "birth_of_cognition": OntologicalLayer.O1_THINKING,
    "practical_cognition": OntologicalLayer.O6_REASONING,
    "self_doing": OntologicalLayer.O3_ACTING,
    "closure_completion": OntologicalLayer.O10_ABSOLVING,
    "contraction_focus": OntologicalLayer.O4_TAGGING,

    # Ka Varga - Throat sounds (gutturals)
    "hope_pressure": OntologicalLayer.O7_PURPOSING,
    "worry_pressure": OntologicalLayer.O8_META_OBSERVING,
    "action_pressure": OntologicalLayer.O3_ACTING,
    "attachment_pressure": OntologicalLayer.O9_UNIFYING,
    "vanity_pressure": OntologicalLayer.O4_TAGGING,

    # Ca Varga - Palatal sounds
    "scatter_pressure": OntologicalLayer.O5_DIRECTING,
    "nervous_pressure": OntologicalLayer.O8_META_OBSERVING,
    "greed_pressure": OntologicalLayer.O7_PURPOSING,
    "hypocrisy_pressure": OntologicalLayer.O4_TAGGING,

    # Tta Varga - Retroflex sounds
    "overstatement_pressure": OntologicalLayer.O5_DIRECTING,
    "repentance_pressure": OntologicalLayer.O10_ABSOLVING,
    "shyness_pressure": OntologicalLayer.O8_META_OBSERVING,
    "cruelty_pressure": OntologicalLayer.O3_ACTING,
    "envy_pressure": OntologicalLayer.O4_TAGGING,

    # Ta Varga - Dental sounds
    "inertia_pressure": OntologicalLayer.O4_TAGGING,
    "melancholy_pressure": OntologicalLayer.O1_THINKING,
    "irritability_pressure": OntologicalLayer.O3_ACTING,
    "craving_pressure": OntologicalLayer.O7_PURPOSING,

    # Pa Varga - Labial sounds
    "revulsion_pressure": OntologicalLayer.O10_ABSOLVING,
    "fear_pressure": OntologicalLayer.O8_META_OBSERVING,
    "indifference_pressure": OntologicalLayer.O4_TAGGING,
    "delusion_pressure": OntologicalLayer.O1_THINKING,
    "indulgence_pressure": OntologicalLayer.O3_ACTING,

    # Semi-vowels
    "distrust_pressure": OntologicalLayer.O8_META_OBSERVING,
    "destruction_pressure": OntologicalLayer.O10_ABSOLVING,
    "external_dharma_pressure": OntologicalLayer.O6_REASONING,

    # Sibilants
    "material_greed_pressure": OntologicalLayer.O7_PURPOSING,
    "lust_confusion_pressure": OntologicalLayer.O3_ACTING,
    "escape_pressure": OntologicalLayer.O10_ABSOLVING,

    # Aspirate
    "ignorance_pressure": OntologicalLayer.O1_THINKING,

    # Conjunct
    "false_knowledge_pressure": OntologicalLayer.O6_REASONING,
}


# =============================================================================
# Cross-Layer Propensity from Bridge Meaning
# =============================================================================

# Each bridge meaning has propensities across all 10 layers
# Primary layer gets 1.0, related layers get partial values

def get_bridge_propensities(bridge_meaning: str) -> Dict[OntologicalLayer, float]:
    """
    Get cross-layer propensities for a bridge meaning.

    Returns weights for all 10 layers based on the semantic nature
    of the bridge meaning.
    """
    primary = BRIDGE_MEANING_TO_LAYER.get(bridge_meaning)
    if not primary:
        # Unknown meaning - neutral propensities
        return {layer: 0.5 for layer in OntologicalLayer}

    # Start with base propensities
    propensities = {layer: 0.3 for layer in OntologicalLayer}

    # Primary layer gets full weight
    propensities[primary] = 1.0

    # Add secondary propensities based on meaning category
    if "cognition" in bridge_meaning or "knowledge" in bridge_meaning:
        propensities[OntologicalLayer.O1_THINKING] = max(propensities[OntologicalLayer.O1_THINKING], 0.8)
        propensities[OntologicalLayer.O6_REASONING] = max(propensities[OntologicalLayer.O6_REASONING], 0.7)

    if "action" in bridge_meaning or "doing" in bridge_meaning:
        propensities[OntologicalLayer.O3_ACTING] = max(propensities[OntologicalLayer.O3_ACTING], 0.8)
        propensities[OntologicalLayer.O5_DIRECTING] = max(propensities[OntologicalLayer.O5_DIRECTING], 0.6)

    if "completion" in bridge_meaning or "escape" in bridge_meaning or "destruction" in bridge_meaning:
        propensities[OntologicalLayer.O10_ABSOLVING] = max(propensities[OntologicalLayer.O10_ABSOLVING], 0.8)

    if "attachment" in bridge_meaning:
        propensities[OntologicalLayer.O9_UNIFYING] = max(propensities[OntologicalLayer.O9_UNIFYING], 0.8)

    if "pressure" in bridge_meaning:
        # Most pressures have some directing aspect
        propensities[OntologicalLayer.O5_DIRECTING] = max(propensities[OntologicalLayer.O5_DIRECTING], 0.5)

    if "hope" in bridge_meaning or "greed" in bridge_meaning or "craving" in bridge_meaning:
        propensities[OntologicalLayer.O7_PURPOSING] = max(propensities[OntologicalLayer.O7_PURPOSING], 0.8)

    if "worry" in bridge_meaning or "fear" in bridge_meaning or "nervous" in bridge_meaning:
        propensities[OntologicalLayer.O8_META_OBSERVING] = max(propensities[OntologicalLayer.O8_META_OBSERVING], 0.7)

    return propensities


# =============================================================================
# Varna Data Structure
# =============================================================================

@dataclass(frozen=True)
class VarnaEntry:
    """Single entry from varna bridge map."""
    sound: str
    sound_type: str  # "vowel" or "consonant"
    bridge_meaning: str
    aspirated: bool
    varna_group: str
    primary_layer: OntologicalLayer
    propensities: Dict[str, float]  # layer.value -> propensity


@dataclass(frozen=True)
class VarnaBridgeMap:
    """Complete varna bridge map."""
    vowels: Dict[str, VarnaEntry]
    consonants: Dict[str, VarnaEntry]

    def get_entry(self, sound: str) -> Optional[VarnaEntry]:
        """Get entry by sound."""
        sound_lower = sound.lower()
        if sound_lower in self.vowels:
            return self.vowels[sound_lower]
        if sound_lower in self.consonants:
            return self.consonants[sound_lower]
        return None

    def get_layer(self, sound: str) -> Optional[OntologicalLayer]:
        """Get primary layer for a sound."""
        entry = self.get_entry(sound)
        return entry.primary_layer if entry else None


# =============================================================================
# Loader
# =============================================================================

def load_varna_bridge_map(path: Optional[Path] = None) -> VarnaBridgeMap:
    """
    Load varna bridge map from JSON file.

    Args:
        path: Path to JSON file. Defaults to standard location.

    Returns:
        VarnaBridgeMap with all entries
    """
    if path is None:
        path = VARNA_DATA_PATH

    with open(path, "r") as f:
        data = json.load(f)

    vowels: Dict[str, VarnaEntry] = {}
    consonants: Dict[str, VarnaEntry] = {}

    # Process vowels
    for sound, info in data.get("vowels", {}).items():
        bridge_meaning = info.get("bridge_meaning", "")
        primary_layer = BRIDGE_MEANING_TO_LAYER.get(bridge_meaning, OntologicalLayer.O4_TAGGING)
        propensities = get_bridge_propensities(bridge_meaning)

        vowels[sound] = VarnaEntry(
            sound=sound,
            sound_type="vowel",
            bridge_meaning=bridge_meaning,
            aspirated=False,
            varna_group="vowel",
            primary_layer=primary_layer,
            propensities={k.value: v for k, v in propensities.items()},
        )

    # Process consonants
    for sound, info in data.get("consonants", {}).items():
        bridge_meaning = info.get("bridge_meaning", "")
        primary_layer = BRIDGE_MEANING_TO_LAYER.get(bridge_meaning, OntologicalLayer.O4_TAGGING)
        propensities = get_bridge_propensities(bridge_meaning)

        consonants[sound] = VarnaEntry(
            sound=sound,
            sound_type="consonant",
            bridge_meaning=bridge_meaning,
            aspirated=info.get("aspirated", False),
            varna_group=info.get("varna_group", ""),
            primary_layer=primary_layer,
            propensities={k.value: v for k, v in propensities.items()},
        )

    return VarnaBridgeMap(vowels=vowels, consonants=consonants)


# =============================================================================
# ARPABET to Varna Mapping
# =============================================================================

# Map ARPABET phonemes to closest Varna sounds
ARPABET_TO_VARNA: Dict[str, str] = {
    # Vowels
    "AA": "a", "AE": "a", "AH": "a",
    "AO": "o", "AW": "o", "AY": "a",
    "EH": "e", "ER": "a", "EY": "e",
    "IH": "i", "IY": "i",
    "OW": "o", "OY": "o",
    "UH": "u", "UW": "u",

    # Plosives (Ka/Ta/Pa varga)
    "K": "ka", "G": "ga",
    "T": "ta", "D": "da",
    "P": "pa", "B": "ba",

    # Affricates (Ca varga)
    "CH": "ca", "JH": "ja",

    # Fricatives
    "F": "pha", "V": "va",
    "TH": "tha", "DH": "dha",
    "S": "sa", "Z": "ja",
    "SH": "sha", "ZH": "sha",
    "HH": "ha",

    # Nasals
    "M": "ma", "N": "na", "NG": "nga",

    # Liquids/Semi-vowels
    "L": "la", "R": "ra",
    "W": "va", "Y": "ya",
}


def arpabet_to_varna(phoneme: str) -> Optional[str]:
    """Convert ARPABET phoneme to closest Varna sound."""
    # Remove stress markers
    clean = phoneme.rstrip("012")
    return ARPABET_TO_VARNA.get(clean)


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    "VarnaEntry",
    "VarnaBridgeMap",
    "load_varna_bridge_map",
    "arpabet_to_varna",
    "get_bridge_propensities",
    "BRIDGE_MEANING_TO_LAYER",
    "ARPABET_TO_VARNA",
    "VARNA_DATA_PATH",
]
