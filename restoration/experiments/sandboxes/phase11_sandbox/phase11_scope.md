# Phase-11 Scope Definition

> This document defines what Phase-11 sandbox experiments take as input,
> produce as output, and how we judge success or failure.
>
> There are no formal invariants here—just scope boundaries.

---

## Inputs

Phase-11 sandbox experiments receive inputs from upstream phases and the PPV system.

### From Phase-10 (Acoustic Parameterization)

The `Phase10Result` provides:

| Field | Type | Description |
|-------|------|-------------|
| `artifact_hash` | 64-char hex | Deterministic hash of upstream artifact |
| `vc_facts` | tuple[str, ...] | Verified VC facts (VC-1 through VC-5) |
| `acoustic_regime` | AcousticRegime | NEUTRAL, SOFT, FLAT, or RESTRAINED |
| `source_phoneme_ids` | tuple[str, ...] | Phoneme identifiers from upstream |

### From Phase-10 Envelope (Optional PPV Attachment)

The `Phase10Envelope` may include:

| Field | Type | Description |
|-------|------|-------------|
| `ppv` | PPVVector or None | Optional 8-dimensional structural signal |
| `envelope_hash` | 64-char hex | Hash of the envelope |

### PPV Vector Structure

When present, the PPV provides 8 numeric dimensions:

| Dimension | Range | Description |
|-----------|-------|-------------|
| `edge_tension` | 0–7 | Phoneme boundary tension signature |
| `edge_release` | 0–7 | Phoneme boundary release signature |
| `onset_sharpness` | 0–7 | Onset attack characteristics |
| `sonority_lift` | 0–7 | Sonority contour signature |
| `continuity` | 0–7 | Flow continuity marker |
| `discontinuity` | 0–7 | Break/pause marker |
| `rhythmic_impulse` | 0–7 | Rhythmic pulse signature |
| `stability_pressure` | 0–7 | Structural stability marker |

The `aggregate` field provides a deterministic weighted checksum.

### From Ontological System

Available for routing and selection:

| Input | Description |
|-------|-------------|
| 10 ontological layers | ACTING through ABSOLVING |
| Layer-to-phase mappings | Which layers apply to which phases |
| Relation dominance states | ACTIVE, SUPPRESSED, NEUTRAL |

### Experimental Inputs (Sandbox-Specific)

| Input | Description |
|-------|-------------|
| Random seed | For reproducible stochastic experiments |
| Weight vectors | Soft biases for layer/path selection |
| Mode configuration | Which sandbox mode is active |
| Temperature/variance | How much randomness to inject |

---

## Outputs

Phase-11 sandbox produces experimental artifacts. These are NOT production outputs.

### Primary Output Types

| Output | Description |
|--------|-------------|
| **Text fragments** | Generated text strings (may be incoherent) |
| **Phoneme sequences** | Ordered phoneme identifiers |
| **Path traces** | Ontological paths traversed during generation |
| **Weight logs** | Which biases were applied where |

### Experimental Artifact Structure (Conceptual)

```
ExperimentalOutput:
  output_text: str                    # Generated text (may be garbage)
  output_phonemes: list[str]          # Phoneme sequence
  path_trace: list[OntologicalLayer]  # Layers visited
  ppv_influence_log: dict             # How PPV affected generation
  randomness_applied: float           # How much stochastic noise
  mode_used: str                      # Which sandbox mode
  experiment_id: str                  # Unique identifier
```

### What Outputs Are NOT

- Verified
- Meaningful
- Safe
- Deterministic
- Auditable
- Production-ready

---

## Success Criteria (Qualitative)

Success in Phase-11 is **human-judged**, not machine-verified.

### Signs of Potential Success

| Indicator | Description |
|-----------|-------------|
| **Recognizable structure** | Output has phonotactic plausibility |
| **Variation with bias** | Changing PPV weights changes output character |
| **Path coherence** | Ontological path selection produces distinguishable modes |
| **Non-trivial generation** | Output is not identical to input or empty |
| **Reproducible patterns** | Same seed + config → same output |

### Questions That Suggest Success

- "This sounds different when I change the PPV weights"
- "The FORMING-biased output feels more shaped than THINKING-biased"
- "There's a recognizable pattern here, even if it doesn't mean anything"
- "The variation is interesting, not just noise"

### Success Does NOT Mean

- The output is correct
- The output is meaningful
- The system is intelligent
- The approach should be productionized
- We have solved generation

---

## Failure Criteria (Qualitative)

### Signs of Failure

| Indicator | Description |
|-----------|-------------|
| **Collapse to noise** | Output is random characters with no structure |
| **Collapse to uniformity** | All outputs are identical regardless of input |
| **Input echo** | Output is just the input unchanged |
| **Trivial generation** | Output is empty, single character, or degenerate |
| **Uncontrollable variance** | Small input changes → wildly different outputs |
| **No PPV influence** | Changing PPV weights has no effect |
| **No path influence** | Ontological selection has no effect |

### Questions That Suggest Failure

- "Everything looks the same no matter what I change"
- "This is just random garbage"
- "The PPV does nothing"
- "I can't tell what the ontological layers are doing"
- "This is indistinguishable from `random.choice(alphabet)`"

### Failure Modes to Watch For

1. **Degenerate attractors**: System always produces same output
2. **Chaotic sensitivity**: Tiny changes explode into unrelated outputs
3. **Null generation**: System produces nothing useful
4. **Template leakage**: Output is clearly just template fragments
5. **Combinatorial explosion**: System generates infinitely with no coherence

---

## Scope Boundaries

### In Scope

- Probabilistic path selection over ontological graph
- PPV-biased phoneme/word selection
- Random sampling with controlled variance
- Soft weighting of layer influence
- Experimental text/phoneme generation
- Human evaluation of outputs

### Out of Scope

- Semantic understanding
- Meaning preservation guarantees
- Production deployment
- Governance enforcement
- Verifier integration
- Ledger recording (except optionally for tracing)
- ML model training
- Transformer integration
- NLP library usage

---

## Evaluation Approach

### For Each Experiment

1. **Document configuration**: Mode, weights, seed, inputs
2. **Capture outputs**: Raw text, phonemes, traces
3. **Human assessment**: Does this look interesting? Structured? Varied?
4. **Compare variants**: Same input, different weights → different output?
5. **Record observations**: What worked? What failed? What surprised?

### Metrics (Soft, Not Formal)

| Metric | Description | Good Range |
|--------|-------------|------------|
| Output length | Characters/phonemes generated | Not empty, not infinite |
| Variation coefficient | How much outputs differ | Neither 0 nor maximal |
| Path diversity | How many layers touched | More than 1, not all 10 |
| PPV correlation | Does PPV change affect output? | Noticeable but not chaotic |

---

## Non-Goals

- Proving anything
- Building a product
- Achieving safety
- Creating meaning
- Training models
- Deploying to users

---

*Phase-11 Scope — Inputs, Outputs, and Qualitative Judgment*
