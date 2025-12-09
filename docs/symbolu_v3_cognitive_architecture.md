# **Symbol-U v3.0 Cognitive Architecture — Master Specification**
**Version:** 3.0
**Status:** Canonical Reference
**Date:** December 2025
**Author:** Rakesh Mohan / Symbol-U AGI Stack

---

# **Table of Contents**

1. [Overview](#1-overview)
2. [Turn-Level Cognitive Layer](#2-turn-level-cognitive-layer)
   - 2.1 [TTOR Router](#21-ttor-router)
   - 2.2 [MLCR Mapper Logic](#22-mlcr-mapper-logic)
   - 2.3 [Mapper Profile Builder](#23-mapper-profile-builder)
   - 2.4 [Fusion Renderer](#24-fusion-renderer)
   - 2.5 [DHA Engine](#25-dha-engine)
   - 2.6 [LLM Enhancement Renderer](#26-llm-enhancement-renderer)
3. [Session-Level Cognitive Layer](#3-session-level-cognitive-layer)
   - 3.1 [Coherence Engine](#31-coherence-engine)
   - 3.2 [Session Memory](#32-session-memory)
   - 3.3 [Session Recap Engine](#33-session-recap-engine)
   - 3.4 [Intent Arc Engine](#34-intent-arc-engine)
   - 3.5 [Identity Signature Engine](#35-identity-signature-engine)
   - 3.6 [Motivation Flow Engine](#36-motivation-flow-engine)
4. [Policy Layer](#4-policy-layer)
5. [DILchat Presentation Layer](#5-dilchat-presentation-layer)
6. [Unified API Layer](#6-unified-api-layer)
7. [API Server Layer](#7-api-server-layer)
8. [Security Layer](#8-security-layer)
9. [Drift & Stability CI Guardrails](#9-drift--stability-ci-guardrails)
10. [Cognitive Pipeline Diagram](#10-cognitive-pipeline-diagram)
11. [Deterministic Guarantees](#11-deterministic-guarantees)
12. [Backward Compatibility](#12-backward-compatibility)
13. [Versioning Strategy](#13-versioning-strategy)
14. [Appendix A: Cognitive Constructs Glossary](#14-appendix-a-cognitive-constructs-glossary)

---

# **1. Overview**

Symbol-U v3.0 introduces a full cognitive architecture combining:

- Deterministic turn-level processing
- Multi-turn interpretive cognition
- Session-level memory and trajectory analysis
- Policy guidance
- Unified API output
- DILchat-ready presentation layer

Core principles:

- Zero-LLM (except optional Enhancement Renderer)
- Deterministic and CI-enforced
- Non-invasive to the pipeline
- Additive, fail-safe layers

---

# **2. Turn-Level Cognitive Layer**

## **2.1 TTOR Router**

Determines the routing plan based on:

- Tier (lower / upper / hybrid)
- Flow mode (outer / mixed / inner)
- Entropy state
- Domain modulation
- Experiential anchors

Outputs a `RoutingPlan` consumed by MLCR.

---

## **2.2 MLCR Mapper Logic**

Activates one or more of the three Mapper families:

- HRM (High-Resolution Mapper)
- LCM (Low-Context Mapper)
- LAM (Long-Arc Mapper)

Canonical switching rules v2.0:

HRM: (tier != LOWER) and (normalized_entropy > 0.40)
LCM: (tier == LOWER) and (normalized_entropy > 0.50)
LAM: (long_arc_tension > 0.50)
or temporal_patterns_detected
or (domain in ["therapy", "identity", "spiritual"]
and normalized_entropy > 0.60)

---

## **2.3 Mapper Profile Builder**

Produces a deterministic `MapperProfile`:

MapperProfile(
resolution_level,  # low | medium | high
arc_mode,          # none | temporal | identity | deep_context
detail_bias,       # float
practical_bias,    # float
reflective_bias    # float
)

This profile influences renderers without altering semantics.

---

## **2.4 Fusion Renderer**

Produces three deterministic layers:

1. Symbolic
2. Practical
3. Mirror-Truth

Modulated by MapperProfile (expression-only, no semantic change).

---

## **2.5 DHA Engine**

Structured introspective analysis. Depth influenced by mappers:

- LCM → shallow
- HRM → detailed
- LAM → long-arc reflective

---

## **2.6 LLM Enhancement Renderer**

Optional component. Adjusts only tone and cadence:

- LCM → concise, concrete
- HRM → structured, analytical
- LAM → reflective, slow

Semantics remain fully preserved.

---

# **3. Session-Level Cognitive Layer**

## **3.1 Coherence Engine**

Computes multi-turn metrics:

- coherence_score
- persona_drift_score
- semantic_stability_score
- mapper_volatility_score
- temporal_arc_score

Uses sliding-window history.

---

## **3.2 Session Memory**

Deterministic event detection:

- breakthrough
- fragmentation
- stabilization
- arc_shift
- mapper_flip

---

## **3.3 Session Recap Engine**

Produces a structured summary:

- overall_state
- net_trajectory
- turning_points
- mapper_journey
- key_patterns
- recommended_style

---

## **3.4 Intent Arc Engine**

Classifies into 8 canonical arcs:

- stabilization_arc
- insight_arc
- identity_arc
- resolution_arc
- dissonance_arc
- avoidance_arc
- expansion_arc
- chaotic_arc

---

## **3.5 Identity Signature Engine**

Classifies session identity trajectory:

- self_anchoring
- self_expansion
- self_fragmentation
- self_suppression
- self_integration
- self_dissonance
- self_discovery
- neutral_identity

---

## **3.6 Motivation Flow Engine**

Determines motivational driver:

- hope_driven
- fear_driven
- avoidance_driven
- expansion_driven
- stabilization_driven
- overcorrection
- assertion_driven
- ambiguous_motivation

Drift-tested with 22 guardrail tests.

---

# **4. Policy Layer**

Uses unified output + session summary to generate:

- needs_grounding
- allow_deep_reflection
- prefer_concrete
- prefer_arc_mode
- stability_status
- recommended_style
- recommended_mapper

Domain profiles:

- trading
- therapy
- identity
- generic

---

# **5. DILchat Presentation Layer**

Generates UI-ready content:

- badges
- hints
- content blocks
- tone shaping (optional LLM layer)

Ensures deterministic and semantic-safe presentation.

---

# **6. Unified API Layer**

Provides a consolidated JSON output structure containing:

- rendered text
- fusion layers
- dha insights
- routing plan
- mapper profile
- entropy metrics
- coherence metrics
- session memory
- recap
- intent arc
- identity signature
- motivation profile
- session policy
- metadata

Public API trims sensitive fields.

---

# **7. API Server Layer**

FastAPI endpoints:

- `/dilchat/analyze`
- `/symbolu/analyze`
- `/session/start`
- `/session/{id}/analyze`
- `/session/{id}/summary`
- `/health`

Includes:

- session store
- dependency fallback
- deterministic pipeline execution

---

# **8. Security Layer**

Optional protections:

- API key authentication
- IP-based sliding window rate limiting

Zero impact on cognitive behavior.

---

# **9. Drift & Stability CI Guardrails**

The CI pipeline enforces stability for:

- TTOR routing
- Mapper activation
- Semantic shape
- Coherence metrics
- Intent arc
- Identity signature
- Motivation flow

Any drift from canonical formulas fails CI.

---

# **10. Cognitive Pipeline Diagram**

Turn Input
↓
Kosha/Vritti Interpreter
↓
Aspect Mapping
↓
Entropy Engines (HD, HG, HK)
↓
Experiential Anchors
↓
TTOR Router
↓
MLCR Mapper Switching (HRM/LCM/LAM)
↓
Mapper Profile Builder
↓
Fusion Renderer → DHA → LLM Renderer
↓
Unified Output
↓
Coherence Engine
↓
Session Memory
↓
Session Recap
↓
Intent Arc Engine
↓
Identity Signature Engine
↓
Motivation Flow Engine
↓
Policy Engine
↓
DILchat Adapter
↓
Final Response

---

# **11. Deterministic Guarantees**

- Zero randomness
- Zero-LLM core
- CI-enforced behavioral locking
- Fully reproducible outputs

---

# **12. Backward Compatibility**

Maintains compatibility with:

- Symbol-U v2.6
- Symbol-U v2.7
- All prior routing/mapping semantics

---

# **13. Versioning Strategy**

- **v3.0:** Full cognitive architecture
- **v3.1:** Visual dashboards, signatures explorer
- **v3.2:** Narrative summarizer (optional LLM)

---

# **14. Appendix A: Cognitive Constructs Glossary**

(Reserved for future expansion.)

---
