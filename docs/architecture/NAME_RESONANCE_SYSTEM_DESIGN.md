# Name Resonance System Design

## Engineering Specification v1.0

**Author**: Claude Code
**Date**: 2025-12-21
**Status**: Design Document
**Extends**: SYMBOLU_ENGINE_ARCHITECTURE.md

---

## 1. Executive Summary

This document specifies a deterministic system that transforms names (or short phrases) into cross-domain compatibility assessments. The system produces structured outputs for career fields, sports/skills, and domain resonance without relying on intuition, learned correlations, or stochastic processes.

**What this system IS:**
- A signal extraction and structural projection engine
- A deterministic mapping from phonetic/graphemic features to domain compatibility
- An explainable system with traceable reasoning chains

**What this system is NOT:**
- Personality assessment
- Astrology or numerology
- Predictive psychology
- A claim about individual capabilities or destiny

---

## 2. System Architecture (High Level)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NAME RESONANCE SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Layer 1   │───▶│   Layer 2   │───▶│   Layer 3   │───▶│   Layer 4   │  │
│  │   INPUT     │    │   SIGNAL    │    │  ABSTRACT   │    │   DOMAIN    │  │
│  │ NORMALIZE   │    │ EXTRACTION  │    │   SPACE     │    │ PROJECTION  │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                 │                  │                  │          │
│         ▼                 ▼                  ▼                  ▼          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ Canonical   │    │ Phoneme     │    │ Structural  │    │ Domain      │  │
│  │ Form        │    │ Sequence    │    │ Profile     │    │ Scores      │  │
│  │             │    │ + Rhythm    │    │ (12D)       │    │ + Reasoning │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         Layer 5: EXPLANATION                         │  │
│  │   Full trace from input → signals → structure → domain → reasoning   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Name | Deterministic? | Purpose |
|-------|------|----------------|---------|
| L1 | Input Normalization | Yes | Convert raw input to canonical form |
| L2 | Signal Extraction | Yes | Extract mechanical features from input |
| L3 | Abstract Space | Yes | Project signals into domain-agnostic structure |
| L4 | Domain Projection | Configurable | Map structure to specific domain compatibility |
| L5 | Explanation | Yes | Generate traceable reasoning chain |

**Key invariant**: L1-L3 are fully deterministic. Same input → same abstract structure, always.

**L4 note**: Domain projection rules are explicit and configurable, not learned.

---

## 3. Layer 1: Input Normalization

### 3.1 Purpose
Transform arbitrary input strings into a canonical form suitable for signal extraction.

### 3.2 Operations

```python
@dataclass(frozen=True)
class NormalizedInput:
    """Immutable canonical form of input."""
    original: str               # Raw input
    canonical: str              # Normalized form
    segments: Tuple[str, ...]   # Word/syllable segments
    script_family: str          # "latin", "devanagari", "mixed"
```

### 3.3 Normalization Rules (Deterministic)

1. **Case folding**: Convert to lowercase (preserves original in trace)
2. **Diacritic handling**: Normalize to base form with diacritic metadata
3. **Whitespace**: Collapse to single spaces, strip leading/trailing
4. **Script detection**: Identify character families
5. **Segmentation**: Split on whitespace for multi-word inputs

### 3.4 Examples

| Input | Canonical | Segments |
|-------|-----------|----------|
| "Campbell" | "campbell" | ("campbell",) |
| "José María" | "jose maria" | ("jose", "maria") |
| "राकेश" | "rākēśa" | ("rākēśa",) |

---

## 4. Layer 2: Signal Extraction

### 4.1 Purpose
Extract mechanical, rule-based features from the canonical form. No interpretation at this layer.

### 4.2 Signal Categories

```python
@dataclass(frozen=True)
class ExtractedSignals:
    """All signals extracted from input."""
    # Phonemic signals
    phoneme_sequence: Tuple[str, ...]      # ARPABET or Varṇa sequence
    phoneme_categories: Tuple[str, ...]    # Category per phoneme

    # Rhythmic signals
    syllable_count: int
    stress_pattern: Tuple[int, ...]        # 0=unstressed, 1=stressed, 2=primary
    vowel_consonant_ratio: float

    # Structural signals
    onset_cluster_size: int                # Initial consonant cluster
    coda_cluster_size: int                 # Final consonant cluster
    syllable_structure: str                # CV pattern (e.g., "CVC.CVC")

    # Positional signals
    initial_phoneme: str
    final_phoneme: str
    vowel_trajectory: Tuple[str, ...]      # Sequence of vowels

    # Energy signals (from phoneme categories)
    plosive_count: int
    fricative_count: int
    nasal_count: int
    liquid_count: int
```

### 4.3 Signal Extraction Rules

#### 4.3.1 Phoneme Extraction
- **Latin script**: Use CMU Pronouncing Dictionary or G2P fallback
- **Devanagari**: Use direct grapheme-to-phoneme mapping (more regular)
- **Unknown**: Use rule-based G2P with explicit uncertainty flag

#### 4.3.2 Rhythmic Analysis
- Syllable boundaries: Maximum onset principle
- Stress assignment: Lexical lookup or rule-based (English: penultimate default)

#### 4.3.3 Why These Signals Are Defensible

| Signal Type | Justification |
|-------------|---------------|
| Phoneme sequence | Directly observable acoustic/articulatory structure |
| Syllable structure | Linguistic universal with cross-language validity |
| Stress pattern | Measurable prosodic feature |
| Consonant clusters | Observable phonotactic constraint patterns |
| Energy distribution | Based on articulatory effort (plosive > fricative > liquid) |

---

## 5. Layer 3: Abstract Structural Space

### 5.1 Purpose
Project raw signals into a domain-agnostic structural representation. This is the core abstraction layer.

### 5.2 Structural Profile (12 Dimensions)

The abstract representation uses 12 orthogonal dimensions:

```python
@dataclass(frozen=True)
class StructuralProfile:
    """Domain-agnostic structural representation."""

    # Energy Dimensions (3)
    force: float          # 0.0-1.0: Low (flowing) to High (forceful)
    stability: float      # 0.0-1.0: Variable to Constant
    duration: float       # 0.0-1.0: Brief to Sustained

    # Movement Dimensions (3)
    initiation: float     # 0.0-1.0: Gradual to Explosive
    flow: float           # 0.0-1.0: Interrupted to Continuous
    termination: float    # 0.0-1.0: Fading to Abrupt

    # Structural Dimensions (3)
    complexity: float     # 0.0-1.0: Simple to Complex
    density: float        # 0.0-1.0: Sparse to Dense
    balance: float        # 0.0-1.0: Asymmetric to Symmetric

    # Resonance Dimensions (3)
    openness: float       # 0.0-1.0: Closed to Open (vowel quality)
    depth: float          # 0.0-1.0: Surface to Deep (articulation place)
    connectivity: float   # 0.0-1.0: Isolated to Connected (nasal/liquid presence)

    # Trace
    signal_contributions: Tuple[Tuple[str, str, float], ...]  # (dimension, signal, weight)
```

### 5.3 Signal → Dimension Mapping Rules

These mappings are explicit and deterministic:

```python
SIGNAL_TO_DIMENSION_RULES = {
    # Force dimension
    "force": [
        ("plosive_ratio", 0.4),       # More plosives → higher force
        ("fricative_ratio", 0.3),     # Fricatives contribute moderate force
        ("stress_weight", 0.3),       # Stressed syllables → higher force
    ],

    # Stability dimension
    "stability": [
        ("syllable_regularity", 0.4), # Regular patterns → higher stability
        ("vowel_consistency", 0.3),   # Same vowel type → higher stability
        ("stress_regularity", 0.3),   # Regular stress → higher stability
    ],

    # Duration dimension
    "duration": [
        ("long_vowel_ratio", 0.4),    # Long vowels → higher duration
        ("diphthong_ratio", 0.3),     # Diphthongs → higher duration
        ("syllable_count", 0.3),      # More syllables → higher duration
    ],

    # Initiation dimension
    "initiation": [
        ("onset_cluster_size", 0.4),  # Larger onset → more explosive
        ("initial_plosive", 0.35),    # Plosive initial → explosive
        ("initial_stress", 0.25),     # Initial stress → stronger initiation
    ],

    # Flow dimension
    "flow": [
        ("liquid_ratio", 0.35),       # More liquids → smoother flow
        ("nasal_ratio", 0.35),        # More nasals → continuous flow
        ("cluster_frequency", -0.30), # Fewer clusters → better flow
    ],

    # Termination dimension
    "termination": [
        ("coda_cluster_size", 0.4),   # Larger coda → more abrupt
        ("final_plosive", 0.35),      # Plosive final → abrupt
        ("final_stress", 0.25),       # Final stress → stronger termination
    ],

    # Complexity dimension
    "complexity": [
        ("unique_phonemes", 0.35),    # More variety → higher complexity
        ("syllable_variety", 0.35),   # Different syllable shapes → complex
        ("stress_irregularity", 0.30),# Irregular stress → complex
    ],

    # Density dimension
    "density": [
        ("consonant_ratio", 0.4),     # More consonants → higher density
        ("cluster_count", 0.3),       # More clusters → higher density
        ("syllable_weight", 0.3),     # Heavy syllables → higher density
    ],

    # Balance dimension
    "balance": [
        ("syllable_symmetry", 0.4),   # Symmetric structure → balanced
        ("energy_distribution", 0.3), # Even energy → balanced
        ("vowel_distribution", 0.3),  # Even vowels → balanced
    ],

    # Openness dimension
    "openness": [
        ("open_vowel_ratio", 0.5),    # Open vowels (a, o) → open
        ("vowel_count", 0.3),         # More vowels → open
        ("final_vowel", 0.2),         # Final vowel → open ending
    ],

    # Depth dimension
    "depth": [
        ("back_consonant_ratio", 0.4),# Velar/uvular → depth
        ("low_vowel_ratio", 0.3),     # Low vowels → depth
        ("nasal_presence", 0.3),      # Nasals → resonant depth
    ],

    # Connectivity dimension
    "connectivity": [
        ("nasal_ratio", 0.35),        # Nasals connect
        ("liquid_ratio", 0.35),       # Liquids connect
        ("glide_ratio", 0.30),        # Glides transition/connect
    ],
}
```

### 5.4 Computation Method

```python
def compute_structural_profile(signals: ExtractedSignals) -> StructuralProfile:
    """
    Deterministic projection from signals to structural space.

    Each dimension is computed as:
    dimension_value = sum(signal_value * weight for signal, weight in rules[dimension])

    All values are normalized to [0.0, 1.0] range.
    """
    dimensions = {}
    contributions = []

    for dimension, rules in SIGNAL_TO_DIMENSION_RULES.items():
        value = 0.0
        for signal_name, weight in rules:
            signal_value = compute_signal_value(signals, signal_name)
            value += signal_value * weight
            contributions.append((dimension, signal_name, signal_value * weight))

        dimensions[dimension] = clamp(value, 0.0, 1.0)

    return StructuralProfile(
        **dimensions,
        signal_contributions=tuple(contributions)
    )
```

---

## 6. Layer 4: Cross-Domain Projection

### 6.1 Purpose
Map the abstract structural profile to specific domain compatibility scores.

### 6.2 Domain as Structural Pattern

**Key insight**: Domains are not labels but structural patterns. Each domain has an "ideal profile" representing the structural qualities that enable success in that domain.

```python
@dataclass(frozen=True)
class DomainPattern:
    """Structural pattern defining a domain's requirements."""
    name: str
    category: str  # "career", "sport", "role"

    # Required structural profile for domain success
    ideal_profile: Dict[str, float]  # dimension → ideal value

    # Dimension weights (which dimensions matter most)
    dimension_weights: Dict[str, float]  # dimension → importance (0-1)

    # Threshold for compatibility
    compatibility_threshold: float  # 0.0-1.0

    # Human-readable rationale
    rationale: str
```

### 6.3 Domain Pattern Definitions

#### 6.3.1 Career Domains

```python
CAREER_DOMAIN_PATTERNS = {
    "justice_law_enforcement": DomainPattern(
        name="Justice / Law Enforcement / Judge",
        category="career",
        ideal_profile={
            "force": 0.7,           # Need authority/presence
            "stability": 0.8,       # Consistency is essential
            "duration": 0.6,        # Sustained attention
            "initiation": 0.6,      # Can take decisive action
            "flow": 0.4,            # Controlled, not fluid
            "termination": 0.7,     # Clear endings/judgments
            "complexity": 0.5,      # Moderate complexity
            "density": 0.6,         # Substantial presence
            "balance": 0.7,         # Fairness/equilibrium
            "openness": 0.4,        # Controlled expression
            "depth": 0.6,           # Gravitas
            "connectivity": 0.4,    # Professional distance
        },
        dimension_weights={
            "stability": 0.15, "balance": 0.15, "force": 0.12,
            "termination": 0.12, "depth": 0.10, "density": 0.10,
            "initiation": 0.08, "duration": 0.06, "complexity": 0.05,
            "flow": 0.03, "openness": 0.02, "connectivity": 0.02,
        },
        compatibility_threshold=0.65,
        rationale="Justice requires stability (consistent application), balance (fairness), "
                  "and force (authority), with clear termination (definitive judgments)."
    ),

    "strategic_leadership": DomainPattern(
        name="Strategic Leadership (Govt/Admin)",
        category="career",
        ideal_profile={
            "force": 0.75,
            "stability": 0.65,
            "duration": 0.7,
            "initiation": 0.7,
            "flow": 0.5,
            "termination": 0.6,
            "complexity": 0.7,
            "density": 0.6,
            "balance": 0.6,
            "openness": 0.5,
            "depth": 0.7,
            "connectivity": 0.6,
        },
        dimension_weights={
            "force": 0.14, "initiation": 0.12, "complexity": 0.12,
            "depth": 0.11, "duration": 0.10, "stability": 0.09,
            "connectivity": 0.08, "termination": 0.07, "balance": 0.06,
            "density": 0.05, "flow": 0.03, "openness": 0.03,
        },
        compatibility_threshold=0.60,
        rationale="Strategic leadership requires force (command presence), initiation "
                  "(decisive action), complexity (handling nuance), and depth (gravitas)."
    ),

    "counseling_emotional_care": DomainPattern(
        name="Counseling / Emotional Care",
        category="career",
        ideal_profile={
            "force": 0.3,
            "stability": 0.7,
            "duration": 0.8,
            "initiation": 0.3,
            "flow": 0.8,
            "termination": 0.3,
            "complexity": 0.5,
            "density": 0.3,
            "balance": 0.7,
            "openness": 0.8,
            "depth": 0.7,
            "connectivity": 0.9,
        },
        dimension_weights={
            "connectivity": 0.16, "openness": 0.14, "flow": 0.13,
            "depth": 0.11, "stability": 0.10, "duration": 0.09,
            "balance": 0.08, "complexity": 0.06, "termination": 0.05,
            "force": 0.03, "initiation": 0.03, "density": 0.02,
        },
        compatibility_threshold=0.65,
        rationale="Counseling requires high connectivity (empathy), openness (receptivity), "
                  "flow (gentle guidance), with low force (non-directive) and soft termination."
    ),

    "symbolic_design_architecture": DomainPattern(
        name="Symbolic Design / Architecture",
        category="career",
        ideal_profile={
            "force": 0.5,
            "stability": 0.6,
            "duration": 0.6,
            "initiation": 0.5,
            "flow": 0.6,
            "termination": 0.5,
            "complexity": 0.8,
            "density": 0.5,
            "balance": 0.8,
            "openness": 0.6,
            "depth": 0.7,
            "connectivity": 0.6,
        },
        dimension_weights={
            "complexity": 0.15, "balance": 0.14, "depth": 0.12,
            "flow": 0.10, "stability": 0.09, "openness": 0.09,
            "duration": 0.08, "connectivity": 0.07, "force": 0.05,
            "density": 0.05, "initiation": 0.03, "termination": 0.03,
        },
        compatibility_threshold=0.60,
        rationale="Symbolic design requires complexity (pattern recognition), balance "
                  "(aesthetic harmony), and depth (meaning), with moderate flow (creative process)."
    ),

    "performing_arts": DomainPattern(
        name="Performing Arts (Actor/Singer)",
        category="career",
        ideal_profile={
            "force": 0.6,
            "stability": 0.4,
            "duration": 0.7,
            "initiation": 0.6,
            "flow": 0.8,
            "termination": 0.5,
            "complexity": 0.7,
            "density": 0.4,
            "balance": 0.5,
            "openness": 0.9,
            "depth": 0.6,
            "connectivity": 0.7,
        },
        dimension_weights={
            "openness": 0.15, "flow": 0.14, "connectivity": 0.12,
            "complexity": 0.10, "duration": 0.10, "force": 0.09,
            "initiation": 0.08, "depth": 0.07, "termination": 0.05,
            "balance": 0.04, "stability": 0.03, "density": 0.03,
        },
        compatibility_threshold=0.55,
        rationale="Performing arts require openness (expression), flow (movement/delivery), "
                  "connectivity (audience rapport), with variable stability (range)."
    ),
}
```

#### 6.3.2 Sports/Skill Domains

```python
SPORTS_DOMAIN_PATTERNS = {
    "golf": DomainPattern(
        name="Golf",
        category="sport",
        ideal_profile={
            "force": 0.5,
            "stability": 0.9,
            "duration": 0.6,
            "initiation": 0.5,
            "flow": 0.7,
            "termination": 0.6,
            "complexity": 0.6,
            "density": 0.4,
            "balance": 0.9,
            "openness": 0.4,
            "depth": 0.7,
            "connectivity": 0.3,
        },
        dimension_weights={
            "stability": 0.18, "balance": 0.16, "flow": 0.12,
            "depth": 0.11, "termination": 0.09, "complexity": 0.08,
            "force": 0.07, "duration": 0.06, "initiation": 0.05,
            "openness": 0.03, "density": 0.03, "connectivity": 0.02,
        },
        compatibility_threshold=0.65,
        rationale="Golf requires exceptional stability (consistency), balance (smooth swing), "
                  "and depth (mental focus), with controlled force."
    ),

    "archery_shooting": DomainPattern(
        name="Archery / Shooting",
        category="sport",
        ideal_profile={
            "force": 0.4,
            "stability": 0.95,
            "duration": 0.5,
            "initiation": 0.4,
            "flow": 0.6,
            "termination": 0.8,
            "complexity": 0.4,
            "density": 0.5,
            "balance": 0.9,
            "openness": 0.3,
            "depth": 0.8,
            "connectivity": 0.2,
        },
        dimension_weights={
            "stability": 0.20, "balance": 0.16, "termination": 0.14,
            "depth": 0.12, "flow": 0.09, "force": 0.07,
            "density": 0.06, "complexity": 0.05, "duration": 0.04,
            "initiation": 0.03, "openness": 0.02, "connectivity": 0.02,
        },
        compatibility_threshold=0.70,
        rationale="Archery/shooting requires extreme stability (stillness), precise termination "
                  "(release point), balance, and depth (focus). Low connectivity (solo focus)."
    ),

    "team_sports": DomainPattern(
        name="Team Sports (Soccer, Basketball)",
        category="sport",
        ideal_profile={
            "force": 0.6,
            "stability": 0.5,
            "duration": 0.7,
            "initiation": 0.7,
            "flow": 0.8,
            "termination": 0.5,
            "complexity": 0.6,
            "density": 0.5,
            "balance": 0.5,
            "openness": 0.6,
            "depth": 0.4,
            "connectivity": 0.9,
        },
        dimension_weights={
            "connectivity": 0.18, "flow": 0.14, "initiation": 0.12,
            "duration": 0.10, "force": 0.09, "openness": 0.09,
            "complexity": 0.07, "stability": 0.06, "balance": 0.05,
            "termination": 0.04, "depth": 0.03, "density": 0.03,
        },
        compatibility_threshold=0.55,
        rationale="Team sports require high connectivity (teamwork), flow (continuous play), "
                  "initiation (quick reactions), with moderate stability (adaptability)."
    ),

    "endurance_track": DomainPattern(
        name="Track / Endurance",
        category="sport",
        ideal_profile={
            "force": 0.5,
            "stability": 0.8,
            "duration": 0.9,
            "initiation": 0.5,
            "flow": 0.9,
            "termination": 0.4,
            "complexity": 0.3,
            "density": 0.5,
            "balance": 0.7,
            "openness": 0.5,
            "depth": 0.6,
            "connectivity": 0.3,
        },
        dimension_weights={
            "duration": 0.18, "flow": 0.16, "stability": 0.14,
            "balance": 0.10, "depth": 0.09, "force": 0.08,
            "density": 0.07, "openness": 0.05, "initiation": 0.05,
            "complexity": 0.03, "termination": 0.03, "connectivity": 0.02,
        },
        compatibility_threshold=0.60,
        rationale="Endurance requires exceptional duration (sustained effort), flow "
                  "(rhythm), stability (pacing), with low complexity (repetitive motion)."
    ),
}
```

### 6.4 Compatibility Computation

```python
def compute_domain_compatibility(
    profile: StructuralProfile,
    domain: DomainPattern
) -> DomainCompatibilityResult:
    """
    Compute weighted compatibility between structural profile and domain pattern.

    Method:
    1. For each dimension, compute distance from ideal
    2. Weight distances by dimension importance
    3. Convert to compatibility score (1 - weighted_distance)
    4. Generate per-dimension reasoning
    """
    dimension_scores = {}
    reasoning_parts = []

    for dimension in DIMENSION_NAMES:
        actual = getattr(profile, dimension)
        ideal = domain.ideal_profile[dimension]
        weight = domain.dimension_weights[dimension]

        # Distance metric: absolute difference
        distance = abs(actual - ideal)

        # Dimension score: how well this dimension matches
        dim_score = 1.0 - distance
        weighted_score = dim_score * weight
        dimension_scores[dimension] = {
            "actual": actual,
            "ideal": ideal,
            "weight": weight,
            "score": dim_score,
            "weighted_contribution": weighted_score,
        }

        # Generate reasoning
        if dim_score >= 0.8:
            match = "strong match"
        elif dim_score >= 0.6:
            match = "moderate match"
        elif dim_score >= 0.4:
            match = "partial match"
        else:
            match = "weak match"

        reasoning_parts.append(
            f"{dimension}: {actual:.2f} vs ideal {ideal:.2f} ({match}, weight={weight:.2f})"
        )

    # Overall compatibility
    total_compatibility = sum(
        d["weighted_contribution"] for d in dimension_scores.values()
    )

    # Classify result
    if total_compatibility >= domain.compatibility_threshold + 0.15:
        classification = "STRONG"
        indicator = "HIGH"
    elif total_compatibility >= domain.compatibility_threshold:
        classification = "MODERATE"
        indicator = "MEDIUM"
    elif total_compatibility >= domain.compatibility_threshold - 0.15:
        classification = "PARTIAL"
        indicator = "CAUTION"
    else:
        classification = "WEAK"
        indicator = "LOW"

    return DomainCompatibilityResult(
        domain_name=domain.name,
        domain_category=domain.category,
        compatibility_score=total_compatibility,
        classification=classification,
        indicator=indicator,
        dimension_breakdown=dimension_scores,
        reasoning=domain.rationale,
        trace=tuple(reasoning_parts),
    )
```

---

## 7. Layer 5: Explanation Generation

### 7.1 Purpose
Generate human-readable explanations that trace from input through all layers to final output.

### 7.2 Explanation Structure

```python
@dataclass(frozen=True)
class FullExplanation:
    """Complete trace from input to output."""

    # Input layer
    original_input: str
    normalized_form: str

    # Signal layer
    phoneme_sequence: str
    key_signals: Tuple[Tuple[str, Any], ...]  # (signal_name, value)

    # Abstract layer
    structural_summary: str  # e.g., "High force, moderate flow, low connectivity"
    dominant_dimensions: Tuple[Tuple[str, float], ...]  # Top 3 dimensions

    # Domain layer
    domain_results: Tuple[DomainCompatibilityResult, ...]

    # Synthesis
    summary: str
    caveats: Tuple[str, ...]
```

### 7.3 Explanation Generation Rules

```python
def generate_explanation(
    normalized: NormalizedInput,
    signals: ExtractedSignals,
    profile: StructuralProfile,
    domain_results: Tuple[DomainCompatibilityResult, ...]
) -> FullExplanation:
    """Generate traceable explanation."""

    # Identify dominant dimensions
    dimension_values = [
        (dim, getattr(profile, dim)) for dim in DIMENSION_NAMES
    ]
    sorted_dims = sorted(dimension_values, key=lambda x: x[1], reverse=True)
    dominant = sorted_dims[:3]

    # Generate structural summary
    high_dims = [d for d, v in dimension_values if v >= 0.7]
    low_dims = [d for d, v in dimension_values if v <= 0.3]

    summary_parts = []
    if high_dims:
        summary_parts.append(f"High: {', '.join(high_dims)}")
    if low_dims:
        summary_parts.append(f"Low: {', '.join(low_dims)}")
    structural_summary = "; ".join(summary_parts) if summary_parts else "Balanced profile"

    # Generate overall summary
    strong_matches = [r for r in domain_results if r.classification == "STRONG"]
    weak_matches = [r for r in domain_results if r.classification == "WEAK"]

    summary = f"Input '{normalized.original}' maps to a profile with {structural_summary}. "
    if strong_matches:
        summary += f"Strong compatibility with: {', '.join(r.domain_name for r in strong_matches)}. "
    if weak_matches:
        summary += f"Limited compatibility with: {', '.join(r.domain_name for r in weak_matches)}. "

    # Always include caveats
    caveats = (
        "This analysis is based solely on phonetic/structural features of the input string.",
        "Domain compatibility reflects structural pattern matching, not individual capability.",
        "Cultural, personal, and contextual factors are not considered.",
        "This is a deterministic projection, not a prediction or personality assessment.",
    )

    return FullExplanation(
        original_input=normalized.original,
        normalized_form=normalized.canonical,
        phoneme_sequence=" ".join(signals.phoneme_sequence),
        key_signals=tuple([
            ("syllable_count", signals.syllable_count),
            ("stress_pattern", signals.stress_pattern),
            ("plosive_count", signals.plosive_count),
            ("nasal_count", signals.nasal_count),
            ("vowel_consonant_ratio", round(signals.vowel_consonant_ratio, 2)),
        ]),
        structural_summary=structural_summary,
        dominant_dimensions=dominant,
        domain_results=domain_results,
        summary=summary,
        caveats=caveats,
    )
```

---

## 8. Example Walkthrough: "Campbell"

### 8.1 Layer 1: Input Normalization

```
Input: "Campbell"
Canonical: "campbell"
Segments: ("campbell",)
Script: latin
```

### 8.2 Layer 2: Signal Extraction

Using CMU Pronouncing Dictionary:
```
Phoneme sequence: K AE M P B AH L
Categories: PLOSIVE, VOWEL_SHORT, NASAL, PLOSIVE, PLOSIVE, VOWEL_SHORT, LIQUID

Rhythmic signals:
- syllable_count: 2
- stress_pattern: (1, 0)  # CAMP-bell, stress on first
- vowel_consonant_ratio: 0.43 (3 vowels / 7 total)

Structural signals:
- onset_cluster_size: 1 (just K)
- coda_cluster_size: 1 (just L)
- syllable_structure: CVC.CVC

Positional signals:
- initial_phoneme: K (PLOSIVE - forceful start)
- final_phoneme: L (LIQUID - flowing end)
- vowel_trajectory: AE → AH (front-open to mid-central)

Energy signals:
- plosive_count: 3 (K, P, B)
- fricative_count: 0
- nasal_count: 1 (M)
- liquid_count: 1 (L)
```

### 8.3 Layer 3: Abstract Structure

Applying signal → dimension rules:

| Dimension | Value | Key Contributors |
|-----------|-------|------------------|
| **force** | 0.68 | High plosive ratio (3/7), stressed initial |
| **stability** | 0.72 | Regular CVC.CVC, consistent vowel pattern |
| **duration** | 0.45 | Short vowels, 2 syllables |
| **initiation** | 0.65 | Single-consonant onset but plosive (K) |
| **flow** | 0.52 | Nasal (M) and liquid (L) present, but interrupted by plosive cluster |
| **termination** | 0.48 | Liquid final (soft ending), no coda cluster |
| **complexity** | 0.45 | 5 unique phonemes, regular structure |
| **density** | 0.57 | 4 consonants to 3 vowels |
| **balance** | 0.75 | Symmetric CVC.CVC, even energy distribution |
| **openness** | 0.42 | Short vowels (AE, AH), consonant-heavy |
| **depth** | 0.55 | Velar K, nasal M provide some depth |
| **connectivity** | 0.38 | One nasal, one liquid (moderate) |

**Structural Profile Summary:**
- **High:** stability (0.72), balance (0.75), force (0.68)
- **Moderate:** initiation (0.65), density (0.57), depth (0.55), flow (0.52)
- **Low:** duration (0.45), complexity (0.45), openness (0.42), connectivity (0.38)

### 8.4 Layer 4: Domain Projection

#### Domain 1: Justice / Law Enforcement (HIGH MATCH)

| Dimension | Actual | Ideal | Match | Weight | Contribution |
|-----------|--------|-------|-------|--------|--------------|
| stability | 0.72 | 0.80 | 0.92 | 0.15 | 0.138 |
| balance | 0.75 | 0.70 | 0.95 | 0.15 | 0.143 |
| force | 0.68 | 0.70 | 0.98 | 0.12 | 0.118 |
| termination | 0.48 | 0.70 | 0.78 | 0.12 | 0.094 |
| depth | 0.55 | 0.60 | 0.95 | 0.10 | 0.095 |
| ... | ... | ... | ... | ... | ... |

**Total Score: 0.71** → STRONG compatibility
**Reasoning:** High stability + balance + force aligns with judicial authority requirements. The balanced CVC structure suggests measured, consistent presence.

#### Domain 2: Counseling / Emotional Care (LOW MATCH)

| Dimension | Actual | Ideal | Match | Weight | Contribution |
|-----------|--------|-------|-------|--------|--------------|
| connectivity | 0.38 | 0.90 | 0.48 | 0.16 | 0.077 |
| openness | 0.42 | 0.80 | 0.62 | 0.14 | 0.087 |
| flow | 0.52 | 0.80 | 0.72 | 0.13 | 0.094 |
| force | 0.68 | 0.30 | 0.62 | 0.03 | 0.019 |
| ... | ... | ... | ... | ... | ... |

**Total Score: 0.52** → WEAK compatibility
**Reasoning:** High force and low connectivity/openness conflict with counseling's requirements for receptive, non-directive presence. The plosive-heavy structure suggests assertion rather than reception.

#### Domain 3: Golf (HIGH MATCH)

| Dimension | Actual | Ideal | Match | Weight | Contribution |
|-----------|--------|-------|-------|--------|--------------|
| stability | 0.72 | 0.90 | 0.82 | 0.18 | 0.148 |
| balance | 0.75 | 0.90 | 0.85 | 0.16 | 0.136 |
| flow | 0.52 | 0.70 | 0.82 | 0.12 | 0.098 |
| depth | 0.55 | 0.70 | 0.85 | 0.11 | 0.094 |
| ... | ... | ... | ... | ... | ... |

**Total Score: 0.69** → STRONG compatibility
**Reasoning:** High stability and balance align with golf's requirements for consistent, measured execution. Moderate flow supports smooth swing mechanics.

### 8.5 Final Explanation

```
INPUT: "Campbell"
PHONEMES: K AE M P B AH L

STRUCTURAL PROFILE:
- High: stability (0.72), balance (0.75), force (0.68)
- Low: connectivity (0.38), openness (0.42)

DOMAIN COMPATIBILITY:
✅ Justice/Law: 0.71 (STRONG) - Stability + balance + force align
✅ Golf: 0.69 (STRONG) - Stability + balance for consistent execution
✅ Strategic Leadership: 0.65 (MODERATE) - Force + depth present
⚠️ Performing Arts: 0.58 (PARTIAL) - Limited openness restricts
❌ Counseling: 0.52 (WEAK) - Low connectivity, high force conflict

TRACE:
- K (initial plosive) → high force, strong initiation
- AE-AH (short vowels) → lower duration/openness
- M (nasal) → some connectivity
- P-B (plosive cluster) → interrupted flow
- L (final liquid) → soft termination, some flow

CAVEATS:
- Analysis based solely on phonetic structure
- Does not predict individual capability
- Cultural and personal factors not considered
```

---

## 9. Failure Modes & Limitations

### 9.1 Known Failure Cases

| Case | Description | Handling |
|------|-------------|----------|
| **Ambiguous pronunciation** | Names with multiple valid pronunciations (e.g., "Jean" - English vs French) | Return results for each pronunciation variant with confidence intervals |
| **Non-phonetic scripts** | Logographic systems (Chinese characters) where phonetics ≠ meaning | Flag as "phonetic-only analysis" with explicit limitation |
| **Very short inputs** | Single phoneme or letter | Flag as "insufficient signal" - refuse to project |
| **Transliteration variance** | Same name spelled differently (Rakesh vs Rakesh vs राकेश) | Normalize to canonical phoneme sequence before analysis |
| **Cultural naming patterns** | Names with embedded cultural meaning not in sound structure | Explicit disclaimer that cultural semantics not captured |

### 9.2 What Cannot Be Inferred

The system MUST NOT claim to infer:

1. **Individual capability** - Structure does not determine skill
2. **Personality traits** - No valid mapping from phonemes to personality
3. **Future outcomes** - This is not prediction
4. **Innate qualities** - Names are assigned, not chosen
5. **Cultural fit** - Cultural meaning is not phonetically encoded
6. **Relationship compatibility** - Beyond scope
7. **Health, wealth, or fortune** - No valid signal

### 9.3 Ambiguity Handling

```python
@dataclass(frozen=True)
class AmbiguityReport:
    """Report ambiguous cases."""
    type: str  # "pronunciation", "transliteration", "insufficient_signal"
    description: str
    variants: Tuple[str, ...]  # Alternative interpretations
    confidence_impact: float  # How much uncertainty this adds
```

When ambiguity is detected:
1. Flag the ambiguity type
2. Generate results for all variants
3. Lower confidence bounds
4. Include explicit uncertainty in explanation

### 9.4 Preventing False Authority

**Mandatory disclaimers** (always included):

```python
MANDATORY_DISCLAIMERS = (
    "This system analyzes phonetic structure only. It does not assess "
    "personality, capability, or destiny.",

    "Domain compatibility scores reflect structural pattern matching, "
    "not fitness for any actual role or activity.",

    "Names are cultural artifacts. This analysis ignores cultural "
    "meaning, family history, and personal significance.",

    "Individual success in any domain depends on skills, effort, "
    "opportunity, and countless factors not present in a name.",

    "This is a deterministic projection system, not an oracle. "
    "Results should be treated as structural curiosity, not guidance.",
)
```

---

## 10. Implementation Considerations

### 10.1 Integration with Existing Symbolu Infrastructure

The Name Resonance System can leverage:

1. **Existing phoneme infrastructure** (`symbolu/resonance/`)
   - ARPABET mapping
   - Varṇa bridge for Sanskrit
   - 10D ontological layer system

2. **Existing types** (`symbolu/resonance/types.py`)
   - Extend `WordVector` for name-specific features
   - Reuse `PhonemeProfile` and `PhonemeCategory`

3. **Existing formulas** (`symbolu/formulas/`)
   - Potential integration with identity_resonance_memory
   - Guna-kosha resonance for deeper Sanskrit-based analysis

### 10.2 New Components Required

```
symbolu/
├── name_resonance/
│   ├── __init__.py
│   ├── types.py           # NormalizedInput, ExtractedSignals, StructuralProfile
│   ├── normalizer.py      # Layer 1: Input normalization
│   ├── extractor.py       # Layer 2: Signal extraction
│   ├── projector.py       # Layer 3: Abstract space projection
│   ├── domains/
│   │   ├── __init__.py
│   │   ├── base.py        # DomainPattern base class
│   │   ├── careers.py     # Career domain patterns
│   │   ├── sports.py      # Sports domain patterns
│   │   └── roles.py       # General role patterns
│   ├── matcher.py         # Layer 4: Domain matching
│   ├── explainer.py       # Layer 5: Explanation generation
│   └── api.py             # Public interface
```

### 10.3 Determinism Guarantees

All components MUST:
1. Use immutable data structures (frozen dataclasses, tuples)
2. Avoid randomness (no random.*, no sampling)
3. Sort collections before iteration (dict ordering)
4. Use explicit rounding for floating-point operations
5. Document any non-deterministic dependencies (e.g., CMU dict versions)

---

## 11. Testing Strategy

### 11.1 Determinism Tests

```python
def test_determinism():
    """Same input must produce identical output across runs."""
    input_name = "Campbell"

    result_1 = analyze_name(input_name)
    result_2 = analyze_name(input_name)

    assert result_1 == result_2
```

### 11.2 Traceability Tests

```python
def test_traceability():
    """Every output dimension must trace to specific input signals."""
    result = analyze_name("Campbell")

    for dimension, value in result.profile.items():
        contributions = result.trace.get_contributions(dimension)
        assert len(contributions) > 0
        assert abs(sum(c.weight * c.signal_value for c in contributions) - value) < 0.01
```

### 11.3 Caveat Tests

```python
def test_caveats_always_present():
    """All results must include mandatory caveats."""
    result = analyze_name("Campbell")

    for caveat in MANDATORY_DISCLAIMERS:
        assert caveat in result.explanation.caveats
```

---

## 12. Ethical Considerations

### 12.1 Intended Use

- **Curiosity exploration**: Understanding structural patterns in names
- **Creative applications**: Character naming, brand naming analysis
- **Educational**: Demonstrating deterministic reasoning systems
- **Research**: Phonetic pattern analysis

### 12.2 Explicitly Prohibited Uses

- Hiring/employment decisions
- Loan/credit decisions
- Educational placement
- Relationship matching services
- Any consequential life decisions

### 12.3 Technical Safeguards

```python
class NameResonanceAPI:
    def analyze(self, name: str, *, purpose: str) -> NameResonanceResult:
        """
        Analyze a name's structural resonance.

        Args:
            name: The name to analyze
            purpose: Why this analysis is being requested
                     (must be non-empty, logged for audit)

        Returns:
            NameResonanceResult with full explanation and caveats
        """
        if purpose.strip() == "":
            raise ValueError("Purpose must be specified for audit trail")

        # Log purpose for monitoring misuse patterns
        self._log_usage(name, purpose)

        result = self._analyze(name)

        # Always include caveats
        result = result.with_caveats(MANDATORY_DISCLAIMERS)

        return result
```

---

## 13. Summary

The Name Resonance System is a five-layer deterministic engine that:

1. **Normalizes** input to canonical form
2. **Extracts** mechanical phonetic/rhythmic signals
3. **Projects** signals to 12-dimensional abstract structural space
4. **Matches** structure against domain-specific patterns
5. **Explains** every output with full traceability

**Key properties:**
- Deterministic: Same input → same output
- Explainable: Full trace from input to output
- Honest: Explicit limitations and caveats
- Structural: Domains as patterns, not labels

**This system explicitly avoids:**
- Personality claims
- Predictive assertions
- Capability assessments
- Cultural meaning inference
- Any claims requiring validation beyond phonetic structure

---

*Document version: 1.0*
*Last updated: 2025-12-21*
