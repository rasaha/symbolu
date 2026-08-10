# Symbol-U Integration Flow: End-to-End Query Processing

**Version:** 1.0
**Date:** 2025-12-21
**Status:** Reference Documentation

## Overview

This document describes the complete end-to-end flow of how a user query enters Symbol-U, passes through all phases, and produces a response. It covers:

1. Query ingestion
2. MLCR routing (consciousness-aware classification)
3. RAG retrieval
4. Pipeline phase execution
5. Phenome transformation
6. Response delivery

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER QUERY                                      │
│                     "Why do I feel stuck in my career?"                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR ENTRY POINT                             │
│                         SymbolUPipeline.run(request)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌─────────────────┐      ┌─────────────────────┐      ┌─────────────────┐
│   MLCR Engine   │      │   RAG Retrieval     │      │  Mappers (HRM/  │
│  (Routing)      │      │   (Knowledge)       │      │   LCM/LAM)      │
└─────────────────┘      └─────────────────────┘      └─────────────────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GOVERNANCE PHASES (PO1-PO5)                          │
│            Pre-Governance: Grounding → Intent → Actions → Gates             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DELIVERY ADAPTATION (P27-P31)                        │
│           Persona → Identity → DHA → Continuity → Expression → Envelope     │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHENOME TRANSFORMER                                  │
│                  Fusion → Renderer → Final Surface                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER RESPONSE                                   │
│       "It sounds like you're experiencing a sense of stagnation..."          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Flow: Step by Step

### Step 1: Query Ingestion

**Entry Point:** `SymbolUPipeline.run(request)`

```python
# User submits query
request = UserRequest(
    text="Why do I feel stuck in my career?",
    user_id="user_123",
    metadata={
        "session_id": "sess_456",
        "domain": "career",
        "readiness_score": 0.6,
        "resistance_score": 0.3,
    }
)

# Pipeline processes request
pipeline = SymbolUPipeline()
result = pipeline.run(request)
```

**What Happens:**
- Request is validated (non-empty text, valid metadata)
- `PipelineContext` is created to carry state through all phases
- Processing begins

---

### Step 2: MLCR Routing (Multi-Layer Consciousness RAG)

**Component:** `symbolu/mechanical/mlcr/mlcr_engine.py`

```
Input: "Why do I feel stuck in my career?"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    MLCR Engine                               │
│                                                              │
│  ┌──────────────────┐                                       │
│  │ 1. Ontology Mass │ → Compute layer activations           │
│  │    Computation   │   (ACTING, THINKING, PURPOSING...)    │
│  └──────────────────┘                                       │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                       │
│  │ 2. Intent        │ → WHY (philosophical/existential)     │
│  │    Classification│   Confidence: 0.85                    │
│  └──────────────────┘                                       │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                       │
│  │ 3. Entropy       │ → H_D: 0.6 (domain uncertainty)       │
│  │    Computation   │   H_G: 0.7 (emotional entropy)        │
│  └──────────────────┘   H_K: 0.5 (knowledge entropy)        │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                       │
│  │ 4. Tier          │ → UPPER (philosophical tier)          │
│  │    Selection     │                                       │
│  └──────────────────┘                                       │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                       │
│  │ 5. Expert        │ → ["sage", "coach"] (ranked)          │
│  │    Routing       │                                       │
│  └──────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
Output: MlcrResult {
    tier: "UPPER",
    intent: "WHY",
    entropy: {H_D: 0.6, H_G: 0.7, H_K: 0.5},
    experts: ["sage", "coach"],
    activation_plan: {use_hrm: true, use_lcm: false}
}
```

**Key Outputs:**
- `tier`: UPPER/LOWER/HYBRID - determines reasoning depth
- `intent`: WHY/HOW/WHAT/ACTION - guides response style
- `entropy`: Uncertainty measures for adaptation
- `experts`: Which personas/experts to consult
- `activation_plan`: Which mappers to activate

---

### Step 3: RAG Retrieval (Knowledge Retrieval)

**Component:** `symbolu/rag/retrieval/retriever.py`

```
Query: "Why do I feel stuck in my career?"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    RAG Pipeline                              │
│                                                              │
│  ┌──────────────────┐                                       │
│  │ 1. Query         │ → [0.23, -0.45, 0.12, ...]            │
│  │    Embedding     │   (384-dim vector)                    │
│  └──────────────────┘                                       │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                       │
│  │ 2. Vector        │ → Search corpus: "career_guidance"    │
│  │    Search        │   top_k: 5                            │
│  └──────────────────┘                                       │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────┐                                       │
│  │ 3. Chunk         │ → [                                   │
│  │    Retrieval     │     {text: "Career transitions...",   │
│  └──────────────────┘       score: 0.87},                   │
│                             {text: "Purpose and meaning...",│
│                               score: 0.82},                  │
│                             ...                              │
│                           ]                                  │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
Output: List[ScoredChunk] - Retrieved knowledge for fusion
```

---

### Step 4: Cognitive Mappers (HRM/LCM/LAM)

**Components:**
- `symbolu/mechanical/pipeline/hrm_integration.py`
- `symbolu/mechanical/pipeline/lcm_integration.py`
- `symbolu/mechanical/pipeline/lam_integration.py`

```
Conditional Activation (based on MLCR activation_plan):
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌───────────────┐       ┌───────────────┐
│ HRM (High-Res)│       │ LAM (Long-Arc)│
│ use_hrm=true  │       │ if tension>0.5│
└───────────────┘       └───────────────┘
        │                       │
        ▼                       ▼
Deep cognitive         Temporal/trajectory
mapping for            mapping for long-term
symbolic reasoning     pattern recognition
```

**HRM (High-Resolution Mapper):**
- Activated for complex, philosophical queries
- Produces deep symbolic representation
- Outputs: `hrm_map` with symbolic layers

**LCM (Low-Context Mapper):**
- Activated for simple, factual queries
- Produces minimal structural summary
- Outputs: `lcm_map` with semantic skeleton

**LAM (Long-Arc Mapper):**
- Activated for trajectory/life-pattern queries
- Produces temporal cognitive mapping
- Outputs: `lam_map` with arc analysis

---

### Step 5: Pre-Governance Phases (PO1-PO5)

```
┌─────────────────────────────────────────────────────────────┐
│                 PRE-GOVERNANCE BAND                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ PO1: Observer-Observed Grounding                      │   │
│  │ └── Determines: REFLEXIVE / RELATIONAL / PERFORMATIVE│   │
│  │ └── Sets authority boundaries                         │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ PO2: Intent Envelope                                  │   │
│  │ └── Classifies: QUERY / REQUEST / COMMAND / SHARE    │   │
│  │ └── Wraps user intent for downstream phases          │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ PO3: Allowed Action Set                               │   │
│  │ └── Determines what actions are permissible          │   │
│  │ └── Blocks unsafe/unauthorized actions               │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ PO4: Planner Proposal Validation                      │   │
│  │ └── Validates any planned responses                  │   │
│  │ └── Ensures compliance with constraints              │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ PO5: Execution Eligibility Gate                       │   │
│  │ └── Final gate before execution                      │   │
│  │ └── Blocks if any safety constraint violated         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

### Step 6: Persona Resolution (P27 + P34)

```
┌─────────────────────────────────────────────────────────────┐
│                 PERSONA LAYER                                │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ P27: Persona Selection                                │   │
│  │ └── Input: MLCR explain_log, user context            │   │
│  │ └── Output: persona_id = "sage"                      │   │
│  │ └── Confidence: 0.85                                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ P34: Identity Harmonics (Observer)                    │   │
│  │ └── Computes: CIH, AIH, RIH, IHI                     │   │
│  │ └── identity_harmonics_index: 0.72                   │   │
│  │ └── is_identity_stable: true                         │   │
│  │ └── Authority: OBSERVER (read-only analytics)        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
Output: PersonaContext {
    active_persona_id: "sage",
    persona_config: {
        formality: 0.7,
        warmth: 0.8,
        directness: 0.5,
        metaphor_level: 0.7,
        identity_harmonics_index: 0.72
    }
}
```

---

### Step 7: Fusion (Multi-Channel Blending)

**Component:** `symbolu/mechanical/fusion/fusion/fusion_engine.py`

```
┌─────────────────────────────────────────────────────────────┐
│                    FUSION ENGINE                             │
│                                                              │
│  Inputs:                                                     │
│  ├── HRM candidates (symbolic reasoning)                    │
│  ├── LCM candidates (semantic structure)                    │
│  ├── LAM candidates (temporal patterns)                     │
│  ├── RAG candidates (retrieved knowledge)                   │
│  └── MoE candidates (domain expertise)                      │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Candidate Blending                                    │   │
│  │ └── Weight by tier (UPPER/LOWER/HYBRID)              │   │
│  │ └── Weight by intent (WHY/HOW/WHAT)                  │   │
│  │ └── Weight by entropy (uncertainty)                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  Output: FusionResult {                                      │
│      fused_text: "Feeling stuck often signals..."           │
│      candidate_weights: {hrm: 0.4, rag: 0.35, moe: 0.25}    │
│      trace: {...}                                            │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

### Step 8: DHA (Delivery Harmonization & Adaptation)

**Component:** `symbolu/mechanical/dha/dha_engine.py`

```
┌─────────────────────────────────────────────────────────────┐
│                    DHA ENGINE                                │
│                                                              │
│  Inputs:                                                     │
│  ├── fusion_output (what to say)                            │
│  ├── persona_output (who is speaking)                       │
│  ├── readiness_score: 0.6                                   │
│  └── resistance_score: 0.3                                  │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Readiness/Resistance Analysis                         │   │
│  │ └── User readiness: MEDIUM (0.6)                     │   │
│  │ └── User resistance: LOW (0.3)                       │   │
│  │ └── Delivery profile: SWEET_RESONANCE                │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ P28: DHA Phase (Formal Tracing)                       │   │
│  │ └── tone_profile: SUPPORTIVE                         │   │
│  │ └── safety_status: PASSED                            │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ P37: Adaptive Continuity (Predictive)                 │   │
│  │ └── NCC (Narrative Continuity): 0.75                 │   │
│  │ └── ICC (Identity Continuity): 0.72                  │   │
│  │ └── CSS (Continuity Stability): 0.74                 │   │
│  │ └── continuity_band: HIGH                            │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
Output: DhaDecision {
    guarded_text: "It sounds like you're experiencing...",
    tone_profile: "SWEET_RESONANCE",
    readiness_level: "MEDIUM",
    resistance_flags: {},
    adaptation_notes: {
        continuity_band: "HIGH",
        narrative_continuity: 0.75
    }
}
```

---

### Step 9: Phenome Transformer (Rendering)

**Component:** `symbolu/mechanical/pipeline/renderer_integration.py`

```
┌─────────────────────────────────────────────────────────────┐
│               PHENOME TRANSFORMER / RENDERER                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Fusion Renderer                                       │   │
│  │ └── Symbolic Layer: Deep meaning extraction          │   │
│  │ └── Practical Layer: Actionable guidance             │   │
│  │ └── Mirror-Truth Layer: Reflective insight           │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Varna Hybrid Renderer                                 │   │
│  │ └── Phoneme analysis                                 │   │
│  │ └── Acoustic optimization                            │   │
│  │ └── Prosodic routing                                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ P29: Expression Finalization                          │   │
│  │ └── Final text adjustments                           │   │
│  │ └── Style consistency check                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ P30: Output Verification                              │   │
│  │ └── P12 consistency check (if active)                │   │
│  │ └── P13 safety envelope check                        │   │
│  │ └── Coherence verification                           │   │
│  │ └── Gate: PASS / BLOCK                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ P31: Output Envelope                                  │   │
│  │ └── Final wrapping                                   │   │
│  │ └── Metadata attachment                              │   │
│  │ └── Audit trail                                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
Output: RenderedOutput {
    raw_text: "It sounds like you're experiencing a sense
               of stagnation. This is a common feeling when
               our current path no longer aligns with our
               evolving sense of purpose...",
    mode: "standard",
    meta: {
        persona_id: "sage",
        tone_profile: "SWEET_RESONANCE",
        readiness_level: "MEDIUM",
        continuity_band: "HIGH"
    }
}
```

---

### Step 10: Response Delivery

```
┌─────────────────────────────────────────────────────────────┐
│                    FINAL OUTPUT                              │
│                                                              │
│  RenderedOutput → API Response → User Interface              │
│                                                              │
│  {                                                           │
│    "response": "It sounds like you're experiencing a        │
│                 sense of stagnation. This is a common       │
│                 feeling when our current path no longer     │
│                 aligns with our evolving sense of           │
│                 purpose...",                                 │
│                                                              │
│    "metadata": {                                             │
│      "persona": "sage",                                      │
│      "confidence": 0.85,                                     │
│      "tone": "supportive",                                   │
│      "session_id": "sess_456"                               │
│    }                                                         │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
                    USER RECEIVES
              "It sounds like you're experiencing..."
```

---

## Testing the Integration Flow

### Unit Test Points

| Component | Test Location | What to Test |
|-----------|---------------|--------------|
| MLCR | `tests/unit/mechanical/mlcr/` | Routing decisions |
| RAG | `tests/unit/rag/` | Retrieval accuracy |
| Fusion | `tests/unit/mechanical/fusion/` | Candidate blending |
| DHA | `tests/unit/mechanical/dha/` | Tone adaptation |
| P27-P31 | `tests/unit/mechanical/pipeline/p27-p31/` | Phase outputs |
| P34/P37 | `tests/unit/mechanical/pipeline/p34/p37/` | Observer metrics |

### Integration Test Points

```python
# Example integration test
def test_e2e_query_flow():
    pipeline = SymbolUPipeline()
    request = UserRequest(
        text="Why do I feel stuck in my career?",
        metadata={"domain": "career"}
    )

    result = pipeline.run(request)

    # Verify output exists
    assert result.raw_text is not None
    assert len(result.raw_text) > 0

    # Verify metadata
    assert result.meta.get("persona_id") is not None
    assert result.meta.get("tone_profile") is not None

    # Verify no blocked output
    assert result.raw_text != ""
```

### Observability Points

| Stage | Observable | Location |
|-------|-----------|----------|
| MLCR | `ctx.mlcr.explain_log` | Routing decisions |
| Persona | `ctx.persona.persona_config` | Selected persona |
| P34 | `ctx.p34_identity_harmonics` | Identity metrics |
| DHA | `ctx.dha.adaptation_notes` | Delivery adaptation |
| P37 | `ctx.p37_continuity` | Continuity metrics |
| Render | `ctx.rendered.meta` | Final output metadata |

---

## Summary: The Complete Flow

```
1. USER QUERY
   └── "Why do I feel stuck in my career?"

2. MLCR ROUTING
   └── tier=UPPER, intent=WHY, experts=["sage"]

3. RAG RETRIEVAL
   └── Retrieved 5 relevant knowledge chunks

4. COGNITIVE MAPPERS
   └── HRM activated (deep symbolic mapping)

5. PRE-GOVERNANCE (PO1-PO5)
   └── Grounding=REFLEXIVE, Intent=QUERY, Actions=ALLOWED

6. PERSONA (P27 + P34)
   └── persona=sage, identity_stable=true

7. FUSION
   └── Blended HRM (40%) + RAG (35%) + MoE (25%)

8. DHA (P28 + P37)
   └── tone=SWEET_RESONANCE, continuity=HIGH

9. RENDERER (P29-P31)
   └── Expression → Verification → Envelope

10. USER RESPONSE
    └── "It sounds like you're experiencing..."
```

---

## Layman Use Cases: Real-World Examples

### Use Case 1: The Anxious User

**Scenario:** Someone having a panic attack reaches out.

```
USER: "I can't breathe, everything is falling apart, I don't know what to do"
```

#### Module-by-Module Breakdown:

**1. MLCR (Multi-Layer Consciousness RAG)**
```
┌─────────────────────────────────────────────────────────────┐
│ MLCR Analysis                                                │
├─────────────────────────────────────────────────────────────┤
│ Ontology Mass:                                               │
│   lower_mass: 0.2 (not asking about facts)                  │
│   upper_mass: 0.9 (emotional/existential content)           │
│                                                              │
│ Intent Classification:                                       │
│   intent: SHARE (expressing, not querying)                  │
│   confidence: 0.92                                          │
│                                                              │
│ Entropy Computation:                                         │
│   H_D (domain): 0.3 (clear domain - emotional)              │
│   H_G (emotional): 0.95 (high distress)                     │
│   H_K (knowledge): 0.2 (not knowledge-seeking)              │
│                                                              │
│ Tier Selection: UPPER (philosophical/emotional)              │
│ Expert Routing: ["friendly", "nurturer"]                    │
│                                                              │
│ 🔑 Key Decision: "This is emotional crisis, not info need"  │
└─────────────────────────────────────────────────────────────┘
```

**2. RAG (Retrieval)**
```
┌─────────────────────────────────────────────────────────────┐
│ RAG Retrieval                                                │
├─────────────────────────────────────────────────────────────┤
│ Query embedding: [0.12, -0.45, 0.78, ...]                   │
│ Corpus searched: "crisis_support"                           │
│                                                              │
│ Retrieved chunks:                                            │
│   1. "Grounding techniques for acute anxiety..." (0.89)     │
│   2. "Validating emotional distress..." (0.85)              │
│   3. "De-escalation language patterns..." (0.82)            │
│                                                              │
│ 🔑 Key Decision: "Retrieved calming techniques, not advice" │
└─────────────────────────────────────────────────────────────┘
```

**3. Pre-Governance (PO1-PO5)**
```
┌─────────────────────────────────────────────────────────────┐
│ Pre-Governance Gates                                         │
├─────────────────────────────────────────────────────────────┤
│ PO1 Grounding:                                               │
│   mode: REFLEXIVE (we witness, don't diagnose)              │
│   authority_level: LIMITED (can't treat)                    │
│                                                              │
│ PO2 Intent Envelope:                                         │
│   type: SHARE (emotional expression)                        │
│   action_needed: SUPPORT (not solve)                        │
│                                                              │
│ PO3 Allowed Actions:                                         │
│   ✓ Validate feelings                                       │
│   ✓ Offer grounding                                         │
│   ✗ Give medical advice                                     │
│   ✗ Recommend treatment                                     │
│   ✗ Minimize experience                                     │
│                                                              │
│ PO4 Proposal Validation: GROUNDING_ONLY approved            │
│ PO5 Execution Gate: PASSED                                  │
│                                                              │
│ 🔑 Key Decision: "Support only, no problem-solving"         │
└─────────────────────────────────────────────────────────────┘
```

**4. Persona Layer (P27 + P34)**
```
┌─────────────────────────────────────────────────────────────┐
│ Persona Resolution                                           │
├─────────────────────────────────────────────────────────────┤
│ P27 Selection:                                               │
│   persona_id: "friendly"                                    │
│   selection_reason: "SHARE intent + high emotional entropy" │
│   confidence: 0.88                                          │
│                                                              │
│ Persona Config:                                              │
│   formality: 0.2 (very informal)                            │
│   warmth: 0.95 (maximum warmth)                             │
│   directness: 0.3 (gentle, not blunt)                       │
│   metaphor_level: 0.1 (concrete, not abstract)              │
│                                                              │
│ P34 Identity Harmonics:                                      │
│   CIH (core identity): 0.85                                 │
│   AIH (adaptive identity): 0.72                             │
│   identity_stable: TRUE                                     │
│                                                              │
│ 🔑 Key Decision: "Be warm, present, grounded"               │
└─────────────────────────────────────────────────────────────┘
```

**5. DHA (Delivery Harmonization)**
```
┌─────────────────────────────────────────────────────────────┐
│ DHA Analysis                                                 │
├─────────────────────────────────────────────────────────────┤
│ Readiness Assessment:                                        │
│   readiness_score: 0.2 (LOW - in crisis)                    │
│   readiness_level: NOT_READY                                │
│                                                              │
│ Resistance Assessment:                                       │
│   resistance_score: 0.8 (HIGH - defensive)                  │
│   resistance_type: PROTECTIVE (not oppositional)            │
│                                                              │
│ Delivery Profile Selection:                                  │
│   profile: INVERSE_JOLT                                     │
│   meaning: "Match their energy inversely - they're up,      │
│            we stay down. Calm anchor."                      │
│                                                              │
│ P28 Phase Output:                                            │
│   tone_profile: GROUNDING                                   │
│   safety_status: ACTIVE_CAUTION                             │
│                                                              │
│ P37 Continuity:                                              │
│   NCC: 0.4 (narrative break - crisis)                       │
│   ICC: 0.8 (identity continuous)                            │
│   continuity_band: LOW (expect disruption)                  │
│                                                              │
│ 🔑 Key Decision: "Stay calm anchor, don't escalate"         │
└─────────────────────────────────────────────────────────────┘
```

**6. Fusion**
```
┌─────────────────────────────────────────────────────────────┐
│ Fusion Blending                                              │
├─────────────────────────────────────────────────────────────┤
│ Input Channels:                                              │
│   HRM: Deep symbolic content (weight: 0.2)                  │
│   RAG: Grounding techniques (weight: 0.5)                   │
│   MoE: Crisis support patterns (weight: 0.3)                │
│                                                              │
│ Blend Decision:                                              │
│   Prioritize: Concrete grounding over abstract wisdom       │
│   Suppress: Complex metaphors, advice, solutions            │
│   Include: Sensory anchoring, present-moment focus          │
│                                                              │
│ 🔑 Key Decision: "Simple, sensory, present-tense"           │
└─────────────────────────────────────────────────────────────┘
```

**7. Renderer (P29-P31)**
```
┌─────────────────────────────────────────────────────────────┐
│ Final Rendering                                              │
├─────────────────────────────────────────────────────────────┤
│ P29 Expression Finalization:                                 │
│   - Short sentences (cognitive load is high)                │
│   - Present tense ("you're here" not "you'll be ok")        │
│   - Sensory language ("feel your feet")                     │
│   - No questions requiring complex thought                  │
│                                                              │
│ P30 Verification:                                            │
│   ✓ No certainty language detected                         │
│   ✓ No medical advice detected                             │
│   ✓ No minimizing language detected                        │
│   ✓ Grounding technique appropriate                        │
│   STATUS: PASSED                                            │
│                                                              │
│ P31 Envelope:                                                │
│   response_type: CRISIS_SUPPORT                             │
│   follow_up_suggested: TRUE                                 │
│                                                              │
│ 🔑 Key Decision: "Safe to send - grounding only"            │
└─────────────────────────────────────────────────────────────┘
```

**Final Response:**
```
"I hear you. Right now, just focus on this moment with me.
Can you feel your feet on the ground? That's real. You're here.
Let's take one slow breath together..."
```

**Key Safety Features:**
- No advice-giving (could be harmful)
- No certainty language (we don't diagnose)
- Grounding technique (evidence-based)
- Warm but not overwhelming

---

### Use Case 2: The Career Question

**Scenario:** Someone feeling stuck in their job.

```
USER: "Why do I feel stuck in my career?"
```

#### Module-by-Module Breakdown:

**1. MLCR (Multi-Layer Consciousness RAG)**
```
┌─────────────────────────────────────────────────────────────┐
│ MLCR Analysis                                                │
├─────────────────────────────────────────────────────────────┤
│ Ontology Mass:                                               │
│   lower_mass: 0.4 (some practical elements)                 │
│   upper_mass: 0.8 (meaning-seeking)                         │
│                                                              │
│ Intent Classification:                                       │
│   intent: WHY (seeking understanding)                       │
│   confidence: 0.89                                          │
│                                                              │
│ Entropy Computation:                                         │
│   H_D (domain): 0.5 (career is clear domain)                │
│   H_G (emotional): 0.6 (mild frustration)                   │
│   H_K (knowledge): 0.7 (open to insight)                    │
│                                                              │
│ Tier Selection: UPPER (philosophical/purpose)                │
│ Expert Routing: ["sage", "coach"]                           │
│                                                              │
│ 🔑 Key Decision: "Meaning question, not tactical advice"    │
└─────────────────────────────────────────────────────────────┘
```

**2. RAG (Retrieval)**
```
┌─────────────────────────────────────────────────────────────┐
│ RAG Retrieval                                                │
├─────────────────────────────────────────────────────────────┤
│ Query embedding: [0.34, -0.21, 0.56, ...]                   │
│ Corpus searched: "career_wisdom", "life_transitions"        │
│                                                              │
│ Retrieved chunks:                                            │
│   1. "Stagnation as signal of growth..." (0.87)             │
│   2. "Purpose evolution in careers..." (0.84)               │
│   3. "Identity shifts in professional life..." (0.81)       │
│                                                              │
│ 🔑 Key Decision: "Wisdom content, not job-search tips"      │
└─────────────────────────────────────────────────────────────┘
```

**3. Pre-Governance (PO1-PO5)**
```
┌─────────────────────────────────────────────────────────────┐
│ Pre-Governance Gates                                         │
├─────────────────────────────────────────────────────────────┤
│ PO1 Grounding:                                               │
│   mode: RELATIONAL (mutual exploration)                     │
│   authority_level: ADVISORY                                 │
│                                                              │
│ PO3 Allowed Actions:                                         │
│   ✓ Offer perspective/reframe                              │
│   ✓ Ask reflective questions                               │
│   ✓ Share general wisdom                                   │
│   ✗ Tell them to quit their job                            │
│   ✗ Promise career success                                 │
│                                                              │
│ 🔑 Key Decision: "Reflect and reframe, don't prescribe"     │
└─────────────────────────────────────────────────────────────┘
```

**4. Persona Layer (P27 + P34)**
```
┌─────────────────────────────────────────────────────────────┐
│ Persona Resolution                                           │
├─────────────────────────────────────────────────────────────┤
│ P27 Selection:                                               │
│   persona_id: "sage"                                        │
│   selection_reason: "WHY intent + UPPER tier"               │
│   confidence: 0.85                                          │
│                                                              │
│ Persona Config:                                              │
│   formality: 0.6 (moderate - thoughtful)                    │
│   warmth: 0.7 (caring but not saccharine)                   │
│   directness: 0.5 (balanced)                                │
│   metaphor_level: 0.7 (can use symbolic language)           │
│                                                              │
│ P34 Identity Harmonics:                                      │
│   IHI: 0.72 (good persona fit)                              │
│   identity_stable: TRUE                                     │
│                                                              │
│ 🔑 Key Decision: "Wise mentor voice, reflective tone"       │
└─────────────────────────────────────────────────────────────┘
```

**5. DHA (Delivery Harmonization)**
```
┌─────────────────────────────────────────────────────────────┐
│ DHA Analysis                                                 │
├─────────────────────────────────────────────────────────────┤
│ Readiness Assessment:                                        │
│   readiness_score: 0.6 (MEDIUM - open but uncertain)        │
│                                                              │
│ Resistance Assessment:                                       │
│   resistance_score: 0.3 (LOW - receptive)                   │
│                                                              │
│ Delivery Profile:                                            │
│   profile: SWEET_RESONANCE                                  │
│   meaning: "Gentle insight that lands softly"               │
│                                                              │
│ P37 Continuity:                                              │
│   NCC: 0.75 (coherent narrative)                            │
│   continuity_band: HIGH                                     │
│                                                              │
│ 🔑 Key Decision: "Insightful but not overwhelming"          │
└─────────────────────────────────────────────────────────────┘
```

**6. Fusion + Renderer**
```
┌─────────────────────────────────────────────────────────────┐
│ Fusion & Rendering                                           │
├─────────────────────────────────────────────────────────────┤
│ Blend Weights:                                               │
│   HRM (symbolic): 0.40 (deep meaning)                       │
│   RAG (wisdom): 0.35 (retrieved insights)                   │
│   MoE (coaching): 0.25 (practical framing)                  │
│                                                              │
│ P29 Expression:                                              │
│   - Reframe "stuck" as positive signal                      │
│   - End with reflective question                            │
│   - No "you should" language                                │
│                                                              │
│ P30 Verification: PASSED                                     │
│                                                              │
│ 🔑 Key Decision: "Validate + reframe + invite reflection"   │
└─────────────────────────────────────────────────────────────┘
```

**Final Response:**
```
"Feeling stuck often signals that a part of you has outgrown
your current path. It's not about the job being 'bad'—it's
that the you of today needs something different than the you
who started.

What parts of your work still feel meaningful to you?"
```

**Why This Works:**
- Validates the feeling (not dismissive)
- Reframes "stuck" as growth signal
- Ends with reflective question
- No prescriptive "you should..."

---

### Use Case 3: The Simple Question

**Scenario:** Someone asks a straightforward factual question.

```
USER: "What's the capital of France?"
```

**What Symbol-U Does:**

| Step | What Happens | Layman Explanation |
|------|--------------|-------------------|
| MLCR | Intent = WHAT (factual) | "They just want an answer" |
| MLCR | Tier = LOWER (factual) | "No philosophy needed" |
| MLCR | Entropy = LOW | "Clear, simple question" |
| LCM | Activated (minimal processing) | "Don't overthink this" |
| Persona | Selects "neutral" | "Just be helpful" |
| DHA | Readiness = HIGH | "They're ready for the answer" |
| DHA | Delivery = DIRECT | "Just tell them" |

**Response:**
```
"Paris is the capital of France."
```

**Why This Works:**
- No unnecessary elaboration
- Direct answer to direct question
- Respects user's time

---

### Use Case 4: The Resistant User

**Scenario:** Someone pushes back on advice.

```
USER: "That meditation stuff doesn't work for me. I've tried it."
```

**What Symbol-U Does:**

| Step | What Happens | Layman Explanation |
|------|--------------|-------------------|
| MLCR | Detects resistance pattern | "They're pushing back" |
| DHA | Resistance = HIGH | "Don't force anything" |
| DHA | Readiness = LOW | "They're not open right now" |
| DHA | Delivery = DEFERRAL | "Acknowledge, don't argue" |
| P37 | Continuity = check past interactions | "What worked before?" |

**Response:**
```
"That makes sense—meditation isn't for everyone, and forcing
something that doesn't fit can feel frustrating.

What has worked for you in the past when you've needed to
clear your head?"
```

**Why This Works:**
- Validates their experience
- Doesn't argue or re-recommend
- Redirects to their expertise (what works for THEM)
- Maintains rapport

---

### Use Case 5: The Regulated Domain (Medical)

**Scenario:** Someone asks about medication.

```
USER: "Should I stop taking my antidepressants?"
```

**What Symbol-U Does:**

| Step | What Happens | Layman Explanation |
|------|--------------|-------------------|
| MLCR | Domain = MEDICAL (regulated) | "This needs extra caution" |
| PO1 | Grounding = REFLEXIVE | "We're not their doctor" |
| Persona | Selects "regulator" | "Be careful and boundaried" |
| DHA | Safety flags = ACTIVE | "Don't give medical advice" |
| P30 | Verification = extra strict | "Check this twice" |

**Response:**
```
"That's a really important question, and I want to be honest
with you—I'm not able to advise on medication decisions.
That's something only you and your doctor can work through
together.

If you're having concerns about your medication, reaching out
to your prescriber would be the safest next step.

Is there something specific that's making you consider this?"
```

**Why This Works:**
- Clear boundary (not giving medical advice)
- Redirects to appropriate resource (doctor)
- Opens door for emotional discussion
- Doesn't abandon the user

---

### Use Case 6: The Multi-Turn Conversation

**Scenario:** User has been chatting for a while, then shares something deep.

```
Turn 1: "Hi, how are you?"
Turn 2: "I'm okay, just thinking about stuff"
Turn 3: "Actually... I've been really lonely lately"
```

**What Symbol-U Does at Turn 3:**

| Step | What Happens | Layman Explanation |
|------|--------------|-------------------|
| P37 | NCC = 0.6 (narrative shift) | "Topic just got deeper" |
| P37 | ICC = 0.8 (identity continuous) | "Still the same person/persona" |
| P34 | Identity harmonics check | "Maintain consistent voice" |
| DHA | Readiness increased | "They're opening up now" |
| DHA | Delivery = softer than before | "Match their vulnerability" |

**Response:**
```
"Thank you for sharing that with me. Loneliness can be such
a heavy feeling, especially when it sneaks up on us.

What does the loneliness feel like for you?"
```

**Why This Works:**
- Acknowledges the shift (they opened up)
- Doesn't dismiss or minimize
- Invites deeper exploration
- Maintains warmth from earlier turns

---

## Summary: How Symbol-U Adapts

| User State | Symbol-U Response |
|------------|-------------------|
| **Panicking** | Calm, grounding, no advice |
| **Curious** | Informative, engaging |
| **Resistant** | Validating, redirecting |
| **Vulnerable** | Warm, gentle, inviting |
| **Factual** | Direct, efficient |
| **Medical/Legal** | Boundaried, redirecting |

The system continuously adapts its:
- **Persona** (who speaks)
- **Tone** (how they speak)
- **Content** (what they say)
- **Boundaries** (what they won't say)

...all based on real-time analysis of user state, context, and safety requirements.

---

## Related Documents

- [PHASE_ARCHITECTURE_AUDIT_REPORT.md](./PHASE_ARCHITECTURE_AUDIT_REPORT.md)
- [P10_P11_P12_ACTIVATION_PREREQUISITES.md](./P10_P11_P12_ACTIVATION_PREREQUISITES.md)
- [P34_P37_SPECIFICATION.md](./P34_P37_SPECIFICATION.md)
- [PHASE_STATUS.yaml](../../symbolu/mechanical/pipeline/PHASE_STATUS.yaml)
