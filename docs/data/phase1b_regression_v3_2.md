# Phase-1b Regression Test Results (v3.2)

**Date:** 2025-12-15
**Regression Run Against:** v3.2 Environment (Phase-2 Modifier Layer Spec)
**Test File:** `tests/test_phase1b_validation_v3_1.py` (UNCHANGED)
**Acoustic Mapper:** `acoustic_unit_mapper_expressive_delta_v3_1.py`
**Status:** **29 PASSED** | 0 FAILED

---

## PASS / FAIL Summary

| Result | Count |
|--------|-------|
| **PASSED** | 29 |
| **FAILED** | 0 |
| **Total** | 29 |

---

## Verdict

**✅ Phase-1b substrate remains intact under v3.2.**

---

## Test Execution Details

| Metric | Value |
|--------|-------|
| Total Tests | 29 |
| Passed | 29 |
| Failed | 0 |
| Duration | 0.16s |
| Platform | Linux (Python 3.11.14) |
| pytest Version | 9.0.2 |

---

## Test Results by Group

### Group 1: Minimal Sanity Tests (3/3 PASSED)

| Test | Status |
|------|--------|
| `test_single_consonant_sa` | PASSED |
| `test_single_vowel_a` | PASSED |
| `test_aspirated_vs_unaspirated_contrast` | PASSED |

### Group 2: CV Structure Tests (2/2 PASSED)

| Test | Status |
|------|--------|
| `test_cv_pattern_consonants_only` | PASSED |
| `test_cv_pattern_with_vowel` | PASSED |

### Group 3: Semantic Safety Tests (1/1 PASSED)

| Test | Status |
|------|--------|
| `test_sad_no_semantic_leakage` | PASSED |

### Group 4: Vowel-First Negation Tests (1/1 PASSED)

| Test | Status |
|------|--------|
| `test_ab_no_negation_logic` | PASSED |

### Group 5: Unknown Handling Tests (3/3 PASSED)

| Test | Status |
|------|--------|
| `test_garbage_input_all_unknown` | PASSED |
| `test_completely_unknown_sequence` | PASSED |
| `test_unknown_count_function` | PASSED |

### Group 6: Cross-Language Tests (2/2 PASSED)

| Test | Status |
|------|--------|
| `test_english_word_tub` | PASSED |
| `test_indian_dialect_amma` | PASSED |

### Group 7: Acoustic Signature Tests (2/2 PASSED)

| Test | Status |
|------|--------|
| `test_acoustic_signature_format` | PASSED |
| `test_signature_differentiates_aspiration` | PASSED |

### Group 8: Invariant Verification Tests (3/3 PASSED)

| Test | Status |
|------|--------|
| `test_validate_invariants_v3_1` | PASSED |
| `test_validate_unit_consistency` | PASSED |
| `test_substrate_invariants_structure` | PASSED |

### Group 9: Red Flag Detection Tests (4/4 PASSED)

| Test | Status |
|------|--------|
| `test_no_semantic_inference` | PASSED |
| `test_no_vowel_guessing_outside_json` | PASSED |
| `test_no_fallback_classification_for_unknowns` | PASSED |
| `test_no_aspiration_inference_from_spelling` | PASSED |

### Group 10: Version/Module Tests (2/2 PASSED)

| Test | Status |
|------|--------|
| `test_acoustic_mapper_version` | PASSED |
| `test_varna_bridge_map_loads` | PASSED |

### Group 11: Determinism Tests (2/2 PASSED)

| Test | Status |
|------|--------|
| `test_map_acoustic_units_deterministic` | PASSED |
| `test_signature_deterministic` | PASSED |

### Group 12: Edge Case Tests (4/4 PASSED)

| Test | Status |
|------|--------|
| `test_empty_string` | PASSED |
| `test_whitespace_only` | PASSED |
| `test_type_error_on_non_string` | PASSED |
| `test_none_returns_empty` | PASSED |

---

## Regression Confirmation

This regression run confirms:

1. **Acoustic tokenization still works** - All varna segmentation tests pass
2. **No heuristic contamination occurred** - Unknown handling remains opaque
3. **No semantic leakage was introduced** - "sad" does not produce "sadness"
4. **Phase-2 logic did NOT back-propagate into Phase-1b** - All invariants hold

---

## Failures

**None.**

---

## Raw Output

```
============================= test session starts ==============================
platform linux -- Python 3.11.14, pytest-9.0.2, pluggy-1.6.0 -- /usr/local/bin/python
cachedir: .pytest_cache
rootdir: /home/user/symbolu
configfile: pyproject.toml
collecting ... collected 29 items

tests/test_phase1b_validation_v3_1.py::TestMinimalSanity::test_single_consonant_sa PASSED [  3%]
tests/test_phase1b_validation_v3_1.py::TestMinimalSanity::test_single_vowel_a PASSED [  6%]
tests/test_phase1b_validation_v3_1.py::TestMinimalSanity::test_aspirated_vs_unaspirated_contrast PASSED [ 10%]
tests/test_phase1b_validation_v3_1.py::TestCVStructure::test_cv_pattern_consonants_only PASSED [ 13%]
tests/test_phase1b_validation_v3_1.py::TestCVStructure::test_cv_pattern_with_vowel PASSED [ 17%]
tests/test_phase1b_validation_v3_1.py::TestSemanticSafety::test_sad_no_semantic_leakage PASSED [ 20%]
tests/test_phase1b_validation_v3_1.py::TestVowelFirstNegation::test_ab_no_negation_logic PASSED [ 24%]
tests/test_phase1b_validation_v3_1.py::TestUnknownHandling::test_garbage_input_all_unknown PASSED [ 27%]
tests/test_phase1b_validation_v3_1.py::TestUnknownHandling::test_completely_unknown_sequence PASSED [ 31%]
tests/test_phase1b_validation_v3_1.py::TestUnknownHandling::test_unknown_count_function PASSED [ 34%]
tests/test_phase1b_validation_v3_1.py::TestCrossLanguage::test_english_word_tub PASSED [ 37%]
tests/test_phase1b_validation_v3_1.py::TestCrossLanguage::test_indian_dialect_amma PASSED [ 41%]
tests/test_phase1b_validation_v3_1.py::TestAcousticSignature::test_acoustic_signature_format PASSED [ 44%]
tests/test_phase1b_validation_v3_1.py::TestAcousticSignature::test_signature_differentiates_aspiration PASSED [ 48%]
tests/test_phase1b_validation_v3_1.py::TestInvariantVerification::test_validate_invariants_v3_1 PASSED [ 51%]
tests/test_phase1b_validation_v3_1.py::TestInvariantVerification::test_validate_unit_consistency PASSED [ 55%]
tests/test_phase1b_validation_v3_1.py::TestInvariantVerification::test_substrate_invariants_structure PASSED [ 58%]
tests/test_phase1b_validation_v3_1.py::TestRedFlagDetection::test_no_semantic_inference PASSED [ 62%]
tests/test_phase1b_validation_v3_1.py::TestRedFlagDetection::test_no_vowel_guessing_outside_json PASSED [ 65%]
tests/test_phase1b_validation_v3_1.py::TestRedFlagDetection::test_no_fallback_classification_for_unknowns PASSED [ 68%]
tests/test_phase1b_validation_v3_1.py::TestRedFlagDetection::test_no_aspiration_inference_from_spelling PASSED [ 72%]
tests/test_phase1b_validation_v3_1.py::TestVersionModule::test_acoustic_mapper_version PASSED [ 75%]
tests/test_phase1b_validation_v3_1.py::TestVersionModule::test_varna_bridge_map_loads PASSED [ 79%]
tests/test_phase1b_validation_v3_1.py::TestDeterminism::test_map_acoustic_units_deterministic PASSED [ 82%]
tests/test_phase1b_validation_v3_1.py::TestDeterminism::test_signature_deterministic PASSED [ 86%]
tests/test_phase1b_validation_v3_1.py::TestEdgeCases::test_empty_string PASSED [ 89%]
tests/test_phase1b_validation_v3_1.py::TestEdgeCases::test_whitespace_only PASSED [ 93%]
tests/test_phase1b_validation_v3_1.py::TestEdgeCases::test_type_error_on_non_string PASSED [ 96%]
tests/test_phase1b_validation_v3_1.py::TestEdgeCases::test_none_returns_empty PASSED [100%]

=============================== warnings summary ===============================
tests/test_phase1b_validation_v3_1.py:32
  /home/user/symbolu/tests/test_phase1b_validation_v3_1.py:32: UserWarning: This module is EXPERIMENTAL (Delta v3.1 — Phase-1b). Do not use in production pipelines or governance decisions. Uses Varṇa-based substrate only. For production use: symbolu/formulas/acoustic_unit_mapper.py
    from acoustic_unit_mapper_expressive_delta_v3_1 import (

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 29 passed, 1 warning in 0.16s =========================
```

---

## Notes

- Test file was executed **VERBATIM** with no modifications
- No test expectations were changed
- No assertions were added or removed
- No test names were renamed
- This is a pure regression validation run
