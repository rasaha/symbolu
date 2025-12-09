"""
SOULPI Canonical Constants v2.7.1
==================================

AUTHORITATIVE consonant-to-kosha mappings and ontology layers.
Source: Soulpi v2.7.1 Specification (November 28, 2025)
Status: CANONICAL - Do not modify without authorization

Copyright (c) 2025 Rakesh Mohan. All rights reserved.
"""

from typing import Dict, List, Any

# ==============================================================================
# KOSHA LAYERS (Consciousness Depth - Vertical Axis)
# ==============================================================================

CANONICAL_KOSHA_LAYERS: Dict[int, str] = {
    1: "ANNAMAYA",
    2: "PRANAMAYA",
    3: "MANOMAYA",
    4: "VIJNANAMAYA",
    5: "ANANDAMAYA",
}

KOSHA_DESCRIPTIONS: Dict[str, Dict[str, Any]] = {
    "ANNAMAYA": {
        "level": 1,
        "nature": "Physical body, material form",
        "vritti_tendency": "Nidrā (inertness, sleep, dullness)",
        "acoustic_quality": "Heavy, dragging, grounded, viscous",
        "qualities": [
            "Indifference", "Obsession", "Indulgence",
            "Body-tension", "Dense materiality", "Physical fixation",
        ],
    },
    "PRANAMAYA": {
        "level": 2,
        "nature": "Energy body, vital force (prana)",
        "vritti_tendency": "Vikalpa (restless imagination, energetic fantasy)",
        "acoustic_quality": "Explosive, projective, turbulent, pushing",
        "qualities": [
            "Agitation", "Projection", "Breath-force turbulence",
            "Energetic push-pull", "Restless propulsion", "Vital force instability",
        ],
    },
    "MANOMAYA": {
        "level": 3,
        "nature": "Mind layer, emotions, thoughts",
        "vritti_tendency": "Viparyaya (misperception, emotional distortion)",
        "acoustic_quality": "Sharp, cutting, emotional, turbulent",
        "qualities": [
            "Fear", "Craving", "Delusion",
            "Anger", "Sadness", "Emotional volatility",
        ],
    },
    "VIJNANAMAYA": {
        "level": 4,
        "nature": "Wisdom body, discriminative awareness",
        "vritti_tendency": "Pramāṇa (valid cognition, discrimination)",
        "acoustic_quality": "Penetrating, sibilant, sharp, discriminating",
        "qualities": [
            "Discrimination", "Vanity (to be resolved)",
            "Hypocrisy (to be resolved)", "False knowledge (to be resolved)",
            "Cognitive distortion (to be resolved)", "Penetrating analysis",
        ],
    },
    "ANANDAMAYA": {
        "level": 5,
        "nature": "Bliss body, pure being",
        "vritti_tendency": "Pramāṇa (pure clear awareness)",
        "acoustic_quality": "Pure vibration, no obstruction, vowel-only",
        "qualities": [
            "Pure bliss", "Non-dual awareness", "Transcendent being",
            "Causeless peace", "Ultimate stillness",
        ],
    },
}


# ==============================================================================
# CANONICAL CONSONANT-TO-KOSHA MAPPING
# ==============================================================================

CANONICAL_CONSONANT_TO_KOSHA: Dict[str, Dict[str, Any]] = {
    "ANNAMAYA": {
        "consonants": ["ba", "bha", "ma", "ya", "ra", "la"],
        "devanagari": ["ब", "भ", "म", "य", "र", "ल"],
        "vritti": "Nidrā",
    },
    "PRANAMAYA": {
        "consonants": ["ka", "kha", "ga", "gha", "ca", "cha"],
        "devanagari": ["क", "ख", "ग", "घ", "च", "छ"],
        "vritti": "Vikalpa",
    },
    "MANOMAYA": {
        "consonants": ["ta", "tha", "da", "dha", "na", "pa", "pha"],
        "devanagari": ["त", "थ", "द", "ध", "न", "प", "फ"],
        "vritti": "Viparyaya",
    },
    "VIJNANAMAYA": {
        "consonants": ["ja", "jha", "sha", "sa"],
        "devanagari": ["ज", "झ", "श", "स"],
        "vritti": "Pramāṇa",
    },
    "ANANDAMAYA": {
        "consonants": [],
        "devanagari": [],
        "vritti": "Pramāṇa (pure)",
    },
}


# Build reverse mapping: consonant -> kosha info
CONSONANT_TO_KOSHA_MAP: Dict[str, Dict[str, Any]] = {}
for kosha, data in CANONICAL_CONSONANT_TO_KOSHA.items():
    for cons in data["consonants"]:
        CONSONANT_TO_KOSHA_MAP[cons] = {
            "kosha": kosha,
            "level": KOSHA_DESCRIPTIONS[kosha]["level"],
            "vritti": data["vritti"],
        }

# Consonant variants for romanized input
CONSONANT_VARIANTS: Dict[str, List[str]] = {
    "ba": ["b", "B"], "bha": ["bh", "Bh"], "ma": ["m", "M"],
    "ya": ["y", "Y"], "ra": ["r", "R"], "la": ["l", "L"],
    "ka": ["k", "K"], "kha": ["kh", "Kh"], "ga": ["g", "G"],
    "gha": ["gh", "Gh"], "ca": ["c", "C"], "cha": ["ch", "Ch"],
    "ta": ["t", "T"], "tha": ["th", "Th"], "da": ["d", "D"],
    "dha": ["dh", "Dh"], "na": ["n", "N"], "pa": ["p", "P"],
    "pha": ["ph", "Ph", "f", "F"], "ja": ["j", "J"], "jha": ["jh", "Jh"],
    "sha": ["sh", "Sh"], "sa": ["s", "S"],
}

# Expand variants into CONSONANT_TO_KOSHA_MAP
for canonical, variants in CONSONANT_VARIANTS.items():
    if canonical in CONSONANT_TO_KOSHA_MAP:
        base_info = CONSONANT_TO_KOSHA_MAP[canonical]
        for var in variants:
            if var not in CONSONANT_TO_KOSHA_MAP:
                CONSONANT_TO_KOSHA_MAP[var] = base_info.copy()


# ==============================================================================
# ONTOLOGICAL LAYERS (Manifestation Breadth - Horizontal Axis)
# ==============================================================================

ONTOLOGICAL_LAYERS: Dict[str, Dict[str, Any]] = {
    "Execution": {"level": 1, "domain": "Karma, action, physical manifestation"},
    "Identity": {"level": 2, "domain": "Self-tagging, labels, roles"},
    "Form": {"level": 3, "domain": "Body, shape, physical appearance"},
    "Cognition": {"level": 4, "domain": "Mind, thinking, mental processes"},
    "Agency": {"level": 5, "domain": "Ego, control, willpower"},
    "Reasoning": {"level": 6, "domain": "Intellect, analysis, discrimination"},
    "Purpose": {"level": 7, "domain": "Soul-direction, meaning, intention"},
    "Observation": {"level": 8, "domain": "Witness, awareness, observation"},
    "Core": {"level": 9, "domain": "Atman, essence, true self"},
    "Universal": {"level": 10, "domain": "Brahman, cosmic, universal principles"},
}


# ==============================================================================
# STITCHING WEIGHTS (v2.6 Enterprise Baseline)
# ==============================================================================

V26_STITCHING_WEIGHTS = {
    "alpha": 0.45,  # Inner truth weight
    "beta": 0.45,   # Outer meaning weight
    "gamma": 0.10,  # Mismatch penalty
    "delta": 0.05,  # Entropy smoothing
}


# ==============================================================================
# DHA TONE MAPPINGS
# ==============================================================================

DHA_TONES = {
    "SWEET_RESONANCE": {"approach": "Direct, supportive, affirming"},
    "GENTLE_MIRROR": {"approach": "Reflective, questioning, exploratory"},
    "FIRM_COMPASSION": {"approach": "Clear, boundaried, honest"},
    "SILENT_PRESENCE": {"approach": "Minimal words, spacious, allowing"},
}


# ==============================================================================
# VOWEL ASPECT BRIDGES
# ==============================================================================

VOWEL_ASPECT_BRIDGES: Dict[str, Dict[str, Any]] = {
    "a": {"aspect": "EGO", "quality": "self-assertion"},
    "i": {"aspect": "INTELLECT", "quality": "focused discrimination"},
    "u": {"aspect": "EGO", "quality": "will-force"},
    "e": {"aspect": "INTELLECT", "quality": "active inquiry"},
    "o": {"aspect": "EGO", "quality": "manifesting power"},
    "ai": {"aspect": "WITNESS", "quality": "transcendent seeing"},
    "au": {"aspect": "WITNESS", "quality": "cosmic sound"},
}


# ==============================================================================
# SMI THRESHOLDS
# ==============================================================================

SMI_THRESHOLDS = {
    "LOW": 0.3,
    "MODERATE": 0.5,
    "HIGH": 0.7,
}
