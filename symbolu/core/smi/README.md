# SMI (Semantic Mismatch Index) Module

## Overview

The SMI module computes the distance between **inner acoustic meaning (kosha)** and **outer semantic meaning (ontology)** for text analysis. This enables quantification of the gap between what words "sound like" phonetically and what they "mean" semantically.

## Core Concepts

### Kosha (5 Layers) - Inner Consciousness Depth
From physical to transcendent:

| Layer | Name | Description | Dominant Vritti |
|-------|------|-------------|-----------------|
| 1 | ANNAMAYA | Physical/gross body | Nidra (dormancy) |
| 2 | PRANAMAYA | Energy/vital breath | Vikalpa (imagination) |
| 3 | MANOMAYA | Mind/emotions | Viparyaya (misperception) |
| 4 | VIJNANAMAYA | Wisdom/discernment | Pramana (valid cognition) |
| 5 | ANANDAMAYA | Bliss/pure awareness | Pramana (pure) |

### Ontology (10 Layers) - Outer Manifestation Breadth
From concrete to universal:

| Layer | Name | Description |
|-------|------|-------------|
| 1 | Execution | Action/doing |
| 2 | Identity | Self/being |
| 3 | Form | Shape/structure |
| 4 | Cognition | Knowing/thinking |
| 5 | Agency | Will/intention |
| 6 | Reasoning | Logic/analysis |
| 7 | Purpose | Meaning/goal |
| 8 | Observation | Witness/awareness |
| 9 | Core | Essence/truth |
| 10 | Universal | Cosmic/absolute |

### Vritti (5 Modes) - Consciousness States
From Yoga Sutras 1.6:

| Vritti | Sanskrit | Description |
|--------|----------|-------------|
| Pramana | प्रमाण | Valid cognition (perception, inference, testimony) |
| Viparyaya | विपर्यय | Misperception, wrong knowledge |
| Vikalpa | विकल्प | Conceptual imagination, verbal fancy |
| Smrti | स्मृति | Memory, recall |
| Nidra | निद्रा | Sleep, dormancy, absence |

## Architecture

```
Text Input
    │
    ▼
┌─────────────────┐
│  syllabify()    │  Split into CV syllables
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│extract_consonant│  Get leading consonant
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ get_kosha_level │  Consonant → Kosha (1-5)
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│compute_vritti_distribution│  Kosha → Vritti 5D vector
└────────┬────────────────┘
         │
         ▼
┌─────────────────┐
│get_ontology_level│  Context → Ontology (1-10)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   SMI = |K-O|   │  Normalized distance [0,1]
│      / max      │
└─────────────────┘
```

## Components

### 1. SMIEngine (`smi_engine.py`)
Main computation engine.

```python
from symbolu.core.smi import SMIEngine, compute_smi

engine = SMIEngine()
result = engine.compute("hello world")
print(result.smi)  # 0.0 - 1.0
print(result.kosha_level)  # Average kosha
print(result.ontology_level)  # Average ontology

# Quick computation
smi = compute_smi("hello world")
```

### 2. VrittiMapper (`vritti_mapping.py`)
Maps syllables to 5D vritti probability distributions.

```python
from symbolu.core.smi import VrittiMapper, map_syllable_to_vritti

mapper = VrittiMapper()
dist = mapper.map_syllable_to_vritti("ka")
# Returns: [pramana, viparyaya, vikalpa, smrti, nidra]
```

### 3. AcousticMapper (`acoustic_mapper.py`)
Maps consonants to acoustic features.

```python
from symbolu.core.smi import AcousticMapper, get_consonant_features

mapper = AcousticMapper()
features = mapper.get_acoustic_features("k")
# Returns: {articulation, voicing, aspiration, place, energy}
```

### 4. AspectMapper (`aspect_mapping.py`)
Maps words to 10D aspect distributions with vritti-aspect coupling.

```python
from symbolu.core.smi import AspectMapper, VRITTI_ASPECT_COUPLING_MATRIX

mapper = AspectMapper()
aspect = mapper.map_word("understanding")
# Returns 10D distribution across ontology layers
```

## Consonant → Kosha Mapping

Based on place of articulation and phonetic depth:

| Consonants | Kosha | Rationale |
|------------|-------|-----------|
| k, g, kh, gh, ng | 2 (PRANAMAYA) | Velar (back throat) |
| ch, j, jh, ny | 3 (MANOMAYA) | Palatal (mid-mouth) |
| t, d, th, dh, n | 3 (MANOMAYA) | Retroflex/dental |
| p, b, ph, bh, m | 1 (ANNAMAYA) | Labial (lips - physical) |
| y, r, l, v | 4 (VIJNANAMAYA) | Semi-vowels (flowing) |
| sh, s, h | 5 (ANANDAMAYA) | Sibilants (breath-like) |

## Vritti-Aspect Coupling Matrix

5x10 matrix bridging vritti space to aspect space:

```
                 Exec  Ident  Form  Cogn  Agen  Reas  Purp  Obs   Core  Univ
Pramana         0.02   0.03  0.03  0.10  0.05  0.20  0.12  0.20  0.15  0.10
Viparyaya       0.05   0.08  0.20  0.25  0.20  0.10  0.05  0.03  0.02  0.02
Vikalpa         0.10   0.15  0.15  0.20  0.15  0.10  0.08  0.04  0.02  0.01
Smrti           0.08   0.12  0.10  0.15  0.10  0.15  0.12  0.08  0.06  0.04
Nidra           0.20   0.15  0.15  0.10  0.10  0.08  0.08  0.06  0.05  0.03
```

## Usage Examples

### Basic SMI Computation
```python
from symbolu.core.smi import SMIEngine

engine = SMIEngine()

# Analyze a word
result = engine.compute("consciousness")
print(f"SMI: {result.smi:.3f}")
print(f"Kosha: {result.kosha_level:.2f}")
print(f"Ontology: {result.ontology_level:.2f}")

# Analyze with context
result = engine.compute("love", context="philosophy")
```

### Per-Word Analysis
```python
from symbolu.core.smi import SMIEngine

engine = SMIEngine()
words = ["I", "think", "therefore", "I", "am"]
analyses = engine.compute_per_word(words)

for analysis in analyses:
    print(f"{analysis.word}: K={analysis.kosha:.1f}, O={analysis.ontology:.1f}")
```

### Vritti Distribution
```python
from symbolu.core.smi import VrittiMapper, VrittiType

mapper = VrittiMapper()
result = mapper.map_syllable_detailed("om")

print(f"Dominant: {result.dominant.value}")
print(f"Weight: {result.dominant_weight:.3f}")
print(f"Distribution: {result.as_dict()}")
```

## Integration Points

The SMI module integrates with:

1. **Chitta-Vritti Module**: Provides vritti distributions for CV analysis
2. **Presentation Layer**: Informs delivery mode based on SMI score
3. **DHA (Delivery-Hesitation-Adaptation)**: Uses SMI for tone calibration
4. **Coherence Engine**: SMI contributes to coherence scoring

## Design Principles

1. **Deterministic**: Same input always produces same output
2. **Phoneme-based**: Analysis starts from acoustic properties
3. **Layer-aware**: Respects kosha/ontology hierarchies
4. **Culturally-grounded**: Based on Sanskrit phonetic science

## References

- Yoga Sutras 1.5-1.11 (Vritti classification)
- Taittiriya Upanishad (Pancha Kosha model)
- Sanskrit phonetics (Shiksha texts)
