"""
Varna Mapping — Pure Linguistic Bridge
========================================

Single source of truth for ARPABET → Sanskrit Varna mappings.

Contains:
    - ARPABET_TO_VARNA: Phoneme → Varna symbol mapping
    - VARGA_GROUPS: Articulatory classification (Ka-varga, Pa-varga, etc.)
    - VRITTI_LABELS: Mental propensity annotations per consonant
    - VOWEL_STATES: Consciousness state annotations per vowel

Does NOT contain:
    - 12D ontological layer vectors
    - Numeric affinity weights
    - Any dimensional projection

This file is a DATA layer. It encodes Sanskrit grammar, not model architecture.
Downstream consumers (CSRPhonemeHead, PhonemeBCVF, resonance engine) are free
to interpret these mappings into whatever dimensional space they need.
"""

from __future__ import annotations

from typing import Dict, List, Tuple


# =============================================================================
# ARPABET → SANSKRIT VARNA MAPPING
# =============================================================================
# Every ARPABET phoneme maps to a Sanskrit varṇa. This is the linguistic bridge.
#
# Vowels map to Māheśvara Sūtra vowels (states of consciousness).
# Consonants map to Varna Mala consonants (vrittis / mental propensities).

ARPABET_TO_VARNA: Dict[str, str] = {
    # =====================================================================
    # VOWELS: States of Consciousness
    # =====================================================================
    'AA': 'a',    # अ — Birth of cognition / Raw potential
    'AH': 'a',    # अ — Same root vowel
    'AE': 'a',    # अ — Open vowel variant
    'AO': 'o',    # ओ — Completion / Closure
    'AW': 'au',   # औ — Surrender / Letting-go
    'AY': 'ai',   # ऐ — Welfare / Materialization
    'EH': 'e',    # ए — Practical thought / Benefit
    'ER': 'ṛ',    # ऋ — Vocalic R (execution energy)
    'EY': 'e',    # ए — Practical thought
    'IH': 'i',    # इ — I-ness / Doing self
    'IY': 'ī',    # ई — Specialization of self
    'OW': 'o',    # ओ — Completion / Closure
    'OY': 'ai',   # ऐ — Welfare (diphthong blend)
    'UH': 'u',    # उ — Zoom / Contraction
    'UW': 'ū',    # ऊ — Sustained attention / Holding

    # =====================================================================
    # CONSONANTS: Vrittis (Mental Propensities)
    # =====================================================================
    # Ka-varga (Guttural) — Throat
    'K':  'ka',   # क — Āśā (Hope)
    'G':  'ga',   # ग — Ceṣṭā (Action)
    'NG': 'ṅa',   # ङ — Dambha (Vanity)

    # Ca-varga (Palatal) — Palate
    'CH': 'ca',   # च — Vikṣepa (Scatter)
    'JH': 'ja',   # ज — Dambha (Vanity)

    # Ṭa-varga (Retroflex) — Roof of mouth
    'T':  'ṭa',   # ट — Vitarka (Overstatement)
    'D':  'ḍa',   # ड — Lajjā (Shyness)

    # Ta-varga (Dental) — Teeth
    'TH': 'tha',  # थ — Viṣāda (Melancholy)
    'DH': 'dha',  # ध — Tṛṣṇā (Craving)

    # Pa-varga (Labial) — Lips
    'P':  'pa',   # प — Ghrṇā (Hatred/Revulsion)
    'B':  'ba',   # ब — Avajñā (Indifference)
    'M':  'ma',   # म — Praśraya (Indulgence)

    # Semi-vowels (Antaḥstha) — Transitional
    'Y':  'ya',   # य — Aviśvāsa (Lack of confidence)
    'R':  'ra',   # र — Sarvanāśa (Annihilation)
    'L':  'la',   # ल — Krūratā (Cruelty)
    'W':  'va',   # व — Dharma (Righteousness)
    'V':  'va',   # व — Same as W

    # Sibilants (Ūṣman) — Friction/heat
    'S':  'sa',   # स — Escapism / Static detachment
    'SH': 'śa',   # श — Material greed
    'Z':  'ja',   # Voiced sibilant → nearest varna
    'ZH': 'ja',   # Same approximation

    # Aspirate
    'HH': 'ha',   # ह — Avidyā (Darkness/Ignorance)

    # Additional mappings
    'F':  'pha',  # फ — Bhaya (Fear)
    'N':  'na',   # न — Moha (Blind attachment)
}


# =============================================================================
# VARGA GROUPS — Articulatory Classification
# =============================================================================
# Sanskrit classifies consonants by place of articulation (varga).
# Each varga shares a physical production mechanism.

VARGA_GROUPS: Dict[str, List[str]] = {
    'ka_varga':     ['K', 'G', 'NG'],        # Guttural (throat)
    'ca_varga':     ['CH', 'JH'],             # Palatal (palate)
    'ta_varga':     ['T', 'D'],               # Retroflex (roof)
    'tha_varga':    ['TH', 'DH'],             # Dental (teeth)
    'pa_varga':     ['P', 'B', 'M'],          # Labial (lips)
    'antahstha':    ['Y', 'R', 'L', 'W', 'V'],  # Semi-vowels
    'ushman':       ['S', 'SH', 'Z', 'ZH'],  # Sibilants
    'aspirate':     ['HH', 'F', 'N'],         # Aspirate + mapped
}


# =============================================================================
# VOICED / VOICELESS DISTINCTION
# =============================================================================

VOICED_CONSONANTS = frozenset(['G', 'D', 'B', 'JH', 'DH', 'V', 'Z', 'ZH'])
VOICELESS_CONSONANTS = frozenset(['K', 'T', 'P', 'CH', 'TH', 'F', 'S', 'SH'])


# =============================================================================
# VRITTI LABELS — Mental Propensity per Consonant
# =============================================================================
# Each consonant in the Varna Mala carries a vritti (mental propensity).
# These are the Sanskrit labels, NOT numeric weights.

VRITTI_LABELS: Dict[str, Dict[str, str]] = {
    # Ka-varga
    'K':  {'varna': 'ka', 'vritti': 'Āśā',       'english': 'Hope'},
    'G':  {'varna': 'ga', 'vritti': 'Ceṣṭā',     'english': 'Action'},
    'NG': {'varna': 'ṅa', 'vritti': 'Dambha',     'english': 'Vanity'},

    # Ca-varga
    'CH': {'varna': 'ca', 'vritti': 'Vikṣepa',    'english': 'Scatter'},
    'JH': {'varna': 'ja', 'vritti': 'Dambha',     'english': 'Vanity'},

    # Ṭa-varga
    'T':  {'varna': 'ṭa', 'vritti': 'Vitarka',    'english': 'Overstatement'},
    'D':  {'varna': 'ḍa', 'vritti': 'Lajjā',      'english': 'Shyness'},

    # Ta-varga
    'TH': {'varna': 'tha', 'vritti': 'Viṣāda',    'english': 'Melancholy'},
    'DH': {'varna': 'dha', 'vritti': 'Tṛṣṇā',     'english': 'Craving'},

    # Pa-varga
    'P':  {'varna': 'pa', 'vritti': 'Ghrṇā',      'english': 'Hatred'},
    'B':  {'varna': 'ba', 'vritti': 'Avajñā',     'english': 'Indifference'},
    'M':  {'varna': 'ma', 'vritti': 'Praśraya',   'english': 'Indulgence'},

    # Antaḥstha (Semi-vowels)
    'Y':  {'varna': 'ya', 'vritti': 'Aviśvāsa',   'english': 'Lack of confidence'},
    'R':  {'varna': 'ra', 'vritti': 'Sarvanāśa',  'english': 'Annihilation'},
    'L':  {'varna': 'la', 'vritti': 'Krūratā',    'english': 'Cruelty'},
    'W':  {'varna': 'va', 'vritti': 'Dharma',     'english': 'Righteousness'},
    'V':  {'varna': 'va', 'vritti': 'Dharma',     'english': 'Righteousness'},

    # Ūṣman (Sibilants)
    'S':  {'varna': 'sa', 'vritti': 'Parāṅmukhatā', 'english': 'Escapism'},
    'SH': {'varna': 'śa', 'vritti': 'Lobha',       'english': 'Material greed'},
    'Z':  {'varna': 'ja', 'vritti': 'Dambha',      'english': 'Vanity'},
    'ZH': {'varna': 'ja', 'vritti': 'Dambha',      'english': 'Vanity'},

    # Aspirate
    'HH': {'varna': 'ha', 'vritti': 'Avidyā',     'english': 'Ignorance'},
    'F':  {'varna': 'pha', 'vritti': 'Bhaya',      'english': 'Fear'},
    'N':  {'varna': 'na', 'vritti': 'Moha',       'english': 'Blind attachment'},
}


# =============================================================================
# VOWEL STATES — Consciousness States per Vowel
# =============================================================================
# Sanskrit vowels represent states of consciousness, not propensities.

VOWEL_STATES: Dict[str, Dict[str, str]] = {
    'AA': {'varna': 'a',  'devanagari': 'अ',  'state': 'Birth of cognition'},
    'AH': {'varna': 'a',  'devanagari': 'अ',  'state': 'Birth of cognition'},
    'AE': {'varna': 'a',  'devanagari': 'अ',  'state': 'Birth of cognition'},
    'IH': {'varna': 'i',  'devanagari': 'इ',  'state': 'I-ness / Doing self'},
    'IY': {'varna': 'ī',  'devanagari': 'ई',  'state': 'Specialization of self'},
    'UH': {'varna': 'u',  'devanagari': 'उ',  'state': 'Contraction / Focus'},
    'UW': {'varna': 'ū',  'devanagari': 'ऊ',  'state': 'Sustained attention'},
    'EH': {'varna': 'e',  'devanagari': 'ए',  'state': 'Practical thought'},
    'ER': {'varna': 'ṛ',  'devanagari': 'ऋ',  'state': 'Execution energy'},
    'EY': {'varna': 'e',  'devanagari': 'ए',  'state': 'Practical thought'},
    'AY': {'varna': 'ai', 'devanagari': 'ऐ',  'state': 'Welfare / Materialization'},
    'OW': {'varna': 'o',  'devanagari': 'ओ',  'state': 'Completion / Closure'},
    'AO': {'varna': 'o',  'devanagari': 'ओ',  'state': 'Completion / Closure'},
    'OY': {'varna': 'ai', 'devanagari': 'ऐ',  'state': 'Welfare'},
    'AW': {'varna': 'au', 'devanagari': 'औ',  'state': 'Surrender / Letting-go'},
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_varga(phoneme: str) -> str | None:
    """Return the varga group name for an ARPABET phoneme, or None."""
    for varga_name, members in VARGA_GROUPS.items():
        if phoneme in members:
            return varga_name
    return None


def get_vritti(phoneme: str) -> str | None:
    """Return the English vritti label for a consonant, or None for vowels."""
    entry = VRITTI_LABELS.get(phoneme)
    return entry['english'] if entry else None


def get_vowel_state(phoneme: str) -> str | None:
    """Return the consciousness state for a vowel, or None for consonants."""
    entry = VOWEL_STATES.get(phoneme)
    return entry['state'] if entry else None


def is_vowel(phoneme: str) -> bool:
    """Check if an ARPABET phoneme is a vowel."""
    return phoneme in VOWEL_STATES


def is_consonant(phoneme: str) -> bool:
    """Check if an ARPABET phoneme is a consonant."""
    return phoneme in VRITTI_LABELS


def all_phonemes() -> list[str]:
    """Return all mapped ARPABET phonemes."""
    return sorted(ARPABET_TO_VARNA.keys())


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ARPABET_TO_VARNA',
    'VARGA_GROUPS',
    'VOICED_CONSONANTS',
    'VOICELESS_CONSONANTS',
    'VRITTI_LABELS',
    'VOWEL_STATES',
    'get_varga',
    'get_vritti',
    'get_vowel_state',
    'is_vowel',
    'is_consonant',
    'all_phonemes',
]
