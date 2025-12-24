"""
Experiment Pack v1: Phoneme-Only Router (Grounded)
==================================================

EXPERIMENT_ONLY = True

WARNING: This file MUST NOT be used as ontology source of truth.
This is experimental validation code, NOT production infrastructure.

GROUNDING COMPLIANCE:
    This module loads phoneme/varna meaning EXCLUSIVELY from:
        docs/data/varna_bridge_map_v1.json

    NO heuristic phoneme classification (IPA, SoundClass, vowel height/backness).

FAIL-CLOSED BEHAVIOR:
    Unknown varna/phoneme → explicit UNKNOWN and recorded as such.
    No silent defaults for grounded mapping steps.

This router:
    1. Loads varnas from the authoritative JSON file
    2. Maps word characters to varnas (deterministically)
    3. Derives bridge_meanings from varnas
    4. Routes to OntologicalLayers based on bridge_meaning composition
    5. Produces a structured audit trace
"""

EXPERIMENT_ONLY = True

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

# Import OntologicalLayer from k1_schema
sys.path.insert(0, str(Path(__file__).parent.parent / "phase13_sandbox"))
from k1_schema import OntologicalLayer


# =============================================================================
# Constants: Path to Grounded Varna Bridge Map
# =============================================================================

# Resolve path relative to this file's location
_THIS_DIR = Path(__file__).resolve().parent
_VARNA_BRIDGE_MAP_PATH = _THIS_DIR.parent.parent.parent / "docs" / "data" / "varna_bridge_map_v1.json"

# Fallback for different execution contexts
if not _VARNA_BRIDGE_MAP_PATH.exists():
    _VARNA_BRIDGE_MAP_PATH = Path("docs/data/varna_bridge_map_v1.json")


# =============================================================================
# Routing Status Enum
# =============================================================================

class RoutingStatus(Enum):
    """Status of routing operation."""
    SUCCESS = "SUCCESS"
    PARTIAL_UNKNOWN = "PARTIAL_UNKNOWN"  # Some varnas unknown
    ALL_UNKNOWN = "ALL_UNKNOWN"          # No varnas recognized
    EMPTY_INPUT = "EMPTY_INPUT"          # No input word/phonemes


# =============================================================================
# Varna Match Result
# =============================================================================

@dataclass(frozen=True)
class VarnaMatch:
    """Result of matching a character sequence to a varna."""
    varna_key: str                      # e.g., "ka", "a", "sha"
    varna_type: str                     # "vowel" or "consonant"
    bridge_meaning: str                 # e.g., "hope_pressure"
    varna_group: Optional[str]          # e.g., "ka_varga" (consonants only)
    aspirated: Optional[bool]           # True/False for consonants
    source_chars: str                   # Original characters matched
    is_unknown: bool = False            # True if this is a fallback UNKNOWN


# =============================================================================
# Bridge Meaning to Layer Routing Map
# =============================================================================

# This mapping is EXPLICIT and GROUNDED - derived from the semantic
# content of bridge_meaning names in varna_bridge_map_v1.json
#
# Design principles:
#   - Cognitive meanings → O5_COGNITION
#   - Formation/creation → O4_STRUCTURE
#   - Action/doing → O3_EXECUTION
#   - Identification/labeling → O4_TAGGING
#   - Direction/guidance → O6_AGENCY
#   - Causation/reasoning → O7_REASONING
#   - Purpose/intention → O8_PURPOSE
#   - Observation/awareness → O9_WITNESSES
#   - Integration/unity → O10_UNIFYING
#   - Resolution/release → O12_ABSOLVING

BRIDGE_MEANING_TO_LAYER: Dict[str, OntologicalLayer] = {
    # Vowel bridge meanings
    "birth_of_cognition": OntologicalLayer.O5_COGNITION,
    "practical_cognition": OntologicalLayer.O5_COGNITION,
    "self_doing": OntologicalLayer.O3_EXECUTION,
    "closure_completion": OntologicalLayer.O12_ABSOLVING,
    "contraction_focus": OntologicalLayer.O4_STRUCTURE,

    # Ka-varga consonants (throat)
    "hope_pressure": OntologicalLayer.O8_PURPOSE,
    "worry_pressure": OntologicalLayer.O5_COGNITION,
    "action_pressure": OntologicalLayer.O3_EXECUTION,
    "attachment_pressure": OntologicalLayer.O4_TAGGING,
    "vanity_pressure": OntologicalLayer.O4_TAGGING,

    # Ca-varga consonants (palate)
    "scatter_pressure": OntologicalLayer.O7_REASONING,
    "nervous_pressure": OntologicalLayer.O9_WITNESSES,
    "greed_pressure": OntologicalLayer.O8_PURPOSE,
    "hypocrisy_pressure": OntologicalLayer.O6_AGENCY,

    # Tta-varga consonants (retroflex)
    "overstatement_pressure": OntologicalLayer.O6_AGENCY,
    "repentance_pressure": OntologicalLayer.O12_ABSOLVING,
    "shyness_pressure": OntologicalLayer.O9_WITNESSES,
    "cruelty_pressure": OntologicalLayer.O6_AGENCY,
    "envy_pressure": OntologicalLayer.O4_TAGGING,

    # Ta-varga consonants (dental)
    "inertia_pressure": OntologicalLayer.O7_REASONING,
    "melancholy_pressure": OntologicalLayer.O9_WITNESSES,
    "irritability_pressure": OntologicalLayer.O3_EXECUTION,
    "craving_pressure": OntologicalLayer.O8_PURPOSE,

    # Pa-varga consonants (labial)
    "revulsion_pressure": OntologicalLayer.O9_WITNESSES,
    "fear_pressure": OntologicalLayer.O9_WITNESSES,
    "indifference_pressure": OntologicalLayer.O12_ABSOLVING,
    "delusion_pressure": OntologicalLayer.O5_COGNITION,
    "indulgence_pressure": OntologicalLayer.O8_PURPOSE,

    # Semi-vowels (ya, ra, la, va)
    "distrust_pressure": OntologicalLayer.O9_WITNESSES,
    "destruction_pressure": OntologicalLayer.O3_EXECUTION,
    "external_dharma_pressure": OntologicalLayer.O10_UNIFYING,

    # Sibilants (sha, ssa, sa)
    "material_greed_pressure": OntologicalLayer.O8_PURPOSE,
    "lust_confusion_pressure": OntologicalLayer.O4_STRUCTURE,
    "escape_pressure": OntologicalLayer.O12_ABSOLVING,

    # Aspirate and conjunct
    "ignorance_pressure": OntologicalLayer.O5_COGNITION,
    "false_knowledge_pressure": OntologicalLayer.O7_REASONING,
}

# UNKNOWN bridge meaning routing - explicitly routes to a neutral layer
UNKNOWN_BRIDGE_MEANING = "UNKNOWN"
UNKNOWN_LAYER = OntologicalLayer.O4_TAGGING  # Neutral fallback


# =============================================================================
# Varna Bridge Map Loader
# =============================================================================

@dataclass
class VarnaBridgeMap:
    """
    Loaded varna bridge map from varna_bridge_map_v1.json.

    GROUNDING: This is the SOLE source of truth for varna meanings.
    """
    meta: Dict[str, Any]
    vowels: Dict[str, Dict[str, Any]]
    consonants: Dict[str, Dict[str, Any]]
    _loaded_from: str = ""

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "VarnaBridgeMap":
        """
        Load varna bridge map from JSON file.

        Args:
            path: Optional path override. Defaults to canonical location.

        Returns:
            Loaded VarnaBridgeMap

        Raises:
            FileNotFoundError: If varna bridge map file not found
            json.JSONDecodeError: If file is not valid JSON
        """
        load_path = path or _VARNA_BRIDGE_MAP_PATH

        if not load_path.exists():
            raise FileNotFoundError(
                f"GROUNDING FAILURE: varna_bridge_map_v1.json not found at {load_path}. "
                f"This file is required for grounded phoneme routing."
            )

        with open(load_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(
            meta=data.get("meta", {}),
            vowels=data.get("vowels", {}),
            consonants=data.get("consonants", {}),
            _loaded_from=str(load_path),
        )

    def get_varna(self, key: str) -> Optional[Dict[str, Any]]:
        """Get varna data by key, checking both vowels and consonants."""
        if key in self.vowels:
            return {"type": "vowel", **self.vowels[key]}
        if key in self.consonants:
            return {"type": "consonant", **self.consonants[key]}
        return None

    def get_all_varna_keys(self) -> FrozenSet[str]:
        """Get all known varna keys."""
        return frozenset(self.vowels.keys()) | frozenset(self.consonants.keys())

    def get_bridge_meaning(self, key: str) -> Optional[str]:
        """Get bridge_meaning for a varna key."""
        varna = self.get_varna(key)
        if varna:
            return varna.get("bridge_meaning")
        return None


# Global singleton for loaded map (lazy initialization)
_LOADED_VARNA_MAP: Optional[VarnaBridgeMap] = None


def get_varna_bridge_map() -> VarnaBridgeMap:
    """Get the singleton varna bridge map instance."""
    global _LOADED_VARNA_MAP
    if _LOADED_VARNA_MAP is None:
        _LOADED_VARNA_MAP = VarnaBridgeMap.load()
    return _LOADED_VARNA_MAP


def reset_varna_bridge_map() -> None:
    """Reset the singleton (for testing)."""
    global _LOADED_VARNA_MAP
    _LOADED_VARNA_MAP = None


# =============================================================================
# Word to Varna Mapping
# =============================================================================

def word_to_varnas(
    word: str,
    varna_map: Optional[VarnaBridgeMap] = None,
) -> Tuple[VarnaMatch, ...]:
    """
    Map a word to its constituent varnas.

    This uses a simple character-based approach where:
    - Single vowels (a, e, i, o, u) are matched directly
    - Consonant clusters are matched greedily (longest match first)

    FAIL-CLOSED: Unknown characters produce VarnaMatch with is_unknown=True.

    Args:
        word: Input word (any language, will be lowercased)
        varna_map: Optional varna map (uses singleton if not provided)

    Returns:
        Tuple of VarnaMatch objects
    """
    if not word:
        return ()

    varna_map = varna_map or get_varna_bridge_map()
    word_lower = word.lower().strip()

    # Build lookup for consonants (sorted by length descending for greedy matching)
    consonant_keys = sorted(varna_map.consonants.keys(), key=len, reverse=True)
    vowel_keys = set(varna_map.vowels.keys())

    matches: List[VarnaMatch] = []
    i = 0

    while i < len(word_lower):
        char = word_lower[i]
        matched = False

        # Try consonant clusters (longest first)
        for consonant_key in consonant_keys:
            if word_lower[i:].startswith(consonant_key):
                varna_data = varna_map.consonants[consonant_key]
                matches.append(VarnaMatch(
                    varna_key=consonant_key,
                    varna_type="consonant",
                    bridge_meaning=varna_data.get("bridge_meaning", UNKNOWN_BRIDGE_MEANING),
                    varna_group=varna_data.get("varna_group"),
                    aspirated=varna_data.get("aspirated"),
                    source_chars=consonant_key,
                    is_unknown=False,
                ))
                i += len(consonant_key)
                matched = True
                break

        if not matched and char in vowel_keys:
            # Match vowel
            varna_data = varna_map.vowels[char]
            matches.append(VarnaMatch(
                varna_key=char,
                varna_type="vowel",
                bridge_meaning=varna_data.get("bridge_meaning", UNKNOWN_BRIDGE_MEANING),
                varna_group=None,
                aspirated=None,
                source_chars=char,
                is_unknown=False,
            ))
            i += 1
            matched = True

        if not matched:
            # FAIL-CLOSED: Record unknown character
            matches.append(VarnaMatch(
                varna_key=f"UNKNOWN_{char}",
                varna_type="unknown",
                bridge_meaning=UNKNOWN_BRIDGE_MEANING,
                varna_group=None,
                aspirated=None,
                source_chars=char,
                is_unknown=True,
            ))
            i += 1

    return tuple(matches)


# =============================================================================
# Routing Trace
# =============================================================================

@dataclass(frozen=True)
class RoutingTrace:
    """
    Structured audit trace of the routing decision.

    This provides full transparency into how a routing decision was made.
    """
    word: str
    varna_matches: Tuple[VarnaMatch, ...]
    bridge_meanings: Tuple[str, ...]
    layer_votes: Dict[str, float]  # layer.value -> vote count
    unknown_count: int
    total_varnas: int
    final_layer: Optional[OntologicalLayer]
    confidence: float
    status: RoutingStatus
    routing_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary for serialization."""
        return {
            "word": self.word,
            "varna_matches": [
                {
                    "varna_key": m.varna_key,
                    "varna_type": m.varna_type,
                    "bridge_meaning": m.bridge_meaning,
                    "varna_group": m.varna_group,
                    "is_unknown": m.is_unknown,
                    "source_chars": m.source_chars,
                }
                for m in self.varna_matches
            ],
            "bridge_meanings": list(self.bridge_meanings),
            "layer_votes": self.layer_votes,
            "unknown_count": self.unknown_count,
            "total_varnas": self.total_varnas,
            "final_layer": self.final_layer.value if self.final_layer else None,
            "confidence": self.confidence,
            "status": self.status.value,
            "routing_hash": self.routing_hash,
        }


# =============================================================================
# Phoneme-Only Router
# =============================================================================

@dataclass(frozen=True)
class PhonemeOnlyRouter:
    """
    Phoneme-only router using grounded varna bridge map.

    CRITICAL:
        - Does NOT use POS tagging
        - Does NOT use semantic lexicons
        - Routes purely based on phoneme/varna composition
        - Fails closed on unknown varnas

    GROUNDING:
        - All varna meanings from varna_bridge_map_v1.json
        - Bridge meaning to layer mapping is explicit and auditable
    """
    varna_map: VarnaBridgeMap
    ablation_mode: str = "full"  # "full", "no_meaning", "randomized"
    _randomized_meanings: Optional[Dict[str, str]] = None

    @classmethod
    def create(
        cls,
        ablation_mode: str = "full",
        randomized_meanings: Optional[Dict[str, str]] = None,
    ) -> "PhonemeOnlyRouter":
        """
        Create a phoneme-only router.

        Args:
            ablation_mode: One of:
                - "full": Use full bridge_meaning for routing
                - "no_meaning": Use only varna identity, ignore bridge_meaning
                - "randomized": Use randomized bridge_meaning mapping
            randomized_meanings: For "randomized" mode, mapping of original to randomized meanings

        Returns:
            Configured PhonemeOnlyRouter
        """
        return cls(
            varna_map=get_varna_bridge_map(),
            ablation_mode=ablation_mode,
            _randomized_meanings=randomized_meanings,
        )

    def route(
        self,
        word: str,
        phonemes: Optional[Tuple[str, ...]] = None,
    ) -> Tuple[Optional[OntologicalLayer], RoutingTrace]:
        """
        Route a word to an ontological layer using phoneme-only analysis.

        Args:
            word: The word to route
            phonemes: Optional pre-computed phoneme tuple (ignored - we derive from varnas)

        Returns:
            Tuple of (assigned_layer, routing_trace)
            - assigned_layer is None if routing fails closed
        """
        # Step 1: Map word to varnas
        varna_matches = word_to_varnas(word, self.varna_map)

        if not varna_matches:
            # Empty input - fail closed
            return None, self._create_trace(
                word=word,
                varna_matches=(),
                layer_votes={},
                final_layer=None,
                status=RoutingStatus.EMPTY_INPUT,
            )

        # Step 2: Extract bridge meanings (applying ablation if configured)
        bridge_meanings = self._get_bridge_meanings(varna_matches)

        # Step 3: Compute layer votes from bridge meanings
        layer_votes: Dict[str, float] = {}
        unknown_count = sum(1 for m in varna_matches if m.is_unknown)

        for meaning in bridge_meanings:
            if meaning == UNKNOWN_BRIDGE_MEANING:
                continue

            layer = BRIDGE_MEANING_TO_LAYER.get(meaning)
            if layer:
                layer_votes[layer.value] = layer_votes.get(layer.value, 0) + 1.0

        # Step 4: Determine final layer
        total_varnas = len(varna_matches)

        if not layer_votes:
            # All unknown - fail closed
            return None, self._create_trace(
                word=word,
                varna_matches=varna_matches,
                layer_votes={},
                final_layer=None,
                status=RoutingStatus.ALL_UNKNOWN,
            )

        # Find layer with most votes
        max_layer = max(layer_votes.items(), key=lambda x: x[1])
        final_layer = OntologicalLayer(max_layer[0])

        # Determine status
        status = RoutingStatus.PARTIAL_UNKNOWN if unknown_count > 0 else RoutingStatus.SUCCESS

        return final_layer, self._create_trace(
            word=word,
            varna_matches=varna_matches,
            layer_votes=layer_votes,
            final_layer=final_layer,
            status=status,
        )

    def _get_bridge_meanings(self, varna_matches: Tuple[VarnaMatch, ...]) -> Tuple[str, ...]:
        """Get bridge meanings from varna matches, applying ablation mode."""
        if self.ablation_mode == "no_meaning":
            # Return varna identities as "meanings" (no semantic content)
            return tuple(m.varna_key for m in varna_matches)

        if self.ablation_mode == "randomized" and self._randomized_meanings:
            # Apply randomized meaning mapping
            meanings = []
            for m in varna_matches:
                original = m.bridge_meaning
                randomized = self._randomized_meanings.get(original, original)
                meanings.append(randomized)
            return tuple(meanings)

        # Default: full bridge meanings
        return tuple(m.bridge_meaning for m in varna_matches)

    def _create_trace(
        self,
        word: str,
        varna_matches: Tuple[VarnaMatch, ...],
        layer_votes: Dict[str, float],
        final_layer: Optional[OntologicalLayer],
        status: RoutingStatus,
    ) -> RoutingTrace:
        """Create a routing trace for audit."""
        bridge_meanings = tuple(m.bridge_meaning for m in varna_matches)
        unknown_count = sum(1 for m in varna_matches if m.is_unknown)
        total_varnas = len(varna_matches)
        total_votes = sum(layer_votes.values()) or 1.0
        max_votes = max(layer_votes.values()) if layer_votes else 0.0
        confidence = max_votes / total_votes if total_votes > 0 else 0.0

        # Compute deterministic hash
        hash_content = f"{word.lower()}|{','.join(m.varna_key for m in varna_matches)}|{final_layer.value if final_layer else 'NONE'}"
        routing_hash = hashlib.sha256(hash_content.encode()).hexdigest()[:12]

        return RoutingTrace(
            word=word,
            varna_matches=varna_matches,
            bridge_meanings=bridge_meanings,
            layer_votes=layer_votes,
            unknown_count=unknown_count,
            total_varnas=total_varnas,
            final_layer=final_layer,
            confidence=confidence,
            status=status,
            routing_hash=routing_hash,
        )

    def route_batch(
        self,
        words: Tuple[str, ...],
    ) -> Tuple[Tuple[Optional[OntologicalLayer], RoutingTrace], ...]:
        """Route multiple words."""
        return tuple(self.route(w) for w in words)


# =============================================================================
# Factory Functions
# =============================================================================

def create_router(
    ablation_mode: str = "full",
    randomized_meanings: Optional[Dict[str, str]] = None,
) -> PhonemeOnlyRouter:
    """
    Create a phoneme-only router.

    Args:
        ablation_mode: "full", "no_meaning", or "randomized"
        randomized_meanings: For randomized mode, the meaning shuffle map

    Returns:
        Configured PhonemeOnlyRouter
    """
    return PhonemeOnlyRouter.create(
        ablation_mode=ablation_mode,
        randomized_meanings=randomized_meanings,
    )


def create_randomized_meaning_map(seed: int = 42) -> Dict[str, str]:
    """
    Create a randomized bridge meaning mapping for ablation.

    Shuffles bridge meanings across varnas while preserving distribution.
    """
    import random
    rng = random.Random(seed)

    all_meanings = list(BRIDGE_MEANING_TO_LAYER.keys())
    shuffled = list(all_meanings)
    rng.shuffle(shuffled)

    return dict(zip(all_meanings, shuffled))


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Enums
    "RoutingStatus",
    # Data classes
    "VarnaMatch",
    "RoutingTrace",
    "VarnaBridgeMap",
    "PhonemeOnlyRouter",
    # Constants
    "BRIDGE_MEANING_TO_LAYER",
    "UNKNOWN_BRIDGE_MEANING",
    "UNKNOWN_LAYER",
    # Functions
    "get_varna_bridge_map",
    "reset_varna_bridge_map",
    "word_to_varnas",
    "create_router",
    "create_randomized_meaning_map",
]
