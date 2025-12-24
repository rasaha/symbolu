# Name Resonance System - Canonical Matching Design

## Overview

The canonical matching framework provides a principled approach to measuring
resonance between words/names through the formula:

```
MATCH = C × R × S
```

This document captures the complete design rationale, including analysis from
collaborative sessions with ChatGPT that identified and resolved architectural
concerns.

---

## The C × R × S Framework

### Formula Components

| Term | Name | Source | Question Answered |
|------|------|--------|-------------------|
| **C** | Constraint/Feasibility | Phonemic (varṇa/ontological) | "Is this allowed to exist?" |
| **R** | Realization/Strength | Phonemic (structural/experiential) | "How strongly does it manifest?" |
| **S** | Referential Coherence | **Non-phonemic** (external referents) | "Do these point to the same invariant?" |

### Diagnostic Matrix (C × R, gated by S)

```
              ┌─────────────┬───────────────┬───────────────┐
              │             │   High R      │    Low R      │
              ├─────────────┼───────────────┼───────────────┤
              │   High C    │  TRUE_MATCH   │    LATENT     │
              │   Low C     │  DISTORTED    │   NON_MATCH   │
              └─────────────┴───────────────┴───────────────┘
```

When S is low, MATCH collapses to REFERENT_MISMATCH regardless of C × R.

---

## Source Independence Principle

### The Problem (identified by ChatGPT)

The original C × R formula had a **source-independence violation**:

```
C derives from phonemes → varṇa → ontological layers
R derives from phonemes → structure → experiential dimensions

Both C and R trace back to the same phonemic evidence base.
```

This means C and R are not truly independent observations—they're two views
of the same underlying data. High correlation between C and R could be
an artifact of shared phonemic source rather than genuine resonance.

### The Solution

Add S (Referential Coherence) as a third, **non-phonemic** term:

```
S derives from:
- External referent class mappings
- Symbolic, finite, deterministic word→class lookup
- NOT from phonemes, acoustics, or statistical embeddings
```

### Why S Must Be Non-Phonemic

| Property | C | R | S |
|----------|---|---|---|
| Source | Phonemes | Phonemes | External dictionary |
| Derivation | varṇa bridge | Structural projection | Referent classes |
| Evidence base | Acoustic | Acoustic | Symbolic/conceptual |

S provides the orthogonal axis required for valid triangulation:

```
     C (phonemic)
      \
       \_____ MATCH
       /
      /
     R (phonemic)
      |
      S (non-phonemic) ← orthogonal validation
```

---

## Names vs Words: Epistemic Restraint

### The Concern

> "Names likely won't be in the referent dictionary → S = 0.5 for most
> name comparisons."

### Why This Is Correct By Design

This is a **feature, not a bug**. The design explicitly states:

> "This system analyzes phonetic structure only. It does not assess
> personality, capability, or destiny."

### Implicit Type Dispatch

```python
MATCH(a, b) = C × R × S

where S = {
    compute_referent_coherence(a, b)   # if both are words
    0.5                                 # if either is a name (UNKNOWN)
}
```

### Why Names Must Not Rely on S

If S were active for names, the system would collapse into:

1. **Cultural bias** — "Rama" would inherit Hindu referent classes; "Mary"
   would inherit Christian ones

2. **Dictionary leakage** — "Rose" (as name) would match BOTANICAL;
   "Hunter" (as name) would match PREDATOR

3. **Personality inference** — Violates the explicit design constraint
   against assessing "personality, capability, or destiny"

### The Correct Behavior

| Input Type | C | R | S | Rationale |
|------------|---|---|---|-----------|
| **Words** | Active | Active | Active | Full semantic discrimination |
| **Names** | Active | Active | Neutral (0.5) | Phonetic structure only |

The neutral S (0.5) lets C and R dominate for names—which is exactly what
phonetic structure analysis should do.

**This is not a workaround. It is correct epistemic restraint.**

---

## Referent Classes (ERC)

### Primary vs Secondary Structure

Words are mapped to referent classes with Primary/Secondary distinction:

- **Primary**: What the word IS (core identity)
- **Secondary**: What it produces/enables/affects

```python
"sun": ReferentProfile(
    primary=frozenset({NATURAL_BODY, ENERGY_SOURCE}),
    secondary=frozenset({LUMINOUS}),
)

"light": ReferentProfile(
    primary=frozenset({PHENOMENON}),
    secondary=frozenset({LUMINOUS}),
)

"king": ReferentProfile(
    primary=frozenset({ROLE_BEARER, SOCIAL}),
    secondary=frozenset(),
)
```

### S Computation

```
Primary overlap    → 0.7 - 1.0 (high coherence)
Secondary only     → 0.3 - 0.5 (partial coherence)
No overlap         → 0.0       (referent mismatch)
UNKNOWN present    → 0.5       (epistemic uncertainty)
```

### Class Taxonomy

The ORGANISM class was split per ChatGPT review to prevent false matches:

| Original | Refined | Rationale |
|----------|---------|-----------|
| ORGANISM | BIOLOGICAL_ORGANISM | Living things (plants, animals) |
| ORGANISM | ROLE_BEARER | Social agents who bear roles |

This prevents `king ↔ banana` from matching (both were ORGANISM, now
king = ROLE_BEARER, banana = BIOLOGICAL_ORGANISM).

### Full Class List

```
LUMINOUS           - Sources and carriers of light/energy
BIOLOGICAL_ORGANISM - Living things (plants, animals) - NOT roles
ROLE_BEARER        - Social agents who bear roles (king, doctor)
ARTIFACT           - Human-made objects and tools
NATURAL_BODY       - Natural physical entities (celestial, geological)
SUBSTANCE          - Materials and matter
PROCESS            - Actions, events, transformations
ABSTRACT           - Concepts, relations, qualities
SIGNAL             - Communication, information carriers
TEMPORAL           - Time-related concepts
SPATIAL            - Space, location, direction
EMOTIONAL          - Feelings, psychological states
SOCIAL             - Roles, relationships, institutions
ENERGY_SOURCE      - Things that produce/emit energy
PHENOMENON         - Observable occurrences (not sources)
UNKNOWN            - Unmapped words (epistemic uncertainty)
```

---

## STL Integration Assessment

### Architecture Context

**STL = Symbolic Transformer Logic** — a deterministic, zero-parameter
symbolic computation engine.

**Engine Tiers:**
- Enterprise Tier 1: Pure STL (PhonemeRouterProvider, HashEmbeddingProvider)
- Enterprise Tier 2: STL + 7B specialized models
- Consumer Tier: STL + 768D embeddings + cascading LLM

### Provider Pattern

Three pluggable interfaces exist:
- `EmbeddingProvider` — 256D (enterprise) or 768D (consumer)
- `RouterProvider` — 10D layer affinity analysis
- `FilterProvider` — Phoneme resonance or attention-based

### Tier Classification

```
Canonical Matching:
  Tier: Core/Substrate (Tier 1)
  Authority: NONE (signal processing only)
```

This matches name_resonance's tier classification—pure signal processing
with zero governance authority.

### Integration Points

| Integration Style | Feasibility | Notes |
|-------------------|-------------|-------|
| Diagnostic metadata | **Recommended** | Add to EngineResult.metadata |
| Standalone utility | Good | For explicit coherence audits |
| Deep pipeline integration | Poor | Use case mismatch (pairwise vs query→response) |
| Governance enforcement | Poor | Authority mismatch (Tier 1 vs Tier 2+) |

### Recommended Integration

Add canonical match results to `EngineResult.metadata` for post-generation
coherence diagnostics:

```python
result = EngineResult(
    response="The king reigns supreme",
    metadata={
        "coherence_check": {
            "words": ("king", "reigns"),
            "match_score": 0.687,
            "mode": "TRUE_MATCH",
            "components": {"C": 0.82, "R": 0.84, "S": 0.99}
        }
    }
)
```

### Use Case Assessment

| Scenario | C × R × S Applicability |
|----------|------------------------|
| Word-to-word semantic matching | Full (S discriminates) |
| Name-to-name phonetic matching | Partial (S neutral, C×R active) |
| Post-generation coherence | Good (pairwise on output terms) |
| Query routing | Poor (no natural pairwise comparison) |

---

## Match Modes

```python
class MatchMode(Enum):
    TRUE_MATCH = "true_match"           # High C, High R, High S
    LATENT = "latent"                   # High C, Low R, High S
    DISTORTED = "distorted"             # Low C, High R, High S
    NON_MATCH = "non_match"             # Low C, Low R, or Low S
    REFERENT_MISMATCH = "ref_mismatch"  # Any C/R, but Low S
```

### Interpretation

- **TRUE_MATCH**: Structurally allowed, strongly manifest, referentially coherent
- **LATENT**: Allowed but not yet manifest (potential exists)
- **DISTORTED**: Manifest despite constraints (forced/unnatural)
- **NON_MATCH**: Neither allowed nor manifest
- **REFERENT_MISMATCH**: Phonetically similar but semantically unrelated

---

## Validation Results

### ChatGPT Failure Mode Tests (All Pass)

| Test Case | Expected | Actual | Status |
|-----------|----------|--------|--------|
| king ↔ banana | ~0.0 | 0.000 | PASS |
| tree ↔ computer | ~0.0 | 0.000 | PASS |
| sun ↔ light | Partial | 0.4xx | PASS |
| fire ↔ flame | High | 0.7xx | PASS |

### Key Fixes Applied

1. **Source independence**: Added S term (non-phonemic)
2. **ORGANISM too coarse**: Split into BIOLOGICAL_ORGANISM + ROLE_BEARER
3. **Primary/Secondary**: Implemented ReferentProfile with distinct sets

---

## File Structure

```
symbolu/name_resonance/
├── __init__.py              # Public exports
├── api.py                   # High-level API (analyze_name, etc.)
├── canonical_matcher.py     # C × R × S implementation
├── referent_classes.py      # S term: External Referent Classes
├── ontological_bridge.py    # C term: 10D layer constraint analysis
├── projector.py             # R term: 12D structural projection
├── extractor.py             # Signal extraction from input
├── matcher.py               # Domain compatibility matching
├── types.py                 # Shared type definitions
└── DESIGN.md                # This document
```

---

## Design Principles

1. **Source Independence**: At least one axis must be non-phonemic
2. **Epistemic Restraint**: Names get neutral S to prevent cultural bias
3. **Deterministic**: Same input always produces identical output
4. **Zero Authority**: Signal processing only, no governance decisions
5. **Graceful Degradation**: Unknown words get S=0.5, not failure

---

## References

- ChatGPT analysis sessions (source-independence, ORGANISM split, epistemic restraint)
- STL_LLM_CAPABILITY_EVALUATION.md (tier architecture)
- Authority Cascade Validator (governance hierarchy)

---

*Document created: Canonical Matching Design v1.0*
*Framework: MATCH = C × R × S*
*Tier: Core/Substrate (Tier 1)*
*Authority: NONE*
