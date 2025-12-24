# Generative Axes: Dimensions of Experimental Freedom

> This document describes the dimensions of freedom available in Phase-11
> sandbox experiments. These are not parameters to optimize—they are
> axes to explore.
>
> This is not code. This is a map of the experimental space.

---

## Overview

Phase-11 experiments can vary along multiple independent axes. Each axis
represents a dimension where we can make different choices and observe
different behaviors.

The goal is to understand the space, not to find the "best" settings.

---

## Axis 1: Ontological Layer Selection

**What it is**: Choosing which of the 10 ontological layers to activate,
weight, or traverse during generation.

### The 10 Layers (Reference)

| Layer | Name | Character |
|-------|------|-----------|
| 1 | ACTING | Operational, executable |
| 2 | TAGGING | Labeling, categorizing |
| 3 | FORMING | Shaping, structuring |
| 4 | THINKING | Conceptual, ideational |
| 5 | DIRECTING | Guiding, flowing |
| 6 | REASONING | Logical, inferential |
| 7 | PURPOSING | Intentional, goal-oriented |
| 8 | META_OBSERVING | Reflexive, self-aware |
| 9 | UNIFYING | Integrating, synthesizing |
| 10 | ABSOLVING | Releasing, gated |

### Selection Modes

| Mode | Description |
|------|-------------|
| **Fixed** | Always use exactly these layers |
| **Weighted** | Sample layers with probability proportional to weights |
| **Sequential** | Traverse layers in order |
| **Random** | Uniform random selection |
| **PPV-biased** | Let PPV dimensions influence layer probability |

### Questions to Explore

- Does FORMING-heavy generation feel more "shaped"?
- Does THINKING-heavy generation feel more "conceptual"?
- Does layer diversity affect output coherence?
- Can we feel the difference between layer configurations?

---

## Axis 2: PPV Weighting Strength

**What it is**: How strongly the PPV vector influences generation choices.

### Weighting Levels

| Level | Description | Expected Behavior |
|-------|-------------|-------------------|
| **Zero** | PPV ignored | Baseline—no PPV effect |
| **Light** | PPV as subtle nudge | Small bias, mostly structural |
| **Moderate** | PPV as significant factor | Clear influence, still varied |
| **Heavy** | PPV as dominant force | Output strongly shaped by PPV |
| **Total** | PPV deterministic | Output fully determined by PPV |

### PPV Dimension Mapping (Hypothetical)

| PPV Dimension | Might Influence |
|---------------|-----------------|
| `edge_tension` | Consonant cluster density |
| `edge_release` | Syllable boundary placement |
| `onset_sharpness` | Initial phoneme selection |
| `sonority_lift` | Vowel selection |
| `continuity` | Run length between pauses |
| `discontinuity` | Pause/break frequency |
| `rhythmic_impulse` | Stress pattern |
| `stability_pressure` | Repetition vs variation |

### Questions to Explore

- Is there a "Goldilocks zone" where PPV has useful but not overwhelming influence?
- Do different PPV dimensions affect different aspects of output?
- Does the `aggregate` value predict anything about output character?

---

## Axis 3: Randomness Level (Temperature)

**What it is**: How much stochastic noise to inject into generation choices.

### Temperature Scale

| Temperature | Description |
|-------------|-------------|
| **0.0** | Deterministic (always pick highest-weight option) |
| **0.1–0.3** | Low noise (occasional variation) |
| **0.4–0.6** | Moderate noise (regular variation) |
| **0.7–0.9** | High noise (frequent surprises) |
| **1.0** | Maximum noise (uniform random) |

### Where Randomness Applies

- Layer selection (which layer to activate)
- Path branching (which edge to follow)
- Phoneme selection (which phoneme to emit)
- Slot filling (which value to place)
- Continuation decisions (continue vs terminate)

### Questions to Explore

- Where does useful variation become noise?
- Does low temperature produce boring output?
- Does high temperature produce incoherent output?
- Is there a sweet spot?

---

## Axis 4: Generation Strategy

**What it is**: The fundamental approach to producing output.

### Strategies

| Strategy | Description |
|----------|-------------|
| **Slot-based** | Fill predefined slots with selected values |
| **Sequence-based** | Emit one element at a time, building a sequence |
| **Tree-based** | Build a tree structure, then linearize |
| **Path-based** | Follow ontological graph, collect emissions |
| **Template-based** | Select and instantiate templates |

### Slot-Based Details

- Define slots: `[ONSET] [NUCLEUS] [CODA]`
- Fill each slot based on weights/PPV
- Concatenate to produce output

### Sequence-Based Details

- Start with seed/initial state
- Emit next element based on current state + weights
- Continue until termination condition

### Path-Based Details

- Start at ontological node
- Follow edges (probabilistically or weighted)
- Collect artifacts at each node
- Terminate when path ends or length reached

### Questions to Explore

- Does slot-based feel more constrained?
- Does sequence-based produce longer outputs?
- Does path-based align with ontological intuitions?
- Which strategy is most controllable?

---

## Axis 5: Continuation vs Branching

**What it is**: When generating sequences, whether to continue forward or
branch into alternatives.

### Modes

| Mode | Description |
|------|-------------|
| **Pure continuation** | Always extend current path forward |
| **Single branch** | Sometimes take alternative path |
| **Multi-branch** | Explore multiple paths, select best |
| **Beam search** | Keep top-k paths, prune others |

### Continuation Policy

- **Greedy**: Always continue with highest-weight next
- **Stochastic**: Sample next according to weights
- **Exhaustive**: Try all continuations (expensive)

### Branching Policy

- **Never branch**: Linear generation only
- **Branch on low confidence**: Branch when weights are close
- **Branch randomly**: With probability p, branch instead of continue
- **Branch at layers**: Branch when crossing ontological layer boundaries

### Questions to Explore

- Does branching produce more diverse outputs?
- Is branching computationally tractable?
- Does beam search help or just add complexity?

---

## Axis 6: Termination Conditions

**What it is**: When to stop generating.

### Termination Modes

| Mode | Description |
|------|-------------|
| **Fixed length** | Stop after N elements |
| **End token** | Stop when special END marker emitted |
| **Confidence threshold** | Stop when max weight drops below threshold |
| **Path exhaustion** | Stop when no more edges to follow |
| **Resource limit** | Stop after K steps regardless |

### Questions to Explore

- Does fixed length produce truncated-feeling output?
- Can we learn natural stopping points?
- Does path exhaustion align with intuitive completeness?

---

## Axis 7: Input Influence

**What it is**: How much the Phase-10 input shapes the output.

### Influence Levels

| Level | Description |
|-------|-------------|
| **Echo** | Output closely mirrors input |
| **Transformation** | Output systematically transforms input |
| **Seeding** | Input seeds generation but doesn't constrain |
| **Independent** | Output ignores input (bad—baseline only) |

### Input Components That Might Influence

- Source phoneme sequence → target phoneme selection
- Acoustic regime → generation style
- VC facts → structural constraints
- Artifact hash → random seed (reproducibility)

### Questions to Explore

- Can we feel the input in the output?
- Is there a useful transformation (not just echo, not independent)?
- Do different input components have different influence?

---

## Axis Summary Table

| Axis | Range | Default Exploration |
|------|-------|---------------------|
| Layer selection | Fixed → Weighted → Random | Weighted |
| PPV strength | 0.0 → 1.0 | 0.3 (light) |
| Temperature | 0.0 → 1.0 | 0.5 (moderate) |
| Strategy | Slot / Sequence / Path | Path-based |
| Continuation | Continue → Branch | Single branch |
| Termination | Fixed / Threshold / Exhaustion | Fixed length |
| Input influence | Echo → Seed → Independent | Seeding |

---

## Interaction Effects

Some axes interact:

- High temperature + heavy PPV = chaotic mess?
- Path-based + layer weighting = natural synergy?
- Sequence-based + continuation-only = linear chains?

Exploration should consider interactions, not just single-axis sweeps.

---

## What We're NOT Exploring (Yet)

- Learned weights (no training loops)
- Semantic influence (no meaning analysis)
- External feedback (no RL)
- Multi-modal generation (no images/audio)
- Cross-phase influence (no modifying upstream phases)

---

*Generative Axes — The Dimensions of Phase-11 Freedom*
