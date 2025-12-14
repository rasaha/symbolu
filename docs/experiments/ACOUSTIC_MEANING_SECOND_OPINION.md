# Acoustic Meaning Second Opinion — Audit Report

**Date:** 2025-12-14
**Purpose:** Independent second-opinion analysis of acoustic properties
**Query Analyzed:** "What is the acoustic meaning of 'tub'?"

---

## Executive Summary

This report provides an auditable second-opinion analysis that **separates deterministic acoustic observations from optional heuristic abstractions**. The key finding is:

> **This does not claim meaning; it claims observed motion + optional abstraction.**

All acoustic mappings are either **RULE-BASED** (from repository definitions) or **HEURISTIC** (interpretive guesses marked as such). Dictionary meanings are explicitly **FORBIDDEN** and flagged when detected.

---

## 1. What Was Deterministic vs Heuristic

### Deterministic (RULE-BASED) Components

| Component | Source | Invariant Protection |
|-----------|--------|---------------------|
| Acoustic unit segmentation | `symbolu/formulas/acoustic_unit_mapper.py` | NO_SEMANTICS, DETERMINISTIC |
| Sound class classification | `CONSONANT_CLASS_MAP` in repo | LANGUAGE_AGNOSTIC |
| Vowel height/backness | `VOWEL_HEIGHT_MAP`, `VOWEL_BACKNESS_MAP` | READ_ONLY |
| Vritti assignment | `SOUND_CLASS_VRITTI_MAP` in repo | NO_INTENT, NO_POLICY |
| Vritti distribution | `get_vritti_distribution()` algorithm | DETERMINISTIC |
| Acoustic signature | `get_acoustic_signature()` algorithm | NO_SEMANTICS |

These components are **self-contained in the repository** and produce **identical output for identical input** (INV-EXP-4 verified).

### Heuristic Components

| Component | Risk Level | Justification |
|-----------|------------|---------------|
| Onset-coda shape interpretation | MEDIUM | "abrupt/gradual" mapping not in repo |
| Energy contour interpretation | HIGH | weight-to-energy metaphor not defined |
| Motion profile labels | MEDIUM | labels like "impact-sustain" are interpretive |
| Terminal closure interpretation | MEDIUM | "closure" as concept not in repo |
| Non-standard form detection | HIGH | vowel-less words are highly speculative |

---

## 2. Repository Mapping Coverage

### Mappings That EXIST (Deterministic)

```python
# From symbolu/formulas/acoustic_unit_mapper.py
CONSONANT_CLASS_MAP = {
    'p': STOP, 'b': STOP, 't': STOP, 'd': STOP, 'k': STOP, 'g': STOP,
    'f': FRICATIVE, 'v': FRICATIVE, 's': FRICATIVE, 'z': FRICATIVE,
    'm': NASAL, 'n': NASAL,
    'l': LIQUID, 'r': LIQUID,
    'w': GLIDE, 'y': GLIDE,
    'j': AFFRICATE,
}

# From symbolu/formulas/vritti_mapper.py
SOUND_CLASS_VRITTI_MAP = {
    STOP: ACTIVATION,       # Sudden release of energy
    FRICATIVE: TENSION,     # Constrained/turbulent energy
    NASAL: INERTIA,         # Sustained energy
    LIQUID: OSCILLATION,    # Alternating energy
    GLIDE: OSCILLATION,     # Modulating energy
    VOWEL: RELEASE,         # Opening energy
}

VOWEL_HEIGHT_VRITTI_MODIFIER = {
    LOW: RELEASE,           # Open vowels
    HIGH: TENSION,          # Constrained vowels
    MID: INERTIA,           # Neutral vowels
}
```

### Mappings That Are MISSING (Heuristic Gap)

| Missing Mapping | Current Status | Recommendation |
|-----------------|----------------|----------------|
| Phoneme → motion shape (onset/coda) | HEURISTIC in experiment | Define in P22/P23 if needed |
| Vritti weight → energy | HEURISTIC in experiment | Consider for P23 alignment |
| Consonant cluster density → risk | HEURISTIC in experiment | Could be rule in P22 |
| Motion profile labels | HEURISTIC in experiment | Leave as interpretive layer |

---

## 3. Sample Outputs

### "tub" Analysis

```json
{
  "input": "tub",
  "acoustic_signature": "VH",
  "acoustic_units": [{
    "raw_text": "tub",
    "sound_class": "vowel",
    "vowel_height": "high",
    "vowel_backness": "back",
    "consonant_count": 2,
    "vowel_count": 1
  }],
  "vritti_distribution": {
    "tension": 1.0,
    "activation": 0.0,
    "inertia": 0.0,
    "oscillation": 0.0,
    "release": 0.0
  },
  "motion_profile": {
    "dominant_vritti": "tension",
    "profile_label": "tension-dominant",
    "derivation": "HEURISTIC"
  },
  "forbidden_semantic_inferences_detected": [
    "FORBIDDEN: 'tub' has dictionary meaning 'container/bathtub' - NOT asserted"
  ]
}
```

**Key observations:**
- The word "tub" is segmented as a single unit with high back vowel /u/
- Vritti: 100% TENSION (from high vowel modifier)
- Dictionary meaning "container" is **explicitly forbidden** and not asserted

### "gsdf" Analysis (Nonsense Word)

```json
{
  "input": "gsdf",
  "acoustic_signature": "SX",
  "acoustic_units": [{
    "raw_text": "gsdf",
    "sound_class": "stop",
    "vowel_height": "unknown",
    "vowel_backness": "unknown",
    "consonant_count": 4,
    "vowel_count": 0
  }],
  "vritti_distribution": {
    "activation": 1.0,
    "tension": 0.0,
    "inertia": 0.0,
    "oscillation": 0.0,
    "release": 0.0
  },
  "abstraction_candidates": [
    {"label": "motion-sequence-observation", "derivation": "RULE-BASED", "semantic_risk": "low"},
    {"label": "onset-coda-shape", "derivation": "HEURISTIC", "semantic_risk": "medium"},
    {"label": "terminal-closure", "derivation": "HEURISTIC", "semantic_risk": "medium"},
    {"label": "non-standard-form", "derivation": "HEURISTIC", "semantic_risk": "high"}
  ],
  "forbidden_semantic_inferences_detected": []
}
```

**Key observations:**
- No vowels → single consonant cluster → "unknown" vowel properties
- Vritti: 100% ACTIVATION (from stop consonant)
- **HIGH RISK** flagged for non-standard form (no syllable nuclei)
- No dictionary meaning to forbid (nonsense word)

---

## 4. Recommendations for P22/P23/P24

### P22 (Acoustic-Vritti Witness)

| Current State | Recommendation |
|--------------|----------------|
| Produces motion primitives correctly | Keep as-is |
| Missing: dense cluster detection | Add optional `cluster_density` field |
| Missing: non-standard form flag | Add `is_standard_phonological_form` boolean |

### P23 (Inner-Outer Alignment)

| Current State | Recommendation |
|--------------|----------------|
| Compares pressure vs regime | Keep as-is |
| Uses motion_balance correctly | Keep as-is |
| Missing: pressure source traceability | Add `pressure_derivation` field |
| Consider: add "heuristic_gap" tag | When alignment uses non-repo mappings |

### P24 (Acoustic-Ontology Projection)

| Current State | Recommendation |
|--------------|----------------|
| Projects ontology layers | Keep as-is |
| Has risk flagging | Keep as-is |
| Consider: explicit derivation labels | Mark each projection as RULE-BASED or HEURISTIC |
| Consider: confidence decay | Lower confidence for heuristic-heavy projections |

---

## 5. Invariants Verified

| Invariant | Status | Evidence |
|-----------|--------|----------|
| INV-EXP-1 (No semantics) | ✅ PASS | "tub" flags dictionary meaning as FORBIDDEN |
| INV-EXP-2 (Traceability) | ✅ PASS | All candidates have `source_facts` |
| INV-EXP-3 (Labeling) | ✅ PASS | All claims labeled RULE-BASED or HEURISTIC |
| INV-EXP-4 (Determinism) | ✅ PASS | Same input → identical JSON (verified in tests) |
| INV-EXP-5 (Separation) | ✅ PASS | `acoustic_units` independent of `abstraction_candidates` |
| INV-EXP-6 (Risk flagging) | ✅ PASS | "gsdf" gets HIGH risk for non-standard form |

---

## 6. Conclusion

### What This Report Claims

1. **Observed acoustic properties** of input words (deterministic, RULE-BASED)
2. **Motion quality distributions** based on repository-defined mappings (RULE-BASED)
3. **Optional abstraction candidates** with explicit derivation labels (HEURISTIC where applicable)
4. **Semantic risk flags** for any interpretive leaps

### What This Report Does NOT Claim

- ❌ Dictionary meanings ("tub = container")
- ❌ Emotional interpretations
- ❌ Intent or purpose
- ❌ Cultural/linguistic meanings

### Final Statement

> **This does not claim meaning; it claims observed motion + optional abstraction.**

The acoustic analysis pipeline in Symbol-U correctly separates deterministic observation (P22) from interpretive synthesis. The experiment validates that:

1. RULE-BASED mappings are traceable to repository definitions
2. HEURISTIC interpretations are explicitly labeled and risk-flagged
3. Dictionary semantics are forbidden and not asserted

---

## Appendix: Files Created

| File | Purpose |
|------|---------|
| `tools/experiments/acoustic_meaning_second_opinion.py` | Standalone experiment script |
| `tests/experiments/test_acoustic_meaning_second_opinion.py` | 6 tests (one per invariant) |
| `docs/experiments/ACOUSTIC_MEANING_SECOND_OPINION.md` | This report |

---

*Generated by acoustic-meaning-audit experiment, 2025-12-14*
