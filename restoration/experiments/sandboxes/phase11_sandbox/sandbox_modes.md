# Sandbox Modes: Experimental Configurations

> This document defines specific experimental modes for Phase-11 sandbox.
> Each mode is a fixed configuration along the generative axes, designed
> to test specific questions.
>
> Modes are not competing approaches—they're different lenses.

---

## Mode Overview

| Mode | Primary Question |
|------|------------------|
| `ONTO_PATH_SAMPLING` | Can ontological graph traversal produce structured output? |
| `PPV_BIASED_GENERATION` | Can PPV vectors meaningfully shape generation? |
| `LAYER_FOCUS_SWEEP` | Do different layer emphases produce different characters? |
| `TEMPERATURE_GRADIENT` | Where is the useful randomness range? |

---

## Mode 1: ONTO_PATH_SAMPLING

### Purpose

Test whether traversing the ontological graph probabilistically produces
output that reflects ontological structure.

### What Varies

| Aspect | Setting |
|--------|---------|
| Path selection | Probabilistic (weighted by layer connections) |
| Starting layer | Variable (test all 10 starting points) |
| Edge following | Stochastic with temperature |
| Emission rule | Emit artifact at each visited node |

### What Stays Fixed

| Aspect | Setting |
|--------|---------|
| PPV influence | Zero (disabled) |
| Temperature | 0.5 (moderate) |
| Termination | Fixed path length (5 nodes) |
| Strategy | Path-based only |

### What Question It Tests

> "Does the ontological graph, when traversed probabilistically, produce
> output that has structure—or is it just random node collection?"

### Expected Observations

**If promising**:
- Different starting layers produce distinguishable outputs
- Path traces show meaningful patterns (not random walks)
- Output has recognizable phonotactic structure

**If failing**:
- All starting points produce similar output
- Paths are indistinguishable from random walks
- Output is structureless noise

### Experiment Protocol

1. Select Phase-10 input with known phoneme sequence
2. For each starting layer (1–10):
   - Run 10 trials with same input, different seeds
   - Record path trace and output
3. Compare outputs across starting layers
4. Human assessment: Can you tell which starting layer was used?

---

## Mode 2: PPV_BIASED_GENERATION

### Purpose

Test whether PPV vectors can serve as meaningful generative bias—not just
checksums, but actual influence on output character.

### What Varies

| Aspect | Setting |
|--------|---------|
| PPV weighting | Variable (0.0 → 0.3 → 0.6 → 0.9) |
| PPV dimension focus | Test each dimension individually |
| Output measure | Phoneme distribution, run length |

### What Stays Fixed

| Aspect | Setting |
|--------|---------|
| Layer selection | Fixed (FORMING only) |
| Temperature | 0.3 (low) |
| Strategy | Slot-based |
| Termination | Fixed length (10 phonemes) |

### What Question It Tests

> "If we use PPV as a generation bias instead of a verification hash,
> does it produce meaningful variation—or does it just add noise?"

### Dimension-Specific Hypotheses

| PPV Dimension | Hypothesis |
|---------------|------------|
| `edge_tension` | Higher values → more consonant clusters |
| `sonority_lift` | Higher values → more open vowels |
| `continuity` | Higher values → longer runs without pauses |
| `discontinuity` | Higher values → more frequent breaks |
| `rhythmic_impulse` | Higher values → more regular stress patterns |

### Expected Observations

**If promising**:
- Changing PPV weights changes output character
- Different dimensions affect different output aspects
- There's a "useful" weighting range (not too weak, not too strong)

**If failing**:
- PPV weights have no discernible effect
- All dimensions do the same thing
- Any weighting > 0 produces chaos

### Experiment Protocol

1. Create test PPV vectors:
   - All-zeros baseline
   - Single-dimension high (one dim = 7, others = 0)
   - Uniform (all dims = 4)
   - Natural (from actual Phase-10 output)
2. For each PPV vector and weighting level:
   - Generate 10 outputs with same input, different seeds
   - Measure: phoneme distribution, run lengths, cluster frequency
3. Compare: Does PPV configuration correlate with output measures?

---

## Mode 3: LAYER_FOCUS_SWEEP

### Purpose

Test whether emphasizing different ontological layers produces
qualitatively different output character.

### What Varies

| Aspect | Setting |
|--------|---------|
| Layer weights | One layer = 1.0, others = 0.1 |
| Focus layer | Sweep through all 10 |

### What Stays Fixed

| Aspect | Setting |
|--------|---------|
| PPV influence | Light (0.2) |
| Temperature | 0.4 |
| Strategy | Sequence-based |
| Termination | Fixed length (15 elements) |

### What Question It Tests

> "Do the 10 ontological layers correspond to different expressive modes,
> or are they interchangeable from a generation perspective?"

### Layer Character Hypotheses

| Layer | Hypothesized Character |
|-------|------------------------|
| ACTING | Direct, action-oriented fragments |
| TAGGING | Categorical, label-like outputs |
| FORMING | Shaped, structured patterns |
| THINKING | Conceptual, abstract sequences |
| DIRECTING | Flowing, transitional outputs |
| REASONING | Sequential, inferential chains |
| PURPOSING | Goal-oriented structures |
| META_OBSERVING | Reflexive, recursive patterns |
| UNIFYING | Synthesized, integrated outputs |
| ABSOLVING | Released, boundary-crossing (gated) |

### Expected Observations

**If promising**:
- Each layer produces distinguishable output
- Human judges can (sometimes) identify which layer dominated
- Layer character matches hypothesized descriptions

**If failing**:
- All layers produce same output
- Layer choice makes no difference
- Hypothesized characters are not reflected

### Experiment Protocol

1. Fix input and random seed
2. For each focus layer:
   - Generate output with that layer weighted high
   - Record output and trace
3. Blind evaluation: Can humans match output to layer?
4. Quantitative: Do outputs cluster by layer in feature space?

---

## Mode 4: TEMPERATURE_GRADIENT

### Purpose

Find the useful temperature range—where output is neither deterministic
nor chaotic.

### What Varies

| Aspect | Setting |
|--------|---------|
| Temperature | Sweep from 0.0 to 1.0 in 0.1 increments |

### What Stays Fixed

| Aspect | Setting |
|--------|---------|
| Layer selection | Weighted (uniform across FORMING, THINKING, DIRECTING) |
| PPV influence | Moderate (0.4) |
| Strategy | Path-based |
| Termination | Fixed length (8 nodes) |

### What Question It Tests

> "Is there a 'Goldilocks zone' of randomness where output is varied
> but not chaotic, structured but not deterministic?"

### Expected Observations

**Temperature 0.0 (deterministic)**:
- Same input always produces same output
- No variation across trials
- Might be "correct" but boring

**Temperature 0.3–0.5 (hypothesized sweet spot)**:
- Variation across trials
- Recognizable structure maintained
- Different enough to be interesting, similar enough to be coherent

**Temperature 0.8–1.0 (high noise)**:
- High variation across trials
- Structure may break down
- Approaches random sampling

### Experiment Protocol

1. Fix input and PPV
2. For each temperature (0.0, 0.1, ..., 1.0):
   - Run 20 trials with different seeds
   - Measure: variance of output features, structural coherence
3. Plot: variance vs temperature, coherence vs temperature
4. Identify: Is there a range with both moderate variance and high coherence?

---

## Mode Comparison Matrix

| Property | ONTO_PATH | PPV_BIASED | LAYER_FOCUS | TEMP_GRAD |
|----------|-----------|------------|-------------|-----------|
| PPV active | No | Yes (primary) | Yes (light) | Yes (fixed) |
| Layer selection | Probabilistic | Fixed | Weighted | Weighted |
| Temperature | Fixed (0.5) | Fixed (0.3) | Fixed (0.4) | Variable |
| Strategy | Path-based | Slot-based | Sequence | Path-based |
| Primary variable | Start layer | PPV weights | Focus layer | Temperature |

---

## How to Run Experiments

### Setup (Conceptual)

```
1. Select mode
2. Configure axes according to mode definition
3. Prepare input (Phase-10 result + optional PPV)
4. Set random seed for reproducibility
5. Run generation
6. Capture output + traces
7. Evaluate (quantitative + human judgment)
```

### Recording Results

For each experiment run, record:

- Mode name
- Full configuration (all axis values)
- Input hash (for reproducibility)
- Random seed
- Raw output
- Path trace (if applicable)
- Human evaluation notes
- Quantitative metrics

### Comparing Modes

After running multiple modes:

1. Which modes produced the most interesting outputs?
2. Which modes showed the clearest variation with parameter changes?
3. Which modes failed to produce useful variation?
4. What interactions between modes were observed?

---

## Mode Extension

Future modes to consider (not implemented here):

| Mode | Question |
|------|----------|
| `CROSS_LAYER_ROUTING` | Does multi-layer traversal produce richer output? |
| `PPV_DIMENSION_INTERACTION` | Do PPV dimensions interact or operate independently? |
| `REGIME_INFLUENCE` | Does acoustic regime from Phase-10 affect generation? |
| `INPUT_ECHO_GRADIENT` | How much can we transform while maintaining input signature? |

---

## Non-Goals

- Finding the "best" mode (there is no best)
- Optimizing any mode (no gradient descent)
- Productionizing any mode (this is sandbox)
- Claiming success for any mode (all are experiments)

---

*Sandbox Modes — Fixed Configurations for Controlled Exploration*
