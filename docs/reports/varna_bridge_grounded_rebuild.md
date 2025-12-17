# Varna Bridge Grounded Rebuild Report

**Date:** 2025-12-17
**Type:** Forensic Correction
**Severity:** CRITICAL

---

## Executive Summary

Previous implementations incorrectly substituted heuristics where a ground-truth data file existed. This report documents the violations found, corrections made, and outstanding issues.

**Acknowledgment (Mandatory):**

> "Previous logic incorrectly substituted heuristics where a ground-truth data file existed."

---

## 1. What Was Wrong

### 1.1 Ground-Truth Data File

The authoritative data source exists at:

```
/docs/data/varna_bridge_map_v1.json
```

This file defines:
- **5 vowels:** a, e, i, o, u
- **34 consonants:** ka, kha, ga, gha, nga, ca, cha, ja, jha, nya, tta, ttha, dda, ddha, nna, ta, tha, da, dha, na, pa, pha, ba, bha, ma, ya, ra, la, va, sha, ssa, sa, ha, ksha
- **Bridge meanings** for each varna (e.g., "escape_pressure", "birth_of_cognition")
- **Aspiration status** for consonants
- **Varna groups** (ka_varga, ca_varga, etc.)

### 1.2 Violations Identified

#### VIOLATION 1: `symbolu/formulas/acoustic_unit_mapper.py` (CRITICAL)

**Location:** Lines 176-213

**Heuristic Code:**
```python
# Hard-coded IPA/articulatory consonant classification
CONSONANT_CLASS_MAP = {
    'p': SoundClass.STOP, 'b': SoundClass.STOP,
    't': SoundClass.STOP, 'd': SoundClass.STOP,
    'k': SoundClass.STOP, 'g': SoundClass.STOP,
    'f': SoundClass.FRICATIVE, 'v': SoundClass.FRICATIVE,
    'm': SoundClass.NASAL, 'n': SoundClass.NASAL,
    ...
}

# Hard-coded vowel height mapping
VOWEL_HEIGHT_MAP = {
    'i': VowelHeight.HIGH, 'u': VowelHeight.HIGH,
    'e': VowelHeight.MID, 'o': VowelHeight.MID,
    'a': VowelHeight.LOW,
}

# Hard-coded vowel backness mapping
VOWEL_BACKNESS_MAP = {
    'i': VowelBackness.FRONT, 'e': VowelBackness.FRONT,
    'a': VowelBackness.CENTRAL,
    'o': VowelBackness.BACK, 'u': VowelBackness.BACK,
}
```

**Why This Is Wrong:**
- Mappings are based on IPA/Western articulatory phonetics
- Ground-truth JSON uses Sanskrit varna-based classification
- No correspondence between heuristic SoundClass and JSON structure
- Used by production code throughout the codebase

---

#### VIOLATION 2: `symbolu/formulas/vritti_mapper.py`

**Location:** Lines 62-67, 163-202

**Heuristic Code:**
```python
# Imports heuristic data classes
from symbolu.formulas.acoustic_unit_mapper import (
    SoundClass,      # HEURISTIC
    VowelHeight,     # HEURISTIC
    VowelBackness,   # HEURISTIC
)

# Uses heuristic SoundClass
SOUND_CLASS_VRITTI_MAP: Dict[SoundClass, VrittiType] = {
    SoundClass.STOP: VrittiType.ACTIVATION,
    SoundClass.FRICATIVE: VrittiType.TENSION,
    ...
}
```

**Why This Is Wrong:**
- Entirely depends on heuristic `SoundClass` enum
- No correspondence to `varna_bridge_map_v1.json`
- All vritti assignments derived from inferred mappings

---

#### VIOLATION 3: `symbolu/ppv/ppv_builder_v1.py` (CRITICAL)

**Location:** Lines 64-136

**Heuristic Code:**
```python
# Hard-coded phoneme feature mapping
PHONEME_FEATURES: Dict[str, Tuple[int, ...]] = {
    "a": (1, 2, 1, 6, 5, 1, 3, 2),
    "e": (1, 2, 1, 5, 5, 1, 3, 2),
    "p": (5, 3, 6, 1, 1, 5, 5, 4),
    "sa": (3, 2, 4, 4, 4, 2, 4, 3),
    ...
}

# Fallback default (violates fail-closed)
DEFAULT_PHONEME_FEATURES: Tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0, 0)
```

**Why This Is Wrong:**
- 8-dimensional feature tuples are **invented values**
- No ground-truth data defines PPV structural features
- `DEFAULT_PHONEME_FEATURES` allows silent failure instead of fail-closed
- Completely bypasses authoritative data

---

## 2. What Changed

### 2.1 New Central Data Authority

Created `symbolu/formulas/varna_bridge_loader.py`:

```python
# Ground-truth loader with fail-closed behavior
class VarnaBridgeLoader:
    """
    Ground-truth data loader for varna bridge mappings.
    SOLE authoritative access to varna data.
    """

class VarnaMappingNotFoundError(KeyError):
    """
    Raised when varna mapping is not found.
    FAIL-CLOSED - no defaults, no guesses.
    """
```

**Key Functions:**
- `get_varna_entry(varna, strict=True)` - Raises error if not found
- `get_bridge_meaning(varna)` - Returns bridge meaning or raises error
- `is_known_varna(varna)` - Returns True/False
- `is_vowel(varna)`, `is_consonant(varna)`, `is_aspirated(varna)`

### 2.2 Design Principles Enforced

| Principle | Implementation |
|-----------|----------------|
| No heuristics | All lookups from JSON only |
| No fallback defaults | `VarnaMappingNotFoundError` raised |
| Fail closed | Missing mappings cause errors |
| Single source of truth | `varna_bridge_map_v1.json` |

---

## 3. What Results Are Now Invalid

### 3.1 INVALID: Production Acoustic Unit Mapper

**File:** `symbolu/formulas/acoustic_unit_mapper.py`

**Status:** INVALID

The `SoundClass`, `VowelHeight`, and `VowelBackness` classifications have **no correspondence** to ground-truth data. All outputs from this module are invalid under data-grounded standards.

**Affected Downstream:**
- `symbolu/formulas/vritti_mapper.py` - All vritti assignments
- `symbolu/formulas/phase1_snapshot.py` - All Phase 1 snapshots
- Any module importing from `acoustic_unit_mapper.py`

### 3.2 INVALID: PPV Feature Computation

**File:** `symbolu/ppv/ppv_builder_v1.py`

**Status:** INVALID

The `PHONEME_FEATURES` table contains **invented values** with no ground-truth backing. All PPV vectors computed from this table are invalid.

**Affected Downstream:**
- `symbolu/ppv/*` - All PPV-related modules
- `symbolu/mechanical/pipeline/p10_acoustic/*` - PPV envelope
- `symbolu/mechanical/pipeline/p11_controller/*` - PPV integration

### 3.3 Tests That Are Now INVALID or ACCIDENTALLY PASSING

| Test File | Status | Reason |
|-----------|--------|--------|
| `tests/test_phase1_acoustic_symbolic.py` | INVALID | Tests heuristic `SoundClass` mappings (lines 270-313) |
| `tests/phase11/test_ppv_integration_v1.py` | INVALID | Tests `PHONEME_FEATURES` table (line 44, 576-583) |
| `tests/core_phases/test_phase2_modifiers_v1.py` | SUSPECT | Uses heuristic acoustic units |
| `tests/core_phases/test_phase3_rule_engine_v3_0.py` | SUSPECT | Uses heuristic acoustic units |

---

## 4. What Results Still Hold

### 4.1 VALID: Experimental v3.1 Mapper

**File:** `docs/experiments/acoustic_unit_mapper_expressive_delta_v3_1.py`

**Status:** VALID

This experimental module correctly:
- Loads `varna_bridge_map_v1.json`
- Uses `VarnaBridgeMap` class for data-driven lookups
- Emits unknown units without heuristic classification
- Has explicit `NO_PHONETIC_HEURISTICS: True` invariant

### 4.2 VALID: Phase-1b Validation Tests

**File:** `tests/core_phases/test_phase1b_validation_v3_1.py`

**Status:** VALID

These tests correctly validate:
- JSON-only authority
- No heuristic fallback classification
- Unknown handling
- Bridge meaning correspondence

---

## 5. What Remains Untested

### 5.1 No Ground-Truth for PPV Structural Features

**Critical Gap:**

The ground-truth JSON (`varna_bridge_map_v1.json`) does NOT define PPV structural features. The 8-dimensional feature tuples:

```
(edge_tension, edge_release, onset_sharpness, sonority_lift,
 continuity, discontinuity, rhythmic_impulse, stability_pressure)
```

...have **no authoritative data source**.

**Required Action:**

Option A: Create new ground-truth file `docs/data/varna_ppv_features_v1.json` that declares PPV features for each bridge_meaning.

Option B: Mark PPV computation as INVALID until proper ground-truth is established.

### 5.2 No Bridge-to-Vritti Mapping

The vritti mapper uses `SoundClass` which has no ground-truth correspondence. A new mapping from `bridge_meaning` to `VrittiType` is needed.

### 5.3 Integration Tests Missing

No integration tests verify that:
- Production code uses `varna_bridge_loader.py`
- Fail-closed behavior is enforced
- Unknown varnas cause errors (not silent defaults)

---

## 6. Architectural Recommendations

### 6.1 Replace Production Acoustic Mapper

The production `symbolu/formulas/acoustic_unit_mapper.py` should be replaced with the experimental v3.1 mapper approach:

```python
# Instead of heuristic SoundClass
from symbolu.formulas.varna_bridge_loader import (
    get_varna_entry,
    VarnaMappingNotFoundError,
)
```

### 6.2 Define PPV Ground-Truth

Create `docs/data/varna_ppv_features_v1.json`:

```json
{
  "meta": {
    "version": "1.0",
    "purpose": "PPV structural features for bridge meanings"
  },
  "features": {
    "birth_of_cognition": [1, 2, 1, 6, 5, 1, 3, 2],
    "escape_pressure": [3, 2, 4, 4, 4, 2, 4, 3],
    ...
  }
}
```

### 6.3 Update Import Chain

All modules should import from `varna_bridge_loader.py` instead of using hard-coded tables:

```python
# WRONG
CONSONANT_CLASS_MAP = { 'p': SoundClass.STOP, ... }

# RIGHT
from symbolu.formulas.varna_bridge_loader import is_consonant, get_bridge_meaning
```

---

## 7. Conclusion

### Summary of Findings

| Component | Status | Action Required |
|-----------|--------|-----------------|
| `varna_bridge_map_v1.json` | VALID | Ground-truth source |
| `symbolu/formulas/acoustic_unit_mapper.py` | **OBSOLETE** | Do NOT use - contains heuristics |
| `docs/experiments/acoustic_unit_mapper_expressive_delta_v3_1.py` | **CORRECT** | Use this implementation |
| `vritti_mapper.py` | INVALID | Needs new ground-truth mapping |
| `ppv_builder_v1.py` | INVALID | PPV features need ground-truth |
| `varna_bridge_loader.py` | NEW | Central data authority |

### CRITICAL: Correct Acoustic Unit Mapper

**DO NOT USE:** `symbolu/formulas/acoustic_unit_mapper.py`
- Contains heuristic IPA-based mappings
- `SoundClass`, `VowelHeight`, `VowelBackness` are NOT from ground-truth
- This file is **OBSOLETE**

**USE INSTEAD:** `docs/experiments/acoustic_unit_mapper_expressive_delta_v3_1.py`
- Loads `varna_bridge_map_v1.json` as sole authority
- Uses `VarnaBridgeMap` class for data-driven lookups
- Emits unknown varnas without heuristic classification
- Has explicit `NO_PHONETIC_HEURISTICS: True` invariant

### Success Condition

> "All phoneme -> ontological interactions are driven exclusively by declared mappings, never inferred behavior."

**Current Status:** NOT MET

The system still contains heuristic mappings in production code. Full compliance requires:

1. Replacing all heuristic tables with `varna_bridge_loader.py` lookups
2. Creating ground-truth data for PPV features
3. Creating ground-truth data for vritti mappings
4. Updating all affected tests

---

## Appendix: Files Changed

| File | Change |
|------|--------|
| `symbolu/formulas/varna_bridge_loader.py` | NEW - Central data authority |
| `docs/reports/varna_bridge_grounded_rebuild.md` | NEW - This report |

---

*Report generated as forensic correction. No new theory introduced.*
