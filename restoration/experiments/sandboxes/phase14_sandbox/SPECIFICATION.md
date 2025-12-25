# Phase-14: Phonemic-Ontological Accumulator

## Problem Statement

### The Core Question

Can a structured system (ontology + phonemics) accumulate meaning representations through RAG exposure, creating an alternative to transformer-based statistical learning?

### What Transformers Do

Transformers learn meaning through:
1. Massive corpus exposure (billions of tokens)
2. Statistical pattern recognition (attention weights)
3. Frozen knowledge in weights (not editable after training)
4. Black-box representations (not auditable)

**Result**: Powerful but opaque, expensive to train, not correctable.

### What We Hypothesize

Meaning can be represented through:
1. **Designed structure** (10 ontological layers, 17 K1 slots, 14 discourse acts)
2. **Phonemic character** (how a word's sound creates propensities across layers)
3. **Incremental accumulation** (patterns emerge through RAG exposure, not bulk training)
4. **Auditable atoms** (every mapping has provenance, is editable)

**Hypothesis**: If we expose this structure to knowledge (via RAG), patterns will stabilize over time, creating a representation that:
- Starts useful immediately (not useless until fully trained)
- Improves with exposure
- Remains auditable and correctable

---

## The Gap Between Current State and Vision

### What We Have (Phases 1-13)

| Component | Status | Purpose |
|-----------|--------|---------|
| PPV (8 dimensions) | ✅ Built | Acoustic/prosodic signal |
| Canonicalizer | ✅ Built | Collapse PPV to 6 representatives |
| Ontological Routing | ✅ Built | Route to 10 families |
| K1 Schema | ✅ Built | 17 slots, 14 discourse acts |
| K1 Store | ✅ Built | Indexed storage with ledger |

### What We Don't Have

| Component | Status | Purpose |
|-----------|--------|---------|
| Word → Phoneme analyzer | ❌ Missing | Extract phonemic structure from words |
| Word → Layer mapper | ❌ Missing | Assign word to primary ontological layer |
| Cross-layer character | ❌ Missing | How word's phonemes affect other 9 layers |
| RAG → K1 pipeline | ❌ Missing | Ingest retrieved content into K1 |
| Pattern accumulator | ❌ Missing | Track stability of mappings over time |

---

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                 PHASE-14: ACCUMULATOR PIPELINE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: RAG Retrieval                                          │
│  ────────────────────                                           │
│  Input: Query                                                   │
│  Output: Text chunks from knowledge base                        │
│  Example: "The enzyme catalyzes the reaction between..."        │
│                                                                 │
│  Step 2: Word Extraction                                        │
│  ───────────────────────                                        │
│  Input: Text chunk                                              │
│  Output: List of significant words                              │
│  Example: ["enzyme", "catalyzes", "reaction"]                   │
│                                                                 │
│  Step 3: Phonemic Analysis (Simplified)                         │
│  ──────────────────────────────────────                         │
│  Input: Word                                                    │
│  Output: Phoneme sequence + PPV-like vector                     │
│  Example: "catalyzes" → [k,æ,t,ə,l,aɪ,z,ɪ,z] → PPV(3,4,5,...)  │
│                                                                 │
│  Step 4: Ontological Layer Assignment                           │
│  ────────────────────────────────────                           │
│  Input: Word + context + phonemic profile                       │
│  Output: Primary ontological layer                              │
│  Example: "catalyzes" → O3_EXECUTION (action verb)                 │
│                                                                 │
│  Step 5: Cross-Layer Character Derivation                       │
│  ─────────────────────────────────────────                      │
│  Input: Phonemic profile + primary layer                        │
│  Output: Character propensities for other 9 layers              │
│  Example: "catalyzes" →                                         │
│    O5_COGNITION: low (not reflective)                            │
│    O4_STRUCTURE: medium (creates something)                       │
│    O3_EXECUTION: PRIMARY                                           │
│    O7_REASONING: medium (implies causation)                     │
│    ...                                                          │
│                                                                 │
│  Step 6: K1 Atom Creation                                       │
│  ────────────────────────                                       │
│  Input: Word + layer + character + context                      │
│  Output: K1Atom stored in K1Store                               │
│  Example:                                                       │
│    atom_id: k1_abc123                                           │
│    layer: O3_EXECUTION                                             │
│    slot: CAUSE (catalyzes causes reaction)                      │
│    discourse_act: TRIGGER                                       │
│    payload_ref: "rag:chunk_id:word_pos"                         │
│    provenance: "corpus_v1:doc_123"                              │
│                                                                 │
│  Step 7: Pattern Accumulation                                   │
│  ───────────────────────────                                    │
│  Track: How often does "catalyze" → O3_EXECUTION?                  │
│  When stable: Promote to "known mapping"                        │
│  When conflicting: Flag for review                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## How Each Step Works (Basic Level)

### Step 3: Phonemic Analysis

**Problem**: How do we get phonemes from a word?

**Solution Options**:
1. **Lookup table**: Use CMU Pronouncing Dictionary (free, 134k words)
2. **G2P model**: Grapheme-to-phoneme neural model (more coverage)
3. **Simplified**: Rule-based approximation (fastest to build)

**For prototype**: Use CMU dictionary + fallback rules

**Output**:
```python
"catalyzes" → {
    "phonemes": ["K", "AE", "T", "AH", "L", "AY", "Z", "IH", "Z"],
    "ppv_estimate": (3, 4, 5, 4, 3, 5, 6, 4)  # derived from phoneme properties
}
```

### Step 4: Ontological Layer Assignment

**Problem**: How do we know which layer a word belongs to?

**Solution Options**:
1. **POS-based heuristics**: Verbs often → ACTING, abstract nouns → THINKING
2. **WordNet integration**: Use semantic categories
3. **Context-based**: Look at surrounding words
4. **Hybrid**: Combine all three

**For prototype**: POS tagging + simple heuristics

**Heuristic Examples**:
| Pattern | Primary Layer |
|---------|---------------|
| Action verbs (run, make, do) | O3_EXECUTION |
| Cognitive verbs (think, consider) | O5_COGNITION |
| Creation verbs (form, build, shape) | O4_STRUCTURE |
| Causal connectors (because, therefore) | O7_REASONING |
| Goal words (aim, purpose, intend) | O8_PURPOSE |

### Step 5: Cross-Layer Character

**Problem**: How does a word's phonemic structure create propensities in other layers?

**Hypothesis**: Phonemic properties correlate with layer affinity.

**Simplified Model**:
```
Phoneme properties → Layer affinities

Example mappings (to be validated):
- Plosives (p, b, t, d, k, g) → higher ACTING affinity
- Fricatives (f, v, s, z, sh) → higher DIRECTING affinity
- Nasals (m, n, ng) → higher UNIFYING affinity
- Long vowels → higher THINKING/REFLECTING affinity
```

**For prototype**: Simple weighted scoring based on phoneme categories

### Step 7: Pattern Accumulation

**Problem**: How do we know when a mapping is "stable"?

**Solution**: Track statistics per word:
```python
WordStats = {
    "catalyze": {
        "observations": 47,
        "layer_votes": {
            "O3_EXECUTION": 42,
            "O4_STRUCTURE": 3,
            "O7_REASONING": 2
        },
        "confidence": 0.89,  # 42/47
        "status": "STABLE"   # confidence > 0.8 after N observations
    }
}
```

**Stability rules**:
- `UNSTABLE`: < 10 observations
- `EMERGING`: 10-50 observations, confidence < 0.7
- `STABLE`: 50+ observations, confidence > 0.8
- `CONFLICTED`: 50+ observations, confidence < 0.5 → flag for review

---

## What Success Looks Like

### Minimum Viable Success

After processing N documents through the pipeline:

1. **Vocabulary grows**: System has seen and mapped X unique words
2. **Patterns emerge**: Some words reach STABLE status
3. **Predictions work**: Given a new word, system can predict:
   - Primary ontological layer
   - Cross-layer character profile
   - Appropriate K1 slot and discourse act
4. **Accuracy measurable**: We can test predictions against held-out data

### Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Layer prediction accuracy | > 70% | Compare to human annotation sample |
| Stability rate | > 50% of vocabulary | Words reaching STABLE after exposure |
| K1 atom coherence | No slot violations | Automated invariant checks |
| Accumulation growth | Linear with exposure | Vocabulary size vs documents processed |

---

## Minimal Prototype Scope

### What I Will Build

1. **Phoneme Extractor** (`phoneme_extractor.py`)
   - Uses CMU dictionary
   - Fallback to simple rules
   - Outputs phoneme sequence + PPV estimate

2. **Layer Assigner** (`layer_assigner.py`)
   - POS tagging (using simple rules or spaCy)
   - Heuristic mapping to ontological layers
   - Returns primary layer + confidence

3. **Character Deriver** (`character_deriver.py`)
   - Takes phoneme sequence
   - Computes affinity scores for each layer
   - Returns cross-layer character profile

4. **Accumulator** (`accumulator.py`)
   - Tracks word statistics
   - Computes stability status
   - Stores patterns in K1Store

5. **Pipeline** (`rag_k1_pipeline.py`)
   - Orchestrates all components
   - Input: text chunk
   - Output: K1 atoms + updated statistics

6. **Tests** (target: 30+ tests)
   - Phoneme extraction accuracy
   - Layer assignment coherence
   - Accumulation determinism
   - Pattern stability logic

### What I Will NOT Build (Yet)

- Actual RAG retrieval system (will mock with sample texts)
- Neural G2P model (will use dictionary + rules)
- LLM integration (this is about the accumulator, not generation)
- Production optimization (prototype first)

---

## How This Connects to What We've Built

```
Phase-11B.3 (PPV Canonicalizer)
       │
       │ Provides: canonical signature structure
       ▼
Phase-13 (K1 Schema + Store)
       │
       │ Provides: storage for accumulated knowledge
       ▼
Phase-14 (This Prototype)
       │
       │ Adds: phonemic analysis + layer assignment + accumulation
       ▼
Future: Generation that uses accumulated K1 knowledge
```

---

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Phoneme→Layer mapping is arbitrary | Medium | Start with POS-based, add phonemic later |
| Patterns don't stabilize | Low | Adjust stability thresholds |
| CMU dictionary too limited | Medium | Add fallback rules, expand later |
| Cross-layer character is noise | Medium | Make it optional, test with/without |

---

## Timeline Estimate

| Component | Complexity | Order |
|-----------|-----------|-------|
| Phoneme Extractor | Low | 1st |
| Layer Assigner | Medium | 2nd |
| Character Deriver | Medium | 3rd |
| Accumulator | Low | 4th |
| Pipeline + Tests | Medium | 5th |

---

## Your Decision Points

Before I build, please confirm:

1. **Phoneme source**: CMU dictionary + fallback rules? Or something else?

2. **Layer assignment**: Start with POS heuristics? Or do you have specific word→layer mappings in mind?

3. **Cross-layer character**: Include in prototype? Or defer until layer assignment is proven?

4. **Test corpus**: Should I use a small sample corpus? Or do you have specific texts?

---

## Summary

**Problem**: Can structured phonemic-ontological analysis accumulate meaning through RAG exposure?

**Solution**: Build a pipeline that:
1. Extracts phonemes from words
2. Assigns words to ontological layers
3. Derives cross-layer character
4. Stores as K1 atoms
5. Tracks pattern stability over time

**Why this might work**: The structure (K1 + ontology) is designed, not learned. Only the content (word mappings) accumulates. This means partial knowledge is still useful.

**Why it might not**: If phoneme→layer mappings are too noisy, patterns won't stabilize. We'll know after testing.

---

Do you trust this process? Should I proceed?
