# VTable Architecture for Phase Quad LLM Training

## Pattern Discovery Through Virtual Method Tables

**Document Version**: 1.0.0
**Date**: February 2026
**Status**: Architecture / Design
**Codebase Reference**: Symbol-U V11.1.0
**Branch**: phase-quad-drug-discovery
**Prerequisite Reading**: CDI_EVOLUTION_DESIGN_GUIDE.md, PHASE_QUAD_DRUG_DISCOVERY_EVALUATION.md

---

## Executive Summary

This document defines the **VTable Architecture** — a two-phase design where training populates a virtual method table of pattern definitions and inference dispatches against the frozen table using deterministic pattern matching.

The core insight: CDI's hand-curated pattern library (13 patterns, 7 sequences, 10 aspects, 6 domains) is architecturally equivalent to a **manually authored virtual method table**. Each pattern entry is a vtable row — a named dispatch target with a fixed signal signature. Training can automate and scale this curation process while preserving every inference-time invariant (deterministic, zero-parameter, auditable).

**The two paradigms are not opposites. They are complementary phases:**

| Phase | Paradigm | World Assumption | What Happens |
|-------|----------|-----------------|--------------|
| **Training** | Virtual methods (open world) | New patterns can be discovered | Populate the vtable — discover signal signatures, propose entries |
| **Governance** | Bridge (open → closed) | Review and seal | Name, threshold, interpret, approve each entry |
| **Inference** | Pattern matching (closed world) | All cases enumerated | Dispatch against the frozen vtable — deterministic, auditable |

The vtable is not a runtime abstraction. It is a **compile-time artifact** — populated during training, sealed during governance, immutable during inference. The inference engine never knows whether a vtable entry was hand-curated or training-discovered.

---

## 1. Problem Statement

### 1.1 The Scaling Wall

CDI currently operates with 13 universal patterns, 7 sequences, and 10 aspect derivations. Every entry was hand-curated by domain experts who understood both the signal semantics (SMI ranges, bhava ranges, directional constraints) and the domain interpretations (what `risk_hiding` means in finance vs. medicine vs. education).

This does not scale:

| Dimension | Current | Drug Discovery Needs | General Intelligence Needs |
|-----------|---------|---------------------|---------------------------|
| Patterns | 13 | 50-100+ (molecular, clinical, pharmacological) | 500-1000+ (multi-domain expertise) |
| Sequences | 7 | 20-30+ (resistance trajectories, trial progressions) | 100-200+ (cross-domain compositions) |
| Aspects | 10 | 10 + domain-specific molecular fingerprints | 10 + domain-specific extensions |
| Domains | 6 | 6 + pharmacology, toxicology, clinical | 20-50+ (every expertise domain) |

Hand-curating 500 patterns with 50 domain interpretations each requires 25,000 expert-authored interpretation strings. This is the scaling wall.

### 1.2 The Design Guide's Concern

The CDI Evolution Design Guide (Section 10.9) rejects learned patterns because:

> "Discovered patterns lack interpretability guarantees."

This concern is valid but addresses the wrong failure mode. The risk is not that training discovers uninterpretable patterns. The risk is deploying unreviewed patterns directly to inference. The vtable architecture resolves this by inserting a **governance gate** between discovery and deployment — every training-discovered entry must pass the same interpretability bar as a hand-curated one before entering the frozen vtable.

### 1.3 What Changes, What Doesn't

**Changes:**
- How vtable entries are *authored* (training-assisted, not purely manual)
- How many entries the vtable can hold (scales with data, not with expert hours)
- How new domains get coverage (training proposes, governance approves)

**Does NOT change:**
- INV-P38-1: Deterministic (same inputs → same outputs) — frozen vtable, no runtime learning
- INV-P38-2: Observer-only (never influences decisions) — patterns are read-only signals
- INV-P38-3: No LLM, no ML at inference time — all ML happens during training
- INV-P38-4: Sliding window bounded — memory model unchanged
- INV-P38-5: Locked formulas — aspect derivation functions are frozen after training
- INV-P38-6: Conservative degradation — unknown inputs produce no match, not hallucinated match
- INV-P38-7: Governance-approved — every vtable entry has human sign-off

---

## 2. VTable Structure

### 2.1 What Is the VTable

In object-oriented languages, a virtual method table (vtable) is a dispatch table: given a type tag, look up the concrete method implementation. The caller doesn't know (or care) which implementation it gets — it dispatches through the table.

In Phase Quad, the vtable serves the same role for pattern recognition:

```
Traditional OOP:
    object.method()  →  vtable[type_tag]  →  concrete implementation

Phase Quad CDI:
    signals.classify()  →  vtable[signal_signature]  →  concrete pattern match
```

Each row in the vtable is a **PatternConfig** — a named, configured, thresholded pattern with:
- A signal signature (SMI range, bhava range, directional constraints)
- A minimum confidence threshold
- A category label (protective, growth, stress, conflict, recovery, ...)
- Kosha and ontology weight profiles
- Domain interpretation strings for each supported domain

The vtable is the **complete** set of these rows. Today it has 13 rows, hand-authored in `cross_domain_intelligence.py:41-330`. The vtable architecture makes this set extensible through training.

### 2.2 The Five VTables

CDI actually maintains five coupled vtables. Training can populate any or all:

```
┌─────────────────────────────────────────────────────────┐
│                    CDI VTable System                     │
├─────────────┬───────────┬──────────┬──────────┬─────────┤
│  Pattern    │ Sequence  │  Aspect  │  Domain  │ Weight  │
│  VTable     │ VTable    │  VTable  │  VTable  │ VTable  │
├─────────────┼───────────┼──────────┼──────────┼─────────┤
│ 13 rows     │ 7 rows    │ 10 rows  │ 6 cols   │ 6 vals  │
│ PatternCfg  │ SeqRule   │ DerivFn  │ InterpMap│ Floats  │
│             │           │          │          │         │
│ SMI range   │ step list │ formula  │ per-patt │ bhava:  │
│ bhava range │ gap limit │ inputs   │ per-dom  │  0.30   │
│ direction   │ min conf  │ clamp    │ string   │ dir:    │
│ kosha wts   │ category  │ [0,1]    │          │  0.25   │
│ onto wts    │           │          │          │ smi:    │
│ threshold   │           │          │          │  0.25   │
│ category    │           │          │          │ kosha:  │
│             │           │          │          │  0.10   │
│             │           │          │          │ onto:   │
│             │           │          │          │  0.10   │
└─────────────┴───────────┴──────────┴──────────┴─────────┘
         ↑                                          ↑
    Training populates                    Training optimizes
    Governance freezes                    Governance freezes
    Inference dispatches                  Inference uses
```

#### VTable 1: Pattern VTable (the primary table)

Each row maps a signal signature to a named pattern:

```python
# Current hand-curated vtable entry (cross_domain_intelligence.py:41-75)
PatternConfig(
    name="risk_hiding",
    min_confidence=0.65,
    category="protective",
    smi_range=(0.50, 0.75),
    bhava_range=(3, 7),
    directions=["downward", "neutral"],
    temporal_trends=["falling", "stable"],
    kosha_weights={0: 0.3, 1: 0.4, 2: 0.2, 3: 0.1},
    ontology_weights={2: 0.3, 3: 0.4, 5: 0.2, 7: 0.1},
)

# Training-discovered vtable entry (identical structure)
PatternConfig(
    name="drug_resistance_emergence",     # ← governance-assigned name
    min_confidence=0.70,                  # ← governance-tuned threshold
    category="pharmacological_escalation",# ← new category
    smi_range=(0.55, 0.80),              # ← training-discovered range
    bhava_range=(4, 8),                  # ← training-discovered range
    directions=["upward", "neutral"],    # ← training-discovered constraint
    temporal_trends=["rising", "stable"],# ← training-discovered trend
    kosha_weights={1: 0.3, 2: 0.4, 3: 0.2, 4: 0.1},
    ontology_weights={3: 0.3, 5: 0.3, 7: 0.2, 9: 0.2},
)
```

The inference engine processes both identically. `_compute_pattern_confidence()` in `cross_domain_intelligence.py:332-368` does not distinguish hand-curated from training-discovered — it dispatches through the vtable.

#### VTable 2: Sequence VTable

Each row defines a pattern trajectory:

```python
# Current hand-curated (pattern_sequence_rules.py)
PatternSequenceRule(
    name="suppression_escalation",
    steps=["acute_anxiety", "emotional_masking", "chronic_stress"],
    max_gap_turns=2,
    min_step_confidence=0.60,
    category="escalation",
)

# Training-discovered (identical structure)
PatternSequenceRule(
    name="resistance_cascade",
    steps=["drug_resistance_emergence", "dose_escalation_pressure", "toxicity_threshold"],
    max_gap_turns=3,
    min_step_confidence=0.65,
    category="pharmacological_escalation",
)
```

#### VTable 3: Aspect VTable

Each row defines a derivation function from CDI signals to a universal aspect:

```python
# Current hand-curated (pattern_aspect_derivation.py)
ASPECT_DERIVATIONS = {
    "ENTROPY":    lambda smi, bhava_id, direction, kosha_id, onto_id: clamp(smi),
    "AGENCY":     lambda smi, bhava_id, direction, kosha_id, onto_id: clamp(bhava_id / 11.0),
    "BALANCE":    lambda smi, bhava_id, direction, kosha_id, onto_id: clamp((1-smi) * (1-abs(bhava_id-5.5)/5.5)),
    # ... 7 more
}

# Training-discovered (new aspects for molecular domain)
ASPECT_DERIVATIONS_EXTENDED = {
    "BINDING_AFFINITY":  lambda smi, bhava_id, ..., mol_features: clamp(affinity_fn(mol_features)),
    "SELECTIVITY":       lambda smi, bhava_id, ..., mol_features: clamp(selectivity_fn(mol_features)),
}
```

#### VTable 4: Domain VTable

Maps each pattern to interpretation strings per domain:

```python
# Current: 13 patterns × 6 domains = 78 entries
DOMAIN_INTERPRETATIONS = {
    "risk_hiding": {
        "finance":    "Concealing exposure or downside risk from stakeholders",
        "medicine":   "Withholding symptoms or non-compliance from care providers",
        "education":  "Student masking confusion to avoid appearing unprepared",
        # ...
    },
    # Training can add new patterns AND new domains:
    "drug_resistance_emergence": {
        "pharmacology": "Pathogen or tumor evolving reduced susceptibility to therapeutic agent",
        "oncology":     "Cancer cell population developing treatment-resistant phenotype",
        "infectious":   "Microbial adaptation reducing antibiotic efficacy",
    },
}
```

#### VTable 5: Weight VTable — Per-Pattern Scoring Weights

Today, weights are **global constants** — every pattern uses the same scoring formula:

```python
# Current: ONE weight vector for ALL 13 patterns (cross_domain_intelligence.py)
W_BHAVA_RANGE  = 0.30
W_DIRECTION    = 0.25
W_SMI_RANGE    = 0.25
W_KOSHA        = 0.10
W_ONTOLOGY     = 0.10

# confidence = W_BHAVA * bhava_score + W_DIR * dir_score + W_SMI * smi_score
#            + W_KOSHA * kosha_score + W_ONTO * onto_score
```

This is a design limitation. `risk_hiding` (protective, defined by SMI range and downward direction) and `breakthrough_insight` (growth, defined by bhava range and upward direction) are scored by the same weight vector. The dimensions that matter most for recognizing each pattern are different, but the weights cannot express that.

**The vtable architecture promotes weights from global constants to per-row fields:**

```python
@dataclass(frozen=True)
class PatternConfig:
    name: str
    min_confidence: float
    category: str
    smi_range: Tuple[float, float]
    bhava_range: Tuple[int, int]
    directions: List[str]
    temporal_trends: List[str]
    kosha_weights: Dict[int, float]
    ontology_weights: Dict[int, float]

    # NEW: per-pattern scoring weights (vtable v2.0.0+)
    scoring_weights: ScoringWeights    # ← each row carries its own weight vector

@dataclass(frozen=True)
class ScoringWeights:
    """How much each signal dimension contributes to this pattern's confidence."""
    w_bhava_range: float    # importance of bhava_id being in range
    w_direction: float      # importance of bhava_direction matching
    w_smi_range: float      # importance of SMI being in range
    w_kosha: float          # importance of kosha signature match
    w_ontology: float       # importance of ontology signature match
    # Constraint: all weights sum to 1.0

# Hand-curated pattern: weights chosen by expert intuition
PatternConfig(
    name="risk_hiding",
    scoring_weights=ScoringWeights(
        w_bhava_range=0.30, w_direction=0.25, w_smi_range=0.25,
        w_kosha=0.10, w_ontology=0.10,   # sum = 1.0
    ),   # expert: "SMI and direction matter equally for this pattern"
    ...
)

# Training-discovered pattern: weights derived from data
PatternConfig(
    name="drug_resistance_emergence",
    scoring_weights=ScoringWeights(
        w_bhava_range=0.15, w_direction=0.10, w_smi_range=0.40,
        w_kosha=0.20, w_ontology=0.15,   # sum = 1.0
    ),   # training: "SMI is 4x more discriminative than direction for this pattern"
    ...
)
```

**The inference scoring function changes from global dispatch to per-row dispatch:**

```python
# BEFORE (global weights):
def _compute_pattern_confidence(self, signals, pattern_config):
    bhava_score  = self._score_bhava(signals, pattern_config)
    dir_score    = self._score_direction(signals, pattern_config)
    smi_score    = self._score_smi(signals, pattern_config)
    kosha_score  = self._score_kosha(signals, pattern_config)
    onto_score   = self._score_ontology(signals, pattern_config)
    return (W_BHAVA * bhava_score + W_DIR * dir_score + W_SMI * smi_score
            + W_KOSHA * kosha_score + W_ONTO * onto_score)

# AFTER (per-row weights — vtable dispatch):
def _compute_pattern_confidence(self, signals, pattern_config):
    bhava_score  = self._score_bhava(signals, pattern_config)
    dir_score    = self._score_direction(signals, pattern_config)
    smi_score    = self._score_smi(signals, pattern_config)
    kosha_score  = self._score_kosha(signals, pattern_config)
    onto_score   = self._score_ontology(signals, pattern_config)
    w = pattern_config.scoring_weights   # ← dispatch through the vtable row
    return (w.w_bhava_range * bhava_score + w.w_direction * dir_score
            + w.w_smi_range * smi_score + w.w_kosha * kosha_score
            + w.w_ontology * onto_score)
```

**This is the vtable dispatch.** The scoring function does not use global constants. It reads the weight vector from the vtable row. Each pattern "knows" which signal dimensions matter most for its own recognition. The function is the same for all patterns — only the weights differ. This is virtual dispatch: one call site, N implementations selected by the vtable row.

---

## 3. Training Pipeline: How VTable Entries Are Discovered

### 3.1 Pipeline Overview

```
                        TRAINING PHASE (open world)
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────────┐  │
│  │  Stage 1 │───→│ Stage 2  │───→│ Stage 3  │───→│   Stage 4     │  │
│  │  Corpus  │    │ Signal   │    │ Cluster  │    │   Candidate   │  │
│  │  Prep    │    │ Extract  │    │ & Name   │    │   Proposal    │  │
│  └─────────┘    └──────────┘    └──────────┘    └───────┬───────┘  │
│                                                          │          │
└──────────────────────────────────────────────────────────┼──────────┘
                                                           │
                        GOVERNANCE GATE (open → closed)    │
┌──────────────────────────────────────────────────────────┼──────────┐
│                                                          ▼          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌─────────────┐  │
│  │ Stage 5  │←───│ Stage 6  │←───│ Stage 7  │←───│  Stage 8    │  │
│  │ Freeze   │    │ Approve  │    │ Interpret │    │  Review     │  │
│  │ & Seal   │    │          │    │          │    │  & Thresh   │  │
│  └────┬─────┘    └──────────┘    └──────────┘    └─────────────┘  │
│       │                                                             │
└───────┼─────────────────────────────────────────────────────────────┘
        │
        ▼           INFERENCE PHASE (closed world)
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  ┌─────────────────────────┐    ┌────────────────────────────────┐  │
│  │  Frozen VTable           │───→│ Deterministic Pattern Matching  │  │
│  │  (module-level constants)│    │ (same as current CDI inference) │  │
│  └─────────────────────────┘    └────────────────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 Stage 1: Corpus Preparation

**Input**: Domain-specific conversation/interaction data with labeled outcomes.

For drug discovery:
- Patient-clinician dialogue transcripts with treatment outcomes
- Pharmacovigilance reports (FAERS) with adverse event labels
- Clinical trial narratives with efficacy/safety endpoints
- Drug interaction case reports with severity classifications

**Output**: A set of (signal_trajectory, outcome_label) pairs where each signal_trajectory is a sequence of CDI signal vectors:

```python
@dataclass(frozen=True)
class TrainingExample:
    """One labeled trajectory for vtable discovery."""
    trajectory: List[SignalVector]   # sequence of CDI signal snapshots
    outcome_label: str              # e.g. "resistance_emerged", "efficacy_sustained"
    domain: str                     # e.g. "pharmacology", "oncology"
    source_id: str                  # provenance for audit
    confidence: float               # label confidence (expert agreement)

@dataclass(frozen=True)
class SignalVector:
    """CDI signal state at one turn/timepoint."""
    smi: float                      # Semantic Mismatch Index [0.0, 1.0]
    bhava_id: int                   # Bhava identifier (0-11)
    bhava_direction: str            # "upward" | "downward" | "neutral"
    kosha_id: int                   # Kosha layer (0-7)
    ontology_id: int                # Ontology state (0-12)
    turn_index: int                 # temporal position
```

**Key constraint**: The signal vectors use the existing CDI signal space. Training discovers patterns *within* the established signal dimensions — it does not invent new signal types. This preserves the ontological substrate.

### 3.3 Stage 2: Signal Extraction and Windowing

Run the existing CDI pipeline over each training example to produce signal trajectories in the established 5D signal space (SMI, bhava_id, bhava_direction, kosha_id, ontology_id).

```
For each training example:
    for each turn in example.trajectory:
        signal = extract_cdi_signals(turn)
        # signal = (smi, bhava_id, bhava_direction, kosha_id, ontology_id)

    signal_trajectory = [signal_0, signal_1, ..., signal_N]

    # Apply sliding windows matching P38 conventions
    windows = sliding_window(signal_trajectory, window_size=10)
```

This stage produces **no new abstractions**. It runs the existing pipeline and records what it observes. The ontology freeze contract is respected — no frozen files are modified.

### 3.4 Stage 3: Cluster and Name

This is the core discovery step. Signal trajectories that lead to the same outcome labels are clustered to identify recurring signal signatures.

**Method**: Deterministic clustering on the CDI signal space.

```
Algorithm: VTable Entry Discovery

Input:  Set of (signal_trajectory, outcome_label) pairs
Output: Set of candidate PatternConfig entries

1. Group trajectories by outcome_label
2. For each outcome group:
   a. Compute signal statistics:
      - SMI range: [percentile_10, percentile_90] of SMI values
      - Bhava range: [mode - 1, mode + 1] of bhava_id values
      - Direction: majority vote of bhava_direction values
      - Kosha weights: normalized frequency of kosha_id values
      - Ontology weights: normalized frequency of ontology_id values
   b. Compute separability score:
      - How distinct is this cluster from existing patterns?
      - Does the signal region overlap with known patterns?
      - Is the cluster tight (low variance) or diffuse (high variance)?
   c. If separability > threshold AND cluster_size > minimum:
      - Emit candidate PatternConfig with discovered ranges
      - Assign provisional name from outcome_label
      - Flag for governance review
```

**What this is NOT**: This is not gradient descent. Not backpropagation. Not neural architecture search. It is statistical aggregation over labeled signal trajectories — closer to histogram binning than to deep learning. The "training" in vtable discovery is closer to **data-driven curation** than to model training.

**What this IS**: Automating the expert's process. When a domain expert creates a pattern like `risk_hiding`, they implicitly perform this same analysis — "when SMI is in this range and bhava is in that range and the direction is downward, something protective is happening." The expert does it from clinical intuition; the algorithm does it from labeled data. The output is identical: a PatternConfig.

### 3.5 Stage 3b: Weight Discovery — How Training Learns Per-Pattern Weights

This is the critical substage that binds discovered weights to vtable entries. Ranges (Stage 3) answer *where* a pattern lives in signal space. Weights answer *which dimensions matter most* for recognizing it.

#### The Problem with Global Weights

Under global weights (W_BHAVA=0.30, W_SMI=0.25, ...), every pattern is scored by the same formula. This works when all 13 patterns are in the same domain and were designed by the same expert. It breaks when patterns span domains:

```
risk_hiding (protective):
    Expert intuition: "direction matters a lot — downward is the key signal"
    Ideal weights:  w_direction=0.35, w_smi=0.25, w_bhava=0.20, w_kosha=0.10, w_onto=0.10

drug_resistance_emergence (pharmacological):
    Data shows:     "SMI range is highly discriminative — resistance lives in 0.55-0.80"
    Ideal weights:  w_smi=0.40, w_kosha=0.20, w_onto=0.15, w_bhava=0.15, w_direction=0.10
```

With global weights, both patterns use 0.30/0.25/0.25/0.10/0.10. The pharmaceutical pattern is penalized — its most discriminative dimension (SMI) gets only 0.25 weight, while a less useful dimension (bhava) gets 0.30.

#### How Training Discovers Weights

For each candidate cluster from Stage 3, training computes a **discriminative weight profile** — the weight vector that maximizes separation between this cluster and all other clusters/patterns:

```
Algorithm: Per-Pattern Weight Discovery

Input:  Candidate cluster C (signal vectors labeled as this pattern)
        Background B (all signal vectors NOT in this cluster)
Output: ScoringWeights for this vtable entry

1. For each signal dimension d ∈ {bhava_range, direction, smi_range, kosha, ontology}:

   a. Compute within-cluster variance:
      var_within[d] = variance of dimension d across all vectors in C

   b. Compute between-cluster distance:
      dist_between[d] = |mean(C[d]) - mean(B[d])|

   c. Compute discriminative power:
      fisher[d] = dist_between[d] / (var_within[d] + epsilon)

      High fisher[d] = this dimension separates C from B well
      Low fisher[d]  = this dimension does not help distinguish C

2. Normalize to weight vector:
   raw_weights = {d: fisher[d] for d in dimensions}
   total = sum(raw_weights.values())
   scoring_weights = {d: raw_weights[d] / total for d in dimensions}

3. Clamp minimum weight:
   # No dimension gets less than 0.05 (prevents zero-weight blind spots)
   for d in dimensions:
       scoring_weights[d] = max(scoring_weights[d], 0.05)
   # Re-normalize to sum to 1.0
   total = sum(scoring_weights.values())
   scoring_weights = {d: scoring_weights[d] / total for d in dimensions}
```

This is **Fisher's Linear Discriminant** applied per-dimension — a classical statistical method, not neural network training. It asks: "for this specific pattern, which signal dimensions carry the most information?"

#### Worked Example: Weight Discovery for `drug_resistance_emergence`

```
Training data:
    Cluster C: 3,960 signal vectors where resistance was observed
    Background B: 8,040 signal vectors where resistance was NOT observed

Step 1 — Compute per-dimension discriminative power:

    Dimension        var_within    dist_between    fisher_score
    ─────────────    ──────────    ────────────    ────────────
    smi_range           0.008         0.18           22.5   ← highly discriminative
    kosha               0.012         0.11            9.2
    ontology            0.015         0.09            6.0
    bhava_range         0.020         0.07            3.5
    direction           0.025         0.04            1.6   ← least discriminative

Step 2 — Normalize:
    total = 22.5 + 9.2 + 6.0 + 3.5 + 1.6 = 42.8

    w_smi_range   = 22.5 / 42.8 = 0.526 → after min-clamp + renorm → 0.40
    w_kosha       =  9.2 / 42.8 = 0.215 → after min-clamp + renorm → 0.20
    w_ontology    =  6.0 / 42.8 = 0.140 → after min-clamp + renorm → 0.15
    w_bhava_range =  3.5 / 42.8 = 0.082 → after min-clamp + renorm → 0.15
    w_direction   =  1.6 / 42.8 = 0.037 → after min-clamp + renorm → 0.10
                                                              total = 1.00  ✓

Result: ScoringWeights(
    w_smi_range=0.40,    # SMI is the dominant discriminator
    w_kosha=0.20,        # kosha depth matters (deeper layers = more structural)
    w_ontology=0.15,     # ontology state provides moderate signal
    w_bhava_range=0.15,  # bhava range is weakly useful
    w_direction=0.10,    # direction is least informative for this pattern
)
```

**Interpretation**: For drug resistance emergence, SMI (semantic mismatch) carries 4x more discriminative power than bhava direction. This makes pharmacological sense — resistance manifests as a specific type of semantic divergence (the treatment is "mismatching" the pathogen), while the directional component (upward/downward) is noisy because resistance can emerge in multiple clinical contexts.

A hand-curating expert might have guessed this. Training *proves* it from 3,960 examples.

#### How Weights Bind to VTable Rows

The binding is structural — weights are a **field of PatternConfig**, not a separate lookup:

```
VTable Row #14: drug_resistance_emergence
┌────────────────────────────────────────────────────────────────────┐
│ name: "drug_resistance_emergence"                                  │
│ smi_range: (0.55, 0.80)               ← WHERE in signal space     │
│ bhava_range: (4, 8)                                                │
│ directions: ["upward", "neutral"]                                  │
│ scoring_weights:                       ← HOW MUCH each dim matters │
│   w_smi_range:   0.40  ─────────────────→ smi_score × 0.40        │
│   w_kosha:       0.20  ─────────────────→ kosha_score × 0.20      │
│   w_ontology:    0.15  ─────────────────→ onto_score × 0.15       │
│   w_bhava_range: 0.15  ─────────────────→ bhava_score × 0.15      │
│   w_direction:   0.10  ─────────────────→ dir_score × 0.10        │
│                                                                     │
│ confidence = Σ (w_i × score_i)         ← DISPATCH through weights  │
└────────────────────────────────────────────────────────────────────┘

VTable Row #1: risk_hiding (original, hand-curated)
┌────────────────────────────────────────────────────────────────────┐
│ name: "risk_hiding"                                                │
│ smi_range: (0.50, 0.75)                                            │
│ bhava_range: (3, 7)                                                │
│ directions: ["downward", "neutral"]                                │
│ scoring_weights:                       ← original global weights   │
│   w_bhava_range: 0.30  ─────────────────→ bhava_score × 0.30      │
│   w_direction:   0.25  ─────────────────→ dir_score × 0.25        │
│   w_smi_range:   0.25  ─────────────────→ smi_score × 0.25        │
│   w_kosha:       0.10  ─────────────────→ kosha_score × 0.10      │
│   w_ontology:    0.10  ─────────────────→ onto_score × 0.10       │
│                                                                     │
│ confidence = Σ (w_i × score_i)         ← SAME function, DIFF wts  │
└────────────────────────────────────────────────────────────────────┘
```

The scoring function is **identical** for both rows. The only difference is which weight vector it reads from the vtable row. This is the virtual dispatch — the "method" (confidence computation) is the same, but the "implementation" (which dimensions to emphasize) varies per vtable entry.

#### Backward Compatibility: Original 13 Patterns Keep Global Weights

The original 13 hand-curated patterns are migrated to per-row weights by copying the current global constants into each row:

```python
# Migration: vtable_v1.0.0 → vtable_v2.0.0
LEGACY_GLOBAL_WEIGHTS = ScoringWeights(
    w_bhava_range=0.30, w_direction=0.25, w_smi_range=0.25,
    w_kosha=0.10, w_ontology=0.10,
)

for pattern in ORIGINAL_13_PATTERNS:
    pattern.scoring_weights = LEGACY_GLOBAL_WEIGHTS  # exact same behavior
```

This guarantees that vtable_v2.0.0 produces **identical** confidence scores for all 13 original patterns. The per-row weight mechanism is active, but the values are the same as the old global constants. Existing invariants preserved.

Training can **optionally** re-optimize weights for the original 13 patterns too — but only if governance approves the new weights after reviewing the impact on existing confidence scores. This is a governance decision, not an automatic migration.

#### Weight Discovery vs. Weight Guessing

| Approach | Method | Risk | Governance Burden |
|----------|--------|------|-------------------|
| **Hand-curated** (current) | Expert picks 0.30/0.25/0.25/0.10/0.10 | Suboptimal for non-obvious patterns | Low (expert self-validates) |
| **Training-discovered** (vtable) | Fisher discriminant from labeled data | Overfitting to training corpus | Medium (review weight profile + held-out validation) |
| **Neural-learned** (rejected) | Gradient descent on weight vector | Black-box, non-interpretable | High (cannot inspect reasoning) |

The vtable architecture uses Fisher discriminant because it is:
1. **Interpretable** — "SMI got weight 0.40 because its fisher score was 22.5" is a reviewable statement
2. **Deterministic** — same data always produces same weights
3. **Auditable** — the per-dimension statistics (var_within, dist_between) are logged
4. **Non-parametric** — no hyperparameters to tune beyond the min-weight clamp (0.05)

### 3.6 Stage 4: Candidate Proposal

Each discovered cluster becomes a **candidate vtable entry** — a fully specified PatternConfig that has not yet been approved:

```python
@dataclass(frozen=True)
class CandidateVTableEntry:
    """A training-discovered pattern awaiting governance approval."""

    # The proposed pattern configuration
    pattern_config: PatternConfig

    # Discovery provenance (for governance review)
    discovery_method: str           # "cluster_outcome_label"
    training_corpus: str            # corpus identifier
    sample_count: int               # how many examples support this cluster
    separability_score: float       # how distinct from existing patterns
    overlap_with: List[str]         # names of overlapping existing patterns

    # Statistical evidence
    smi_mean: float
    smi_std: float
    bhava_mode: int
    bhava_entropy: float            # low = concentrated, high = diffuse
    direction_agreement: float      # fraction of examples matching majority direction

    # Example trajectories (for human review)
    example_trajectories: List[str] # source_ids of representative examples

    # Status
    status: str                     # "proposed" | "approved" | "rejected" | "deferred"
    reviewer: Optional[str]         # governance reviewer ID
    review_notes: Optional[str]     # reviewer comments
```

**The candidate is not a pattern until governance approves it.** It is a proposal backed by data, not a deployed vtable entry.

---

## 4. The Governance Gate: Where Virtual Methods Become Pattern Matches

### 4.1 Why the Gate Exists

The governance gate is the architectural bridge between the open world (training discovers candidates) and the closed world (inference dispatches against frozen patterns). Without this gate, the system degenerates:

| Without Gate | Consequence |
|-------------|-------------|
| Training → Inference directly | Unreviewed patterns in production; no interpretability guarantee |
| No naming review | Pattern #47 instead of `drug_resistance_emergence`; humans can't reason about it |
| No threshold review | Over-sensitive patterns firing on noise; under-sensitive patterns missing real signals |
| No domain interpretation | Patterns match but produce no actionable insight for practitioners |
| No overlap check | Redundant patterns that fire together, inflating confidence without adding information |

### 4.2 Governance Review Checklist

Each candidate vtable entry must satisfy all criteria before entering the frozen vtable:

```
GOVERNANCE REVIEW: Candidate VTable Entry
═════════════════════════════════════════════

□ 1. INTERPRETABILITY
    Does the pattern have a clear, human-understandable meaning?
    Can a domain expert explain WHAT this pattern represents?
    Is the name accurate and unambiguous?

□ 2. SEPARABILITY
    Is this pattern meaningfully distinct from all existing patterns?
    Does the signal region overlap exceed 30% with any existing pattern?
    If overlap exists, does the new pattern capture genuinely different semantics?

□ 3. STATISTICAL SUPPORT
    Does the cluster have >= N supporting examples? (N domain-specific)
    Is the direction agreement >= 0.70?
    Is the bhava entropy <= 1.5? (concentrated, not diffuse)
    Is the SMI std <= 0.15? (tight range, not noise)

□ 4. DOMAIN INTERPRETATION
    Has at least one domain interpretation been authored?
    For drug discovery: pharmacology interpretation required
    Does the interpretation map to actionable practitioner knowledge?

□ 5. THRESHOLD CALIBRATION
    Has min_confidence been tested on held-out data?
    False positive rate at proposed threshold <= 5%?
    False negative rate at proposed threshold <= 15%?

□ 6. SEQUENCE COMPATIBILITY
    Does this pattern participate in any known or proposed sequences?
    If it replaces a step in an existing sequence, is the sequence updated?
    Are new sequences proposed that include this pattern?

□ 7. ASPECT DERIVATION
    Does the pattern produce meaningful aspect fingerprints
    under the existing 10 derivation functions?
    If not, is a new aspect derivation function proposed and reviewed?

□ 8. INVARIANT PRESERVATION
    Does adding this pattern preserve INV-P38-1 through INV-P38-7?
    Is the inference path still deterministic?
    Is the vtable still frozen at inference time?
```

### 4.3 The Approval → Freeze Protocol

```
Candidate "drug_resistance_emergence"
    │
    ├─ Governance Review: APPROVED (2026-02-13, reviewer: domain_expert_pharma)
    │
    ├─ Assigned vtable slot: Pattern #14
    │
    ├─ Domain interpretations authored:
    │     pharmacology: "Pathogen or tumor evolving reduced susceptibility"
    │     oncology:     "Cancer cell population developing resistant phenotype"
    │     infectious:   "Microbial adaptation reducing antibiotic efficacy"
    │
    ├─ Threshold calibrated: min_confidence = 0.70 (FPR=3.2%, FNR=11.8%)
    │
    ├─ Sequence integration:
    │     Added to: "resistance_cascade" (new sequence, also governance-approved)
    │
    └─ FROZEN
        │
        ├─ Written to: cross_domain_intelligence.py as module-level constant
        ├─ Checksum recorded in vtable manifest
        ├─ Version: vtable_v2.0.0 (bumped from v1.0.0)
        └─ Immutable until next governance cycle
```

Once frozen, the entry is **indistinguishable from a hand-curated pattern**. The inference engine processes it with the same `_compute_pattern_confidence()` function. The provenance (training-discovered vs. hand-curated) is recorded in the vtable manifest but has no effect on runtime behavior.

---

## 5. VTable Integration with Phase Quad Training Stages

### 5.1 Where VTable Discovery Fits in the 17-Controller Training Architecture

The training diagnosis document (TRAINING_DIAGNOSIS_FIX_v9.9.0.md) establishes a staged training approach to resolve controller conflicts:

```
Phase A: Pure Language Modeling (PPL > disengage threshold)
    Controllers OFF — model learns fundamentals

Phase B: Ontological Bridge (engage < PPL < disengage)
    Bridge controller ramps up — model learns signal semantics

Phase C: CSR + Remaining Controllers (PPL < engage threshold)
    Full controller suite — model learns sophisticated behavior
```

**VTable discovery is a Phase D** — it happens *after* the model has stabilized through Phases A-C:

```
Phase A: Pure LM              → Model learns language
Phase B: Ontological Bridge   → Model learns signal semantics (bhava, kosha, ontology)
Phase C: Full Controller Suite→ Model learns CDI pattern recognition (existing vtable)
Phase D: VTable Discovery     → Model's signal outputs are analyzed for new patterns
                                 ↓
                              Candidates proposed
                                 ↓
                              Governance gate
                                 ↓
                              VTable v2.0.0 frozen
                                 ↓
Phase C': Re-tune with        → Model fine-tuned on expanded vtable
          expanded vtable        (same Phase C procedure, new pattern targets)
```

### 5.2 Phase D: VTable Discovery Stage

**Precondition**: The model has completed Phase C and is producing stable CDI signals (PPL below engage threshold, all 17 controllers active and converged).

**Process**:

```
Phase D — VTable Discovery
══════════════════════════

Step D.1: Signal Harvest
    Run trained model over domain-specific evaluation corpus
    Record CDI signal vectors at each turn
    Pair with outcome labels from the corpus
    Output: Set of (signal_trajectory, outcome_label) pairs

Step D.2: Existing Pattern Verification
    Run existing 13-pattern vtable over harvested signals
    Measure coverage: what fraction of labeled outcomes are
    captured by existing patterns?

    If coverage >= 95%: STOP — existing vtable is sufficient
    If coverage < 95%:  Continue — gaps exist that new patterns could fill

Step D.3: Gap Analysis
    Identify signal trajectories where:
    - Outcome label indicates meaningful event (e.g., "resistance_emerged")
    - No existing pattern matches with confidence >= 0.60
    - Signal vectors cluster tightly (low variance in SMI, bhava)

    These are the GAPS — outcomes the current vtable cannot recognize.

Step D.4: Cluster Discovery
    Apply Stage 3 clustering (Section 3.4) to gap trajectories
    Each cluster becomes a candidate vtable entry

Step D.5: Candidate Validation
    For each candidate:
    - Cross-validate on held-out signal trajectories
    - Measure precision/recall at proposed threshold
    - Check overlap with existing patterns
    - Run invariant preservation checks (INV-P38-1 through INV-P38-7)

Step D.6: Governance Submission
    Package candidates with provenance, statistics, examples
    Submit to governance gate (Section 4)
    Wait for approval/rejection/deferral

Step D.7: VTable Update
    Approved candidates → new module-level constants
    Version bump: vtable_v1.x.y → vtable_v2.0.0
    Checksum manifest updated
    Previous vtable version preserved (never deleted)
```

### 5.3 Phase C': Re-tuning with Expanded VTable

After the vtable is expanded and frozen, the model undergoes a short re-tuning phase:

**Purpose**: The model's CDI classifier needs to recognize the new patterns. The classifier weights in the phase transformer's 32D sovereign state must be updated to dispatch against the expanded vtable.

**Method**: Standard Phase C training procedure, but with the expanded vtable as the target pattern set. The new patterns become additional classification targets in the CDI head.

**Duration**: Short — the model already understands the signal space. It only needs to learn the new decision boundaries within that space.

**Invariant**: The re-tuned model produces the same results as the original model for all 13 original patterns. New patterns are additive — they do not disturb existing dispatch.

```
Re-tuning validation:

For each of the 13 original patterns:
    For each validation example:
        confidence_original = model_v1.classify(example)
        confidence_retrained = model_v2.classify(example)
        assert abs(confidence_original - confidence_retrained) < epsilon
        # epsilon = 0.02 (tolerance for floating-point drift from re-training)
```

---

## 6. VTable Discovery Applied to Drug Discovery

### 6.1 Pharmaceutical Training Corpus

The drug discovery evaluation document identifies five application areas. Each provides training data for vtable discovery:

| Application | Data Source | Outcome Labels | Expected Pattern Discoveries |
|-------------|-----------|---------------|------------------------------|
| Literature mining | PubMed abstracts, DrugBank | drug-target associations, mechanism labels | Target engagement patterns, pathway activation signatures |
| Drug-target interaction | ChEMBL, BindingDB | binding affinity categories | Binding selectivity patterns, off-target risk signatures |
| Adverse reactions | FAERS reports, WHO-UMC | adverse event types, severity | Toxicity escalation patterns, organ-specific risk signatures |
| Clinical trials | ClinicalTrials.gov, EudraCT | efficacy outcomes, dropout reasons | Response trajectory patterns, non-adherence signatures |
| Drug repurposing | CTD, KEGG pathways | shared mechanism labels | Cross-indication transfer patterns |

### 6.2 Example: Discovering `drug_resistance_emergence`

**Step 1 — Corpus**: 12,000 pharmacovigilance narratives from FAERS, each labeled with whether antimicrobial resistance was reported.

**Step 2 — Signal Harvest**: Run Phase Quad over each narrative. Record CDI signals at each sentence. Narratives average 15-20 sentences, producing 15-20 signal vectors per example.

**Step 3 — Gap Analysis**: Existing 13 patterns cover 67% of labeled resistance events. The remaining 33% fall in a signal region not covered by any current pattern: SMI 0.55-0.80, bhava 4-8, direction upward/neutral. This is the *gap* — a signal region with meaningful outcomes but no vtable entry.

**Step 4 — Cluster**: The gap trajectories cluster into a tight region:
- SMI: mean 0.67, std 0.09
- Bhava: mode 6, entropy 1.1
- Direction: 78% upward, 22% neutral
- The cluster is well-separated from `chronic_stress` (SMI 0.55-0.75, bhava 2-5, direction downward) and from `defensive_rationalization` (SMI 0.45-0.65, bhava 4-8, direction neutral/upward)

**Step 5 — Candidate**:

```python
CandidateVTableEntry(
    pattern_config=PatternConfig(
        name="drug_resistance_emergence",   # provisional, governance may rename
        min_confidence=0.70,
        category="pharmacological_escalation",
        smi_range=(0.55, 0.80),
        bhava_range=(4, 8),
        directions=["upward", "neutral"],
        temporal_trends=["rising", "stable"],
        kosha_weights={1: 0.3, 2: 0.4, 3: 0.2, 4: 0.1},
        ontology_weights={3: 0.3, 5: 0.3, 7: 0.2, 9: 0.2},
    ),
    discovery_method="cluster_outcome_label",
    training_corpus="faers_amr_12k_v1",
    sample_count=3960,             # 33% of 12,000
    separability_score=0.82,       # well-separated from neighbors
    overlap_with=["chronic_stress"],# 12% overlap (acceptable)
    smi_mean=0.67,
    smi_std=0.09,
    bhava_mode=6,
    bhava_entropy=1.1,
    direction_agreement=0.78,
    example_trajectories=["FAERS-2024-001234", "FAERS-2024-005678", ...],
    status="proposed",
    reviewer=None,
    review_notes=None,
)
```

**Step 6 — Governance**: Pharmacology domain expert reviews the candidate. Confirms the signal signature matches clinical understanding of resistance emergence (increasing mismatch, elevated agentic state, upward trajectory = "the pathogen is adapting"). Approves with a renamed pattern and authored interpretations.

**Step 7 — Freeze**: Entry becomes Pattern #14 in vtable_v2.0.0.

### 6.3 Expected Pharmaceutical VTable Expansion

Based on the drug discovery application areas, training is expected to discover patterns in these categories:

```
Pharmacological Escalation Patterns:
    #14  drug_resistance_emergence      — pathogen/tumor adapting to therapy
    #15  dose_escalation_pressure       — clinical need to increase dosage
    #16  toxicity_threshold_approach    — signals approaching toxic boundary
    #17  polypharmacy_interaction       — multi-drug signal interference

Efficacy Trajectory Patterns:
    #18  therapeutic_response_onset     — early signs of drug effectiveness
    #19  efficacy_plateau               — response ceiling reached
    #20  treatment_fatigue              — declining response over time

Clinical Safety Patterns:
    #21  adverse_event_cascade          — one AE triggering subsequent AEs
    #22  organ_toxicity_accumulation    — gradual organ-specific damage signal
    #23  withdrawal_risk                — signals preceding abrupt discontinuation

Recovery/Remission Patterns:
    #24  remission_trajectory           — disease regression under treatment
    #25  relapse_precursor              — early signals of disease return
```

These 12 new patterns would expand the vtable from 13 → 25 entries. With 3 domains (pharmacology, oncology, infectious disease), that is 12 × 3 = 36 new domain interpretation strings — feasible for governance review.

### 6.4 Pharmaceutical Sequence VTable Expansion

New patterns enable new sequences:

```python
# Escalation sequences
PatternSequenceRule("resistance_cascade",
    ["drug_resistance_emergence", "dose_escalation_pressure", "toxicity_threshold_approach"],
    max_gap_turns=3, min_step_confidence=0.65, category="escalation")

PatternSequenceRule("polypharmacy_spiral",
    ["efficacy_plateau", "polypharmacy_interaction", "adverse_event_cascade"],
    max_gap_turns=2, min_step_confidence=0.70, category="escalation")

# Resolution sequences
PatternSequenceRule("successful_treatment_arc",
    ["therapeutic_response_onset", "efficacy_plateau", "remission_trajectory"],
    max_gap_turns=4, min_step_confidence=0.60, category="resolution")

PatternSequenceRule("managed_resistance",
    ["drug_resistance_emergence", "dose_escalation_pressure", "therapeutic_response_onset"],
    max_gap_turns=3, min_step_confidence=0.65, category="resolution")

# Warning sequences (high clinical value)
PatternSequenceRule("relapse_warning",
    ["remission_trajectory", "treatment_fatigue", "relapse_precursor"],
    max_gap_turns=2, min_step_confidence=0.70, category="escalation")
```

---

## 7. VTable Versioning and the Ontology Freeze Contract

### 7.1 Compatibility with Existing Freeze Contract

The Ontology Freeze Contract (`ONTOLOGY_FREEZE_CONTRACT.md`) governs three frozen JSON files:
- `varna_bridge_map_v1.json`
- `ontological_layers_v1.json`
- `varna_layer_interaction_v1.json`

**The vtable does not modify these files.** The ontological substrate (10 layers, 12 bhavas, 8 koshas, 13 ontology states) remains frozen. VTable entries operate *within* this substrate — they define regions in the signal space, not new signal dimensions.

The relationship:

```
Ontology Freeze Contract (immutable substrate):
    Defines the DIMENSIONS: bhava (0-11), kosha (0-7), ontology (0-12)

VTable (extensible dispatch table):
    Defines REGIONS within those dimensions: smi_range, bhava_range, etc.

Training discovers new REGIONS, not new DIMENSIONS.
```

### 7.2 VTable Versioning Scheme

```
vtable_v{major}.{minor}.{patch}

major: New patterns added (vtable rows changed)
minor: Thresholds or weights adjusted (vtable values changed)
patch: Domain interpretations added/edited (metadata changed)

Examples:
    vtable_v1.0.0  — Initial 13 patterns (hand-curated, current)
    vtable_v2.0.0  — 25 patterns (13 original + 12 pharma-discovered)
    vtable_v2.1.0  — 25 patterns, retuned weights for pharma domain
    vtable_v2.1.1  — 25 patterns, added oncology interpretations
    vtable_v3.0.0  — 40 patterns (added 15 from clinical trial corpus)
```

### 7.3 VTable Manifest

Each vtable version is accompanied by a manifest:

```python
@dataclass(frozen=True)
class VTableManifest:
    """Immutable record of a vtable version."""
    version: str                              # "vtable_v2.0.0"
    created_date: str                         # ISO 8601
    pattern_count: int                        # total patterns
    sequence_count: int                       # total sequences
    aspect_count: int                         # total aspect derivations
    domain_count: int                         # total domain columns

    # Provenance
    entries: List[VTableEntryProvenance]       # one per pattern

    # Integrity
    checksum_sha256: str                      # SHA-256 of serialized vtable
    parent_version: Optional[str]             # previous vtable version

    # Governance
    governance_cycle: str                     # governance review identifier
    approvers: List[str]                      # reviewer IDs who approved

@dataclass(frozen=True)
class VTableEntryProvenance:
    """How a single vtable entry came to exist."""
    pattern_name: str
    origin: str                               # "hand_curated" | "training_discovered"
    origin_version: str                       # vtable version where first introduced
    training_corpus: Optional[str]            # if training_discovered
    sample_count: Optional[int]               # if training_discovered
    separability_score: Optional[float]       # if training_discovered
    governance_reviewer: str                  # who approved
    governance_date: str                      # when approved
```

---

## 8. Invariant Preservation Proof

The vtable architecture must preserve all existing CDI invariants. This section proves that it does.

### INV-P38-1: Deterministic (same inputs → same outputs)

**Proof**: At inference time, the vtable is a frozen set of module-level constants. `_compute_pattern_confidence()` iterates over the vtable and applies deterministic scoring formulas. Adding more rows to the vtable does not change the scoring function — it only adds more iterations. Same signals always produce the same pattern matches against the same frozen vtable.

### INV-P38-2: Observer-only (never influences decisions)

**Proof**: The vtable adds new pattern names to the CDI output but does not create new actuator paths. New patterns are reported in the same observer-only channel as existing patterns. The DHA (tone adjustment) remains soft steering — non-binding, advisory. No vtable entry can trigger an action, only a classification.

### INV-P38-3: No LLM, no ML at inference time

**Proof**: All ML (clustering, statistical aggregation) happens in Phase D (training). The output of Phase D is a frozen PatternConfig — a static data structure with float ranges and string labels. The inference engine processes PatternConfig entries with arithmetic comparisons and weighted sums, not with any ML model.

### INV-P38-4: Sliding window bounded (max 10 snapshots)

**Proof**: The vtable architecture does not modify the CrossDomainPatternTracker's window management. New patterns are classified within the same 10-snapshot sliding window. More patterns per snapshot does not increase the window size.

### INV-P38-5: Locked formulas

**Proof**: Aspect derivation functions are frozen after governance approval, identical to existing hand-curated derivations. If training proposes a new derivation function, it must pass governance review and then be frozen as a module-level constant — same as the existing 10 derivations.

### INV-P38-6: Conservative degradation

**Proof**: An input that does not match any vtable entry produces no match — this is the pattern matching semantics. Adding more vtable entries can only *increase* coverage (more regions are recognized), never *decrease* safety (an unrecognized region still produces no match). The system never hallucinates a match where none exists.

### INV-P38-7: Governance-approved

**Proof**: The governance gate (Section 4) is a mandatory step in the pipeline. No training-discovered candidate enters the frozen vtable without passing the full governance checklist. The gate is architectural, not procedural — the freeze step requires a governance approval record.

---

## 9. The Deeper Architectural Insight

### 9.1 Where Curation Happens in the Pipeline

The vtable architecture shifts **where** curation happens, not **whether** it happens:

```
Today:
    Human Expert ─────────────────────→ Pattern Library → Inference
                   (manual authoring)   (frozen vtable)

VTable Architecture:
    Data → Training → Candidates → Governance → Pattern Library → Inference
           (discover   (proposed    (human       (frozen vtable,
            vtable      entries)     review +     indistinguishable
            entries)                 naming)      from hand-curated)
```

The governance review step is the invariant. It guarantees that every vtable entry — regardless of origin — meets the same interpretability, separability, and calibration bar. Training accelerates the *proposal* side of curation. Governance maintains the *quality* side.

### 9.2 Virtual Methods Were Always There

CDI already has virtual methods — they are just hand-authored. Every PatternConfig is a vtable row. Every call to `_compute_pattern_confidence()` is a virtual dispatch. The "closed world" of pattern matching is closed only because the vtable was manually authored with a fixed number of rows.

The insight that pattern matching and virtual methods are "two opposite ends" is correct at the language level but not at the architecture level. CDI's pattern matching *is* virtual dispatch — with the vtable populated at "compile time" (design phase) rather than at runtime. Training simply automates part of the compile-time population.

### 9.3 The Compile-Time / Runtime Boundary

In traditional OOP:
- **Compile time**: vtable layout is determined by class hierarchy
- **Runtime**: vtable dispatch resolves method calls

In Phase Quad:
- **Training time**: vtable entries are discovered from data
- **Governance time**: vtable entries are reviewed and frozen
- **Inference time**: vtable dispatch classifies signal vectors

The key insight is that **governance time IS compile time**. It is the moment when the open world (training discoveries) becomes the closed world (frozen dispatch table). The compilation is performed by human reviewers, not by a compiler — but the architectural role is identical.

### 9.4 Scaling Properties

```
Hand-curated vtable:
    Patterns scale with: expert hours × domain knowledge
    Bottleneck: human authoring speed
    Typical: 13 patterns over 12+ months

Training-discovered vtable:
    Patterns scale with: labeled data × compute × governance bandwidth
    Bottleneck: governance review speed
    Typical: 50-100 patterns per training cycle (governance is the limiter, not discovery)
```

The vtable architecture moves the bottleneck from **pattern discovery** (hard, requires deep domain expertise) to **pattern review** (easier, requires domain expertise but not creative synthesis). Discovery is automated. Review remains human. This is a 5-10x throughput improvement for vtable population.

---

## 10. Implementation Sequence

### 10.1 Phased Delivery

| Phase | Deliverable | Changes to Existing Code |
|-------|-----------|-------------------------|
| **V1: VTable Manifest** | Formalize existing 13 patterns as vtable_v1.0.0 with manifest and provenance records | Metadata only — no behavioral change |
| **V2: Training Harness** | Signal harvesting pipeline (Stage 1-2) that runs Phase Quad over labeled corpora and records CDI signals | New module, no changes to existing CDI |
| **V3: Discovery Engine** | Clustering and candidate proposal pipeline (Stage 3-4) | New module, no changes to existing CDI |
| **V4: Governance Tooling** | Review interface, approval workflow, freeze protocol (Stage 5-8) | New module, vtable loading from versioned config |
| **V5: Pharma Pilot** | First training-discovered patterns from FAERS corpus, governance-approved, vtable_v2.0.0 | VTable expanded, inference unchanged |
| **V6: Re-tuning** | Phase C' re-tuning with expanded vtable, validation of original pattern preservation | Training procedure extension |

### 10.2 Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Training discovers noise patterns (low signal, high variance) | Separability score threshold + governance review |
| Expanded vtable slows inference | Pattern matching is O(N) with small constants; 25 patterns vs 13 adds ~1μs per turn |
| New patterns destabilize existing pattern confidences | Phase C' re-tuning validation: all 13 original patterns must reproduce within epsilon |
| Governance bottleneck limits throughput | Batch review cycles (quarterly); prioritize by coverage gap impact |
| Domain experts unavailable for pharmaceutical review | Partner with pharma advisory board; defer patterns without domain review |

---

## 11. Conclusion

The vtable architecture resolves the tension between CDI's closed-world pattern matching (deterministic, auditable, frozen) and the need to scale beyond 13 hand-curated patterns. By recognizing that CDI's pattern library is architecturally a virtual method table — populated at design time, dispatched at inference time — we can insert a training phase that automates the population step while preserving every inference-time invariant.

Training discovers the vtable entries. Governance seals them. Inference dispatches against them. The three phases are complementary, not conflicting. The virtual method (open world, extensible) and the pattern match (closed world, exhaustive) are the same structure observed at different points in its lifecycle.

For drug discovery, this means Phase Quad can scale from 13 universal patterns to 25+ pharmaceutical patterns without an army of domain experts hand-authoring each one — while maintaining the deterministic explainability, conservative degradation, and audit-trail integrity that make Phase Quad trustworthy in regulated industries.

The vtable was always there. Training just learned to populate it.

---

*Architecture document prepared for Cognade Labs / Symbol-U Architecture Team*
*February 2026*
