# Canonical Architecture Mapping: Hybrid ↔ Formulas ↔ Phases

## Overview

This document shows how `symbolu/hybrid/` (Phoneme-Transformer Optimization) connects to the existing Symbol-U architecture: `symbolu/formulas/` (Core/Substrate utilities) and the pipeline phases (PO1–P55).

---

## 1. Architecture Layer Model

```
╔═══════════════════════════════════════════════════════════════════════════════════╗
║                              SYMBOL-U LAYER MODEL                                  ║
╠═══════════════════════════════════════════════════════════════════════════════════╣
║                                                                                   ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │ LAYER 4: EXTERNAL INTERFACES                                                │  ║
║  │                                                                             │  ║
║  │   symbolu/llm/          ─── LLM Interface Contract (constrained renderer)  │  ║
║  │   symbolu/hybrid/       ─── Transformer Optimization (NEW)                 │  ║
║  │   symbolu/api/          ─── Unified API Layer                              │  ║
║  └─────────────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                            ║
║                                      ▼                                            ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │ LAYER 3: PIPELINE PHASES (Authoritative)                                   │  ║
║  │                                                                             │  ║
║  │   PO1-PO5   ─── Governance Phases (HIGH authority)                         │  ║
║  │   P6-P9    ─── Regime & Language Phases (HIGH authority)                   │  ║
║  │   P10-P13  ─── Acoustic Phases (MEDIUM authority)                          │  ║
║  │   P14-P55  ─── Extended Processing Phases                                  │  ║
║  │                                                                             │  ║
║  │   symbolu/mechanical/pipeline/    ─── Phase implementations                │  ║
║  │   symbolu/phases/                 ─── Phase 7/8 targeted generation        │  ║
║  └─────────────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                            ║
║                                      ▼                                            ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │ LAYER 2: RESONANCE ENGINE (Deterministic Semantics)                        │  ║
║  │                                                                             │  ║
║  │   symbolu/resonance/    ─── 10D Phoneme Vectors (NEW)                      │  ║
║  │                                                                             │  ║
║  │   • Phoneme → 12D ontological projection                                   │  ║
║  │   • Cosine similarity for word/phrase harmony                              │  ║
║  │   • Zero parameters, fully deterministic                                   │  ║
║  └─────────────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                            ║
║                                      ▼                                            ║
║  ┌─────────────────────────────────────────────────────────────────────────────┐  ║
║  │ LAYER 1: CORE/SUBSTRATE (Zero Authority)                                   │  ║
║  │                                                                             │  ║
║  │   symbolu/formulas/     ─── Foundational utilities                         │  ║
║  │                                                                             │  ║
║  │   • Acoustic Unit Mapper (phonetic decomposition)                          │  ║
║  │   • Vṛtti Mapper (mental fluctuation assignment)                           │  ║
║  │   • Resonance Formulas (SMI, ΔSMI, Bhava Gap)                              │  ║
║  │   • 40+ formula modules                                                    │  ║
║  │                                                                             │  ║
║  │   Invariants: NO_SEMANTICS, NO_INTENT, NO_ROUTING, DETERMINISTIC           │  ║
║  └─────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. File-Level Mapping

### 2.1 Hybrid ↔ Formulas Connections

| Hybrid File | Depends On | Formulas Analog | Relationship |
|-------------|------------|-----------------|--------------|
| `resonance/phoneme_map.py` | — | `formulas/acoustic_unit_mapper.py` | **Extends** acoustic categories with 10D affinities |
| `resonance/types.py` | — | `formulas/phase1_snapshot.py` | **Parallels** immutable data structure pattern |
| `resonance/engine.py` | `phoneme_map.py` | `formulas/resonance_formulas.py` | **Extends** resonance concept to word vectors |
| `resonance/analyzer.py` | `engine.py` | `formulas/vritti_mapper.py` | **Parallels** phoneme-to-meaning mapping |
| `hybrid/attention.py` | `resonance/*` | — | **Consumes** resonance for attention |
| `hybrid/prefilter.py` | `resonance/*` | — | **Consumes** resonance for filtering |
| `hybrid/router.py` | `resonance/*` | — | **Consumes** resonance for routing |

### 2.2 Detailed Connections

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        FORMULAS → RESONANCE EVOLUTION                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  formulas/acoustic_unit_mapper.py          resonance/phoneme_map.py             │
│  ───────────────────────────────           ─────────────────────────            │
│                                                                                 │
│  class SoundClass(Enum):          →        class PhonemeCategory(Enum):         │
│      PLOSIVE                                   PLOSIVE                          │
│      FRICATIVE                                 FRICATIVE                        │
│      NASAL                                     NASAL                            │
│      LIQUID                         +          LIQUID                           │
│      GLIDE                                     GLIDE                            │
│      VOWEL                                     VOWEL_SHORT, VOWEL_LONG          │
│                                               DIPHTHONG, AFFRICATE              │
│                                                                                 │
│  Acoustic decomposition            →        12D layer affinities                │
│  (no semantic meaning)                      (ontological projection)            │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  formulas/resonance_formulas.py            resonance/engine.py                  │
│  ──────────────────────────────            ────────────────────                 │
│                                                                                 │
│  compute_smi()                    →        word_to_vector()                     │
│  (consciousness state scalar)              (10D word vector)                    │
│                                                                                 │
│  compute_bhava_gap()              →        compute_resonance()                  │
│  (distance in bhava cycle)                 (cosine similarity)                  │
│                                                                                 │
│  compute_tension_corridor()       →        analyze_phrase_vectors()             │
│  (composite tension signal)                (phrase harmony analysis)            │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  formulas/vritti_mapper.py                 resonance/analyzer.py                │
│  ─────────────────────────                 ─────────────────────                │
│                                                                                 │
│  assign_vritti()                  →        get_phonemes()                       │
│  (mental fluctuation type)                 (phoneme extraction)                 │
│                                                                                 │
│  get_vritti_distribution()        →        analyze_phrase()                     │
│  (distribution across types)               (harmony distribution)               │
│                                                                                 │
│  get_dominant_vritti()            →        vec.dominant_layer                   │
│  (strongest fluctuation)                   (strongest dimension)                │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase Pipeline Integration

### 3.1 Where Hybrid Fits in PO1–P55

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PHASE PIPELINE FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  INPUT                                                                          │
│    │                                                                            │
│    ▼                                                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ PO1-PO5: GOVERNANCE (Who, Intent, Allowed Actions, Eligibility)        │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│    │                                                                            │
│    ▼                                                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ P6: REGIME SELECTION                                                   │    │
│  │                                                                        │    │
│  │   ┌──────────────────────────────────────────────────────────────┐    │    │
│  │   │ ★ HYBRID ROUTER INTEGRATION POINT ★                          │    │    │
│  │   │                                                               │    │    │
│  │   │ SemanticRouter can INFORM regime selection:                   │    │    │
│  │   │   • O10_UNIFYING dominant → REFLECT regime                    │    │    │
│  │   │   • O7_REASONING dominant → INFORM regime                    │    │    │
│  │   │   • O3_EXECUTION dominant → CLARIFY regime                      │    │    │
│  │   └──────────────────────────────────────────────────────────────┘    │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│    │                                                                            │
│    ▼                                                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ P7: DISCOURSE ACT RESOLUTION                                           │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│    │                                                                            │
│    ▼                                                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ P8: SEMANTIC SLOT RESOLUTION                                           │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│    │                                                                            │
│    ▼                                                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ P9: LEXICAL SELECTION                                                  │    │
│  │                                                                        │    │
│  │   ┌──────────────────────────────────────────────────────────────┐    │    │
│  │   │ ★ HYBRID PREFILTER INTEGRATION POINT ★                       │    │    │
│  │   │                                                               │    │    │
│  │   │ CandidatePreFilter can ACCELERATE lexical selection:          │    │    │
│  │   │   • Filter 50,000 vocabulary → 500 candidates                │    │    │
│  │   │   • Use phoneme resonance for fast pre-ranking               │    │    │
│  │   │   • Only run expensive scoring on filtered set               │    │    │
│  │   └──────────────────────────────────────────────────────────────┘    │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│    │                                                                            │
│    ▼                                                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ P10-P13: ACOUSTIC PHASES                                               │    │
│  │                                                                        │    │
│  │   P10: Acoustic Parameterization                                       │    │
│  │   P11: Prosodic Evidence                                               │    │
│  │   P12: Consistency Check                                               │    │
│  │   P13: Acoustic Safety Envelope                                        │    │
│  │                                                                        │    │
│  │   ┌──────────────────────────────────────────────────────────────┐    │    │
│  │   │ ★ HYBRID ATTENTION INTEGRATION POINT ★                       │    │    │
│  │   │                                                               │    │    │
│  │   │ PhonemeAttentionHead can REPLACE transformer attention:       │    │    │
│  │   │   • Acoustic consistency via phoneme similarity              │    │    │
│  │   │   • 82% FLOPs savings per attention head                     │    │    │
│  │   │   • Deterministic, zero-parameter attention                  │    │    │
│  │   └──────────────────────────────────────────────────────────────┘    │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│    │                                                                            │
│    ▼                                                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │ P14-P55: EXTENDED PHASES (Surface, Interaction, Fusion, etc.)          │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│    │                                                                            │
│    ▼                                                                            │
│  OUTPUT                                                                         │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Phase-by-Phase Integration Matrix

| Phase | Name | Hybrid Integration | Module Used |
|-------|------|-------------------|-------------|
| PO1 | Observer-Observed Grounding | — | — |
| PO2 | Intent & Response Posture | — | — |
| PO3 | Allowed Action Contract | — | — |
| PO4 | Planner Proposal Envelope | — | — |
| PO5 | Execution Eligibility Gate | — | — |
| **P6** | **Regime Selection** | **SemanticRouter** | `hybrid/router.py` |
| P7 | Discourse Act Resolver | — | — |
| P8 | Semantic Slot Resolution | — | — |
| **P9** | **Lexical Selection** | **CandidatePreFilter** | `hybrid/prefilter.py` |
| **P10** | **Acoustic Parameterization** | **PhonemeAttentionHead** | `hybrid/attention.py` |
| P11 | Prosodic Evidence | Resonance metrics | `resonance/engine.py` |
| P12 | Consistency Check | Harmony validation | `resonance/analyzer.py` |
| P13 | Acoustic Safety Envelope | Dissonance detection | `resonance/engine.py` |
| P14+ | Extended Phases | — | — |

---

## 4. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DATA FLOW: FORMULAS → HYBRID                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  INPUT: "Truth is light"                                                        │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ formulas/acoustic_unit_mapper.py                                        │   │
│  │                                                                         │   │
│  │   "Truth" → [AcousticUnit(TH, FRICATIVE), AcousticUnit(R, LIQUID), ...] │   │
│  │                                                                         │   │
│  │   Output: Phonetic decomposition (no semantics)                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ resonance/phoneme_map.py                                                │   │
│  │                                                                         │   │
│  │   TH → [0.4, 0.3, 0.2, 0.2, 0.4, 0.6, 0.3, 0.3, 0.2, 0.3]  (10D)       │   │
│  │   R  → [0.3, 0.5, 0.3, 0.2, 0.4, 0.3, 0.5, 0.3, 0.5, 0.3]  (10D)       │   │
│  │   UW → [0.4, 0.4, 0.2, 0.2, 0.2, 0.3, 0.4, 0.5, 0.6, 0.6]  (10D)       │   │
│  │                                                                         │   │
│  │   Output: Per-phoneme ontological affinities                            │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ resonance/engine.py                                                     │   │
│  │                                                                         │   │
│  │   word_to_vector("truth") →                                             │   │
│  │     WordVector(                                                         │   │
│  │       word="truth",                                                     │   │
│  │       phonemes=("T", "R", "UW", "TH"),                                  │   │
│  │       vector=(0.31, 0.38, 0.25, ..., 0.42),  # normalized 10D           │   │
│  │       dominant_layer="O10_UNIFYING"                                      │   │
│  │     )                                                                   │   │
│  │                                                                         │   │
│  │   compute_resonance(truth_vec, light_vec) → 0.91 (HARMONIC)            │   │
│  │                                                                         │   │
│  │   Output: Resonance score between words                                 │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ hybrid/attention.py                                                     │   │
│  │                                                                         │   │
│  │   PhonemeAttentionHead.compute_attention(["truth", "is", "light"])     │   │
│  │                                                                         │   │
│  │   Attention matrix:                                                     │   │
│  │     truth → truth: 1.00  truth → is: 0.72  truth → light: 0.91         │   │
│  │     is    → truth: 0.72  is    → is: 1.00  is    → light: 0.68         │   │
│  │     light → truth: 0.91  light → is: 0.68  light → light: 1.00         │   │
│  │                                                                         │   │
│  │   Output: Attention weights for transformer layer                       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│           │                                                                     │
│           ▼                                                                     │
│  OUTPUT: Attention matrix ready for transformer integration                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Ontological Layer Mapping

### 5.1 Formulas Kosha/Bhava ↔ Resonance 10D Layers

The existing Symbol-U architecture uses **Kosha** (sheaths) and **Bhava** (states) from Vedantic philosophy. The resonance engine maps to these concepts:

| Resonance Layer | Vedantic Concept | Kosha Alignment | Phase Relevance |
|-----------------|------------------|-----------------|-----------------|
| O5_COGNITION | Vijñānamaya | Intellectual sheath | P7 (Discourse) |
| O4_STRUCTURE | Manomaya | Mental sheath | P8 (Semantic) |
| O3_EXECUTION | Prāṇamaya | Vital sheath | P9 (Lexical) |
| O4_TAGGING | Annamaya | Physical sheath | P10 (Acoustic) |
| O6_AGENCY | Prāṇamaya | Vital sheath | P6 (Regime) |
| O7_REASONING | Vijñānamaya | Intellectual sheath | PO3 (Action) |
| O8_PURPOSE | Ānandamaya | Bliss sheath | PO2 (Intent) |
| O9_WITNESSES | Ānandamaya | Bliss sheath | PO1 (Observer) |
| O10_UNIFYING | Ānandamaya | Bliss sheath | Fusion |
| O12_ABSOLVING | Beyond Kosha | Pure consciousness | — |

### 5.2 Vṛtti Types ↔ Phoneme Categories

| Vṛtti Type | Mental Pattern | Phoneme Category | Sound Character |
|------------|---------------|------------------|-----------------|
| PRAMANA | Valid cognition | FRICATIVE | Continuous, analytical |
| VIPARYAYA | Misconception | PLOSIVE | Abrupt, forceful |
| VIKALPA | Imagination | GLIDE | Transitional, flowing |
| NIDRA | Sleep | NASAL | Resonant, sustained |
| SMRITI | Memory | LIQUID | Smooth, connecting |

---

## 6. Code Integration Examples

### 6.1 Using Resonance in P9 (Lexical Selection)

```python
# symbolu/mechanical/pipeline/p9_lexical/selector.py

from symbolu.hybrid import CandidatePreFilter

class LexicalSelector:
    def __init__(self):
        self.prefilter = CandidatePreFilter(threshold=0.5, top_k=100)
        self.vocabulary = load_vocabulary()  # 50,000 words

    def select_lexical_items(self, semantic_slots, context_words):
        """Select lexical items for semantic slots."""
        selected = {}

        for slot in semantic_slots:
            # Step 1: Pre-filter with phoneme resonance (FAST)
            target = context_words[0] if context_words else slot.name
            candidates = self.prefilter.filter(
                self.vocabulary,
                target=target,
            )
            # Now candidates is ~100 words instead of 50,000

            # Step 2: Full scoring on filtered set (EXPENSIVE but small)
            scores = self.full_lexical_scoring(candidates, slot)
            selected[slot] = max(scores, key=scores.get)

        return selected
```

### 6.2 Using Resonance in P10 (Acoustic Parameterization)

```python
# symbolu/mechanical/pipeline/p10_acoustic/parameterizer.py

from symbolu.hybrid import PhonemeAttentionHead

class AcousticParameterizer:
    def __init__(self):
        self.phoneme_attn = PhonemeAttentionHead(temperature=1.0)

    def compute_acoustic_coherence(self, tokens):
        """Compute acoustic coherence using phoneme attention."""
        result = self.phoneme_attn.compute_attention(tokens)

        # Check for dissonant pairs
        dissonant_pairs = []
        for i, weights in enumerate(result.attention_weights):
            for j, weight in enumerate(weights):
                if weight < 0.3 and i != j:
                    dissonant_pairs.append((tokens[i], tokens[j]))

        return {
            "coherent": len(dissonant_pairs) == 0,
            "dissonant_pairs": dissonant_pairs,
            "dominant_layers": result.dominant_layers,
        }
```

### 6.3 Using Resonance in P6 (Regime Selection)

```python
# symbolu/mechanical/pipeline/phase_p6/regime_selector.py

from symbolu.hybrid import SemanticRouter, ModelType

class RegimeSelector:
    def __init__(self):
        self.router = SemanticRouter(confidence_threshold=0.4)

    def select_regime(self, query, governance_context):
        """Select operational regime based on phoneme signature."""
        decision = self.router.route(query)

        # Map model type to regime
        regime_map = {
            ModelType.RELATIONSHIP: "REFLECT",
            ModelType.REASONING: "INFORM",
            ModelType.ACTION: "CLARIFY",
            ModelType.CREATIVE: "SUPPORT",
            ModelType.REFLECTIVE: "REFLECT",
            ModelType.DIRECTIVE: "DIRECT",
            ModelType.TRANSCENDENT: "HOLD",
            ModelType.GENERAL: governance_context.default_regime,
        }

        return regime_map.get(decision.model_type, "STABILIZE")
```

---

## 7. Invariant Preservation

### 7.1 Core/Substrate Invariants (Maintained)

The hybrid modules maintain the same invariants as `formulas/`:

| Invariant | formulas/ | resonance/ | hybrid/ |
|-----------|-----------|------------|---------|
| NO_SEMANTICS | ✓ | Partial* | Partial* |
| NO_INTENT | ✓ | ✓ | ✓ |
| NO_ROUTING | ✓ | ✓ | Partial** |
| NO_POLICY | ✓ | ✓ | ✓ |
| NO_LLM_CALLS | ✓ | ✓ | ✓ |
| DETERMINISTIC | ✓ | ✓ | ✓ |

*Resonance adds ontological semantics (10D projections) but these are derived from phonetic structure, not learned from text.

**Router suggests routing but does not enforce it; final authority remains with governance phases.

### 7.2 Authority Flow (Preserved)

```
PO1-PO5 (HIGH)  →  Cannot be overridden by hybrid
      ↓
P6-P9 (HIGH)    →  Hybrid can INFORM but not OVERRIDE
      ↓
P10-P13 (MEDIUM) → Hybrid can ACCELERATE these phases
      ↓
P14+ (LOW)      →  Hybrid optimizations apply here
```

---

## 8. Summary

| Component | Layer | Authority | Purpose |
|-----------|-------|-----------|---------|
| `formulas/` | Core/Substrate | ZERO | Foundational utilities |
| `resonance/` | Resonance | ZERO | 10D phoneme projections |
| `hybrid/` | External Interface | ZERO* | Transformer optimization |
| `phases/` | Pipeline | HIGH | Authoritative processing |
| `mechanical/` | Pipeline | HIGH | Phase implementations |

*Hybrid has zero authority over meaning/intent but can optimize computation.

### Key Insight

The hybrid system extends the Core/Substrate pattern:
- **Formulas** → Acoustic decomposition (no meaning)
- **Resonance** → 10D meaning from structure (deterministic)
- **Hybrid** → Use resonance to optimize transformers

All three layers preserve the fundamental Symbol-U principle: **meaning derived from structure, not statistics**.

---

*Document Version: 1.0*
*Last Updated: 2025-12-19*
