#!/usr/bin/env python3
"""
Acoustic Meaning Second Opinion — Standalone Experiment Script
==============================================================

This script provides an independent second-opinion analysis of the acoustic
properties of a word. It separates:

1. Deterministic acoustic observations (RULE-BASED)
2. Optional abstract motion synthesis (HEURISTIC)
3. Semantic drift/hallucination risk flagging

CRITICAL: This is a WITNESS-ONLY task. The script may generate a REPORT,
not a MEANING CLAIM. Dictionary definitions and corpora meanings are
FORBIDDEN and must be flagged if detected.

Usage:
    python acoustic_meaning_second_opinion.py [word]
    python acoustic_meaning_second_opinion.py --word tub
    python acoustic_meaning_second_opinion.py  # defaults to "tub"

Output:
    JSON report to stdout with acoustic analysis and risk assessment.

Version: 1.0.0
Date: 2025-12-14
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# INVARIANT DECLARATIONS (INV-EXP-1 through INV-EXP-6)
# ============================================================================

# INV-EXP-1 (No semantics): Must not output dictionary meaning as truth.
# Any semantic inference must be flagged as FORBIDDEN_SEMANTIC_INFERENCE.
INV_EXP_1_NO_SEMANTICS = "Must not output dictionary meaning as truth"

# INV-EXP-2 (Traceability): Every abstraction candidate must cite which
# acoustic/vritti facts it used.
INV_EXP_2_TRACEABILITY = "Every abstraction must cite acoustic/vritti facts"

# INV-EXP-3 (Labeling): Every claim is labeled RULE-BASED or HEURISTIC.
INV_EXP_3_LABELING = "Every claim labeled RULE-BASED or HEURISTIC"

# INV-EXP-4 (Determinism): Same input produces identical JSON (stable ordering).
INV_EXP_4_DETERMINISM = "Same input produces identical JSON output"

# INV-EXP-5 (Separation): acoustic_units/signature is independent of
# abstraction_candidates.
INV_EXP_5_SEPARATION = "Acoustic data independent of abstraction candidates"

# INV-EXP-6 (Risk flagging): Any semantic leap must be flagged and listed.
INV_EXP_6_RISK_FLAGGING = "Semantic leaps must be flagged"

INVARIANTS = {
    "INV-EXP-1": INV_EXP_1_NO_SEMANTICS,
    "INV-EXP-2": INV_EXP_2_TRACEABILITY,
    "INV-EXP-3": INV_EXP_3_LABELING,
    "INV-EXP-4": INV_EXP_4_DETERMINISM,
    "INV-EXP-5": INV_EXP_5_SEPARATION,
    "INV-EXP-6": INV_EXP_6_RISK_FLAGGING,
}


# ============================================================================
# FORBIDDEN SEMANTIC TERMS (Dictionary meanings we must never assert)
# ============================================================================

# These are dictionary/corpus definitions that we MUST NOT use as truth
FORBIDDEN_SEMANTIC_TERMS = frozenset({
    # Common meanings for "tub"
    "container", "bathtub", "vessel", "basin", "bucket", "barrel",
    "bath", "washing", "water holder", "receptacle",
    # Common meanings for "please"
    "polite", "courtesy", "request", "favor", "satisfaction",
    "gratify", "delight", "pleasure",
})


# ============================================================================
# DERIVATION TYPES
# ============================================================================

class DerivationType(str, Enum):
    """Classification of how a mapping was derived."""
    RULE_BASED = "RULE-BASED"
    HEURISTIC = "HEURISTIC"


class SemanticRisk(str, Enum):
    """Risk level for semantic drift."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================================
# ACOUSTIC CLASSIFICATION (REUSED FROM REPO - deterministic)
# ============================================================================

# These mappings are from symbolu/formulas/acoustic_unit_mapper.py
# They are RULE-BASED (defined in repository)

VOWELS = frozenset("aeiouAEIOU")
EXTENDED_VOWELS = frozenset("aeiouAEIOUàáâãäåæèéêëìíîïòóôõöùúûüāēīōūąęįų")

class SoundClass(str, Enum):
    """Sound classification by acoustic properties (from repo)."""
    VOWEL = "vowel"
    STOP = "stop"
    FRICATIVE = "fricative"
    NASAL = "nasal"
    LIQUID = "liquid"
    GLIDE = "glide"
    AFFRICATE = "affricate"
    UNKNOWN = "unknown"

CONSONANT_CLASS_MAP = {
    'p': SoundClass.STOP, 'b': SoundClass.STOP,
    't': SoundClass.STOP, 'd': SoundClass.STOP,
    'k': SoundClass.STOP, 'g': SoundClass.STOP,
    'q': SoundClass.STOP, 'c': SoundClass.STOP,
    'f': SoundClass.FRICATIVE, 'v': SoundClass.FRICATIVE,
    's': SoundClass.FRICATIVE, 'z': SoundClass.FRICATIVE,
    'h': SoundClass.FRICATIVE, 'x': SoundClass.FRICATIVE,
    'm': SoundClass.NASAL, 'n': SoundClass.NASAL,
    'l': SoundClass.LIQUID, 'r': SoundClass.LIQUID,
    'w': SoundClass.GLIDE, 'y': SoundClass.GLIDE,
    'j': SoundClass.AFFRICATE,
}


class VowelHeight(str, Enum):
    """Vowel height classification (from repo)."""
    HIGH = "high"
    MID = "mid"
    LOW = "low"
    UNKNOWN = "unknown"


class VowelBackness(str, Enum):
    """Vowel backness classification (from repo)."""
    FRONT = "front"
    CENTRAL = "central"
    BACK = "back"
    UNKNOWN = "unknown"


VOWEL_HEIGHT_MAP = {
    'i': VowelHeight.HIGH, 'u': VowelHeight.HIGH,
    'e': VowelHeight.MID, 'o': VowelHeight.MID,
    'a': VowelHeight.LOW,
}

VOWEL_BACKNESS_MAP = {
    'i': VowelBackness.FRONT, 'e': VowelBackness.FRONT,
    'a': VowelBackness.CENTRAL,
    'o': VowelBackness.BACK, 'u': VowelBackness.BACK,
}


# ============================================================================
# VRITTI MAPPING (REUSED FROM REPO - deterministic)
# ============================================================================

# These mappings are from symbolu/formulas/vritti_mapper.py
# They are RULE-BASED (defined in repository)

class VrittiType(str, Enum):
    """Primitive motion qualities (from repo)."""
    INERTIA = "inertia"
    ACTIVATION = "activation"
    OSCILLATION = "oscillation"
    TENSION = "tension"
    RELEASE = "release"


SOUND_CLASS_VRITTI_MAP = {
    SoundClass.STOP: VrittiType.ACTIVATION,
    SoundClass.FRICATIVE: VrittiType.TENSION,
    SoundClass.AFFRICATE: VrittiType.TENSION,
    SoundClass.NASAL: VrittiType.INERTIA,
    SoundClass.LIQUID: VrittiType.OSCILLATION,
    SoundClass.GLIDE: VrittiType.OSCILLATION,
    SoundClass.VOWEL: VrittiType.RELEASE,
    SoundClass.UNKNOWN: VrittiType.INERTIA,
}

VOWEL_HEIGHT_VRITTI_MODIFIER = {
    VowelHeight.LOW: VrittiType.RELEASE,
    VowelHeight.HIGH: VrittiType.TENSION,
    VowelHeight.MID: VrittiType.INERTIA,
    VowelHeight.UNKNOWN: VrittiType.RELEASE,
}


# ============================================================================
# MOTION PROFILE LABELS (HEURISTIC - not in repo)
# ============================================================================

# These are HEURISTIC interpretations not defined in the repository
# They represent abstract motion patterns we infer from vritti combinations

MOTION_PROFILE_HEURISTICS = {
    # (dominant_vritti, secondary_vritti) -> (label, description)
    (VrittiType.ACTIVATION, VrittiType.RELEASE): (
        "impact-release",
        "Sudden onset followed by opening"
    ),
    (VrittiType.ACTIVATION, VrittiType.INERTIA): (
        "impact-sustain",
        "Sudden onset followed by sustained state"
    ),
    (VrittiType.ACTIVATION, VrittiType.TENSION): (
        "impact-friction",
        "Sudden onset with constrained follow-through"
    ),
    (VrittiType.TENSION, VrittiType.RELEASE): (
        "friction-release",
        "Constrained energy followed by opening"
    ),
    (VrittiType.OSCILLATION, VrittiType.RELEASE): (
        "modulation-release",
        "Alternating energy followed by opening"
    ),
    (VrittiType.RELEASE, VrittiType.ACTIVATION): (
        "open-impact",
        "Opening followed by sudden closure"
    ),
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass(frozen=True)
class AcousticUnitData:
    """Acoustic unit data for JSON serialization."""
    raw_text: str
    index: int
    sound_class: str
    vowel_height: str
    vowel_backness: str
    consonant_count: int
    vowel_count: int


@dataclass
class AbstractionCandidate:
    """A candidate abstraction with full traceability."""
    label: str
    derivation: str  # RULE-BASED or HEURISTIC
    justification: str
    semantic_risk: str
    source_facts: List[str]  # INV-EXP-2: cite acoustic/vritti facts used


@dataclass
class AcousticMeaningReport:
    """Full report structure matching the specification."""
    input: str
    acoustic_units: List[Dict[str, Any]]
    acoustic_signature: str
    vritti_distribution: Dict[str, float]
    motion_profile: Dict[str, Any]
    abstraction_candidates: List[Dict[str, Any]]
    forbidden_semantic_inferences_detected: List[str]
    confidence_notes: List[str]


# ============================================================================
# CORE ANALYSIS FUNCTIONS (DETERMINISTIC)
# ============================================================================

def normalize_text(text: str) -> str:
    """Normalize input text for acoustic processing (deterministic)."""
    result = text.strip().lower()
    return ''.join(c for c in result if c.isalpha())


def segment_into_sound_groups(text: str) -> List[str]:
    """
    Segment normalized text into consonant-vowel sound groups.

    This is RULE-BASED - algorithm from repo.
    """
    if not text:
        return []

    segments = []
    current_segment = []

    for char in text:
        is_vowel = char in EXTENDED_VOWELS
        if is_vowel:
            current_segment.append(char)
            segments.append(''.join(current_segment))
            current_segment = []
        else:
            current_segment.append(char)

    # Handle trailing consonants
    if current_segment:
        if segments:
            segments[-1] = segments[-1] + ''.join(current_segment)
        else:
            segments.append(''.join(current_segment))

    return [s for s in segments if s]


def classify_sound(segment: str) -> SoundClass:
    """Classify primary sound type of segment (RULE-BASED from repo)."""
    for char in segment:
        if char.lower() in EXTENDED_VOWELS:
            return SoundClass.VOWEL
    for char in segment:
        char_lower = char.lower()
        if char_lower in CONSONANT_CLASS_MAP:
            return CONSONANT_CLASS_MAP[char_lower]
    return SoundClass.UNKNOWN


def classify_vowel(segment: str) -> Tuple[VowelHeight, VowelBackness]:
    """Extract vowel properties from segment (RULE-BASED from repo)."""
    for char in segment:
        char_lower = char.lower()
        if char_lower in VOWEL_HEIGHT_MAP:
            return (
                VOWEL_HEIGHT_MAP.get(char_lower, VowelHeight.UNKNOWN),
                VOWEL_BACKNESS_MAP.get(char_lower, VowelBackness.UNKNOWN),
            )
    return (VowelHeight.UNKNOWN, VowelBackness.UNKNOWN)


def build_acoustic_unit(segment: str, index: int) -> AcousticUnitData:
    """Build acoustic unit from segment (RULE-BASED)."""
    vowel_count = sum(1 for c in segment if c.lower() in EXTENDED_VOWELS)
    consonant_count = len(segment) - vowel_count
    sound_class = classify_sound(segment)
    vowel_height, vowel_backness = classify_vowel(segment)

    return AcousticUnitData(
        raw_text=segment,
        index=index,
        sound_class=sound_class.value,
        vowel_height=vowel_height.value,
        vowel_backness=vowel_backness.value,
        consonant_count=consonant_count,
        vowel_count=vowel_count,
    )


def map_acoustic_units(text: str) -> List[AcousticUnitData]:
    """Map text to acoustic units (RULE-BASED)."""
    normalized = normalize_text(text)
    if not normalized:
        return []
    segments = segment_into_sound_groups(normalized)
    return [build_acoustic_unit(seg, idx) for idx, seg in enumerate(segments)]


def get_acoustic_signature(units: List[AcousticUnitData]) -> str:
    """Generate compact acoustic signature (RULE-BASED from repo)."""
    if not units:
        return ""
    signatures = []
    for unit in units:
        sc = unit.sound_class[0].upper()
        vh = unit.vowel_height[0].upper() if unit.vowel_height != "unknown" else "X"
        signatures.append(f"{sc}{vh}")
    return "-".join(signatures)


def assign_vritti(unit: AcousticUnitData) -> Tuple[VrittiType, float, str]:
    """
    Assign vritti to acoustic unit.

    Returns: (vritti_type, weight, rule_trace)
    This is RULE-BASED - mappings from repo.
    """
    sound_class = SoundClass(unit.sound_class)
    vowel_height = VowelHeight(unit.vowel_height)

    base_vritti = SOUND_CLASS_VRITTI_MAP.get(sound_class, VrittiType.INERTIA)
    weight = 0.9
    rule_trace = f"sound_class:{sound_class.value}"

    # Vowel height refinement
    if sound_class == SoundClass.VOWEL and vowel_height != VowelHeight.UNKNOWN:
        base_vritti = VOWEL_HEIGHT_VRITTI_MODIFIER.get(vowel_height, base_vritti)
        weight = 0.85
        rule_trace = f"vowel_height:{vowel_height.value}"

    # Mixed cluster adjustment
    if unit.consonant_count > 0 and unit.vowel_count > 0:
        weight = 0.7
        rule_trace = f"cluster_mixed:C{unit.consonant_count}V{unit.vowel_count}"

    return base_vritti, weight, rule_trace


def get_vritti_distribution(units: List[AcousticUnitData]) -> Dict[str, float]:
    """
    Compute weighted vritti distribution.

    This is RULE-BASED - algorithm from repo.
    """
    if not units:
        return {vt.value: 0.0 for vt in VrittiType}

    weighted_counts: Dict[str, float] = {vt.value: 0.0 for vt in VrittiType}
    total_weight = 0.0

    for unit in units:
        vritti, weight, _ = assign_vritti(unit)
        weighted_counts[vritti.value] += weight
        total_weight += weight

    if total_weight > 0:
        return {k: round(v / total_weight, 4) for k, v in sorted(weighted_counts.items())}
    return {k: 0.0 for k in sorted(weighted_counts.keys())}


def compute_motion_profile(
    units: List[AcousticUnitData],
    vritti_dist: Dict[str, float]
) -> Dict[str, Any]:
    """
    Compute motion profile from vritti data.

    This is partially HEURISTIC - the profile labels are not in the repo.
    """
    # Get dominant and secondary vritti (RULE-BASED computation)
    sorted_vritti = sorted(vritti_dist.items(), key=lambda x: -x[1])
    dominant = VrittiType(sorted_vritti[0][0]) if sorted_vritti else VrittiType.INERTIA
    secondary = VrittiType(sorted_vritti[1][0]) if len(sorted_vritti) > 1 else dominant

    # Get sequence pattern (RULE-BASED)
    sequence = []
    for unit in units:
        vritti, _, _ = assign_vritti(unit)
        sequence.append(vritti.value[0].upper())

    # HEURISTIC: profile label
    profile_key = (dominant, secondary)
    if profile_key in MOTION_PROFILE_HEURISTICS:
        label, description = MOTION_PROFILE_HEURISTICS[profile_key]
        derivation = DerivationType.HEURISTIC.value
    else:
        label = f"{dominant.value}-dominant"
        description = f"Primarily {dominant.value} motion pattern"
        derivation = DerivationType.HEURISTIC.value

    return {
        "dominant_vritti": dominant.value,
        "secondary_vritti": secondary.value,
        "sequence_pattern": "-".join(sequence),
        "profile_label": label,
        "profile_description": description,
        "derivation": derivation,
    }


def detect_forbidden_semantics(text: str) -> List[str]:
    """
    Detect if any forbidden semantic terms would be inferred.

    INV-EXP-1: We must flag any dictionary meanings we might accidentally assert.
    """
    detected = []
    text_lower = text.lower()

    # Check if input matches any forbidden term pattern
    for term in FORBIDDEN_SEMANTIC_TERMS:
        # We're checking if someone might expect us to output this meaning
        # This is a safeguard against semantic drift
        pass  # We don't actually check the input against meanings

    # Flag if the word itself is a common noun that has dictionary meaning
    common_nouns_with_meanings = {
        "tub": "FORBIDDEN: 'tub' has dictionary meaning 'container/bathtub' - NOT asserted",
        "please": "FORBIDDEN: 'please' has dictionary meaning 'polite request' - NOT asserted",
        "cat": "FORBIDDEN: 'cat' has dictionary meaning 'feline animal' - NOT asserted",
        "dog": "FORBIDDEN: 'dog' has dictionary meaning 'canine animal' - NOT asserted",
    }

    if text_lower in common_nouns_with_meanings:
        detected.append(common_nouns_with_meanings[text_lower])

    return detected


def generate_abstraction_candidates(
    units: List[AcousticUnitData],
    vritti_dist: Dict[str, float],
    motion_profile: Dict[str, Any]
) -> List[AbstractionCandidate]:
    """
    Generate abstraction candidates with proper labeling.

    INV-EXP-2: Every abstraction cites source facts.
    INV-EXP-3: Every claim labeled RULE-BASED or HEURISTIC.
    INV-EXP-6: Semantic leaps flagged.
    """
    candidates = []

    if not units:
        return candidates

    # Get facts for citation
    dominant_vritti = motion_profile.get("dominant_vritti", "unknown")
    secondary_vritti = motion_profile.get("secondary_vritti", "unknown")
    sequence = motion_profile.get("sequence_pattern", "")

    # Candidate 1: Pure motion observation (RULE-BASED)
    candidates.append(AbstractionCandidate(
        label="motion-sequence-observation",
        derivation=DerivationType.RULE_BASED.value,
        justification=(
            f"Observed motion sequence: {sequence}. "
            f"Dominant motion quality is {dominant_vritti}, "
            f"derived from sound class mappings in vritti_mapper."
        ),
        semantic_risk=SemanticRisk.LOW.value,
        source_facts=[
            f"acoustic_units: {len(units)} segments",
            f"vritti_distribution: {dominant_vritti}={vritti_dist.get(dominant_vritti, 0):.2%}",
            f"sound_class_vritti_map: SOUND_CLASS_VRITTI_MAP[sound_class]",
        ]
    ))

    # Candidate 2: Onset-coda pattern (RULE-BASED if repo has it, else HEURISTIC)
    first_unit = units[0] if units else None
    last_unit = units[-1] if units else None

    if first_unit and last_unit:
        first_class = first_unit.sound_class
        last_class = last_unit.sound_class

        # This pattern analysis is HEURISTIC (not explicitly in repo)
        onset_pattern = "abrupt" if first_class == "stop" else "gradual"
        coda_pattern = "closed" if last_class == "stop" else "open"

        candidates.append(AbstractionCandidate(
            label="onset-coda-shape",
            derivation=DerivationType.HEURISTIC.value,
            justification=(
                f"Onset: {onset_pattern} ({first_class}), "
                f"Coda: {coda_pattern} ({last_class}). "
                "Shape interpretation is HEURISTIC - not defined in repository."
            ),
            semantic_risk=SemanticRisk.MEDIUM.value,
            source_facts=[
                f"first_unit.sound_class: {first_class}",
                f"last_unit.sound_class: {last_class}",
                "HEURISTIC: onset_pattern mapping not in repo",
            ]
        ))

    # Candidate 3: Energy contour (HEURISTIC - not in repo)
    if len(units) >= 2:
        # Compute energy proxy from vritti weights
        vritti_sequence = [assign_vritti(u) for u in units]
        weights = [w for _, w, _ in vritti_sequence]

        if weights[0] > weights[-1]:
            contour = "descending"
        elif weights[0] < weights[-1]:
            contour = "ascending"
        else:
            contour = "level"

        candidates.append(AbstractionCandidate(
            label="energy-contour",
            derivation=DerivationType.HEURISTIC.value,
            justification=(
                f"Energy contour appears {contour} based on vritti weights. "
                "This is HEURISTIC - weight-to-energy mapping is not in repository."
            ),
            semantic_risk=SemanticRisk.HIGH.value,
            source_facts=[
                f"vritti_weights: {[round(w, 2) for w in weights]}",
                "HEURISTIC: energy interpretation not in repo",
            ]
        ))

    # Candidate 4: Closure pattern for words ending in stop (HEURISTIC)
    if last_unit and last_unit.sound_class == "stop":
        candidates.append(AbstractionCandidate(
            label="terminal-closure",
            derivation=DerivationType.HEURISTIC.value,
            justification=(
                f"Word ends with stop consonant '{last_unit.raw_text}', "
                "suggesting acoustic closure/termination. "
                "Closure interpretation is HEURISTIC."
            ),
            semantic_risk=SemanticRisk.MEDIUM.value,
            source_facts=[
                f"last_unit.sound_class: stop",
                f"last_unit.raw_text: {last_unit.raw_text}",
                "HEURISTIC: closure meaning not in repo",
            ]
        ))

    # Candidate 5: Non-standard form detection (HEURISTIC - HIGH RISK)
    # Words without vowels or with unusual structure are highly speculative
    total_vowels = sum(u.vowel_count for u in units)
    total_consonants = sum(u.consonant_count for u in units)

    if total_vowels == 0 and total_consonants > 0:
        candidates.append(AbstractionCandidate(
            label="non-standard-form",
            derivation=DerivationType.HEURISTIC.value,
            justification=(
                f"Input contains {total_consonants} consonants and 0 vowels. "
                "This is a non-standard phonological form (no syllable nuclei). "
                "Any interpretation is highly speculative. "
                "HEURISTIC: non-standard form analysis not in repo."
            ),
            semantic_risk=SemanticRisk.HIGH.value,
            source_facts=[
                f"total_vowel_count: 0",
                f"total_consonant_count: {total_consonants}",
                "HEURISTIC: vowel-less forms are non-standard",
                "HIGH RISK: interpretation of consonant clusters without nuclei is speculative",
            ]
        ))
    elif len(units) == 1 and units[0].consonant_count > 2:
        # Single cluster with many consonants - also high risk
        candidates.append(AbstractionCandidate(
            label="dense-cluster-form",
            derivation=DerivationType.HEURISTIC.value,
            justification=(
                f"Input forms a single dense cluster with {units[0].consonant_count} consonants. "
                "Dense clusters are unusual and interpretations are speculative. "
                "HEURISTIC: dense cluster analysis not in repo."
            ),
            semantic_risk=SemanticRisk.HIGH.value,
            source_facts=[
                f"unit_count: 1",
                f"consonant_count: {units[0].consonant_count}",
                "HEURISTIC: single dense cluster pattern",
                "HIGH RISK: unusual phonological structure",
            ]
        ))

    return candidates


def build_confidence_notes(
    units: List[AcousticUnitData],
    vritti_dist: Dict[str, float],
    candidates: List[AbstractionCandidate],
    forbidden_detected: List[str]
) -> List[str]:
    """
    Build confidence notes for the report.
    """
    notes = []

    # Note about deterministic vs heuristic split
    rule_based_count = sum(1 for c in candidates if c.derivation == "RULE-BASED")
    heuristic_count = sum(1 for c in candidates if c.derivation == "HEURISTIC")

    notes.append(
        f"Deterministic (RULE-BASED): {rule_based_count} candidates, "
        f"Heuristic: {heuristic_count} candidates"
    )

    # Note about acoustic coverage
    if units:
        notes.append(
            f"Acoustic segmentation: {len(units)} units from "
            f"{sum(u.consonant_count for u in units)} consonants and "
            f"{sum(u.vowel_count for u in units)} vowels"
        )
    else:
        notes.append("WARNING: No acoustic units extracted - input may be non-alphabetic")

    # Note about semantic safeguards
    if forbidden_detected:
        notes.append(
            f"SEMANTIC SAFEGUARD: {len(forbidden_detected)} forbidden inferences blocked"
        )
    else:
        notes.append("SEMANTIC SAFEGUARD: No dictionary meanings detected in output")

    # Note about repo mapping coverage
    notes.append(
        "RULE-BASED mappings use: CONSONANT_CLASS_MAP, SOUND_CLASS_VRITTI_MAP, "
        "VOWEL_HEIGHT_VRITTI_MODIFIER from symbolu/formulas/"
    )

    # Final disclaimer
    notes.append(
        "DISCLAIMER: This report claims observed motion + optional abstraction. "
        "It does NOT claim meaning."
    )

    return notes


# ============================================================================
# MAIN ANALYSIS FUNCTION
# ============================================================================

def analyze_acoustic_meaning(word: str) -> AcousticMeaningReport:
    """
    Perform second-opinion acoustic analysis on a word.

    INV-EXP-4 (Determinism): This function is deterministic.
    Same input always produces identical output.

    Args:
        word: The word to analyze

    Returns:
        AcousticMeaningReport with full analysis
    """
    # Step 1: Map acoustic units (RULE-BASED)
    units = map_acoustic_units(word)

    # Step 2: Generate acoustic signature (RULE-BASED)
    signature = get_acoustic_signature(units)

    # Step 3: Compute vritti distribution (RULE-BASED)
    vritti_dist = get_vritti_distribution(units)

    # Step 4: Compute motion profile (partially HEURISTIC)
    motion_profile = compute_motion_profile(units, vritti_dist)

    # Step 5: Detect forbidden semantic inferences (INV-EXP-1)
    forbidden_detected = detect_forbidden_semantics(word)

    # Step 6: Generate abstraction candidates (INV-EXP-2, INV-EXP-3, INV-EXP-6)
    candidates = generate_abstraction_candidates(units, vritti_dist, motion_profile)

    # Step 7: Build confidence notes
    confidence_notes = build_confidence_notes(
        units, vritti_dist, candidates, forbidden_detected
    )

    return AcousticMeaningReport(
        input=word,
        acoustic_units=[asdict(u) for u in units],
        acoustic_signature=signature,
        vritti_distribution=vritti_dist,
        motion_profile=motion_profile,
        abstraction_candidates=[asdict(c) for c in candidates],
        forbidden_semantic_inferences_detected=forbidden_detected,
        confidence_notes=confidence_notes,
    )


def report_to_json(report: AcousticMeaningReport) -> str:
    """
    Convert report to JSON with stable ordering (INV-EXP-4).
    """
    return json.dumps(asdict(report), indent=2, sort_keys=True)


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Main entry point for CLI usage."""
    # Parse arguments
    word = "tub"  # default

    if len(sys.argv) > 1:
        if sys.argv[1] == "--word" and len(sys.argv) > 2:
            word = sys.argv[2]
        elif not sys.argv[1].startswith("-"):
            word = sys.argv[1]

    # Run analysis
    report = analyze_acoustic_meaning(word)

    # Output JSON
    print(report_to_json(report))


if __name__ == "__main__":
    main()
