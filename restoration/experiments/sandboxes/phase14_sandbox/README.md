# Phase-14: Phonemic-Ontological Accumulator

## Overview

Phase-14 implements a prototype for accumulating word-layer mappings through RAG exposure. This is an experimental alternative to transformer-based statistical learning.

**Core Hypothesis**: Instead of training transformer weights, we explicitly track how words map to ontological layers. Patterns that stabilize become "known mappings". Patterns that don't stabilize get flagged for review.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    PHASE-14 PIPELINE                           │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Input: Text from RAG retrieval                                │
│     ↓                                                          │
│  Word Extraction (stop words filtered)                         │
│     ↓                                                          │
│  Phoneme Extractor → PPV estimate                              │
│     ↓                                                          │
│  Layer Assigner → Primary ontological layer                    │
│     ↓                                                          │
│  Character Deriver → Cross-layer propensities                  │
│     ↓                                                          │
│  K1 Atom Creation (Phase-13 integration)                       │
│     ↓                                                          │
│  Accumulator Update (pattern tracking)                         │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Components

| Component | File | Purpose |
|-----------|------|---------|
| Phoneme Extractor | `phoneme_extractor.py` | Word → phonemes → PPV estimate |
| Layer Assigner | `layer_assigner.py` | Word → ontological layer (O1-O10) |
| Character Deriver | `character_deriver.py` | Phonemes → cross-layer propensities |
| Accumulator | `accumulator.py` | Track stability of word mappings |
| RAG-K1 Pipeline | `rag_k1_pipeline.py` | Orchestrate full pipeline |

## Key Concepts

### Phoneme → PPV Estimation

Phonemes are classified by category (plosive, fricative, nasal, etc.) and mapped to an 8-dimensional PPV estimate:

```
(attack, sustain, brightness, warmth, density, flow, resonance, edge)
```

This connects to Phase-11B.3's canonicalization system.

### Layer Assignment

Words are assigned to one of 10 ontological layers based on:
1. POS tagging (cognitive verbs → THINKING, action verbs → ACTING, etc.)
2. Override lexicon (specific words like "purpose" → PURPOSING)
3. Context hints (surrounding words can modify assignment)

### Cross-Layer Character

The hypothesis: A word's phonemic structure creates "character" - propensity weights for how strongly it resonates with each layer beyond its primary assignment.

Example: "catalyze" maps to O3_ACTING, but has secondary resonance with O2_FORMING and O6_REASONING.

### Stability States

| Status | Observations | Confidence | Meaning |
|--------|--------------|------------|---------|
| UNSTABLE | < 10 | - | Too little data |
| EMERGING | 10-50 | < 0.7 | Pattern forming |
| STABLE | 50+ | > 0.8 | Reliable mapping |
| CONFLICTED | 50+ | < 0.5 | Needs review |

## What Works

1. **Phoneme extraction** from embedded dictionary + fallback rules
2. **PPV estimation** from phoneme categories
3. **Layer assignment** from POS heuristics + override lexicon
4. **Cross-layer character derivation** (experimental)
5. **Accumulation with stability tracking**
6. **K1 atom creation** integrating with Phase-13
7. **Full pipeline orchestration**
8. **104 tests passing**

## What's Experimental / Uncertain

1. **Phoneme → Layer affinity mappings**: These are initial hypotheses:
   - Plosives → ACTING, DIRECTING
   - Nasals → UNIFYING, THINKING
   - Long vowels → THINKING, ABSOLVING

   *These need validation through accumulation data.*

2. **Cross-layer character usefulness**: Does phonemic "character" actually predict useful secondary layer resonance? Unknown until tested with real data.

3. **Accumulation convergence**: Will patterns actually stabilize with RAG exposure? Depends on:
   - Quality of layer assignment heuristics
   - Consistency of word usage in corpus
   - Threshold tuning

## Tests

```
tests/
├── test_phoneme_extractor.py   # 28 tests
├── test_layer_assigner.py      # 25 tests
├── test_accumulator.py         # 27 tests
└── test_pipeline.py            # 24 tests

Total: 104 tests passing
```

## Usage

```python
from rag_k1_pipeline import create_pipeline, SAMPLE_RAG_TEXTS

# Create pipeline
pipeline = create_pipeline()

# Process text
result = pipeline.process_text(
    "The enzyme catalyzes the reaction.",
    "doc_001"
)

# Check results
print(f"Words processed: {result.words_processed}")
for wr in result.word_results:
    print(f"  {wr.word}: {wr.layer_assignment.layer.value}")

# Get accumulation report
report = pipeline.get_accumulation_report()
print(f"Total words: {report.total_words}")
print(f"Stable mappings: {report.stable_mappings}")
```

## Integration with Previous Phases

- **Phase-11B.3**: PPV estimates can be canonicalized through existing infrastructure
- **Phase-13**: K1 atoms are created and stored in K1Store
- **Phase-12**: Accumulated K1 knowledge can feed into generation pipeline

## Next Steps

1. Run against actual RAG corpus to see if patterns stabilize
2. Validate phoneme → layer affinity hypotheses
3. Tune stability thresholds based on observed data
4. Connect to Phase-12 generation pipeline

## Files

```
phase14_sandbox/
├── README.md                  # This file
├── SPECIFICATION.md           # Detailed specification
├── phoneme_extractor.py       # Phoneme extraction + PPV
├── layer_assigner.py          # Layer assignment
├── character_deriver.py       # Cross-layer character
├── accumulator.py             # Pattern tracking
├── rag_k1_pipeline.py         # Full pipeline
└── tests/
    ├── __init__.py
    ├── test_phoneme_extractor.py
    ├── test_layer_assigner.py
    ├── test_accumulator.py
    └── test_pipeline.py
```
