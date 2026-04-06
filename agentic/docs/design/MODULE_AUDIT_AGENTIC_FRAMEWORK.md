# Symbolu Module Audit: Unified Agentic Framework Candidacy

**Date:** 2026-04-03
**Scope:** All 51 subdirectories under `symbolu/symbolu/`
**Purpose:** Classify each module's relationship to a unified agentic framework product

---

## Classification System

Each module is assigned one of five categories:

| Category | Meaning |
|---|---|
| **CORE AGENTIC** | Already part of `agentic_framework/` or directly implements agentic governance, safety, or tool mediation |
| **INTEGRATE** | Strong candidate for integration — provides signals, controls, or capabilities the agentic framework should consume or expose |
| **SUPPLY** | Provides infrastructure or data the framework depends on but should remain a separate dependency, not merged in |
| **INDEPENDENT** | Serves a distinct product purpose (training, vision, robotics, etc.) — not part of the agentic framework |
| **DEPRECATED/EMPTY** | Empty, placeholder, or experimental — skip |

---

## Module-by-Module Classification

### CORE AGENTIC — Already in or should be in the agentic framework

| # | Module | Files | What It Does | Why Core |
|---|--------|-------|-------------|----------|
| 1 | **agentic_framework** | 24 | Agent orchestration, safety contracts, confidence gating, MCP gateway, reflective loop, proactive scheduler, governance API | This IS the framework. |
| 2 | **safety** | 3 | GCC runtime guard, static scanner, ledger invariant checker. Fail-closed constraint enforcement. | Direct safety enforcement. The `FORBIDDEN_CAPABILITIES` in the agentic framework mirror these. Should be formally imported rather than duplicated. |
| 3 | **policy** | 9 | Policy engine (909 lines), interaction modes, insight window gating, trading guardrails, session policy, domain profiles. | Policy decisions feed the agentic framework. Currently advisory-only (UI-layer), but the governance API could make these enforceable. The `policy_engine.compute_policy_flags()` should be callable from `GovernanceService`. |
| 4 | **posture** | 5 | Decision posture profiles, behavioral sovereignty layer, audit records. Operator-defined behavioral modulation within immutable truth constraints. | Direct governance — controls HOW the system behaves. `apply_posture_to_escalation()` directly maps to the agentic framework's escalation logic. |
| 5 | **ledger** | 3 | Deterministic ledger replay verification, hash-stable append-only store, spec-compliant entries. | Audit infrastructure. The agentic framework's in-memory `audit_log` should evolve toward this ledger pattern for persistence and tamper-evidence. |

### INTEGRATE — Should feed signals into or be consumed by the agentic framework

| # | Module | Files | What It Does | Integration Point |
|---|--------|-------|-------------|-------------------|
| 6 | **entropy** | 7 | Cross-domain entropy engine for structural coherence regulation. Guna, Kosha, cross-domain dimensions. | Entropy scores could feed `ConfidenceSignals.volatility_index` and `session_stability` in the governance service. |
| 7 | **coherence** (inside `core/`) | 6 | Temporal arc tracing, coherence computation. | Already consumed indirectly — `CoherenceState` in the agentic framework mirrors these metrics. Formal bridge would reduce duplication. |
| 8 | **identity** | 2 | Identity signature classification for multi-turn sessions. | `identity_stability` is a SafetyContract precondition. This module could provide the actual signal instead of requiring callers to supply it. |
| 9 | **motivation** | 2 | Deterministic motivation driver classification. | Maps directly to `AdaptivePolicyEngine.SessionTrajectory` (HOPE_DRIVEN, FEAR_DRIVEN, etc.). Should be the canonical source instead of the agentic framework reimplementing trajectory classification. |
| 10 | **sovereign** | 18+ | Sovereign-1 state management, PID governor, ontological routing, reasoning kernel. | `sovereign_bridge.py` in the agentic framework already bridges the 32D Sovereign State → ConfidenceSignals. The bridge exists; the sovereign module is the upstream signal source. |
| 11 | **inference** | 25+ | Sovereign scorer, state monitor, logit modulation, coherence-aware decoding. | `SovereignStateMonitor` and `SovereignScorer` provide runtime state signals that should feed the governance service's confidence evaluation. |
| 12 | **chitta_vritti** | 9 | 5-element vritti distribution (cognitive mode classification). | Vritti signals (Pramāṇa=valid cognition, Viparyaya=misconception) directly indicate epistemic reliability — a natural input to `ConfidenceGate.quality_score`. |
| 13 | **temporal** | 5 | Cross-domain pattern tracking, trajectory analysis. | Trajectory data feeds `trajectory_confidence` in the governance service. |
| 14 | **guna_modulation** | 19+ | Guna-aware entropy modulation, state evolution, mirror balance. | Guna signals (Sattva/Rajas/Tamas) already route to the governor via sovereign bridge. Deeper integration would let the governance API report energy-state context in its rationale. |
| 15 | **dha** | 7 | Delivery Harmonization Algorithm — tone weights, intensity, restraint scalars. | DHA restraint signals could inform the governance service's `execution_mode` — high restraint → more conservative execution posture. |
| 16 | **llm** | 3 | LLM interface layer with authority boundary enforcement. No hallucination, no constraint override, no upstream feedback. | The authority boundary model (deterministic core → optional LLM renderer) is a governance pattern. The `validate_llm_response()` function could be exposed as a governance check in the API. |
| 17 | **api** | 3 | Coherence API, unified API. | Already an API surface. Could host or proxy the governance API endpoints alongside existing coherence endpoints. |

### SUPPLY — Dependencies the framework uses but shouldn't absorb

| # | Module | Files | What It Does | Relationship |
|---|--------|-------|-------------|--------------|
| 18 | **formulas** | 42 | Acoustic-symbolic tokenization, resonance computation, temporal math. Deterministic, stateless. | Provides computational primitives used throughout the pipeline. The agentic framework doesn't need these directly — they're consumed by phases that produce the signals the framework evaluates. |
| 19 | **ontological** | 56+ | Learnable 156D ontological engine, encoders, contrastive training. | The ML backbone. Produces ontological embeddings consumed by downstream phases. The framework evaluates decisions about outputs, not the encoding itself. |
| 20 | **resonance** | 8 | Phonetic resonance engine, 12D projections, Sattvic controller. | Signal source for phases, not directly consumed by governance. |
| 21 | **name_resonance** | 10 | Cross-domain name analysis. | Application-specific analysis, not governance. |
| 22 | **ppv** | 3 | Phonemic propensity vectors. | Structural signals consumed by the pipeline, not by the agentic framework. |
| 23 | **rag** | 7 | RAG with vector store, corpus indexing, episodic memory. | Memory infrastructure. The agentic framework has its own `MemoryStore`; RAG is a separate retrieval system. |
| 24 | **service** | 4+ | API server, chat service, request models, usage tracking. | Hosts the FastAPI server. The governance API (`governance_api.py`) could be mounted as a sub-application on this server. |
| 25 | **orchestration** | 4 | Pipeline routing between deterministic and generation pipelines. | Orchestration of the cognitive pipeline, not of agent actions. |
| 26 | **presentation** | 14 | Presentation layer translating signals to UX directives. | Output formatting, not governance. |
| 27 | **renderer** | 2 | Re-exports SOULPI renderer components. | Output rendering, not governance. |
| 28 | **providers** | 2+ | Pluggable provider architecture (embedding, routing, filtering). | Infrastructure plumbing. |
| 29 | **licensing** | 2 | License validation and feature control. | Could gate governance features per license tier, but is infrastructure, not governance. |
| 30 | **adapter** | 2 | DILchat adapter (presentation transformation). | Output formatting. |
| 31 | **common** | 2 | Shared projectors for Sovereign/JEPA models. | ML infrastructure. |
| 32 | **mechanical** | 2+ | Non-patented mechanical processing, core bridge. Contains the 53-phase pipeline. | The pipeline is the reasoning engine. The governance phases (P51-P55) inside it are governance, but the pipeline itself is reasoning infrastructure. |
| 33 | **hybrid** | 7 | Phoneme-transformer optimization (64x attention reduction). | Inference optimization, not governance. |
| 34 | **engine** | 9 | Unified engine factory for deployment tiers. | Deployment infrastructure. |
| 35 | **cloud_controller** | 4 | Neural cloud scaling controller. | Infrastructure scaling, not governance. |

### INDEPENDENT — Separate products/domains, not part of agentic framework

| # | Module | Files | What It Does | Why Independent |
|---|--------|-------|-------------|----------------|
| 36 | **training** | 6 | Training infrastructure, confidence scaler, entropy control. | Training-time, not runtime governance. |
| 37 | **losses** | 2 | Custom loss functions (Kosha gyroscope). | Training-time. |
| 38 | **jepa** | 6 | Ontological State Predictor with Phase Attention. | ML model architecture, not governance. |
| 39 | **vision** | 23 | Phase-Quad image generator. | Separate product domain. |
| 40 | **image_gen** | 8 | FLUX-integrated image synthesis. | Separate product domain. |
| 41 | **voice** | 6+ | Hybrid Voice SDK with prosody and safety gates. | Separate product domain. Voice safety gate could feed governance signals but is a separate product. |
| 42 | **diagnostics** | 2 | Training diagnostic logger. | Training-time. |
| 43 | **monitors** | 2 | Graduation monitor for training. | Training-time. |
| 44 | **benchmarks** | 4 | Benchmark suites. | Testing/evaluation. |
| 45 | **experimental** | 17 | Tier 3 Ontological State-Delta training. | Research/experimental. |
| 46 | **intent** | 3 | Intent classification and ARC processing. | Could be consumed by goal decomposition but is a separate NLU module. |
| 47 | **phases** | 2 | Phase 7 implementation. | Pipeline phase, not governance. |

### DEPRECATED/EMPTY

| # | Module | Files | Status |
|---|--------|-------|--------|
| 48 | **tools** | 0 | Empty directory |
| 49 | **dynamics** | 1 | Only `__init__.py`, placeholder |
| 50 | **ontology** | 1 | Only `__init__.py`, placeholder |
| 51 | **experiments** | 1 | Only `__init__.py`, experimental placeholder |

---

## Summary Counts

| Category | Count | Modules |
|---|---|---|
| **CORE AGENTIC** | 5 | agentic_framework, safety, policy, posture, ledger |
| **INTEGRATE** | 12 | entropy, core/coherence, identity, motivation, sovereign, inference, chitta_vritti, temporal, guna_modulation, dha, llm, api |
| **SUPPLY** | 18 | formulas, ontological, resonance, name_resonance, ppv, rag, service, orchestration, presentation, renderer, providers, licensing, adapter, common, mechanical, hybrid, engine, cloud_controller |
| **INDEPENDENT** | 12 | training, losses, jepa, vision, image_gen, voice, diagnostics, monitors, benchmarks, experimental, intent, phases |
| **DEPRECATED/EMPTY** | 4 | tools, dynamics, ontology, experiments |

---

## Unified Agentic Framework: Recommended Architecture

```
symbolu/agentic_framework/          ← CORE (already exists)
  ├── agent.py                       ← Main wrapper
  ├── safety_contract.py             ← Pre-execution authorization
  ├── confidence_gate.py             ← Behavioral confidence control
  ├── mcp_gateway.py                 ← Tool mediation
  ├── governance_service.py          ← External authorization (NEW)
  ├── governance_api.py              ← FastAPI endpoints (NEW)
  ├── governance_models.py           ← API schemas (NEW)
  ├── ...existing modules...
  │
  ├── signals/                       ← NEW: Signal adapters for INTEGRATE modules
  │   ├── entropy_signals.py         ← entropy → ConfidenceSignals
  │   ├── vritti_signals.py          ← chitta_vritti → quality_score
  │   ├── identity_signals.py        ← identity → identity_stability
  │   ├── motivation_signals.py      ← motivation → SessionTrajectory
  │   ├── dha_signals.py             ← dha → execution_posture
  │   └── guna_signals.py            ← guna_modulation → energy context
  │
  ├── policy_bridge.py               ← NEW: Bridge to symbolu/policy/
  │   (makes policy_engine flags enforceable, not just advisory)
  │
  └── audit/                          ← NEW: Persistent audit using ledger patterns
      ├── audit_store.py             ← Append-only persistent store
      └── audit_verifier.py          ← Hash-chain verification (from ledger/)

symbolu/safety/                      ← CORE (keep separate, import from)
symbolu/policy/                      ← CORE (keep separate, bridge from)
symbolu/posture/                     ← CORE (keep separate, bridge from)
symbolu/ledger/                      ← CORE (keep separate, pattern-reuse)
```

## Key Insight

The agentic framework is currently **self-contained** — it imports nothing from the rest of `symbolu/` except one lazy import (`symbolu.training.unified.mistral_wrapper` in `llm_adapters.py`). This is both a strength (clean separation) and a weakness (doesn't benefit from the rich signal ecosystem the rest of symbolu provides).

The 12 INTEGRATE modules produce exactly the signals the governance service needs for better decisions — entropy, vritti cognitive modes, identity stability, motivation trajectory, Guna energy states, DHA restraint. The `sovereign_bridge.py` already demonstrates the pattern: take tensor-level signals from the sovereign module and convert them into `ConfidenceSignals`. The same pattern should be applied to the other INTEGRATE modules via thin signal adapters.

The 5 CORE AGENTIC modules (agentic_framework + safety + policy + posture + ledger) form the natural governance product boundary. Everything else is either a signal source (INTEGRATE), infrastructure (SUPPLY), or a separate product (INDEPENDENT).
