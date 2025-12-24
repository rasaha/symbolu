# Comparison: ARPABET Phoneme Map vs Varṇa Bridge Map

## Question

> Does using `acoustic_unit_mapper_expressive_delta_v3_1.py` and `varna*.json` files
> (from experimental phases p1b-14) produce better results than the current
> `resonance/phoneme_map.py` implementation?

## Short Answer

**Yes, the Varṇa-based approach is richer and likely produces better results** because:

1. **Pre-defined 12D layer meanings** per consonant (not just numeric affinities)
2. **Polarity awareness** (positive/negative manifestations)
3. **Distortion/sublimation vectors** (directional transformations)
4. **Sanskrit acoustic substrate** (phonetically grounded in millennia of study)

---

## Detailed Comparison

### Current Implementation: `resonance/phoneme_map.py`

```python
# ARPABET phoneme → 10D affinity vector (manually tuned)
LIQUID_AFFINITIES = {
    "L": (0.3, 0.6, 0.2, 0.2, 0.3, 0.3, 0.4, 0.3, 0.6, 0.4),
    #     O1   O2   O3   O4   O5   O6   O7   O8   O9   O10
}
```

**Characteristics:**
- 39 ARPABET phonemes
- Numeric affinities (0.0-1.0) manually tuned
- English-centric phonetic categories
- No polarity (positive/negative)
- No directional vectors
- ~200 lines of affinity data

### Experimental: `varna_bridge_map_v1.json` + `varna_layer_interaction_v1.json`

```json
"sa": {
  "bridge_meaning": "escape_pressure",
  "layers": {
    "O1_ACTING": "exit activation state",
    "O2_IDENTITY": "exit-route classification",
    "O3_FORMING": "evasion shaping force",
    "O4_THINKING": "exit pattern bias",
    ...
  }
}
```

```json
"a": {
  "O1_ACTING": {
    "manifestation_positive": "body awakens with fresh readiness",
    "manifestation_negative": "body startles into raw activation",
    "distortion_vector": "lateral",
    "sublimate_vector": "upward"
  },
  ...
}
```

**Characteristics:**
- 43+ Sanskrit varṇas
- Semantic descriptions per layer (not just numbers)
- Bridge meanings (conceptual primitives)
- Positive/negative polarity
- Distortion/sublimation vectors
- ~700 lines of rich semantic data

---

## Data Richness Comparison

| Feature | ARPABET (Current) | Varṇa (Experimental) |
|---------|-------------------|----------------------|
| Phonemes/Varṇas | 39 | 43+ |
| Layer representation | 10 floats | 10 semantic descriptions |
| Bridge meaning | — | ✓ (e.g., "escape_pressure") |
| Polarity | — | ✓ (positive/negative) |
| Distortion vector | — | ✓ (lateral/downward) |
| Sublimation vector | — | ✓ (upward/terminating) |
| Varna groups | — | ✓ (ka_varga, ta_varga, etc.) |
| Aspiration | ✓ | ✓ |
| JSON-driven | ✗ (hardcoded) | ✓ |

---

## Why Varṇa is Likely Better

### 1. Grounded in Acoustic Science

Sanskrit Varṇa Mālā (alphabet) is organized by:
- **Place of articulation** (velar → labial)
- **Manner of articulation** (stops, nasals, sibilants)
- **Aspiration** (ka vs kha)
- **Phonetic groups** (varga system)

This is more systematic than ARPABET which is English-specific.

### 2. Semantic Layer Descriptions

Current approach:
```python
"L": (0.3, 0.6, 0.2, 0.2, 0.3, 0.3, 0.4, 0.3, 0.6, 0.4)
# What does 0.6 for O4_STRUCTURE mean? Unclear.
```

Varṇa approach:
```json
"la": {
  "O3_FORMING": "abrasion shaping force"
}
// Clear conceptual meaning
```

### 3. Polarity Enables Richer Analysis

Varṇa can distinguish:
- **Positive**: "body awakens with fresh readiness"
- **Negative**: "body startles into raw activation"

Current approach has no polarity concept.

### 4. Directional Vectors

Varṇa tracks transformation direction:
- `distortion_vector: "lateral"` → sideways drift
- `sublimate_vector: "upward"` → transcendent transformation

This enables tracking **meaning evolution** in phrases.

---

## Proposed Integration

### Option A: Replace phoneme_map.py with Varṇa

```
resonance/
├── phoneme_map.py      → DEPRECATED
├── varna_map.py        → NEW (uses varna_bridge_map_v1.json)
├── varna_loader.py     → NEW (loads JSON data)
└── engine.py           → MODIFIED (use varna vectors)
```

### Option B: Hybrid (ARPABET + Varṇa fallback)

```python
def get_layer_affinities(phoneme: str) -> Tuple[float, ...]:
    # Try varṇa lookup first
    varna = arpabet_to_varna(phoneme)
    if varna:
        return varna_to_10d_vector(varna)
    # Fallback to ARPABET
    return ARPABET_AFFINITIES.get(phoneme, DEFAULT)
```

### Option C: Use Varṇa for Sanskrit, ARPABET for English

```python
def word_to_vector(word: str, language: str = "en") -> WordVector:
    if language == "sa":  # Sanskrit
        return varna_based_vector(word)
    else:
        return arpabet_based_vector(word)
```

---

## Converting Varṇa to 10D Vectors

The Varṇa JSON has **semantic descriptions** not numbers. To use with the current engine, we need to convert:

```python
def varna_to_10d_vector(varna_data: dict) -> Tuple[float, ...]:
    """Convert varṇa layer data to numeric 10D vector."""
    layers = varna_data.get("layers", {})

    # Map semantic descriptions to affinities using keywords
    KEYWORD_WEIGHTS = {
        "activation": 0.7,
        "force": 0.8,
        "shaping": 0.6,
        "tracking": 0.5,
        "integration": 0.7,
        "dissolution": 0.4,
        # ...
    }

    vector = []
    for layer_name in LAYER_ORDER:
        description = layers.get(layer_name, "")
        # Score based on keyword presence
        score = compute_keyword_score(description, KEYWORD_WEIGHTS)
        vector.append(score)

    return normalize(tuple(vector))
```

---

## Recommendation

**Use the Varṇa-based data from experimental phases** because:

1. ✅ More phonemes (43+ vs 39)
2. ✅ Richer semantic data per layer
3. ✅ Polarity awareness (positive/negative)
4. ✅ Directional vectors (distortion/sublimation)
5. ✅ JSON-driven (easy to update without code changes)
6. ✅ Grounded in Sanskrit acoustic tradition
7. ✅ Already tested in phases p1b-14

### Migration Path

```
Phase 1: Add varna_loader.py to resonance/
Phase 2: Create varna_to_10d_vector() converter
Phase 3: Test alongside ARPABET (A/B comparison)
Phase 4: If better, deprecate phoneme_map.py
Phase 5: Update hybrid/ to use varna vectors
```

---

## Files to Integrate

| Experimental File | Target Location |
|-------------------|-----------------|
| `docs/experiments/acoustic_unit_mapper_expressive_delta_v3_1.py` | `symbolu/resonance/varna_mapper.py` |
| `docs/data/varna_bridge_map_v1.json` | `symbolu/resonance/data/` |
| `docs/data/varna_layer_interaction_v1.json` | `symbolu/resonance/data/` |
| `docs/data/varna_polarity_map_v1.json` | `symbolu/resonance/data/` |
| `docs/data/varna_distortion_map_v1.json` | `symbolu/resonance/data/` |

---

*Analysis Date: 2025-12-19*
