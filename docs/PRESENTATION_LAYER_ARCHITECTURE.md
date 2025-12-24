# Symbol-U Presentation Layer Architecture

## Document Version: 1.0.0
## Date: December 2024

---

# Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Module Inventory](#3-module-inventory)
4. [Tier Architecture](#4-tier-architecture)
5. [Canonical Workflows](#5-canonical-workflows)
6. [Governing Policies](#6-governing-policies)
7. [Configuration Reference](#7-configuration-reference)
8. [Feature Matrix](#8-feature-matrix)
9. [Implementation Roadmap](#9-implementation-roadmap)

---

# 1. Executive Summary

The Symbol-U Presentation Layer transforms internal signals into natural language responses. It sits at Layer 4 of the system architecture, consuming outputs from:

- **Ontological Layer** (12D encoding)
- **RAG Layer** (retrieval)
- **Synthesis Layer** (reasoning)
- **STL/Hybrid Layer** (semantic routing)

The presentation layer supports **three tiers** with distinct policies:

| Tier | Use Case | Character |
|------|----------|-----------|
| **Tier 1: Enterprise Search** | Classification, tagging | Strict, auditable, machine-readable |
| **Tier 2: Enterprise Chat** | Professional chat | Professional, transparent, escalatable |
| **Tier 3: Consumer** | General public | Friendly, simple, personalized |

---

# 2. System Overview

## 2.1 Complete Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER QUERY                                      │
│                         "What makes a good leader?"                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: ONTOLOGICAL ENCODING                                               │
│  ═══════════════════════════════════════════════════════════════════════════ │
│  Module: symbolu/ontology/backbone/encoder.py                                │
│                                                                              │
│  Input:  "What makes a good leader?"                                         │
│  Output: 12D Vector [O1_POTENTIAL, O2_IDENTITY, ..., O12_ABSOLVING]         │
│                                                                              │
│  Process:                                                                    │
│  ├─ Phoneme extraction (varna analysis)                                      │
│  ├─ Structural dimension mapping                                             │
│  └─ 12D ontological vector generation                                        │
│                                                                              │
│  12D LAYERS:                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ O1_POTENTIAL   O2_IDENTITY   O3_FORCE      O4_STRUCTURE               │ │
│  │ O5_COGNITION   O6_VOLITION   O7_WITNESS    O8_PURPOSE                 │ │
│  │ O9_WITNESSES   O10_UNIFIED   O11_ABSOLUTES O12_ABSOLVING              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: RAG RETRIEVAL                                                      │
│  ═══════════════════════════════════════════════════════════════════════════ │
│  Module: symbolu/rag/stitching/pipeline.py                                   │
│                                                                              │
│  Functions:                                                                  │
│  ├─ index_corpus(name, path) → index documents                              │
│  ├─ run_rag(query, corpus, top_k) → retrieve candidates                     │
│  └─ run_rag_multi(query, corpora) → multi-corpus retrieval                  │
│                                                                              │
│  Ontological RAG Enhancement:                                                │
│  Module: symbolu/ontology/backbone/rag_integration.py                        │
│  ├─ OntologicalRAGIndex → 12D-aware retrieval                               │
│  ├─ hybrid_retrieve() → combine embedding + structural similarity           │
│  └─ DomainWeights → domain-specific dimension weighting                     │
│                                                                              │
│  Output: List[CandidateEntry] with content, scores, metadata                │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: REASONING SYNTHESIS                                                │
│  ═══════════════════════════════════════════════════════════════════════════ │
│  Module: symbolu/ontology/backbone/reasoning_synthesizer.py                  │
│                                                                              │
│  Input: Problem + List[ExperientialObject]                                   │
│  Output: SynthesisResult                                                     │
│                                                                              │
│  SynthesisResult contains:                                                   │
│  ├─ primary_insight: str          → Main takeaway                           │
│  ├─ supporting_insights: List     → Evidence from sources                   │
│  ├─ cross_domain_connections: List → Patterns across domains                │
│  ├─ recommended_actions: List     → Actionable steps                        │
│  ├─ warnings: List                → Cautions                                │
│  └─ confidence_score: float       → Overall confidence                      │
│                                                                              │
│  Pattern Types Recognized:                                                   │
│  ├─ CAUSAL       → cause-effect relationships                               │
│  ├─ BIFURCATION  → splitting/divergence                                     │
│  ├─ ESCALATION   → intensifying dynamics                                    │
│  ├─ CYCLICAL     → recurring patterns                                       │
│  ├─ TRANSFORMATION → state changes                                          │
│  ├─ CONVERGENCE  → unifying patterns                                        │
│  ├─ THRESHOLD    → tipping points                                           │
│  └─ EQUILIBRIUM  → balanced states                                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4A: STL RICH ROUTING                                                  │
│  ═══════════════════════════════════════════════════════════════════════════ │
│  Module: symbolu/hybrid/rich_routing.py                                      │
│                                                                              │
│  Input: Query string                                                         │
│  Output: RichRoutingReport                                                   │
│                                                                              │
│  RichRoutingReport contains:                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ phase_profile:                                                         │ │
│  │   ├─ dominant_phase: "GENESIS" | "OPERATION" | "RETURN"               │ │
│  │   ├─ phase_concentration: float (0.0-1.0)                             │ │
│  │   └─ phase_distribution: {GENESIS: 0.2, OPERATION: 0.6, RETURN: 0.2} │ │
│  │                                                                        │ │
│  │ semantic_field:                                                        │ │
│  │   ├─ coherence_score: float (0.0-1.0)                                 │ │
│  │   ├─ field_description: str                                           │ │
│  │   └─ dominant_layers: List[str]                                       │ │
│  │                                                                        │ │
│  │ query_mode: FOCUSED | DIFFUSE | CLUSTERED | TRANSITIONAL              │ │
│  │                                                                        │ │
│  │ word_contributions: List[WordContribution]                            │ │
│  │   └─ word, layer, weight, phase                                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  PHASE MAPPING:                                                              │
│  ├─ GENESIS (O1-O4):    Potential → Structure    [Formation]               │
│  ├─ OPERATION (O5-O8):  Cognition → Purpose      [Active engagement]       │
│  └─ RETURN (O9-O12):    Witnesses → Absolving    [Integration]             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4B: SIGNAL BRIDGE                                                     │
│  ═══════════════════════════════════════════════════════════════════════════ │
│  Module: symbolu/presentation/signal_bridge.py                               │
│                                                                              │
│  Input: Query (runs STL internally)                                          │
│  Output: BridgeResult + FluencyGuidance                                      │
│                                                                              │
│  PHASE → DELIVERY MODE MAPPING:                                              │
│  ├─ GENESIS    → ACKNOWLEDGING  (still forming, tentative)                  │
│  ├─ OPERATION  → CONFIDENT      (active engagement, direct)                 │
│  └─ RETURN     → HEDGED         (synthesizing, nuanced)                     │
│                                                                              │
│  COHERENCE → CONFIDENCE MAPPING:                                             │
│  ├─ > 0.8  → HIGH                                                           │
│  ├─ > 0.5  → MEDIUM                                                         │
│  ├─ > 0.2  → LOW                                                            │
│  └─ ≤ 0.2  → UNKNOWN                                                        │
│                                                                              │
│  QUERY MODE → BEHAVIORS MAPPING:                                             │
│  ├─ FOCUSED      → show_reasoning=True                                      │
│  ├─ DIFFUSE      → show_alternatives=True, offer_clarification=True        │
│  ├─ CLUSTERED    → show_alternatives=True                                   │
│  └─ TRANSITIONAL → offer_clarification=True                                 │
│                                                                              │
│  FluencyGuidance output:                                                     │
│  ├─ tone: "exploratory, open" | "direct, engaged" | "reflective"           │
│  ├─ pacing: "slower, more pauses" | "confident, steady" | "measured"       │
│  └─ structure: "single point" | "acknowledge cluster" | "bridge views"     │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4C: PRESENTATION ENGINE                                               │
│  ═══════════════════════════════════════════════════════════════════════════ │
│  Module: symbolu/presentation/engine.py                                      │
│                                                                              │
│  Input: SignalBundle + TierConfig                                            │
│  Output: PresentationDirective                                               │
│                                                                              │
│  RULE EVALUATION (Priority Order):                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ [100] Critical Viparyaya  → viparyaya > threshold                    │   │
│  │ [98]  Unreliable Estimate → bayesian_confidence < 0.5 (v2.7)        │   │
│  │ [95]  Severe Nidrā        → nidra > threshold OR layers < 2         │   │
│  │ [88]  Regressing State    → cognitive state regressing (v2.7)       │   │
│  │ [80]  High Vikalpa        → vikalpa > threshold AND entropy > 0.5   │   │
│  │ [78]  Concept Unstable    → concept_readiness < 0.4 (v2.7)          │   │
│  │ [70]  Elevated Smṛti      → smrti > threshold AND low_motion > 3    │   │
│  │ [68]  Low Utility Streak  → low_utility_streak >= 5 (v2.7)          │   │
│  │ [60]  Moderate Uncertainty→ moderate <= score < confident           │   │
│  │ [55]  Low Confidence      → score < moderate                        │   │
│  │ [50]  High Pramāṇa        → pramana > threshold AND score >= conf   │   │
│  │ [0]   Default             → always true (fallback)                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  PresentationDirective contains:                                             │
│  ├─ delivery_mode: CONFIDENT | HEDGED | ACKNOWLEDGING | CLARIFYING | SILENT│
│  ├─ confidence: HIGH | MEDIUM | LOW | UNKNOWN                               │
│  ├─ behaviors: SuggestedBehaviors                                           │
│  │   ├─ show_reasoning: bool                                                │
│  │   ├─ show_alternatives: bool                                             │
│  │   ├─ offer_clarification: bool                                           │
│  │   ├─ request_repeat: bool                                                │
│  │   └─ escalate_to_human: bool                                             │
│  ├─ explanation: str                                                        │
│  └─ triggered_rule: str                                                     │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4D: RESPONSE RENDERER                                                 │
│  ═══════════════════════════════════════════════════════════════════════════ │
│  Module: symbolu/presentation/response_renderer.py                           │
│                                                                              │
│  Input: PresentationDirective + FluencyGuidance + SynthesisResult           │
│  Output: RenderedResponse (natural language text)                            │
│                                                                              │
│  SECTION COMPOSITION:                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ 1. ACKNOWLEDGMENT    → "Here's what I found:" / "It appears that"   │   │
│  │ 2. HEDGE             → "While I'm less certain here," (if LOW conf) │   │
│  │ 3. MAIN_INSIGHT      → Primary insight from synthesis               │   │
│  │ 4. SUPPORTING_EVIDENCE → "This is supported by: ..."               │   │
│  │ 5. CROSS_DOMAIN      → "Patterns emerge across domains: ..."        │   │
│  │ 6. ACTIONS           → "Here's what to do: 1. 2. 3."               │   │
│  │ 7. CLARIFICATION     → "Would you like me to clarify?"              │   │
│  │ 8. CLOSING           → "Let me know if you want to explore further" │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  TONE ADAPTATION:                                                            │
│  ├─ Tier 1: "[Uncertain]", "[Review recommended]"                           │
│  ├─ Tier 2: "Based on available information...", "Subject to verification" │
│  └─ Tier 3: "I think...", "It seems like...", "Possibly"                   │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4E: QUALITY CHECKS                                                    │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  Resonance Check (signal_bridge.py):                                         │
│  ├─ check_response_resonance(query, response) → (score, explanation)        │
│  ├─ Compares phase alignment between query and response                     │
│  └─ Validates coherence levels are compatible                               │
│                                                                              │
│  Governed Gate (governed_gate.py):                                           │
│  ├─ evaluate_governed(directive) → GateDecision                             │
│  ├─ GateAction: ALLOW | BLOCK | WARN | ESCALATE                            │
│  └─ Enforces tier-specific output policies                                  │
│                                                                              │
│  Acoustic Chain (acoustic_chain.py):                                         │
│  ├─ run_acoustic_chain(text) → AcousticChainResult                         │
│  └─ Ensures phonetic consistency in output                                  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FINAL RESPONSE                                     │
│  "Here's what I found: Effective leadership combines vision with the        │
│   ability to inspire and empower others.                                    │
│                                                                              │
│   This is supported by:                                                      │
│     - Historical leaders succeeded by adapting to their context (history)  │
│     - Emotional intelligence correlates with success (psychology)          │
│                                                                              │
│   Here's what to do:                                                        │
│     1. Develop self-awareness through feedback                              │
│     2. Practice active listening                                            │
│     3. Build trust through consistency"                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 3. Module Inventory

## 3.1 Core Modules

| Module | Path | Purpose |
|--------|------|---------|
| **Ontological Encoder** | `symbolu/ontology/backbone/encoder.py` | Text → 12D vector |
| **RAG Pipeline** | `symbolu/rag/stitching/pipeline.py` | Document retrieval |
| **Ontological RAG** | `symbolu/ontology/backbone/rag_integration.py` | 12D-enhanced retrieval |
| **Reasoning Synthesizer** | `symbolu/ontology/backbone/reasoning_synthesizer.py` | Multi-source synthesis |
| **Rich Routing (STL)** | `symbolu/hybrid/rich_routing.py` | Query phase/coherence analysis |
| **Signal Bridge** | `symbolu/presentation/signal_bridge.py` | STL → Presentation translation |
| **Presentation Engine** | `symbolu/presentation/engine.py` | Rule evaluation |
| **Response Renderer** | `symbolu/presentation/response_renderer.py` | Directive → Text |
| **Unified Pipeline** | `symbolu/presentation/pipeline.py` | End-to-end orchestration |

## 3.2 Supporting Modules

| Module | Path | Purpose |
|--------|------|---------|
| **Config** | `symbolu/presentation/config.py` | Tier configurations |
| **Rules** | `symbolu/presentation/rules.py` | Rule definitions |
| **Types** | `symbolu/presentation/types.py` | Data structures |
| **Signals** | `symbolu/presentation/signals.py` | Signal bundle |
| **Session** | `symbolu/presentation/session.py` | Session state tracking |
| **Governed Gate** | `symbolu/presentation/governed_gate.py` | Output gate |
| **Acoustic Chain** | `symbolu/presentation/acoustic_chain.py` | Phonetic validation |
| **Prosodic Renderer** | `symbolu/presentation/prosodic_renderer.py` | SSML generation |
| **Speech Pipeline** | `symbolu/presentation/speech_pipeline.py` | Speech output |

## 3.3 Bridge Modules

| Module | Path | Purpose |
|--------|------|---------|
| **P6-Lite** | `symbolu/presentation/p6_lite.py` | Delivery → Regime mapping |
| **P7-Lite** | `symbolu/presentation/p7_lite.py` | Delivery → Discourse act mapping |
| **Rich Resonance** | `symbolu/name_resonance/rich_resonance.py` | Name-to-name analysis |

---

# 4. Tier Architecture

## 4.1 Tier 1: Enterprise Search

### Purpose
Classification, tagging, and semantic search where **accuracy is paramount**.

### Characteristics

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 1: ENTERPRISE SEARCH                                                   │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  PERSONALITY: Strict, Auditable, Machine-Readable                           │
│                                                                              │
│  USE CASES:                                                                  │
│  ├─ Document classification                                                  │
│  ├─ Semantic tagging                                                         │
│  ├─ Contract analysis                                                        │
│  ├─ Compliance checking                                                      │
│  └─ Knowledge base indexing                                                  │
│                                                                              │
│  THRESHOLDS (Strictest):                                                     │
│  ├─ viparyaya_critical: 0.2    (most sensitive to misperception)           │
│  ├─ nidra_severe: 0.4          (sensitive to missing info)                 │
│  ├─ vikalpa_high: 0.25         (sensitive to ambiguity)                    │
│  ├─ smrti_elevated: 0.3        (sensitive to staleness)                    │
│  ├─ score_confident: 0.9       (highest bar for confidence)                │
│  ├─ score_moderate: 0.6                                                     │
│  ├─ pramana_high: 0.8          (highest bar for valid cognition)           │
│  └─ low_motion: 0.15                                                        │
│                                                                              │
│  BEHAVIORS:                                                                  │
│  ├─ allow_silent_mode: TRUE    ← Can suppress uncertain results            │
│  ├─ escalate_to_human: TRUE    ← Flags for human review                    │
│  ├─ show_reasoning: FALSE      ← Clean machine-readable output             │
│  └─ include_diagnostics: TRUE  ← Full audit trail                          │
│                                                                              │
│  LANGUAGE:                                                                   │
│  ├─ hedging: "[Uncertain]", "[Low confidence]"                             │
│  ├─ clarifying: "[Ambiguous input]", "[Requires clarification]"            │
│  └─ acknowledging: "[Potential error]", "[Review recommended]"             │
│                                                                              │
│  OUTPUT FORMAT: Structured tags, not conversational                         │
│  EXAMPLE: "[CLASSIFICATION: Legal/Contract] [CONFIDENCE: 0.72] [REVIEW]"   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### RAG Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 1 RAG: RESTRICTED & ISOLATED                                          │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  ACCESS MODEL: Per-tenant isolation                                          │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                       │
│  │  Tenant A    │  │  Tenant B    │  │  Tenant C    │                       │
│  │  Legal Firm  │  │  Hospital    │  │  Bank        │                       │
│  │  ──────────  │  │  ──────────  │  │  ──────────  │                       │
│  │  Corpora:    │  │  Corpora:    │  │  Corpora:    │                       │
│  │  - contracts │  │  - patient   │  │  - accounts  │                       │
│  │  - case_law  │  │  - medical   │  │  - compliance│                       │
│  │  - statutes  │  │  - protocols │  │  - risk      │                       │
│  │              │  │              │  │              │                       │
│  │  BLOCKED:    │  │  BLOCKED:    │  │  BLOCKED:    │                       │
│  │  - public_web│  │  - public_web│  │  - public_web│                       │
│  │  - external  │  │  - external  │  │  - external  │                       │
│  └──────────────┘  └──────────────┘  └──────────────┘                       │
│         │                 │                 │                               │
│         └─────────────────┴─────────────────┘                               │
│                           │                                                  │
│                           ▼                                                  │
│              ┌─────────────────────────┐                                    │
│              │  Shared Ontological     │                                    │
│              │  Engine (read-only)     │                                    │
│              └─────────────────────────┘                                    │
│                                                                              │
│  POLICIES:                                                                   │
│  ├─ require_audit: TRUE         → All queries logged                       │
│  ├─ cross_tenant_access: FALSE  → Strict isolation                         │
│  ├─ external_api_access: FALSE  → No external data                         │
│  └─ retention_policy: 7_years   → Compliance retention                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4.2 Tier 2: Enterprise Chat

### Purpose
Professional conversational interface for **specialized domains** (legal, medical, financial).

### Characteristics

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 2: ENTERPRISE CHAT                                                     │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  PERSONALITY: Professional, Transparent, Accountable                        │
│                                                                              │
│  USE CASES:                                                                  │
│  ├─ Legal research assistant                                                 │
│  ├─ Medical consultation support                                             │
│  ├─ Financial advisory chat                                                  │
│  ├─ HR policy guidance                                                       │
│  └─ Technical support (enterprise)                                           │
│                                                                              │
│  THRESHOLDS (Moderate):                                                      │
│  ├─ viparyaya_critical: 0.3    (balanced sensitivity)                      │
│  ├─ nidra_severe: 0.5                                                       │
│  ├─ vikalpa_high: 0.35                                                      │
│  ├─ smrti_elevated: 0.4                                                     │
│  ├─ score_confident: 0.85      (high but achievable bar)                   │
│  ├─ score_moderate: 0.5                                                     │
│  ├─ pramana_high: 0.75                                                      │
│  └─ low_motion: 0.1                                                         │
│                                                                              │
│  BEHAVIORS:                                                                  │
│  ├─ allow_silent_mode: FALSE   ← Must always respond                       │
│  ├─ escalate_to_human: TRUE    ← Can escalate to specialist                │
│  ├─ show_reasoning: TRUE       ← Transparency by default                   │
│  └─ include_diagnostics: TRUE  ← Audit trail for compliance                │
│                                                                              │
│  LANGUAGE:                                                                   │
│  ├─ hedging: "Based on available information", "Subject to verification"   │
│  ├─ clarifying: "Please confirm the intended meaning"                      │
│  └─ acknowledging: "I may have misunderstood", "There's some uncertainty"  │
│                                                                              │
│  OUTPUT FORMAT: Professional conversational with reasoning                  │
│  EXAMPLE: "Based on available information, the contract clause appears     │
│            to favor Party A. [Reasoning: Sections 3.2 and 5.1 indicate...] │
│            Would you like me to clarify any specific aspect?"              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### RAG Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 2 RAG: CURATED & DEPARTMENTAL                                         │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  ACCESS MODEL: Department-based with shared enterprise resources            │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    ENTERPRISE SHARED CORPUS                          │    │
│  │  ├─ company_policies                                                 │    │
│  │  ├─ product_documentation                                            │    │
│  │  └─ approved_procedures                                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│         ┌────────────────────┼────────────────────┐                         │
│         │                    │                    │                         │
│         ▼                    ▼                    ▼                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                 │
│  │  Legal Dept  │     │  HR Dept     │     │  Finance     │                 │
│  │  ──────────  │     │  ──────────  │     │  ──────────  │                 │
│  │  + case_law  │     │  + benefits  │     │  + budgets   │                 │
│  │  + contracts │     │  + handbook  │     │  + forecasts │                 │
│  │  + precedents│     │  + training  │     │  + reports   │                 │
│  └──────────────┘     └──────────────┘     └──────────────┘                 │
│                                                                              │
│  POLICIES:                                                                   │
│  ├─ require_audit: TRUE            → All queries logged                    │
│  ├─ cross_department_access: LIMITED → With approval                       │
│  ├─ external_api_access: CURATED   → Approved APIs only                    │
│  └─ escalation_routing: TRUE       → Route to human specialists            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4.3 Tier 3: Consumer

### Purpose
General public interface optimized for **user experience and flow**.

### Characteristics

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 3: CONSUMER                                                            │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  PERSONALITY: Friendly, Simple, Personalized                                │
│                                                                              │
│  USE CASES:                                                                  │
│  ├─ General Q&A                                                              │
│  ├─ Learning assistance                                                      │
│  ├─ Creative writing help                                                    │
│  ├─ Personal productivity                                                    │
│  └─ Casual conversation                                                      │
│                                                                              │
│  THRESHOLDS (Most Tolerant):                                                 │
│  ├─ viparyaya_critical: 0.6    (rarely triggers error mode)                │
│  ├─ nidra_severe: 0.8          (tolerant of incomplete info)               │
│  ├─ vikalpa_high: 0.5          (OK with ambiguity)                         │
│  ├─ smrti_elevated: 0.6                                                     │
│  ├─ score_confident: 0.7       (lower bar for confidence)                  │
│  ├─ score_moderate: 0.4                                                     │
│  ├─ pramana_high: 0.6                                                       │
│  └─ low_motion: 0.05                                                        │
│                                                                              │
│  BEHAVIORS:                                                                  │
│  ├─ allow_silent_mode: FALSE   ← Always respond (never suppress)           │
│  ├─ escalate_to_human: FALSE   ← Handle everything internally              │
│  ├─ show_reasoning: FALSE      ← Keep responses simple                     │
│  └─ include_diagnostics: FALSE ← No debug info to users                    │
│                                                                              │
│  LANGUAGE:                                                                   │
│  ├─ hedging: "I think", "It seems like", "Possibly"                        │
│  ├─ clarifying: "Did you mean", "Just to confirm"                          │
│  └─ acknowledging: "I'm not sure, but", "It might be"                      │
│                                                                              │
│  OUTPUT FORMAT: Natural, conversational, concise                            │
│  EXAMPLE: "I think effective leaders combine vision with empathy.          │
│            They inspire others while staying grounded."                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### RAG Configuration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 3 RAG: EXTERNAL + PERSONALIZED                                        │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  ACCESS MODEL: Public corpus + user personalization                         │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    SHARED PUBLIC CORPUS                              │    │
│  │  ├─ general_knowledge (Wikipedia-style)                              │    │
│  │  ├─ common_procedures (how-to guides)                                │    │
│  │  └─ reference_data (facts, figures)                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│         ┌────────────────────┼────────────────────┐                         │
│         │                    │                    │                         │
│         ▼                    ▼                    ▼                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                 │
│  │   User A     │     │   User B     │     │   User C     │                 │
│  │  ──────────  │     │  ──────────  │     │  ──────────  │                 │
│  │  Personal KB:│     │  Personal KB:│     │  Personal KB:│                 │
│  │  - notes     │     │  - recipes   │     │  - research  │                 │
│  │  - bookmarks │     │  - shopping  │     │  - papers    │                 │
│  │              │     │              │     │              │                 │
│  │  APIs:       │     │  APIs:       │     │  APIs:       │                 │
│  │  - weather   │     │  - none      │     │  - arxiv     │                 │
│  │  - calendar  │     │              │     │  - scholar   │                 │
│  │              │     │              │     │              │                 │
│  │  Preferences:│     │  Preferences:│     │  Preferences:│                 │
│  │  coherence:  │     │  coherence:  │     │  coherence:  │                 │
│  │    0.6       │     │    0.8       │     │    0.9       │                 │
│  │  verbosity:  │     │  verbosity:  │     │  verbosity:  │                 │
│  │    concise   │     │    detailed  │     │    technical │                 │
│  └──────────────┘     └──────────────┘     └──────────────┘                 │
│                                                                              │
│  POLICIES:                                                                   │
│  ├─ require_audit: FALSE          → Privacy-first                          │
│  ├─ personal_data_isolation: TRUE → User data never shared                 │
│  ├─ external_api_access: USER_CONTROLLED → User enables APIs               │
│  └─ preference_persistence: TRUE  → Remember user settings                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4.4 Tier Comparison Summary

```
┌─────────────────┬────────────────────┬────────────────────┬────────────────────┐
│                 │  TIER 1: SEARCH    │  TIER 2: CHAT      │  TIER 3: CONSUMER  │
├─────────────────┼────────────────────┼────────────────────┼────────────────────┤
│ Primary Goal    │ Accuracy           │ Accountability     │ User Experience    │
│ Error Handling  │ Suppress uncertain │ Escalate to human  │ Handle gracefully  │
│ Transparency    │ Audit trail only   │ Show reasoning     │ Hide complexity    │
│ RAG Access      │ Restricted/Isolated│ Curated/Department │ Open/Personalized  │
│ Customization   │ Admin only         │ Department admins  │ Per-user settings  │
│ Output Style    │ Machine-readable   │ Professional       │ Conversational     │
│ Silent Mode     │ Allowed            │ Not allowed        │ Not allowed        │
│ Escalation      │ Yes                │ Yes                │ No                 │
└─────────────────┴────────────────────┴────────────────────┴────────────────────┘
```

---

# 5. Canonical Workflows

## 5.1 Tier 1: Classification Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 1 WORKFLOW: Document Classification                                    │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  INPUT: "This agreement hereby grants Party A exclusive rights to..."       │
│                                                                              │
│  STEP 1: ONTOLOGICAL ENCODING                                                │
│  ├─ Extract 12D vector                                                       │
│  ├─ High activation: O4_STRUCTURE, O6_VOLITION, O8_PURPOSE                  │
│  └─ Pattern: Formal agreement language                                       │
│                                                                              │
│  STEP 2: RAG RETRIEVAL (Restricted)                                          │
│  ├─ Corpus: tenant_legal_contracts (only)                                   │
│  ├─ Retrieved: Similar contract templates                                    │
│  └─ Cross-reference: Legal taxonomy                                          │
│                                                                              │
│  STEP 3: STL ROUTING                                                         │
│  ├─ Phase: OPERATION (active, structural)                                   │
│  ├─ Coherence: 0.92 (highly focused)                                        │
│  └─ Query Mode: FOCUSED                                                      │
│                                                                              │
│  STEP 4: SIGNAL EVALUATION                                                   │
│  ├─ score: 0.88 (below 0.9 confident threshold)                             │
│  ├─ pramana: 0.82 (above 0.8 threshold)                                     │
│  └─ viparyaya: 0.08 (below 0.2 threshold) ✓                                 │
│                                                                              │
│  STEP 5: RULE MATCHING                                                       │
│  ├─ [100] Critical Viparyaya: NO (0.08 < 0.2)                               │
│  ├─ [95] Severe Nidrā: NO                                                   │
│  ├─ [60] Moderate Uncertainty: YES (0.88 < 0.9)                             │
│  └─ TRIGGERED: moderate_uncertainty                                          │
│                                                                              │
│  STEP 6: OUTPUT GENERATION                                                   │
│  ├─ delivery_mode: HEDGED                                                    │
│  ├─ confidence: MEDIUM                                                       │
│  └─ include_diagnostics: TRUE                                                │
│                                                                              │
│  OUTPUT:                                                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ {                                                                       │ │
│  │   "classification": "Legal/Contract/Licensing",                        │ │
│  │   "confidence": 0.88,                                                  │ │
│  │   "status": "[Low confidence]",                                        │ │
│  │   "diagnostics": {                                                     │ │
│  │     "triggered_rule": "moderate_uncertainty",                          │ │
│  │     "pramana": 0.82,                                                   │ │
│  │     "coherence": 0.92                                                  │ │
│  │   },                                                                   │ │
│  │   "review_required": true                                              │ │
│  │ }                                                                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 5.2 Tier 2: Professional Chat Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 2 WORKFLOW: Legal Research Assistant                                   │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  INPUT: "What are the precedents for breach of fiduciary duty?"             │
│                                                                              │
│  STEP 1: ONTOLOGICAL ENCODING                                                │
│  ├─ Extract 12D vector                                                       │
│  ├─ High activation: O5_COGNITION, O6_VOLITION, O7_WITNESS                  │
│  └─ Pattern: Analytical legal query                                          │
│                                                                              │
│  STEP 2: RAG RETRIEVAL (Departmental)                                        │
│  ├─ Primary: legal_case_law corpus                                          │
│  ├─ Secondary: enterprise_policies                                           │
│  └─ Retrieved: 5 relevant precedents                                         │
│                                                                              │
│  STEP 3: REASONING SYNTHESIS                                                 │
│  ├─ Pattern detected: CAUSAL (breach → liability)                           │
│  ├─ Cross-domain: Corporate law ↔ Trust law                                 │
│  └─ Primary insight: "Fiduciary duty breaches require proving..."           │
│                                                                              │
│  STEP 4: STL ROUTING                                                         │
│  ├─ Phase: OPERATION (analytical engagement)                                │
│  ├─ Coherence: 0.85                                                          │
│  └─ Query Mode: CLUSTERED (multiple related concepts)                       │
│                                                                              │
│  STEP 5: SIGNAL BRIDGE                                                       │
│  ├─ Phase → CONFIDENT delivery                                              │
│  ├─ Coherence → HIGH confidence                                             │
│  └─ Mode → show_alternatives: TRUE                                          │
│                                                                              │
│  STEP 6: RULE MATCHING                                                       │
│  ├─ score: 0.87 (above 0.85 confident threshold)                            │
│  ├─ pramana: 0.78 (above 0.75 threshold)                                    │
│  └─ TRIGGERED: high_pramana                                                  │
│                                                                              │
│  STEP 7: RESPONSE RENDERING                                                  │
│  ├─ Sections: ACKNOWLEDGMENT + MAIN_INSIGHT + SUPPORTING + ACTIONS         │
│  ├─ Tone: Professional                                                       │
│  └─ Include: Reasoning trail                                                 │
│                                                                              │
│  OUTPUT:                                                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Based on available information, fiduciary duty breach precedents       │ │
│  │ establish three key elements:                                           │ │
│  │                                                                         │ │
│  │ 1. Existence of fiduciary relationship                                  │ │
│  │ 2. Breach of duty of loyalty or care                                    │ │
│  │ 3. Resulting damages to the beneficiary                                 │ │
│  │                                                                         │ │
│  │ Key precedents include:                                                 │ │
│  │ - Smith v. Jones (2018): Established duty of disclosure                │ │
│  │ - Corp v. Director (2020): Defined scope of care                       │ │
│  │                                                                         │ │
│  │ [Reasoning: Analysis based on corporate and trust law corpus.          │ │
│  │  Confidence: 0.87. Sources: 5 case law documents.]                     │ │
│  │                                                                         │ │
│  │ Would you like me to elaborate on any specific precedent?              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 5.3 Tier 3: Consumer Chat Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 3 WORKFLOW: General Q&A                                                │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  INPUT: "What makes a good leader?"                                          │
│                                                                              │
│  USER PREFERENCES:                                                           │
│  ├─ coherence_preference: 0.7                                               │
│  ├─ verbosity: "concise"                                                    │
│  └─ communication_style: "casual"                                           │
│                                                                              │
│  STEP 1: ONTOLOGICAL ENCODING                                                │
│  ├─ Extract 12D vector                                                       │
│  ├─ High activation: O5_COGNITION, O6_VOLITION, O7_WITNESS                  │
│  └─ Pattern: Philosophical/reflective query                                  │
│                                                                              │
│  STEP 2: RAG RETRIEVAL (Public + Personal)                                   │
│  ├─ Public corpus: general_knowledge                                        │
│  ├─ User's personal KB: (none relevant)                                     │
│  └─ Retrieved: Leadership articles, quotes                                   │
│                                                                              │
│  STEP 3: REASONING SYNTHESIS                                                 │
│  ├─ Pattern detected: CONVERGENCE (multiple traits unite)                   │
│  ├─ Cross-domain: Psychology ↔ History                                      │
│  └─ Primary insight: "Effective leadership combines..."                     │
│                                                                              │
│  STEP 4: STL ROUTING                                                         │
│  ├─ Phase: OPERATION (engaged thinking)                                     │
│  ├─ Coherence: 0.78 (above user's 0.7 preference)                           │
│  └─ Query Mode: CLUSTERED                                                    │
│                                                                              │
│  STEP 5: SIGNAL BRIDGE                                                       │
│  ├─ Phase → CONFIDENT delivery                                              │
│  ├─ Coherence → HIGH confidence                                             │
│  └─ Fluency: "direct, engaged, action-oriented"                             │
│                                                                              │
│  STEP 6: RULE MATCHING                                                       │
│  ├─ score: 0.78 (above 0.7 confident threshold for Consumer)               │
│  ├─ pramana: 0.72 (above 0.6 threshold for Consumer)                        │
│  └─ TRIGGERED: high_pramana                                                  │
│                                                                              │
│  STEP 7: RESPONSE RENDERING                                                  │
│  ├─ Sections: ACKNOWLEDGMENT + MAIN_INSIGHT (concise)                       │
│  ├─ Tone: Casual ("I think...")                                             │
│  └─ No reasoning shown (user preference)                                     │
│                                                                              │
│  OUTPUT:                                                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ I think effective leaders combine vision with empathy. They inspire    │ │
│  │ others while staying grounded and adaptable.                           │ │
│  │                                                                         │ │
│  │ The best leaders I've seen in history and research share these traits: │ │
│  │ - Clear communication                                                   │ │
│  │ - Emotional intelligence                                                │ │
│  │ - Willingness to listen and learn                                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 6. Governing Policies

## 6.1 Policy Categories

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  POLICY CATEGORIES                                                           │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  1. ACCESS POLICIES        → Who can access what data                       │
│  2. QUALITY POLICIES       → Minimum thresholds for output                  │
│  3. PRIVACY POLICIES       → Data handling and retention                    │
│  4. ESCALATION POLICIES    → When to involve humans                         │
│  5. CUSTOMIZATION POLICIES → What users can configure                       │
│  6. AUDIT POLICIES         → Logging and compliance                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 6.2 Tier 1 Policies (Enterprise Search)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 1 GOVERNING POLICIES                                                   │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  ACCESS POLICIES:                                                            │
│  ├─ [MUST] Tenant isolation enforced at RAG level                           │
│  ├─ [MUST] No cross-tenant data access                                      │
│  ├─ [MUST] Admin approval for corpus additions                              │
│  ├─ [OPTIONAL] IP-based access restrictions                                 │
│  └─ [OPTIONAL] Time-based access windows                                    │
│                                                                              │
│  QUALITY POLICIES:                                                           │
│  ├─ [MUST] Minimum confidence 0.6 for any output                            │
│  ├─ [MUST] Suppress output below confidence threshold (silent mode)        │
│  ├─ [MUST] Include confidence score in all outputs                          │
│  ├─ [OPTIONAL] Custom confidence thresholds per classification type        │
│  └─ [OPTIONAL] Ensemble validation (multiple model agreement)              │
│                                                                              │
│  PRIVACY POLICIES:                                                           │
│  ├─ [MUST] No PII in classification outputs                                 │
│  ├─ [MUST] Data retention per compliance requirements                       │
│  ├─ [MUST] Encryption at rest and in transit                                │
│  └─ [OPTIONAL] Data anonymization for training                              │
│                                                                              │
│  ESCALATION POLICIES:                                                        │
│  ├─ [MUST] Flag low-confidence results for human review                     │
│  ├─ [MUST] Queue management for review backlog                              │
│  ├─ [OPTIONAL] Auto-escalation rules by document type                       │
│  └─ [OPTIONAL] SLA tracking for review turnaround                           │
│                                                                              │
│  CUSTOMIZATION POLICIES:                                                     │
│  ├─ [MUST] Admin-only threshold configuration                               │
│  ├─ [MUST] Corpus allow/block lists                                         │
│  ├─ [OPTIONAL] Custom classification taxonomies                             │
│  └─ [OPTIONAL] Custom output formats                                        │
│                                                                              │
│  AUDIT POLICIES:                                                             │
│  ├─ [MUST] Log all queries with timestamps                                  │
│  ├─ [MUST] Log all classification decisions with reasoning                  │
│  ├─ [MUST] Immutable audit trail                                            │
│  ├─ [OPTIONAL] Real-time audit dashboard                                    │
│  └─ [OPTIONAL] Anomaly detection on query patterns                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 6.3 Tier 2 Policies (Enterprise Chat)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 2 GOVERNING POLICIES                                                   │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  ACCESS POLICIES:                                                            │
│  ├─ [MUST] Department-based corpus access                                   │
│  ├─ [MUST] Shared enterprise corpus for all departments                     │
│  ├─ [MUST] Role-based access control (RBAC)                                 │
│  ├─ [OPTIONAL] Cross-department access with approval                        │
│  └─ [OPTIONAL] Guest access with limited corpus                             │
│                                                                              │
│  QUALITY POLICIES:                                                           │
│  ├─ [MUST] Always respond (no silent mode)                                  │
│  ├─ [MUST] Show reasoning for transparency                                  │
│  ├─ [MUST] Cite sources when available                                      │
│  ├─ [OPTIONAL] Confidence thresholds per department                        │
│  └─ [OPTIONAL] Response templates by topic                                  │
│                                                                              │
│  PRIVACY POLICIES:                                                           │
│  ├─ [MUST] Session-based conversation isolation                             │
│  ├─ [MUST] No cross-user conversation access                                │
│  ├─ [MUST] Configurable retention periods                                   │
│  └─ [OPTIONAL] User consent for conversation storage                        │
│                                                                              │
│  ESCALATION POLICIES:                                                        │
│  ├─ [MUST] Route to human specialists when uncertain                        │
│  ├─ [MUST] Clear escalation triggers (thresholds)                          │
│  ├─ [MUST] Specialist routing by topic/department                           │
│  ├─ [OPTIONAL] Warm handoff with conversation context                       │
│  └─ [OPTIONAL] Escalation analytics                                         │
│                                                                              │
│  CUSTOMIZATION POLICIES:                                                     │
│  ├─ [MUST] Department admins can configure thresholds                       │
│  ├─ [MUST] Department-specific language preferences                         │
│  ├─ [OPTIONAL] Custom greeting/closing messages                             │
│  └─ [OPTIONAL] Department branding                                          │
│                                                                              │
│  AUDIT POLICIES:                                                             │
│  ├─ [MUST] Log all conversations with metadata                              │
│  ├─ [MUST] Log escalations and resolutions                                  │
│  ├─ [MUST] Compliance reporting capabilities                                │
│  ├─ [OPTIONAL] Sentiment analysis on conversations                          │
│  └─ [OPTIONAL] Quality scoring on responses                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 6.4 Tier 3 Policies (Consumer)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TIER 3 GOVERNING POLICIES                                                   │
│  ═══════════════════════════════════════════════════════════════════════════ │
│                                                                              │
│  ACCESS POLICIES:                                                            │
│  ├─ [MUST] Public corpus available to all users                             │
│  ├─ [MUST] Personal KB isolated per user                                    │
│  ├─ [MUST] User controls external API connections                           │
│  ├─ [OPTIONAL] Premium corpus access (subscription)                         │
│  └─ [OPTIONAL] Community-contributed corpus                                 │
│                                                                              │
│  QUALITY POLICIES:                                                           │
│  ├─ [MUST] Always respond (graceful handling)                               │
│  ├─ [MUST] No technical jargon in responses                                 │
│  ├─ [MUST] Respect user verbosity preferences                               │
│  ├─ [OPTIONAL] User-adjustable quality thresholds                          │
│  └─ [OPTIONAL] A/B testing for response quality                             │
│                                                                              │
│  PRIVACY POLICIES:                                                           │
│  ├─ [MUST] No audit logging by default (privacy-first)                      │
│  ├─ [MUST] User data never shared across users                              │
│  ├─ [MUST] Right to deletion (personal KB)                                  │
│  ├─ [MUST] Clear data usage disclosure                                      │
│  ├─ [OPTIONAL] Opt-in analytics for improvement                             │
│  └─ [OPTIONAL] Data export capability                                       │
│                                                                              │
│  ESCALATION POLICIES:                                                        │
│  ├─ [MUST] No escalation to humans (handle internally)                      │
│  ├─ [MUST] Graceful fallback for edge cases                                 │
│  ├─ [OPTIONAL] User feedback mechanism                                      │
│  └─ [OPTIONAL] Report issue functionality                                   │
│                                                                              │
│  CUSTOMIZATION POLICIES:                                                     │
│  ├─ [MUST] User-adjustable coherence sensitivity                            │
│  ├─ [MUST] User-adjustable verbosity                                        │
│  ├─ [MUST] Communication style preferences                                  │
│  ├─ [OPTIONAL] Theme/personality selection                                  │
│  ├─ [OPTIONAL] Custom response templates                                    │
│  └─ [OPTIONAL] Favorite topics/interests                                    │
│                                                                              │
│  AUDIT POLICIES:                                                             │
│  ├─ [MUST] Aggregate analytics only (no individual tracking)               │
│  ├─ [OPTIONAL] User-visible history                                         │
│  └─ [OPTIONAL] Usage statistics for user                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 7. Configuration Reference

## 7.1 Threshold Configuration

```python
@dataclass
class TierThresholds:
    """Threshold configuration for presentation rules."""

    # Vṛtti thresholds
    viparyaya_critical: float    # Misperception sensitivity
    nidra_severe: float          # Missing info sensitivity
    vikalpa_high: float          # Ambiguity sensitivity
    smrti_elevated: float        # Staleness sensitivity

    # Score thresholds
    score_confident: float       # Bar for CONFIDENT mode
    score_moderate: float        # Bar for HEDGED mode

    # Cognition thresholds
    pramana_high: float          # Valid cognition bar
    low_motion: float            # Repetition detection


# Default values by tier
TIER_1_THRESHOLDS = TierThresholds(
    viparyaya_critical=0.2,
    nidra_severe=0.4,
    vikalpa_high=0.25,
    smrti_elevated=0.3,
    score_confident=0.9,
    score_moderate=0.6,
    pramana_high=0.8,
    low_motion=0.15,
)

TIER_2_THRESHOLDS = TierThresholds(
    viparyaya_critical=0.3,
    nidra_severe=0.5,
    vikalpa_high=0.35,
    smrti_elevated=0.4,
    score_confident=0.85,
    score_moderate=0.5,
    pramana_high=0.75,
    low_motion=0.1,
)

TIER_3_THRESHOLDS = TierThresholds(
    viparyaya_critical=0.6,
    nidra_severe=0.8,
    vikalpa_high=0.5,
    smrti_elevated=0.6,
    score_confident=0.7,
    score_moderate=0.4,
    pramana_high=0.6,
    low_motion=0.05,
)
```

## 7.2 RAG Configuration

```python
@dataclass
class RAGConfig:
    """RAG access configuration."""

    # Corpus access
    allowed_corpora: List[str]
    blocked_corpora: List[str]
    default_corpus: str

    # Retrieval settings
    top_k: int = 5
    min_similarity: float = 0.5
    use_ontological_boost: bool = True

    # Access control
    require_tenant_isolation: bool = False
    allow_cross_department: bool = False
    allow_external_apis: bool = False

    # Audit
    log_queries: bool = True
    log_results: bool = True


# Example configurations
TIER_1_RAG = RAGConfig(
    allowed_corpora=["tenant_specific"],
    blocked_corpora=["public_web", "external"],
    default_corpus="tenant_primary",
    require_tenant_isolation=True,
    allow_cross_department=False,
    allow_external_apis=False,
    log_queries=True,
    log_results=True,
)

TIER_3_RAG = RAGConfig(
    allowed_corpora=["public_knowledge", "user_personal"],
    blocked_corpora=[],
    default_corpus="public_knowledge",
    require_tenant_isolation=False,
    allow_cross_department=True,
    allow_external_apis=True,  # User controlled
    log_queries=False,  # Privacy first
    log_results=False,
)
```

## 7.3 User Preference Configuration (Tier 3)

```python
@dataclass
class UserPreferences:
    """Per-user customization for Consumer tier."""

    # Signal sensitivity
    coherence_preference: float = 0.7      # 0.5 - 0.9
    motion_sensitivity: float = 0.5        # Repetition tolerance
    entropy_tolerance: float = 0.6         # Ambiguity tolerance

    # Communication style
    verbosity: str = "concise"             # concise | detailed | exhaustive
    communication_style: str = "casual"    # casual | formal | technical
    include_reasoning: bool = False        # Show reasoning?

    # RAG preferences
    personal_corpora: List[str] = field(default_factory=list)
    enabled_apis: List[str] = field(default_factory=list)

    # Personalization
    favorite_topics: List[str] = field(default_factory=list)
    language: str = "en"
    timezone: str = "UTC"
```

---

# 8. Feature Matrix

## 8.1 Must-Have Features

```
┌─────────────────────────────────────────┬─────────┬─────────┬─────────┐
│ FEATURE                                  │ TIER 1  │ TIER 2  │ TIER 3  │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ CORE PIPELINE                           │         │         │         │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ Ontological encoding (12D)              │   ✓     │   ✓     │   ✓     │
│ RAG retrieval                           │   ✓     │   ✓     │   ✓     │
│ STL routing analysis                    │   ✓     │   ✓     │   ✓     │
│ Signal bridge                           │   ✓     │   ✓     │   ✓     │
│ Presentation engine (rules)             │   ✓     │   ✓     │   ✓     │
│ Response renderer                       │   ✓     │   ✓     │   ✓     │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ ACCESS CONTROL                          │         │         │         │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ Tenant isolation                        │   ✓     │   -     │   -     │
│ Department-based access                 │   -     │   ✓     │   -     │
│ User data isolation                     │   -     │   -     │   ✓     │
│ Corpus allow/block lists                │   ✓     │   ✓     │   -     │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ OUTPUT CONTROL                          │         │         │         │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ Confidence scoring                      │   ✓     │   ✓     │   ✓     │
│ Silent mode (suppress uncertain)        │   ✓     │   -     │   -     │
│ Always respond                          │   -     │   ✓     │   ✓     │
│ Show reasoning                          │   -     │   ✓     │   -     │
│ Tier-appropriate language               │   ✓     │   ✓     │   ✓     │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ ESCALATION                              │         │         │         │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ Human review flagging                   │   ✓     │   ✓     │   -     │
│ Specialist routing                      │   -     │   ✓     │   -     │
│ Graceful fallback                       │   -     │   -     │   ✓     │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ AUDIT                                   │         │         │         │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ Query logging                           │   ✓     │   ✓     │   -     │
│ Decision logging                        │   ✓     │   ✓     │   -     │
│ Diagnostics in output                   │   ✓     │   ✓     │   -     │
│ Privacy-first (no individual tracking)  │   -     │   -     │   ✓     │
└─────────────────────────────────────────┴─────────┴─────────┴─────────┘
```

## 8.2 Optional Features

```
┌─────────────────────────────────────────┬─────────┬─────────┬─────────┐
│ FEATURE                                  │ TIER 1  │ TIER 2  │ TIER 3  │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ ADVANCED RETRIEVAL                      │         │         │         │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ Ontological RAG boost                   │   ○     │   ○     │   ○     │
│ Cross-domain bridge discovery           │   ○     │   ○     │   ○     │
│ Hybrid retrieval (embedding + 12D)      │   ○     │   ○     │   ○     │
│ External API integration                │   -     │   ○     │   ○     │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ REASONING                               │         │         │         │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ Pattern detection (8 types)             │   ○     │   ○     │   ○     │
│ Cross-domain synthesis                  │   ○     │   ○     │   ○     │
│ Actionable recommendations              │   ○     │   ○     │   ○     │
│ Warning generation                      │   ○     │   ○     │   ○     │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ PERSONALIZATION                         │         │         │         │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ Custom thresholds                       │   ○     │   ○     │   ○     │
│ Custom language templates               │   ○     │   ○     │   ○     │
│ User preference persistence             │   -     │   -     │   ○     │
│ Personal knowledge base                 │   -     │   -     │   ○     │
│ Favorite topics/interests               │   -     │   -     │   ○     │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ QUALITY ASSURANCE                       │         │         │         │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ Resonance checking                      │   ○     │   ○     │   ○     │
│ Acoustic chain validation               │   ○     │   ○     │   ○     │
│ Governed gate                           │   ○     │   ○     │   ○     │
│ V2.7 experimental rules                 │   ○     │   ○     │   ○     │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ OUTPUT FORMATS                          │         │         │         │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ JSON structured output                  │   ○     │   ○     │   -     │
│ SSML speech output                      │   -     │   ○     │   ○     │
│ Markdown formatting                     │   -     │   ○     │   ○     │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ ANALYTICS                               │         │         │         │
├─────────────────────────────────────────┼─────────┼─────────┼─────────┤
│ Real-time audit dashboard               │   ○     │   ○     │   -     │
│ Query pattern analysis                  │   ○     │   ○     │   -     │
│ Classification accuracy tracking        │   ○     │   -     │   -     │
│ Conversation quality scoring            │   -     │   ○     │   -     │
│ Aggregate usage analytics               │   -     │   -     │   ○     │
└─────────────────────────────────────────┴─────────┴─────────┴─────────┘

Legend: ✓ = Must have, ○ = Optional, - = Not applicable
```

---

# 9. Implementation Roadmap

## 9.1 Phase 1: Core Pipeline (Complete)

```
STATUS: ✓ COMPLETE

Modules implemented:
├─ ✓ Ontological encoder (12D)
├─ ✓ RAG pipeline
├─ ✓ Rich routing (STL)
├─ ✓ Signal bridge
├─ ✓ Presentation engine
├─ ✓ Response renderer
└─ ✓ Unified pipeline orchestrator

Tests: 10,614 passing
```

## 9.2 Phase 2: Tier Differentiation (Next)

```
STATUS: ○ PLANNED

Tasks:
├─ [ ] Extended tier configuration schema
│     ├─ [ ] RAGConfig per tier
│     ├─ [ ] UserPreferences for Tier 3
│     └─ [ ] Tenant/Department configs for Tier 1/2
│
├─ [ ] Access control layer
│     ├─ [ ] Tenant isolation enforcement
│     ├─ [ ] Department-based RBAC
│     └─ [ ] User data isolation
│
├─ [ ] Audit logging framework
│     ├─ [ ] Query logging (Tier 1/2)
│     ├─ [ ] Decision logging (Tier 1/2)
│     └─ [ ] Aggregate analytics (Tier 3)
│
└─ [ ] Escalation framework
      ├─ [ ] Human review queue (Tier 1)
      ├─ [ ] Specialist routing (Tier 2)
      └─ [ ] Graceful fallback (Tier 3)
```

## 9.3 Phase 3: Personalization (Future)

```
STATUS: ○ PLANNED

Tasks:
├─ [ ] User preference system
│     ├─ [ ] Preference storage
│     ├─ [ ] Preference UI
│     └─ [ ] Preference application in pipeline
│
├─ [ ] Personal knowledge base
│     ├─ [ ] User corpus management
│     ├─ [ ] Document upload/indexing
│     └─ [ ] Privacy controls
│
└─ [ ] External API integration
      ├─ [ ] API registry
      ├─ [ ] User-controlled connections
      └─ [ ] API result integration
```

## 9.4 Phase 4: Advanced Features (Future)

```
STATUS: ○ PLANNED

Tasks:
├─ [ ] V2.7 experimental rules
├─ [ ] Ontological RAG boost
├─ [ ] Cross-domain synthesis
├─ [ ] Speech output (SSML)
├─ [ ] Real-time dashboards
└─ [ ] A/B testing framework
```

---

# Appendix A: API Reference

## A.1 Main Entry Points

```python
# Quick response (Tier 3 default)
from symbolu.presentation import respond, quick_respond

response = respond("What makes a good leader?")
response = quick_respond("What makes a good leader?")  # Minimal processing

# Full pipeline with details
from symbolu.presentation import process_with_details

result = process_with_details("What makes a good leader?")
print(result.response_text)
print(result.resonance_score)
print(result.fluency_guidance.tone)

# With tier configuration
from symbolu.presentation import (
    PresentationPipeline,
    PipelineConfig,
    ENTERPRISE_SEARCH_CONFIG,
)

config = PipelineConfig(
    use_rag=True,
    rag_corpus="legal_documents",
    check_resonance=True,
)
pipeline = PresentationPipeline(config)
result = pipeline.process("Analyze this contract clause...")
```

## A.2 Tier-Specific Usage

```python
# Tier 1: Enterprise Search
from symbolu.presentation import (
    PresentationEngine,
    ENTERPRISE_SEARCH_CONFIG,
    SignalBundle,
)

engine = PresentationEngine(ENTERPRISE_SEARCH_CONFIG)
directive = engine.compute(signals)

# Tier 2: Enterprise Chat
from symbolu.presentation import ENTERPRISE_CHAT_CONFIG

engine = PresentationEngine(ENTERPRISE_CHAT_CONFIG)
directive = engine.compute(signals)

# Tier 3: Consumer
from symbolu.presentation import CONSUMER_CONFIG

engine = PresentationEngine(CONSUMER_CONFIG)
directive = engine.compute(signals)
```

---

# Appendix B: Glossary

| Term | Definition |
|------|------------|
| **12D Vector** | 12-dimensional ontological encoding (O1-O12) |
| **Coherence** | Measure of semantic focus (0.0-1.0) |
| **Delivery Mode** | Output style: CONFIDENT, HEDGED, ACKNOWLEDGING, CLARIFYING, SILENT |
| **Entropy (H_g)** | Measure of uncertainty/ambiguity |
| **Motion** | Measure of semantic change between turns |
| **Phase** | Query lifecycle stage: GENESIS, OPERATION, RETURN |
| **Pramāṇa** | Valid cognition signal |
| **Query Mode** | Query classification: FOCUSED, DIFFUSE, CLUSTERED, TRANSITIONAL |
| **RAG** | Retrieval-Augmented Generation |
| **STL** | Semantic Transport Layer (routing analysis) |
| **Tier** | System configuration level (1=Search, 2=Chat, 3=Consumer) |
| **Viparyaya** | Misperception signal |
| **Vikalpa** | Ambiguity/multiple interpretation signal |
| **Vṛtti** | Mental modification (5 types in system) |

---

*Document maintained by Symbol-U Team*
*Last updated: December 2024*
