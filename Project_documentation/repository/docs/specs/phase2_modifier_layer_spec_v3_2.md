# Phase-2 Modifier Layer Specification

**Version:** 3.2
**Status:** DRAFT
**Date:** 2025-12-15
**Depends On:** Phase-1b Acoustic Unit Mapper v3.1

---

## 1. Overview

### 1.1 Purpose

Phase-2 is a **structural modifier layer** that operates exclusively on the output of Phase-1b (`List[AcousticBridgeUnit]`). It annotates **structural relationships** between adjacent acoustic units without introducing semantic interpretation.

### 1.2 Scope

Phase-2 answers exactly one question:

> "How do acoustic units relate structurally when placed in sequence?"

Phase-2 does NOT answer:
- What the units mean
- What the units intend
- What emotion they convey
- What word they form

### 1.3 Design Principle

Phase-2 functions as a **pure annotation layer**. It attaches modifier envelopes to acoustic units without mutating the underlying Phase-1b data structures.

---

## 2. Processing Contract

### 2.1 Input Specification

```
Input: List[AcousticBridgeUnit]
```

Where `AcousticBridgeUnit` is the frozen dataclass from Phase-1b:

| Field | Type | Description |
|-------|------|-------------|
| `varna` | `str` | Sanskrit varṇa symbol |
| `index` | `int` | Position in sequence (0-indexed) |
| `is_vowel` | `bool` | True if vowel varṇa |
| `is_consonant` | `bool` | True if consonant varṇa |
| `is_aspirated` | `bool` | True if aspirated consonant |
| `bridge_meaning` | `str` | Identifier from JSON (opaque) |
| `cluster_order` | `ClusterOrder` | CV/VC/CVC pattern marker |

### 2.2 Output Specification

```
Output: List[ModifiedAcousticUnit]
```

Where `ModifiedAcousticUnit` is defined as:

```
ModifiedAcousticUnit:
    source_unit: AcousticBridgeUnit    # IMMUTABLE reference to Phase-1b unit
    modifiers: ModifierEnvelope        # Phase-2 annotations (additive only)
```

### 2.3 Mutation Policy

| Operation | Permitted |
|-----------|-----------|
| Read Phase-1b fields | YES |
| Copy Phase-1b fields | YES |
| Reference Phase-1b units | YES |
| Modify Phase-1b fields | **NO** |
| Replace Phase-1b values | **NO** |
| Delete Phase-1b units | **NO** |

### 2.4 Reversibility Guarantee

Given `List[ModifiedAcousticUnit]`, the original `List[AcousticBridgeUnit]` MUST be recoverable by:

```
original = [modified.source_unit for modified in modified_units]
```

No information loss. No transformation. Direct extraction.

---

## 3. Modifier Table (SPEC)

### 3.1 Table Format

Each modifier is specified with:

| Column | Description |
|--------|-------------|
| `modifier_id` | Unique identifier (snake_case) |
| `trigger_condition` | Structural condition that activates modifier |
| `applies_to` | Scope: `UNIT`, `PAIR`, or `SPAN` |
| `output_shape` | Data type and structure of modifier value |
| `forbidden_inference` | Explicit list of prohibited interpretations |

### 3.2 Modifier Definitions

---

#### 3.2.1 `adjacency_type`

| Property | Value |
|----------|-------|
| **modifier_id** | `adjacency_type` |
| **trigger_condition** | Always computed for each unit |
| **applies_to** | `UNIT` |
| **output_shape** | `Literal["isolated", "bound_left", "bound_right", "bound_both"]` |
| **forbidden_inference** | word_boundary, syllable_boundary, morpheme_boundary, semantic_grouping |

**Computation Rules:**

| Condition | Value |
|-----------|-------|
| `index == 0 AND len(sequence) == 1` | `isolated` |
| `index == 0 AND len(sequence) > 1` | `bound_right` |
| `index == len(sequence) - 1 AND len(sequence) > 1` | `bound_left` |
| `0 < index < len(sequence) - 1` | `bound_both` |

---

#### 3.2.2 `vowel_consonant_transition`

| Property | Value |
|----------|-------|
| **modifier_id** | `vowel_consonant_transition` |
| **trigger_condition** | Computed for adjacent pairs where classification differs |
| **applies_to** | `PAIR` |
| **output_shape** | `Literal["V_to_C", "C_to_V", "V_to_V", "C_to_C", "U_involved"]` |
| **forbidden_inference** | syllable_structure, phonotactic_rule, pronunciation_guide, linguistic_pattern |

**Computation Rules:**

| Current | Next | Value |
|---------|------|-------|
| `is_vowel=True` | `is_consonant=True` | `V_to_C` |
| `is_consonant=True` | `is_vowel=True` | `C_to_V` |
| `is_vowel=True` | `is_vowel=True` | `V_to_V` |
| `is_consonant=True` | `is_consonant=True` | `C_to_C` |
| Either unit unknown | Any | `U_involved` |

---

#### 3.2.3 `aspiration_contrast`

| Property | Value |
|----------|-------|
| **modifier_id** | `aspiration_contrast` |
| **trigger_condition** | Adjacent consonant pair where both are consonants |
| **applies_to** | `PAIR` |
| **output_shape** | `Literal["both_aspirated", "both_unaspirated", "contrast_present", "not_applicable"]` |
| **forbidden_inference** | emphasis, stress, force, emotion, intensity, observer_observed_relation |

**Computation Rules:**

| Current | Next | Value |
|---------|------|-------|
| Both `is_consonant=True`, both `is_aspirated=True` | - | `both_aspirated` |
| Both `is_consonant=True`, both `is_aspirated=False` | - | `both_unaspirated` |
| Both `is_consonant=True`, aspiration differs | - | `contrast_present` |
| Either not consonant | - | `not_applicable` |

---

#### 3.2.4 `unknown_barrier`

| Property | Value |
|----------|-------|
| **modifier_id** | `unknown_barrier` |
| **trigger_condition** | Unit is unknown OR adjacent to unknown |
| **applies_to** | `UNIT` |
| **output_shape** | `Literal["is_unknown", "left_of_unknown", "right_of_unknown", "between_unknowns", "none"]` |
| **forbidden_inference** | error_classification, noise_type, character_category, encoding_issue |

**Computation Rules:**

| Condition | Value |
|-----------|-------|
| `is_vowel=False AND is_consonant=False` | `is_unknown` |
| Current known, next unknown | `left_of_unknown` |
| Current known, previous unknown | `right_of_unknown` |
| Previous unknown AND next unknown | `between_unknowns` |
| No unknown involvement | `none` |

---

#### 3.2.5 `boundary_position`

| Property | Value |
|----------|-------|
| **modifier_id** | `boundary_position` |
| **trigger_condition** | Always computed |
| **applies_to** | `UNIT` |
| **output_shape** | `Literal["sequence_start", "sequence_end", "sequence_interior", "singleton"]` |
| **forbidden_inference** | word_start, word_end, phrase_boundary, sentence_boundary |

**Computation Rules:**

| Condition | Value |
|-----------|-------|
| `len(sequence) == 1` | `singleton` |
| `index == 0` | `sequence_start` |
| `index == len(sequence) - 1` | `sequence_end` |
| Otherwise | `sequence_interior` |

---

#### 3.2.6 `continuity_class`

| Property | Value |
|----------|-------|
| **modifier_id** | `continuity_class` |
| **trigger_condition** | Computed based on unknown interruptions |
| **applies_to** | `SPAN` |
| **output_shape** | `{"type": Literal["continuous", "interrupted"], "span_indices": Tuple[int, int]}` |
| **forbidden_inference** | coherence, meaning_flow, semantic_continuity, discourse_structure |

**Computation Rules:**

A span is `continuous` if all units in the span are known (is_vowel OR is_consonant is True).
A span is `interrupted` if any unit in the span is unknown.

Spans are computed as maximal contiguous regions of same continuity type.

---

#### 3.2.7 `sequence_class`

| Property | Value |
|----------|-------|
| **modifier_id** | `sequence_class` |
| **trigger_condition** | Computed for the entire sequence |
| **applies_to** | `SPAN` (full sequence) |
| **output_shape** | `Literal["all_known", "all_unknown", "mixed", "empty"]` |
| **forbidden_inference** | validity, correctness, language_detection, script_detection |

**Computation Rules:**

| Condition | Value |
|-----------|-------|
| `len(sequence) == 0` | `empty` |
| All units are known | `all_known` |
| All units are unknown | `all_unknown` |
| Mix of known and unknown | `mixed` |

---

#### 3.2.8 `repetition_marker`

| Property | Value |
|----------|-------|
| **modifier_id** | `repetition_marker` |
| **trigger_condition** | Adjacent units have identical varṇa |
| **applies_to** | `PAIR` |
| **output_shape** | `Literal["repeated", "not_repeated"]` |
| **forbidden_inference** | emphasis, stammering, elongation, prosodic_feature, duplication_intent |

**Computation Rules:**

| Condition | Value |
|-----------|-------|
| `current.varna == next.varna` | `repeated` |
| Otherwise | `not_repeated` |

---

### 3.3 Modifier Summary Table

| modifier_id | applies_to | structural_only | reversible |
|-------------|------------|-----------------|------------|
| `adjacency_type` | UNIT | YES | YES |
| `vowel_consonant_transition` | PAIR | YES | YES |
| `aspiration_contrast` | PAIR | YES | YES |
| `unknown_barrier` | UNIT | YES | YES |
| `boundary_position` | UNIT | YES | YES |
| `continuity_class` | SPAN | YES | YES |
| `sequence_class` | SPAN | YES | YES |
| `repetition_marker` | PAIR | YES | YES |

---

## 4. ModifierEnvelope Structure

### 4.1 Definition

```
ModifierEnvelope:
    unit_modifiers: Dict[str, Any]      # Modifiers applying to single unit
    pair_modifiers: Dict[str, Any]      # Modifiers applying to this unit + next
    span_context: Dict[str, Any]        # Span-level modifiers (reference only)
    computation_metadata: ComputationMetadata
```

### 4.2 ComputationMetadata

```
ComputationMetadata:
    phase2_version: str                 # "3.2"
    computed_at_index: int              # Index of the unit
    sequence_length: int                # Total units in sequence
    modifier_count: int                 # Number of modifiers attached
```

### 4.3 Envelope Constraints

| Constraint | Enforcement |
|------------|-------------|
| Envelope is additive only | No deletion of Phase-1b data |
| Envelope references are read-only | No mutation through references |
| Envelope is serializable | JSON-compatible types only |
| Envelope is deterministic | Same input always produces same envelope |

---

## 5. Phase-2 Invariants

### 5.1 Core Invariants

```
PHASE2_INVARIANTS_V3_2 = {
    # Structural constraints
    "DETERMINISTIC": True,
    "REVERSIBLE": True,
    "AUDITABLE": True,
    "NON_MUTATING": True,

    # Semantic exclusions
    "NO_SEMANTICS": True,
    "NO_MEANING_ASSIGNMENT": True,
    "NO_INTENT_INFERENCE": True,
    "NO_EMOTION_INFERENCE": True,
    "NO_SENTIMENT_ANALYSIS": True,

    # Linguistic exclusions
    "NO_WORD_BOUNDARY_DETECTION": True,
    "NO_SYLLABLE_ANALYSIS": True,
    "NO_MORPHEME_DETECTION": True,
    "NO_PHONOTACTIC_RULES": True,
    "NO_PRONUNCIATION_INFERENCE": True,

    # Polarity exclusions
    "NO_VRTTI_POLARITY": True,
    "NO_NEGATION_INFERENCE": True,
    "NO_AFFIRMATION_INFERENCE": True,
    "NO_OBSERVER_OBSERVED_LOGIC": True,

    # Classification exclusions
    "NO_LANGUAGE_DETECTION": True,
    "NO_SCRIPT_CLASSIFICATION": True,
    "NO_ERROR_CLASSIFICATION": True,
    "NO_VALIDITY_JUDGMENT": True,

    # External dependency exclusions
    "NO_DICTIONARY_LOOKUP": True,
    "NO_LLM_INFERENCE": True,
    "NO_HEURISTIC_RULES": True,
    "NO_STATISTICAL_MODELS": True,
}
```

### 5.2 Invariant Verification

Phase-2 implementation MUST provide:

```
def validate_invariants_v3_2() -> bool:
    """Returns True if all invariants hold."""
```

Any invariant violation is a critical error requiring immediate correction.

---

## 6. Phase-2 Non-Goals

### 6.1 Explicit Non-Goals

Phase-2 will **NEVER** implement:

| Category | Non-Goal | Rationale |
|----------|----------|-----------|
| Semantics | Word meaning lookup | Requires dictionary (external authority) |
| Semantics | Definition retrieval | Requires external knowledge |
| Semantics | Synonym/antonym detection | Requires semantic graph |
| Linguistics | Syllable boundary detection | Requires phonotactic rules |
| Linguistics | Morpheme segmentation | Requires morphological analyzer |
| Linguistics | Part-of-speech tagging | Requires syntactic analysis |
| Psychology | Emotion detection | Requires affective computing |
| Psychology | Sentiment analysis | Requires opinion mining |
| Psychology | Intent classification | Requires pragmatic analysis |
| Philosophy | Vr̥tti polarity resolution | Reserved for higher phases |
| Philosophy | Observer/observed logic | Reserved for higher phases |
| Philosophy | Negation/affirmation marking | Reserved for higher phases |
| Validation | Correctness judgment | Phase-2 is descriptive, not prescriptive |
| Validation | Error correction | No authority to determine "correct" |
| Classification | Language identification | Requires language models |
| Classification | Script detection | Requires Unicode analysis |

### 6.2 Boundary with Higher Phases

Phase-2 produces **structural descriptors only**. Higher phases (Phase-3+) may:
- Interpret modifiers semantically
- Apply vr̥tti polarity
- Introduce observer/observed logic
- Connect to dictionary meanings

Phase-2 provides the **structural substrate** for such interpretations without performing them.

---

## 7. Test Case Verification

### 7.1 Required Test Cases

#### Case 1: "sad" → ["sa", "d"]

| Check | Expected | Forbidden |
|-------|----------|-----------|
| Phase-1b output | `[sa(C), d(U)]` | - |
| `adjacency_type[0]` | `bound_right` | word_boundary |
| `adjacency_type[1]` | `bound_left` | word_boundary |
| `vowel_consonant_transition` | `U_involved` | syllable_structure |
| `unknown_barrier[0]` | `left_of_unknown` | - |
| `unknown_barrier[1]` | `is_unknown` | error_type |
| Semantic inference | NONE | "sadness", "emotion", "feeling" |

#### Case 2: "ka kha"

| Check | Expected | Forbidden |
|-------|----------|-----------|
| Phase-1b output | `[ka(C), kha(Ch)]` | - |
| `aspiration_contrast` | `contrast_present` | observer/observed meaning |
| `vowel_consonant_transition` | `C_to_C` | emphasis |
| Semantic inference | NONE | "intensity", "force", "stress" |

#### Case 3: "ab"

| Check | Expected | Forbidden |
|-------|----------|-----------|
| Phase-1b output | `[a(V), b(U)]` | - |
| `vowel_consonant_transition` | `U_involved` | negation_prefix |
| `boundary_position[0]` | `sequence_start` | word_start |
| `unknown_barrier[1]` | `is_unknown` | - |
| Semantic inference | NONE | "negation", "absence", "without" |

#### Case 4: "xyz"

| Check | Expected | Forbidden |
|-------|----------|-----------|
| Phase-1b output | `[x(U), y(U), z(U)]` | - |
| `sequence_class` | `all_unknown` | invalid, error, garbage |
| `continuity_class` | `interrupted` (all) | noise_type |
| `unknown_barrier` | All `is_unknown` | character_category |
| Semantic inference | NONE | classification of any kind |

### 7.2 Test Success Criteria

A Phase-2 implementation is correct if:

1. All Phase-1b fields are preserved unchanged
2. All modifiers are computed deterministically
3. No forbidden inferences appear in output
4. Original sequence is recoverable from modified output
5. All invariants validate as True

---

## 8. Implementation Notes

### 8.1 Recommended Implementation Order

1. Define `ModifierEnvelope` dataclass
2. Define `ModifiedAcousticUnit` dataclass
3. Implement `adjacency_type` (simplest)
4. Implement `boundary_position` (simplest)
5. Implement `unknown_barrier`
6. Implement `vowel_consonant_transition`
7. Implement `aspiration_contrast`
8. Implement `repetition_marker`
9. Implement `continuity_class`
10. Implement `sequence_class`
11. Implement main `apply_modifiers()` function
12. Implement `validate_invariants_v3_2()`

### 8.2 Testing Strategy

1. Unit tests for each modifier in isolation
2. Integration tests for modifier combinations
3. Red flag tests for forbidden inferences
4. Reversibility tests
5. Determinism tests (same input = same output)

### 8.3 File Naming Convention

```
phase2_modifier_layer_v3_2.py       # Implementation
test_phase2_modifier_layer_v3_2.py  # Tests
```

---

## 9. Version History

| Version | Date | Changes |
|---------|------|---------|
| 3.2-DRAFT | 2025-12-15 | Initial specification |

---

## 10. Appendix A: Modifier Type Definitions (Reference)

```python
from typing import Literal, Tuple, Dict, Any
from dataclasses import dataclass

# Modifier value types
AdjacencyType = Literal["isolated", "bound_left", "bound_right", "bound_both"]
VowelConsonantTransition = Literal["V_to_C", "C_to_V", "V_to_V", "C_to_C", "U_involved"]
AspirationContrast = Literal["both_aspirated", "both_unaspirated", "contrast_present", "not_applicable"]
UnknownBarrier = Literal["is_unknown", "left_of_unknown", "right_of_unknown", "between_unknowns", "none"]
BoundaryPosition = Literal["sequence_start", "sequence_end", "sequence_interior", "singleton"]
ContinuityType = Literal["continuous", "interrupted"]
SequenceClass = Literal["all_known", "all_unknown", "mixed", "empty"]
RepetitionMarker = Literal["repeated", "not_repeated"]

@dataclass(frozen=True)
class ContinuitySpan:
    type: ContinuityType
    span_indices: Tuple[int, int]  # (start_index, end_index) inclusive

@dataclass(frozen=True)
class ComputationMetadata:
    phase2_version: str
    computed_at_index: int
    sequence_length: int
    modifier_count: int
```

---

## 11. Appendix B: Forbidden Inference Glossary

| Term | Definition | Why Forbidden |
|------|------------|---------------|
| `word_boundary` | Point where one word ends and another begins | Requires lexical knowledge |
| `syllable_boundary` | Division between syllables | Requires phonotactic rules |
| `morpheme_boundary` | Division between meaning units | Requires morphological analysis |
| `semantic_grouping` | Clustering by meaning | Requires semantic knowledge |
| `emphasis` | Stress or prominence | Requires prosodic analysis |
| `emotion` | Affective state | Requires psychological inference |
| `intent` | Purpose or goal | Requires pragmatic analysis |
| `negation` | Denial or absence | Requires semantic interpretation |
| `observer_observed` | Subject/object relation | Reserved for higher phases |
| `validity` | Correctness judgment | Phase-2 is descriptive only |

---

**END OF SPECIFICATION**
