# Symbol-U Architecture Overview

**Version:** Extracted from codebase December 2025
**Status:** Authoritative extraction — not inferred

---

## 1. Executive Summary

Symbol-U is a **deterministic cognitive constraint system** that governs how responses are generated through a multi-phase pipeline. It is NOT an LLM, NOT a search engine, and NOT a generative system. It is a **governance and routing architecture** that:

1. Establishes authority through governance phases (PO1–PO5, P6)
2. Routes queries through consciousness-aware layers (MLCR, TTOR)
3. Fuses reasoning channels (OLM, LCM, LAM, MoE) via 5+5 ontological layers
4. Adapts delivery (DHA) and persona styling
5. Enforces acoustic isolation (sound cannot influence meaning)
6. Maintains determinism (same inputs → same outputs, no LLM calls)

The architecture enforces **unidirectional authority flow** where governance phases constrain but never consume downstream outputs.

---

## 2. Repository Structure Overview

```
symbolu/
├── core/                    # Core coherence, consciousness, constants
│   ├── coherence/          # Coherence engine and state tracking
│   ├── consciousness/      # Unified consciousness formula (UCF)
│   ├── counterfactual/     # P25 sandbox (observer-only)
│   ├── predictive/         # Predictive persona drift, identity memory
│   └── constants.py        # Canonical Kosha/Vritti mappings
├── formulas/               # Core/Substrate utilities (ZERO authority)
│   ├── acoustic_unit_mapper.py
│   ├── resonance_formulas.py
│   ├── vritti_mapper.py
│   └── [40+ formula modules]
├── mechanical/             # Pipeline engines
│   ├── pipeline/           # Phase implementations (PO1–P49)
│   │   ├── grounding/      # PO1 (Phase Minus One)
│   │   ├── phase_zero/     # PO2
│   │   ├── phase_one/      # PO3
│   │   ├── phase_po4/      # PO4
│   │   ├── phase_po5/      # PO5
│   │   ├── phase_p6/       # P6 Regime Selection
│   │   ├── p7_discourse/   # P7 Discourse Act
│   │   ├── p8_semantics/   # P8 Semantic Slots
│   │   ├── p9_lexical/     # P9 Lexical Selection
│   │   ├── p10_acoustic/   # P10 Acoustic Parameters
│   │   ├── p11_prosodic/   # P11 Prosodic Evidence
│   │   ├── p12_consistency/# P12 Consistency Check
│   │   ├── p13_acoustic_safety/ # P13 Acoustic Safety Envelope
│   │   ├── p14_surface/    # P14 Surface Realization
│   │   ├── p15_interaction/# P15 Interaction
│   │   ├── p16–p49/        # Extended phases
│   │   └── ttor/           # Two-Tier Ontology Router
│   ├── mlcr/               # Multi-Layer Consciousness RAG
│   ├── fusion/             # Fusion Engine (OLM/LCM/LAM/MoE)
│   ├── dha/                # Delivery Harmonization & Adaptation
│   ├── persona/            # Persona Engine
│   └── renderer/           # Output renderers
├── rag/                    # RAG subsystem
├── policy/                 # Domain profiles, trading guardrails
├── api/                    # Unified API layer
└── tools/                  # Dashboards, simulators
```

---

## 3. Phase Model Overview (PO1–P55)

### 3.1 Governance Phases (PO1–PO5) — HIGH AUTHORITY

These are **pre-acoustic governance layers** that establish constraints before any symbolic processing.

| Phase | Name | Purpose | Authority |
|-------|------|---------|-----------|
| **PO1** | Observer-Observed Grounding | WHO is being observed (SELF/OTHER/PHENOMENON), HOW (REFLEXIVE/RELATIONAL/DETACHED) | HIGH |
| **PO2** | Intent & Response Posture | Classifies intent (CLARIFY/SUPPORT/REFLECT/INFORM/ABSTAIN), determines response posture | HIGH |
| **PO3** | Allowed Action Contract | Produces strict `AllowedActionSet` bounding what planner may propose | HIGH |
| **PO4** | Planner Proposal Envelope | Captures and validates planner proposals against PO3 | HIGH |
| **PO5** | Execution Eligibility Gate | Determines if execution is conceptually permitted (NO executor exists) | HIGH |

**Key Constraint:** Authority flows **downward only**. PO phases cannot be overridden by downstream phases.

### 3.2 Regime & Language Phases (P6–P9) — HIGH AUTHORITY

| Phase | Name | Purpose | Authority |
|-------|------|---------|-----------|
| **P6** | Regime Selection | Selects operational regime (STABILIZE/REFLECT/INFORM/CLARIFY/DE_ESCALATE/HOLD) | HIGH |
| **P7** | Discourse Act Resolver | Determines discourse act (QUESTION/REFLECTION/ACKNOWLEDGMENT/EXPLANATION/INSTRUCTION/DEFERRAL) | HIGH |
| **P8** | Semantic Slot Resolution | Resolves which semantic slots are required for discourse act | HIGH |
| **P9** | Lexical Selection | Selects lexical items from curated pools for semantic slots | HIGH |

### 3.3 Acoustic Phases (P10–P13) — MEDIUM AUTHORITY (Constrained)

| Phase | Name | Purpose | Authority |
|-------|------|---------|-----------|
| **P10** | Acoustic Parameterization | Translates lexical selections to acoustic parameters | MEDIUM |
| **P11** | Prosodic Evidence | Captures prosodic evidence frame | MEDIUM |
| **P12** | Consistency Check | Validates consistency between acoustic and semantic layers | MEDIUM |
| **P13** | Acoustic Safety Envelope | **BINDING** safety bounds for acoustic expression | HIGH (Capping) |

**CRITICAL INVARIANT:**
```
Sound must obey meaning.
Meaning must NEVER obey sound.
```

### 3.4 Surface & Delivery Phases (P14–P21) — MEDIUM AUTHORITY

| Phase | Name | Purpose | Authority |
|-------|------|---------|-----------|
| **P14** | Surface Realization | Produces `SurfacePlan` constraining text formatting | MEDIUM |
| **P15** | Interaction Directive | Interaction control | MEDIUM |
| **P16** | Regression Guard | Guards against regression | MEDIUM |
| **P17** | Semantic Integrity | Measures semantic integrity | OBSERVER |
| **P18** | Temporal Entropy | Measures temporal entropy differential | OBSERVER |
| **P19** | Drift Fusion | Computes drift fusion index | OBSERVER |
| **P20** | Unified Snapshot | Produces unified cognitive snapshot | OBSERVER |
| **P21** | Delivery Mode | Determines delivery channel permissions (TEXT_ONLY/TEXT_AND_VOICE/SUPPRESSED) | HIGH |

### 3.5 Observer Phases (P22–P26) — ZERO AUTHORITY

These phases **observe only** and cannot influence behavior, semantics, routing, or delivery.

| Phase | Name | Purpose | Authority |
|-------|------|---------|-----------|
| **P22** | Acoustic Witness | Observes acoustic alignment (cannot influence meaning) | ZERO |
| **P23** | Alignment Observer | Alignment observation | ZERO |
| **P24** | Projection Observer | Projection metrics | ZERO |
| **P25** | Counterfactual Sandbox | What-if simulations (never recommends actions) | ZERO |
| **P26** | Unified Consciousness Formula (UCF) | Computes consciousness indices (observational only) | ZERO |

### 3.6 Predictive/Scenario Phases (P32–P49) — ZERO AUTHORITY

| Phase | Name | Purpose | Authority |
|-------|------|---------|-----------|
| **P32** | Insight Window | Policy-level insight observation | ZERO |
| **P33** | Schema Adaptive Routing | Schema adaptation snapshot | ZERO |
| **P35** | Predictive Persona Drift | Predicts persona drift (observer-only) | ZERO |
| **P36** | Identity Resonance Memory | Identity trajectory tracking | ZERO |
| **P38** | Temporal Forecast | Temporal coherence forecasting | ZERO |
| **P39** | Multi-Horizon | Multi-horizon prediction | ZERO |
| **P40** | Cross-Horizon Alignment | Cross-horizon resonance alignment | ZERO |
| **P41** | Scenario Regime Mapper | Maps coherence to scenario regimes (observer-only) | ZERO |
| **P42** | Scenario Fusion | Scenario fusion engine | ZERO |
| **P43** | Scenario What-If | What-if scenario analysis | ZERO |
| **P44** | Coherence Scenario Alignment | Coherence-scenario alignment | ZERO |
| **P45** | Multi-Trajectory Stability | Multi-trajectory stability field | ZERO |
| **P46** | Trajectory Convergence | Trajectory field convergence | ZERO |
| **P47** | Unified Trajectory Scenario | Unified trajectory-scenario synthesis | ZERO |
| **P48** | Macro Stability | Macro stability regulator | ZERO |
| **P49** | Temporal Stability Index | Temporal stability measurement | ZERO |

---

## 4. Subsystem Architecture

### 4.1 Core/Formulas (ZERO Authority)

**Purpose:** Stateless, deterministic mathematical formulas for acoustic tokenization, resonance metrics, and observability signals.

**Capabilities:**
- Compute acoustic unit tokenizations
- Calculate SMI, ΔSMI, Tension Corridor, Bhava Gap
- Map consonants to Kosha layers
- Generate immutable snapshots

**Constraints:**
- ZERO governance authority
- Cannot influence regime, discourse, semantics, or routing
- No LLM calls, no randomness
- Output consumed only by observer phases

**Phases Executing:** None (utility layer)

### 4.2 MLCR Engine (Multi-Layer Consciousness RAG)

**Purpose:** Consciousness-aware query routing that determines tier, intent, and expert activation.

**Capabilities:**
- Ontology mass computation (lower/upper tiers)
- Intent classification
- Entropy computation (H_D, H_G, H_K)
- Tier selection (LOWER/UPPER/HYBRID)
- Expert routing with canonical mapper rules

**Constraints:**
- Deterministic routing decisions
- No content generation
- Bounded by PO-phase constraints

**Phases Executing:** Operates between PO phases and Fusion

### 4.3 TTOR (Two-Tier Ontology Router)

**Purpose:** Cognitive bridge between symbolic aspect engine and MLCR/Fusion/DHA engines.

**Capabilities:**
- Computes aspect base scores
- Applies entropy boosts and domain modulation
- Determines FlowMode (OUTER_ONLY/OUTER_PLUS_INNER/INNER_PRIORITY)
- Sets OLM/LCM/LAM activation flags using canonical rules

**Canonical Mapper Rules v2.0 (5+5 Ontological Model):**
```
OLM: (tier != LOWER) AND (entropy_mix > 0.40)
     Maps to 5+5 ontological layers: O1-O5 (Execution), O6-O10 (Governance)
LCM: (tier == LOWER) AND (entropy_mix > 0.50)
LAM: (long_arc_tension > 0.50) OR temporal_patterns_detected
     OR (domain in ["therapy", "identity", "spiritual"] AND entropy_mix > 0.60)
```

**Constraints:**
- Fully deterministic
- Complete audit trail
- Cannot modify upstream decisions

### 4.4 Fusion Engine

**Purpose:** Blends reasoning channels and selects optimal candidate response.

**Capabilities:**
- Score candidates across OLM (ontological WHY), LCM (semantic WHAT), MoE (domain HOW)
- Conflict resolution (deterministic)
- Routing decisions
- Explanation generation

**Channel Weights (Default):**
```
OLM: 0.4 (α - Ontological Layer Mapper via 5+5 model)
LCM: 0.3 (β - Linguistic Coherence)
MoE: 0.3 (γ - Mixture of Experts)
```

**Constraints:**
- Deterministic candidate selection
- Cannot generate new content
- Must respect MLCR tier decisions

### 4.5 DHA Engine (Delivery Harmonization & Adaptation)

**Purpose:** Determines HOW to deliver responses for optimal user reception.

**Capabilities:**
- Readiness analysis
- Resistance detection
- Tone selection (SWEET_RESONANCE/INVERSE_JOLT/SYMBOLIC_METAPHOR)
- Delivery modulation
- Safety filtering

**Constraints:**
- Cannot modify semantic content
- Operates on rendered output only
- Must respect P13 acoustic safety envelope

### 4.6 Persona Engine

**Purpose:** Applies persona styling to responses.

**Capabilities:**
- Persona selection (deterministic)
- Layer ordering
- Text composition (intro + headers + content + outro)

**CRITICAL CONSTRAINT:**
```
PersonaEngine NEVER modifies layer contents.
It only controls ordering, framing, and presentation style.
```

### 4.7 Renderer

**Purpose:** Produces final output surface from upstream decisions.

**Capabilities:**
- Rule-based rendering
- LLM-assisted rendering (optional)
- Mode selection (minimal/standard/enhanced/regulated)

**Constraints:**
- Must respect P13 safety envelope
- Must respect P14 surface plan
- Must respect P21 delivery mode decision

### 4.8 Observability/Coherence Observer

**Purpose:** Non-invasive observation and reporting of coherence metrics.

**Capabilities:**
- Track 50+ coherence metrics
- Generate immutable snapshots
- Support dashboards and diagnostics

**Constraints:**
- Zero modification of core behavior
- Read-only observation
- No influence on routing or delivery

### 4.9 RAG Subsystem

**Purpose:** Retrieval-augmented generation support.

**Components:**
- Embeddings
- Indexing
- Ingestion
- Retrieval
- Stitching
- Vector store

**Constraints:**
- Supports MLCR routing
- Does not make governance decisions

---

## 5. End-to-End Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          GOVERNANCE LAYER                                │
│                     (Authority Established Here)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  UserRequest                                                             │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌────────┐│
│  │   PO1   │───▶│   PO2   │───▶│   PO3   │───▶│   PO4   │───▶│  PO5   ││
│  │Grounding│    │ Intent  │    │ Actions │    │Proposal │    │Eligibil││
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └────────┘│
│                                                                          │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼ (Authority flows down)
┌─────────────────────────────────────────────────────────────────────────┐
│                       REGIME & LANGUAGE LAYER                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐              │
│  │   P6    │───▶│   P7    │───▶│   P8    │───▶│   P9    │              │
│  │ Regime  │    │Discourse│    │Semantic │    │Lexical  │              │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘              │
│                                                                          │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     ACOUSTIC LAYER (Sound ← Meaning)                     │
│                   *** Meaning NEVER obeys Sound ***                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐              │
│  │   P10   │───▶│   P11   │───▶│   P12   │───▶│   P13   │              │
│  │Acoustic │    │Prosodic │    │Consist. │    │Safety   │◄── BINDING   │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘              │
│                                                                          │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      ROUTING & FUSION LAYER                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                             │
│  │  MLCR   │───▶│  TTOR   │───▶│ Fusion  │                             │
│  │ Engine  │    │ Router  │    │ Engine  │                             │
│  └─────────┘    └─────────┘    └─────────┘                             │
│       │              │              │                                    │
│       │         OLM/LCM/LAM        │                                    │
│       │         activation         │                                    │
│                                                                          │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      DELIVERY & SURFACE LAYER                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐              │
│  │   P14   │───▶│   DHA   │───▶│ Persona │───▶│Renderer │              │
│  │ Surface │    │ Engine  │    │ Engine  │    │         │              │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘              │
│                                      │                                   │
│                              P21 Delivery Mode                           │
│                                      │                                   │
│                                      ▼                                   │
│                              RenderedOutput                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

                              ═══════════════
                              OBSERVER LAYER
                           (ZERO Authority - Cannot
                            influence above layers)
                              ═══════════════

┌─────────────────────────────────────────────────────────────────────────┐
│   P17-P19 (Integrity/Entropy/Drift)  ──┐                                │
│   P22-P26 (Acoustic Witness/UCF)       ├──▶ Snapshots/Logs/Dashboards   │
│   P32-P49 (Predictive/Scenario)      ──┘                                │
│                                                                          │
│   ✗ Cannot influence regime                                             │
│   ✗ Cannot influence discourse                                          │
│   ✗ Cannot influence delivery                                           │
│   ✗ Cannot gate or block                                                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Authority & Observer Matrix

| Phase | Authority Level | Influences Behavior? | Influences Semantics? | Influences Delivery? |
|-------|-----------------|---------------------|----------------------|---------------------|
| **PO1** | HIGH | Yes | Yes (via constraints) | Yes |
| **PO2** | HIGH | Yes | Yes (via intent) | Yes |
| **PO3** | HIGH | Yes | No | Yes |
| **PO4** | HIGH | Yes | No | No |
| **PO5** | HIGH | Yes | No | No |
| **P6** | HIGH | Yes | Yes (via regime) | Yes |
| **P7** | HIGH | Yes | Yes (discourse act) | Yes |
| **P8** | HIGH | No | Yes (slot resolution) | No |
| **P9** | HIGH | No | Yes (lexical choice) | No |
| **P10** | MEDIUM | No | No | Yes (acoustic) |
| **P11** | MEDIUM | No | No | Yes (prosodic) |
| **P12** | MEDIUM | No | No | Yes (consistency) |
| **P13** | HIGH (Capping) | No | No | Yes (safety bounds) |
| **P14** | MEDIUM | No | No | Yes (surface) |
| **P21** | HIGH | Yes | No | Yes |
| **P17-P19** | ZERO | No | No | No |
| **P22-P26** | ZERO | No | No | No |
| **P32-P49** | ZERO | No | No | No |

---

## 7. Acoustic & Ontology Integration

### 7.1 Where Acoustic Processing Exists

1. **P10 (Acoustic Parameterization):** Translates lexical to acoustic parameters
2. **P11 (Prosodic Evidence):** Captures prosodic frame
3. **P13 (Acoustic Safety):** Enforces hard bounds on acoustic expression
4. **Core Formulas:** `acoustic_unit_mapper.py`, `vritti_mapper.py`

### 7.2 Where Acoustic Is FORBIDDEN to Influence Meaning

**P10 Schema explicitly states:**
```
CRITICAL ARCHITECTURAL INVARIANT:
    Sound must obey meaning.
    Meaning must never obey sound.
```

**Acoustic data CANNOT:**
- Influence P6 regime selection
- Influence P7 discourse act
- Influence P8 semantic slot resolution
- Influence P9 lexical selection
- Override any governance decision

### 7.3 Observer Phases for Acoustic

| Phase | May Observe | May Influence |
|-------|------------|---------------|
| P22 | Acoustic alignment | NOTHING |
| P23 | Alignment metrics | NOTHING |
| P24 | Projection metrics | NOTHING |

### 7.4 Phases That May NEVER See Acoustic Data

All governance phases (PO1-PO5, P6-P9) and predictive phases (P35-P49) are explicitly forbidden from importing or consuming acoustic data.

---

## 8. Invariants & Architectural Guarantees

### 8.1 Determinism (Enforced by Code)

**Guarantee:** Same inputs → same outputs (bitwise identical)

**Evidence:**
- `determinism_verification.py` runs 50-iteration hash tests
- All formulas are pure functions with no side effects
- No LLM calls in governance phases
- No randomness anywhere in pipeline

### 8.2 Non-Interference (Observer → Authority)

**Guarantee:** Observer phases cannot influence authoritative phases

**Evidence (from P41 schema):**
```python
Phase 41 MUST NOT:
    - Modify PipelineContext state outside its own output
    - Affect gating, routing, discourse, or action
    - Import P6-P14 or P50+
```

### 8.3 Regime Monotonicity

**Guarantee:** Regime may only restrict, never expand capability

**Evidence (from P6 schema):**
```python
HOLD is always safe.
Regime may only restrict, never expand capability.
```

### 8.4 Acoustic Isolation

**Guarantee:** Sound obeys meaning; meaning never obeys sound

**Evidence (from P10 schema):**
```python
CRITICAL ARCHITECTURAL INVARIANT:
    Sound must obey meaning.
    Meaning must never obey sound.
```

### 8.5 Authority Flow Direction

**Guarantee:** Authority flows downward only (PO1 → P6 → P9 → delivery)

**Evidence (from all phase schemas):**
```python
Authority Model:
- Authority flows: PO1 → PO2 → PO3 → PO4 → PO5 → P6 → P7 → ...
- [Phase N] cannot override or expand upstream decisions
```

### 8.6 Binding Safety Envelope

**Guarantee:** P13 acoustic safety envelope is binding on all renderers

**Evidence (from P13 schema):**
```python
P13 is BINDING. Lower phases cannot override it.
Renderers violating P13 are considered unsafe by design.
```

### 8.7 Observer-Only Phases

**Guarantee:** P22-P26 and P32-P49 cannot influence any decisions

**Evidence (from P25, P41 schemas):**
```python
observer_only: Literal[True]  # Cannot be False
```

---

## 9. What This System Is / Is Not

### 9.1 What Symbol-U IS

Based strictly on implementation:

1. **A Cognitive Constraint System:**
   - Governs what can be said, how it can be said, and when
   - Enforces hard bounds on expression
   - Maintains deterministic behavior

2. **A Governance Layer:**
   - PO1-PO5 establish intent, grounding, and allowed actions
   - P6-P7 establish regime and discourse constraints
   - Authority flows unidirectionally

3. **A Routing Architecture:**
   - MLCR routes queries to appropriate consciousness tiers
   - TTOR determines mapper activation
   - Fusion selects from candidate responses

4. **A Delivery Adaptation System:**
   - DHA adapts tone for user readiness
   - Persona applies styling without modifying content
   - P21 controls delivery channel permissions

5. **An Observability Platform:**
   - 50+ coherence metrics tracked
   - Full audit trail for every decision
   - Determinism verification built in

### 9.2 What Symbol-U IS NOT

1. **NOT an LLM:**
   - No language model calls in core pipeline
   - No generative text production in governance phases
   - Optional LLM enhancement is clearly separated and post-governance

2. **NOT a Search Engine:**
   - Does not index or retrieve documents as primary function
   - RAG subsystem is support infrastructure, not core purpose

3. **NOT a Generative System:**
   - Does not create content de novo
   - Selects and constrains from pre-existing candidates
   - All generation (if any) is post-governance and optional

4. **NOT a Prediction System:**
   - Predictive phases (P35-P49) are observer-only
   - Predictions cannot influence behavior
   - System is reactive to current state, not predictive

5. **NOT a Traditional Chatbot:**
   - No free-form response generation
   - All responses constrained by multi-phase governance
   - Acoustic expression bound by safety envelope

---

## 10. Open Questions / Ambiguities

### 10.1 Phase Numbering Gaps

The pipeline has gaps in phase numbering (P27-P31, P34, P37, P50+). It is UNCERTAIN whether these:
- Are reserved for future phases
- Were deprecated/removed
- Never existed

### 10.2 "Phase" Labels in Formulas

The `formulas/README.md` notes that "Phase 1", "Phase 8" labels in formula files are **historical development milestones**, NOT pipeline execution phases. This creates potential confusion but is documented.

### 10.3 Renderer LLM Integration

The renderer supports optional LLM enhancement. It is UNCERTAIN:
- When LLM is invoked vs. rule-based rendering
- What constraints apply to LLM output
- Whether LLM output is subject to P13 safety envelope

### 10.4 Executor Absence

PO5 explicitly states "ELIGIBLE is informational only. No executor exists." It is UNCERTAIN what mechanism would execute actions if the system were extended.

---

*This document was extracted from the codebase—not inferred or designed. All statements are traceable to code, schemas, docstrings, or explicit comments.*
