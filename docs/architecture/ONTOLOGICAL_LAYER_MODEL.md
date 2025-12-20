# Symbol-U 5+5 Ontological Layer Model

**Version:** 1.0 (Patent-Aligned)
**Status:** Canonical Architecture Definition

---

## 1. Overview

Symbol-U uses a **10-layer ontological architecture** divided into two groups:
- **Lower 5 (O1-O5):** Execution / Manifestation Layers
- **Upper 5 (O6-O10):** Governance / Coherence Layers

This is a **STRUCTURAL ONTOLOGY**, not a behavioral model.

### 1.1 STE Alignment

The 5+5 Ontological Layer Model operates as a core component within the **Symbolic Transformer Engine (STE)**. The STE is Symbol-U's deterministic processing pipeline that transforms symbolic inputs through constraint-based phases.

Within the STE context:
- **OLM** (Ontological Layer Mapper) computes layer distributions for the STE's constraint satisfaction
- Layer balance (O1-O5 vs O6-O10) informs STE phase routing
- Tension zones trigger STE resolution constraints
- All ontological processing is **deterministic** — same inputs produce bitwise-identical outputs

The 5+5 model provides structural placement information; the STE uses this placement to guide symbol transformation through its phases.

---

## 2. Key Architectural Principles (MANDATORY)

These principles **MUST NOT** be violated:

1. **There is no active/passive mode**
   - The system does not switch between reasoning modes
   - All layers exist and operate simultaneously

2. **There is no controller deciding when layers engage**
   - No executive function or task switcher
   - Behavior emerges from constraint satisfaction

3. **All layers exist simultaneously**
   - Every layer is always present in processing
   - Layer weights describe relative activation, not mode selection

4. **Behavior emerges from ontological placement + constraints**
   - Placement determines processing characteristics
   - Constraints shape output without generating content

5. **Upper layers never generate, only constrain or terminate**
   - O6-O10 are governance layers
   - They enforce coherence and boundaries, not production

6. **The system is deterministic, non-semantic, and non-learning**
   - Same inputs → same outputs
   - No statistical inference
   - No model updates from processing

---

## 3. Canonical 5+5 Ontological Layer Definition

### 3.1 Lower 5 — Execution / Manifestation Layers (O1-O5)

These layers handle symbol dynamics and execution.

| Layer | Name | Description |
|-------|------|-------------|
| **O1** | Action | Immediate execution pressure; raw acts and impulses |
| **O2** | Tagging | Classification and labeling; assigns type without meaning |
| **O3** | Forming | Structural shaping and pattern formation; core compositional layer |
| **O4** | Thinking | Rule-based internal transformation; mechanical manipulation only |
| **O5** | Directing | Trajectory steering and vector control; not purpose or intent |

**Characteristics:**
- Execution-focused
- Concrete operations
- Symbol manipulation
- Pattern construction

### 3.2 Upper 5 — Governance / Coherence Layers (O6-O10)

These layers enforce coherence, alignment, and termination.

| Layer | Name | Description |
|-------|------|-------------|
| **O6** | Reasoning | Logical consistency and admissibility checks; no inference |
| **O7** | Purposing | Constraint alignment toward targets (Phase-7); not semantic "why" |
| **O8** | Meta-Observing | Witness layer; damping, stabilization, distortion exposure |
| **O9** | Unifying | Integration and coherence across structures; contradiction removal |
| **O10** | Absolving | Termination, dissolution, or release; final system boundary |

**Characteristics:**
- Constraint enforcement
- Coherence maintenance
- Boundary management
- Never content generation

---

## 4. Layer Balance and Ontological Placement

### 4.1 Layer Balance Ratio

The **layer balance** describes the ratio between execution and governance activation:

```
layer_balance = execution_sum / (execution_sum + governance_sum)
```

Where:
- `execution_sum` = O1 + O2 + O3 + O4 + O5
- `governance_sum` = O6 + O7 + O8 + O9 + O10

Interpretation:
- **0.0**: Pure governance (O6-O10 dominant)
- **0.5**: Balanced execution and governance
- **1.0**: Pure execution (O1-O5 dominant)

### 4.2 Tier Mapping

| Tier | Typical Layer Balance | Primary Layers |
|------|----------------------|----------------|
| **Lower** | 0.6 - 1.0 | O1-O5 dominant |
| **Upper** | 0.0 - 0.4 | O6-O10 dominant |
| **Hybrid** | 0.4 - 0.6 | Balanced |

---

## 5. Legacy Aspect Mapping

For backward compatibility, legacy aspect names map to ontological layers:

| Legacy Aspect | Ontological Layer |
|---------------|-------------------|
| Execution | O1_action |
| Identity | O2_tagging |
| Form | O3_forming |
| Cognition | O4_thinking |
| Agency | O5_directing |
| Reasoning | O6_reasoning |
| Purpose | O7_purposing |
| Observation | O8_meta_observing |
| Core | O9_unifying |
| Universal | O10_absolving |

**Note:** New code should use O1-O10 nomenclature. Legacy names are deprecated.

---

## 6. Tension Zones

Tension zones are detected when ontological placement creates structural contradictions:

| Tension Zone | Description | Resolution Constraint |
|--------------|-------------|----------------------|
| `execution_governance_gap` | High O1-O5 without O6-O10 constraints | Require governance layer activation |
| `governance_without_grounding` | High O6-O10 without O1-O3 foundation | Require grounding layer activation |
| `action_without_direction` | High O1 without O5 trajectory control | Require O5_directing |
| `purpose_without_coherence` | High O7 without O9 integration | Require O9_unifying |
| `boundary_dissolution_risk` | High O10 with active lower layers | O10 absolving check required |
| `grounding_deficit` | Abstract layers without concrete foundation | Add concrete grounding |

---

## 7. Orthogonal Analyzers (OLM, LCM, LAM)

Symbol-U uses three **orthogonal analyzers** that operate simultaneously and independently:

| Analyzer | Purpose | Operates On |
|----------|---------|-------------|
| **OLM** (Ontological Layer Mapper) | Maps ontological layer distribution (O1-O10) | Structural placement |
| **LCM** (Low-Context Mapper) | Evaluates contextual complexity and routing sufficiency | Query complexity signals |
| **LAM** (Long-Arc Mapper) | Tracks temporal trajectory across conversation turns | Multi-turn patterns |

**Critical distinction:** These are **analyzers**, not modes, agents, or parallel reasoning systems. They:
- Do NOT make decisions
- Do NOT generate content
- Do NOT operate as independent reasoning units

Each analyzer produces a structured map that downstream engines (Fusion, DHA) consume for constraint-informed processing.

### 7.1 Activation Rules

```python
# OLM activation (formerly HRM)
use_olm = (tier != LOWER) AND (entropy_mix > 0.40)

# LCM activation — evaluates contextual complexity and routing sufficiency
# NOTE: LCM does NOT evaluate semantic structure; it measures query complexity
# signals (length, token density, contextual markers) for routing decisions
use_lcm = (tier == LOWER) AND (entropy_mix > 0.50)

# LAM activation — temporal trajectory tracking
use_lam = (long_arc_tension > 0.40) OR explicit_flag
```

### 7.2 OLM Output Structure

```python
OntologicalLayerMap(
    dominant_layers: List[str]       # Highest-weight layers (O1-O10)
    suppressed_layers: List[str]     # Below-threshold layers
    execution_profile: Dict[str, float]  # Normalized O1-O5 weights
    governance_profile: Dict[str, float] # Normalized O6-O10 weights
    anchor_profile: Dict[str, float] # Normalized experiential anchors
    entropy_profile: Dict[str, float]    # H_D, H_G, H_K, mix, regime
    tension_zones: List[str]         # Detected structural tensions
    resolution_constraints: List[str]    # Processing constraints
    tier: str                        # "lower", "upper", "hybrid"
    domain: str                      # Domain classification
    layer_balance: float             # Execution/governance ratio [0, 1]
)
```

---

## 8. Correct vs Incorrect Usage

### 8.1 INCORRECT (HRM-style) — DO NOT USE

```
"The system switches between active and passive reasoning modes..."
"The controller decides when to engage deeper processing..."
"Executive cognition handles complex tasks while background runs simple ones..."
```

### 8.2 CORRECT (Symbol-U Ontological) — USE THIS

```
"Processing is constrained by ontological layer placement. Lower layers (O1-O5)
execute symbol dynamics; upper layers (O6-O10) enforce coherence, alignment,
and termination."

"All layers exist simultaneously. Behavior emerges from layer weight
distribution and constraint satisfaction, not mode switching."

"Upper layers (O6-O10) never generate content. They constrain and govern
execution layer (O1-O5) outputs."
```

---

## 9. Integration with Other Components

### 9.1 TTOR (Two-Tier Ontology Router)

TTOR determines tier and sets OLM activation flags:

```python
# TTOR activation decision
if tier != "LOWER" and entropy_mix > 0.40:
    use_olm = True
```

### 9.2 Fusion Engine

Fusion receives OLM outputs and uses them for candidate scoring:

```python
# Fusion uses layer balance for weighting
if olm_map.layer_balance > 0.7:
    # Execution-dominant: weight concrete candidates higher
elif olm_map.layer_balance < 0.3:
    # Governance-dominant: weight coherent candidates higher
```

### 9.3 DHA Engine

DHA uses resolution constraints for delivery adaptation:

```python
# DHA reads constraints
if "high_entropy_damping" in olm_map.resolution_constraints:
    # Apply stabilization to delivery
```

---

## 10. Phase Mapping

Ontological layers map to Symbol-U phases:

| Layer | Primary Phase Influence |
|-------|------------------------|
| O1_action | PO4, PO5 (Proposal, Eligibility) |
| O2_tagging | P8 (Semantic Slots) |
| O3_forming | P9 (Lexical Selection) |
| O4_thinking | P6 (Regime Selection) |
| O5_directing | P7 (Discourse Act) |
| O6_reasoning | P12 (Consistency Check) |
| O7_purposing | PO3 (Allowed Actions) |
| O8_meta_observing | P22-P26 (Observer Phases) |
| O9_unifying | P20 (Unified Snapshot) |
| O10_absolving | P13 (Acoustic Safety) |

---

## 11. Invariants

### 11.1 Determinism

Same inputs → same outputs (bitwise identical):
```python
olm_map_1 = engine.build_map(olm_input)
olm_map_2 = engine.build_map(olm_input)
assert olm_map_1.to_dict() == olm_map_2.to_dict()
```

### 11.2 Non-Interference

Upper layers cannot generate content:
```python
# O6-O10 can only:
# - Apply constraints
# - Check admissibility
# - Signal termination
# They CANNOT produce new symbolic content
```

### 11.3 Simultaneous Existence

All layers are always present:
```python
# Every layer has a weight, even if zero
# No layer is "turned off"
for layer in ALL_ONTOLOGICAL_LAYERS:
    assert layer in normalized_weights
```

---

*This document defines the canonical 5+5 ontological layer model for Symbol-U.
All implementations must conform to these specifications.*
