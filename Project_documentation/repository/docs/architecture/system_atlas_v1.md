# Symbol-U System Atlas v1.0

**Type:** Archival Documentation
**Date:** 2025-12-17
**Status:** Freeze-frame snapshot — not a roadmap

---

## 1. Executive Summary

This document catalogs everything that currently exists in the Symbol-U codebase. It is:
- **Neutral** — no recommendations or improvements
- **Implementation-faithful** — reflects code, not intent
- **Archival** — a snapshot, not a design document

---

## 2. Phase Inventory

### 2.1 Governance Phases (PO1–PO5) — HIGH AUTHORITY

| Phase | Name | Folder Path | Status | Tests |
|-------|------|-------------|--------|-------|
| **PO1** | Observer-Observed Grounding | `symbolu/mechanical/pipeline/grounding/` | SAFE | Yes |
| **PO2** | Intent Envelope & Response Posture | `symbolu/mechanical/pipeline/phase_zero/` | SAFE | Yes |
| **PO3** | Intent → Allowed Action Contract | `symbolu/mechanical/pipeline/phase_one/` | SAFE | Yes |
| **PO4** | Planner Proposal Envelope | `symbolu/mechanical/pipeline/phase_po4/` | SAFE | Yes |
| **PO5** | Planner Execution Gate | `symbolu/mechanical/pipeline/phase_po5/` | SAFE | Yes |

#### PO1 Components
| File | Class/Function | Deterministic | Invariants |
|------|----------------|---------------|------------|
| `phase_minus_one_schema.py` | `ObservedEntity`, `ObservationMode`, `GroundingCandidate` | Yes | Enums frozen |
| `phase_minus_one_grounding.py` | `ObserverObservedGrounding` | Yes | No LLM calls |
| `phase_minus_one_ambiguity.py` | `AmbiguityResolver` | Yes | Conservative resolution |
| `phase_minus_one_clause_splitter.py` | `ConservativeClauseSplitter` | Yes | Fail-closed |
| `phase_minus_one_pipeline.py` | `PhaseMinusOnePipeline` | Yes | Orchestration only |

#### PO2 Components
| File | Class/Function | Deterministic | Invariants |
|------|----------------|---------------|------------|
| `phase_zero_schema.py` | `IntentType`, `ResponsePosture`, `IntentEnvelope` | Yes | Canonical mapping |
| `phase_zero_resolver.py` | `PhaseZeroResolver` | Yes | `INTENT_TO_POSTURE` mapping |

#### PO3 Components
| File | Class/Function | Deterministic | Invariants |
|------|----------------|---------------|------------|
| `phase_one_schema.py` | `AllowedActionSet` | Yes | Bounded action classes |
| `phase_one_resolver.py` | `PhaseOneResolver`, `INTENT_TO_ACTIONS` | Yes | Canonical mapping |

#### PO4 Components
| File | Class/Function | Deterministic | Invariants |
|------|----------------|---------------|------------|
| `po4_schema.py` | `ProposalStatus`, `PlannerProposalEnvelope` | Yes | Read-only governance |
| `po4_resolver.py` | `PO4Resolver` | Yes | No execution |

#### PO5 Components
| File | Class/Function | Deterministic | Invariants |
|------|----------------|---------------|------------|
| `po5_schema.py` | `ExecutionEligibility`, `ExecutionEligibilityEnvelope` | Yes | ELIGIBLE is informational |
| `po5_gate.py` | `PO5ExecutionGate` | Yes | No executor exists |

---

### 2.2 Regime & Language Phases (P6–P9) — HIGH AUTHORITY

| Phase | Name | Folder Path | Status | Tests |
|-------|------|-------------|--------|-------|
| **P6** | Regime Selection | `symbolu/mechanical/pipeline/phase_p6/` | SAFE | Yes |
| **P7** | Discourse Act Resolver | `symbolu/mechanical/pipeline/p7_discourse/` | SAFE | Yes |
| **P8** | Semantic Slot Resolution | `symbolu/mechanical/pipeline/p8_semantics/` | SAFE | Yes |
| **P9** | Lexical Selection | `symbolu/mechanical/pipeline/p9_lexical/` | SAFE | Yes |

#### P6 Components
| File | Class/Function | Deterministic | Invariants |
|------|----------------|---------------|------------|
| `p6_schema.py` | `OperationalRegime`, `RegimeEnvelope` | Yes | HOLD always safe |
| `p6_regime_gate.py` | `P6RegimeGate` | Yes | Regime restricts only |

#### P7 Components
| File | Class/Function | Deterministic | Invariants |
|------|----------------|---------------|------------|
| `p7_discourse_schema.py` | `DiscourseAct`, `DiscourseEnvelope` | Yes | DEFERRAL always safe |
| `p7_discourse_resolver.py` | `P7DiscourseResolver` | Yes | No semantic interpretation |

---

### 2.3 Acoustic Phases (P10–P13) — MEDIUM AUTHORITY

| Phase | Name | Folder Path | Status | Tests |
|-------|------|-------------|--------|-------|
| **P10** | Acoustic Parameterization | `symbolu/mechanical/pipeline/p10_acoustic/` | SAFE | Yes |
| **P11** | Prosodic Evidence | `symbolu/mechanical/pipeline/p11_prosodic/` | SAFE | Yes |
| **P12** | Consistency Check | `symbolu/mechanical/pipeline/p12_consistency/` | SAFE | Yes |
| **P13** | Acoustic Safety Envelope | `symbolu/mechanical/pipeline/p13_acoustic_safety/` | SAFE | Yes |

**Critical Invariant (P10):**
```
Sound must obey meaning.
Meaning must NEVER obey sound.
```

**P13 Invariant:** BINDING safety bounds — renderers violating P13 are unsafe by design.

---

### 2.4 Surface & Delivery Phases (P14–P21) — MEDIUM AUTHORITY

| Phase | Name | Folder Path | Status | Tests |
|-------|------|-------------|--------|-------|
| **P14** | Surface Realization | `symbolu/mechanical/pipeline/p14_surface/` | SAFE | Yes |
| **P15** | Interaction Directive | `symbolu/mechanical/pipeline/p15_interaction/` | SAFE | Yes |
| **P16** | Regression Guard | `symbolu/mechanical/pipeline/p16_regression_guard/` | SAFE | Yes |
| **P17** | Semantic Integrity | `symbolu/mechanical/pipeline/p17_semantic_integrity/` | SAFE (Observer) | Yes |
| **P18** | Temporal Entropy | `symbolu/mechanical/pipeline/p18_temporal_entropy/` | SAFE (Observer) | Yes |
| **P19** | Drift Fusion | `symbolu/mechanical/pipeline/p19_drift_fusion/` | SAFE (Observer) | Yes |
| **P20** | Unified Snapshot | `symbolu/mechanical/pipeline/p20_snapshot/` | SAFE (Observer) | Yes |
| **P21** | Delivery Mode | `symbolu/mechanical/pipeline/p21_delivery/` | SAFE | Yes |

---

### 2.5 Observer Phases (P22–P26) — ZERO AUTHORITY

| Phase | Name | Folder Path | Authority | Status | Tests |
|-------|------|-------------|-----------|--------|-------|
| **P22** | Acoustic Witness | `symbolu/mechanical/pipeline/p22_acoustic_witness/` | ZERO | SAFE | Yes |
| **P23** | Alignment Observer | `symbolu/mechanical/pipeline/p23_alignment/` | ZERO | SAFE | Yes |
| **P24** | Projection Observer | `symbolu/mechanical/pipeline/p24_projection/` | ZERO | SAFE | Yes |
| **P25** | Counterfactual Sandbox | `symbolu/mechanical/pipeline/p25_counterfactual/` | ZERO | SAFE | Yes |
| **P26** | Unified Consciousness Formula | `symbolu/mechanical/pipeline/p26_ucf/` | ZERO | SAFE | Yes |

**Observer Invariant:** These phases CANNOT influence behavior, semantics, routing, or delivery.

---

### 2.6 Predictive/Scenario Phases (P32–P49) — ZERO AUTHORITY

| Phase | Name | Folder Path | Status | Tests |
|-------|------|-------------|--------|-------|
| **P32** | Insight Window | `symbolu/mechanical/pipeline/p32_insight_window/` | SAFE | Yes |
| **P33** | Schema Adaptive Routing | `symbolu/mechanical/pipeline/p33_schema_adaptive/` | SAFE | Yes |
| **P35** | Predictive Persona Drift | `symbolu/mechanical/pipeline/p35_predictive_persona_drift/` | SAFE | Yes |
| **P36** | Identity Resonance Memory | `symbolu/mechanical/pipeline/p36_identity_resonance_memory/` | SAFE | Yes |
| **P38** | Temporal Forecast | `symbolu/mechanical/pipeline/p38_temporal_forecast/` | SAFE | Yes |
| **P39** | Multi-Horizon | `symbolu/mechanical/pipeline/p39_multi_horizon/` | SAFE | Yes |
| **P40** | Cross-Horizon Alignment | `symbolu/mechanical/pipeline/p40_cross_horizon_alignment/` | SAFE | Yes |
| **P41** | Scenario Regime Mapper | `symbolu/mechanical/pipeline/p41_scenario_regime_mapper/` | SAFE | Yes |
| **P42** | Scenario Fusion | `symbolu/mechanical/pipeline/p42_scenario_fusion/` | SAFE | Yes |
| **P43** | Scenario What-If | `symbolu/mechanical/pipeline/p43_scenario_what_if/` | SAFE | Yes |
| **P44** | Coherence Scenario Alignment | `symbolu/mechanical/pipeline/p44_coherence_scenario_alignment/` | SAFE | Yes |
| **P45** | Multi-Trajectory Stability | `symbolu/mechanical/pipeline/p45_multi_trajectory_stability/` | SAFE | Yes |
| **P46** | Trajectory Convergence | `symbolu/mechanical/pipeline/p46_trajectory_convergence/` | SAFE | Yes |
| **P47** | Unified Trajectory Scenario | `symbolu/mechanical/pipeline/p47_unified_trajectory_scenario/` | SAFE | Yes |
| **P48** | Macro Stability | `symbolu/mechanical/pipeline/p48_macro_stability/` | SAFE | Yes |
| **P49** | Temporal Stability Index | `symbolu/mechanical/pipeline/p49_temporal_stability/` | SAFE | Yes |

**P41 Invariants (Representative):**
- INV-P41-1: Observer-only (no influence on regimes, discourse, routing, or action)
- INV-P41-2: Deterministic (same inputs → same outputs)
- INV-P41-3: Scenario labels only (no probabilities, no forecasts, no optimization)
- INV-P41-4: Monotonic consistency
- INV-P41-5: Absence-safe

---

### 2.7 Final Governance Phases (P50–P54) — ZERO AUTHORITY (Observer)

| Phase | Name | Folder Path | Status | Tests |
|-------|------|-------------|--------|-------|
| **P50** | Cognitive Consistency Regression | `symbolu/mechanical/pipeline/p50_cognitive_consistency/` | SAFE | Yes |
| **P51** | Governance Readiness | `symbolu/mechanical/pipeline/p51_governance_readiness/` | SAFE | Yes |
| **P52** | Governance Adapter | `symbolu/mechanical/pipeline/p52_governance_adapter/` | SAFE | Yes |
| **P53** | Policy Binding | `symbolu/mechanical/pipeline/p53_policy_binding/` | SAFE | Yes |
| **P54** | Audit Trace | `symbolu/mechanical/pipeline/p54_audit_trace/` | SAFE | Yes |

**P50 Invariants:**
- INV-P50-A1: Cannot modify any upstream phase output
- INV-P50-A2: Cannot gate any action or delivery
- INV-P50-A3: Cannot be read by P6-P21
- INV-P50-A4: Output is observer-only
- INV-P50-D1: Same history + same input → same report (bitwise)
- INV-P50-D2: No randomness, no thresholds learned at runtime

---

### 2.8 Experimental Sandboxes (Phase 11–14) — EXPERIMENTAL

| Phase | Name | Folder Path | Status | Tests |
|-------|------|-------------|--------|-------|
| **Phase 11** | Generative Surface Sandbox | `docs/experiments/phase11_sandbox/` | EXPERIMENTAL | Partial |
| **Phase 11B.1** | Ontological Routing | `docs/experiments/phase11_sandbox/phase11b1_routing.py` | EXPERIMENTAL | Yes |
| **Phase 11B.2** | PPV Canonicalization | `docs/experiments/phase11_sandbox/phase11b2_canonicalization.py` | EXPERIMENTAL | Yes |
| **Phase 11B.3** | Template Registry | `docs/experiments/phase11_sandbox/phase11b3_canonicalization.py` | EXPERIMENTAL | Yes |
| **Phase 12** | Governed Generative Pipeline | `docs/experiments/phase12_sandbox/` | EXPERIMENTAL | 100 |
| **Phase 13** | K1 Knowledge Layer | `docs/experiments/phase13_sandbox/` | EXPERIMENTAL | 55 |
| **Phase 14** | Phonemic-Ontological Accumulator | `docs/experiments/phase14_sandbox/` | EXPERIMENTAL | 104 |

#### Phase 11 (Sandbox)
- **Mode:** OPEN only (no governance)
- **Purpose:** Explore PPV influence, ontological routing, probabilistic choice
- **Determinism:** Explicitly disabled
- **Safety Claims:** None — everything may be wrong

#### Phase 12 (Governed Generative)
| Component | File | Status | Tests |
|-----------|------|--------|-------|
| Phase12Schema | `phase12_schema.py` | Complete | — |
| PPVConditioningEncoder | `phase12_ppv_encoder.py` | Complete | 31 |
| Phase12Verifier | `phase12_verifier.py` | Complete | 32 |
| TemplateRetriever | `phase12_retriever.py` | Complete | 23 |
| LLM Integration PoC | `phase12_poc.py` | Complete | 14 |

**Key Principle:** Probabilistic generation sandwiched between deterministic layers.

#### Phase 13 (K1 Knowledge Layer)
| Component | File | Status | Tests |
|-----------|------|--------|-------|
| K1Atom (minimal) | `k1_schema.py` | Complete | 27 |
| K1Store with indices | `k1_store.py` | Complete | 28 |

**K1 Invariants:**
1. Deterministic Retrieval
2. Ledger Recording
3. Replay Provable
4. Index Rebuildable
5. No Free Text (payload_ref is opaque pointer only)

#### Phase 14 (Phonemic-Ontological Accumulator)
| Component | File | Purpose | Tests |
|-----------|------|---------|-------|
| Phoneme Extractor | `phoneme_extractor.py` | Word → phonemes → PPV | 28 |
| Layer Assigner | `layer_assigner.py` | Word → ontological layer | 25 |
| Character Deriver | `character_deriver.py` | Cross-layer propensities | — |
| Accumulator | `accumulator.py` | Pattern tracking | 27 |
| RAG-K1 Pipeline | `rag_k1_pipeline.py` | Orchestration | 24 |

**Stability States:**
| Status | Observations | Confidence | Meaning |
|--------|--------------|------------|---------|
| UNSTABLE | < 10 | — | Too little data |
| EMERGING | 10-50 | < 0.7 | Pattern forming |
| STABLE | 50+ | > 0.8 | Reliable mapping |
| CONFLICTED | 50+ | < 0.5 | Needs review |

---

### 2.9 Pre-Ontological Experiments (Phase 1b–10)

| Phase | Name | Location | Status |
|-------|------|----------|--------|
| Phase 1b | Substrate Bridge Validation | `docs/data/phase1b_*` | Historical |
| Phase 2 | Modifier Engine | `docs/experiments/phase2_modifier_engine_v3_2.py` | Historical |
| Phase 3 | Rule Engine | `docs/experiments/phase3_rule_engine_v3_0.py` | Historical |
| Phase 4 | Transform Engine | `docs/experiments/phase4_transform_engine_v4_0.py` | Historical |
| Phase 5 | Synthesis Engine | `docs/experiments/phase5_synthesis_engine_v5_0.py` | Historical |
| Phase 6 | Generative Boundary | `docs/experiments/phase6_generative_boundary_engine_v6_0.py` | Historical |
| Phase 7 | Structural Folding | `docs/experiments/phase7_structural_folding_engine_v7_0.py` | Historical |
| Phase 9 | Rewrite Engine | `docs/experiments/phase9_rewrite_engine_v0.py` | Historical |

**Note:** "Phase" labels in formula files are HISTORICAL DEVELOPMENT MILESTONES, not pipeline execution phases.

---

## 3. Subsystem Map

### 3.1 Mechanical Pipeline Orchestrator

| Component | Folder Path | Version | Purpose |
|-----------|-------------|---------|---------|
| SymbolUPipeline | `symbolu/mechanical/pipeline/` | 3.0 | Main orchestrator |
| PipelineRouter | `symbolu/mechanical/pipeline/routing.py` | — | Execution path decision |
| Models | `symbolu/mechanical/pipeline/models.py` | — | Data structures |
| Validators | `symbolu/mechanical/pipeline/validators.py` | — | Stage validation |

**Pipeline Sequence:**
```
Persona → MLCR → Fusion → DHA → Renderer
```

### 3.2 MLCR Engine (Multi-Layer Consciousness RAG)

| Component | File | Purpose |
|-----------|------|---------|
| MLCR | `mlcr_engine.py` | Main engine |
| OntologyMassComputer | `ontology_mass.py` | Lower/upper tier mass |
| IntentClassifier | `intent_classifier.py` | Intent classification |
| EntropyAdapter | `entropy_adapter.py` | H_D, H_G, H_K computation |
| TierSelector | `tier_selector.py` | LOWER/UPPER/HYBRID |
| ExpertRouter | `expert_router.py` | Mapper activation |
| RendererContextBuilder | `renderer_context.py` | Context assembly |
| ExplainabilityLogger | `explainability.py` | Audit trail |

**Inputs:**
- User query
- PO-phase constraints

**Outputs:**
- ActivationPlan (tier, intent, expert targets)

**Dependencies:** None (standalone)

### 3.3 TTOR (Two-Tier Ontology Router)

| Component | File | Purpose |
|-----------|------|---------|
| TTORRouter | `router.py` | Main router |
| RouterContext | `models.py` | Input context |
| RoutingPlan | `models.py` | Output plan |
| Constants | `constants.py` | Thresholds, domains |
| Formulas | `formulas.py` | Score computation |

**Canonical Mapper Rules v2.0:**
```
HRM: (tier != LOWER) AND (entropy_mix > 0.40)
LCM: (tier == LOWER) AND (entropy_mix > 0.50)
LAM: (long_arc_tension > 0.50) OR temporal_patterns_detected
     OR (domain in ["therapy", "identity", "spiritual"] AND entropy_mix > 0.60)
```

**Inputs:**
- Aspect probabilities
- Entropy measures (H_D, H_G, H_K)
- Anchor scores
- Domain/risk level

**Outputs:**
- Tier (LOWER/UPPER/HYBRID)
- FlowMode (OUTER_ONLY/OUTER_PLUS_INNER/INNER_PRIORITY)
- HRM/LCM/LAM activation flags

**Dependencies:** MLCR output

### 3.4 Fusion Engine

| Component | Folder Path | Version | Purpose |
|-----------|-------------|---------|---------|
| FusionEngine | `symbolu/mechanical/fusion/` | 3.1 | Candidate blending |
| Candidate | `schemas/` | — | Candidate structure |
| FusionContext | `schemas/` | — | Fusion context |

**Channel Weights (Default):**
```
HRM: 0.4 (α - High-Reasoning)
LCM: 0.3 (β - Linguistic Coherence)
MoE: 0.3 (γ - Mixture of Experts)
```

**Inputs:**
- Candidates from HRM/LCM/MoE
- MLCR tier decision

**Outputs:**
- FusionResult (selected candidate, explanation)

**Dependencies:** MLCR, TTOR

### 3.5 DHA Engine (Delivery Harmonization & Adaptation)

| Component | File | Purpose |
|-----------|------|---------|
| DHAEngine | `dha_engine.py` | Main orchestrator |
| ToneSelector | `tone_selector.py` | Delivery profile selection |
| DeliveryModulator | `delivery_modulator.py` | Message transformation |
| ReadinessAnalyzer | `readiness_analyzer.py` | User readiness |
| ResistanceDetector | `resistance_detector.py` | Resistance patterns |
| SafetyFilters | `safety_filters.py` | Safety guardrails |

**Delivery Profiles:**
- SWEET_RESONANCE: Gentle, supportive
- INVERSE_JOLT: Direct approach
- SYMBOLIC_METAPHOR: Indirect, metaphorical

**Inputs:**
- Rendered output
- Readiness/resistance scores

**Outputs:**
- DHAOutput (adapted message, profile used)

**Dependencies:** Fusion output, P13 safety envelope

### 3.6 Persona Engine

| Component | File | Version | Purpose |
|-----------|------|---------|---------|
| PersonaEngine | `engine.py` | 2.8.2 | Persona styling |
| PersonaSelector | `selector.py` | — | Persona choice |
| PersonaRegistry | `registry.py` | — | Profile storage |

**Default Personas:** sage, analyst, coach, friendly, regulator, neutral

**Critical Constraint:**
```
PersonaEngine NEVER modifies layer contents.
It only controls ordering, framing, and presentation style.
```

**Inputs:**
- DHA output
- Domain/context signals

**Outputs:**
- PersonaResponse (styled message)

**Dependencies:** DHA output

### 3.7 Renderer

| Component | Folder Path | Version | Purpose |
|-----------|-------------|---------|---------|
| Renderer | `symbolu/mechanical/renderer/` | 3.0 | Final output production |
| FusionRenderer | — | — | Fusion-to-output |

**Modes:** minimal, standard, enhanced, regulated

**Constraints:**
- Must respect P13 safety envelope
- Must respect P14 surface plan
- Must respect P21 delivery mode

### 3.8 RAG Subsystem

| Component | Folder Path | Version | Purpose |
|-----------|-------------|---------|---------|
| index_corpus | `symbolu/rag/stitching/pipeline.py` | 3.0 | Document indexing |
| run_rag | `symbolu/rag/stitching/pipeline.py` | 3.0 | Retrieval |
| MemoryVectorStore | `symbolu/rag/vectorstore/memory_store.py` | — | In-memory store |
| Document/Chunk | `symbolu/rag/utils/types.py` | — | Data types |

**Features:**
- Pure Python (no external dependencies)
- Deterministic hash-based embeddings
- Cosine similarity
- CandidateEntry integration

### 3.9 Ledger System

| Component | Folder Path | Purpose |
|-----------|-------------|---------|
| LedgerEntry | `symbolu/ledger/ledger_replay_verifier.py` | Entry with hash chain |
| LedgerEntryStore | `symbolu/ledger/ledger_store.py` | Append-only storage |
| verify_ledger_replay | `symbolu/ledger/ledger_replay_verifier.py` | Replay verification |

**Invariants:**
- Hash chain integrity
- Append-only
- Replay-deterministic

### 3.10 Core/Formulas (ZERO Authority)

| Component | Folder Path | Purpose |
|-----------|-------------|---------|
| Resonance Formulas | `symbolu/formulas/resonance_formulas.py` | SMI, ΔSMI, Bhava Gap |
| Acoustic Unit Mapper | `symbolu/formulas/acoustic_unit_mapper.py` | Tokenization |
| Vritti Mapper | `symbolu/formulas/vritti_mapper.py` | Vritti assignment |
| Phase1 Snapshot | `symbolu/formulas/phase1_snapshot.py` | Immutable snapshots |

**40+ Formula Modules (Selected):**
- `enhanced_smi.py`
- `drift_fusion.py`
- `temporal_entropy_differential.py`
- `semantic_integrity.py`
- `predictive_persona_drift.py`
- `unified_consciousness.py`
- `trajectory_field_convergence.py`

**Constraints:**
- ZERO governance authority
- Cannot influence regime, discourse, semantics, or routing
- No LLM calls, no randomness
- Stateless, deterministic

### 3.11 Ontology Components

| Component | Folder Path | Purpose |
|-----------|-------------|---------|
| Ontology Router | `symbolu/ontology/router/` | Ontological routing |
| Ontology Projection | `symbolu/ontology/projection/` | Layer projection |
| Ontology Contracts | `symbolu/ontology/contracts/` | Interface contracts |
| Ontology Ledger | `symbolu/ontology/ledger/` | Projection ledger |
| Ontology Layers | `symbolu/ontology/layers/` | Layer definitions |

### 3.12 Coherence Observer

| Component | Folder Path | Purpose |
|-----------|-------------|---------|
| CoherenceEngine | `symbolu/core/coherence/coherence_engine.py` | Coherence tracking |
| CoherenceState | `symbolu/core/coherence/coherence_state.py` | State management |
| PersonaDriftMonitor | `symbolu/core/coherence/persona_drift_monitor.py` | Drift detection |
| TemporalArcTracer | `symbolu/core/coherence/temporal_arc_tracer.py` | Arc tracking |

**50+ coherence metrics tracked**

---

## 4. Data Authority Registry

### 4.1 Ground-Truth Data Files

| File | Location | What It Defines | Authoritative For |
|------|----------|-----------------|-------------------|
| `varna_bridge_map_v1.json` | `docs/data/` | Sanskrit varna → bridge meaning mappings | Phase 14, Experiment Pack v1 |
| `constants.py` | `symbolu/core/` | Kosha layers, consonant mappings, ontological layers | All phases |

### 4.2 varna_bridge_map_v1.json

**Source:** Sanskrit Varna Mala
**Version:** 1.0
**Purpose:** Phase-1b substrate bridge meanings (pre-semantic)

**Constraints (per meta):**
- No dictionary meaning
- No vrtti polarity resolution
- No observer/observed logic
- No contextual semantics
- No heuristic phonetics

**Vowels Defined:** a, e, i, o, u
**Consonants Defined:** 25+ canonical consonants with bridge_meaning

**Modules Expected to Use:**
- `docs/experiments/experiment_pack_v1/phoneme_only_router.py`
- `symbolu/formulas/varna_bridge_loader.py`

### 4.3 Canonical Constants (constants.py)

**Version:** 2.7.1 (SOULPI)
**Status:** CANONICAL — Do not modify without authorization

| Constant | Purpose |
|----------|---------|
| `CANONICAL_KOSHA_LAYERS` | 5-layer Kosha model |
| `KOSHA_DESCRIPTIONS` | Layer nature, vritti tendency, acoustic quality |
| `CANONICAL_CONSONANT_TO_KOSHA` | Consonant → Kosha mapping |
| `CONSONANT_TO_KOSHA_MAP` | Reverse mapping |
| `ONTOLOGICAL_LAYERS` | 12-layer ontological model |
| `V26_STITCHING_WEIGHTS` | Stitching weights (alpha, beta, gamma, delta) |
| `DHA_TONES` | Delivery tone mappings |
| `VOWEL_ASPECT_BRIDGES` | Vowel → aspect mappings |
| `SMI_THRESHOLDS` | SMI threshold bands |

### 4.4 Fixture Files

| File | Location | Purpose |
|------|----------|---------|
| `fixture_chain.json` | `symbolu/ledger/fixtures/` | Ledger chain test |
| `fixture_absolving_block.json` | `symbolu/ledger/fixtures/` | Absolution test |
| `fixture_hint_override.json` | `symbolu/ledger/fixtures/` | Override test |
| `fixture_minimal.json` | `symbolu/ledger/fixtures/` | Minimal test |

### 4.5 Snapshot/Baseline Files

| File | Location | Purpose |
|------|----------|---------|
| `delta_baseline.json` | `symbolu/mechanical/pipeline/snapshots/` | Delta baseline |
| `persona_temporal_baseline.json` | `symbolu/mechanical/pipeline/snapshots/` | Persona temporal |
| `mapper_switching_baseline.json` | `symbolu/mechanical/pipeline/ttor/snapshots/` | TTOR v1 |
| `mapper_switching_baseline_v2.json` | `symbolu/mechanical/pipeline/ttor/snapshots/` | TTOR v2 |

---

## 5. Governance Layers (G-Layers)

### G1: Pre-Acoustic Governance (PO1–PO5)

**Phases:** PO1, PO2, PO3, PO4, PO5
**Authority:** HIGH
**Characteristics:**
- Establishes intent, grounding, allowed actions
- Authority flows downward only
- Cannot be overridden by downstream phases

**Fail-Closed Behavior:**
- PO1: Conservative clause splitting
- PO2: Defaults to ABSTAIN posture
- PO3: Empty action set if unclear
- PO4: BLOCKED if proposal not in allow-list
- PO5: PROHIBITED if uncertain

### G2: Regime & Discourse Governance (P6–P9)

**Phases:** P6, P7, P8, P9
**Authority:** HIGH
**Characteristics:**
- Constrains language generation
- Regime may only restrict, never expand capability
- HOLD/DEFERRAL always safe

### G3: Acoustic Constraint Governance (P10–P13)

**Phases:** P10, P11, P12, P13
**Authority:** MEDIUM (P13 is HIGH/Capping)
**Characteristics:**
- Sound obeys meaning
- P13 safety envelope is BINDING
- Acoustic cannot influence semantic phases

### G4: Delivery Governance (P14–P21)

**Phases:** P14, P15, P16, P17–P19, P20, P21
**Authority:** MEDIUM (P21 is HIGH)
**Characteristics:**
- Surface realization constraints
- P17–P19 are observer-only
- P21 controls delivery channel permissions

### G5: Observer Layer (P22–P49)

**Phases:** P22–P26, P32–P49
**Authority:** ZERO
**Characteristics:**
- Cannot influence behavior, semantics, routing, delivery
- Cannot gate or block
- Read-only observation

### G6: Final Governance Band (P50–P54)

**Phases:** P50, P51, P52, P53, P54
**Authority:** ZERO (Observer)
**Characteristics:**
- Cognitive consistency observation
- Governance readiness assessment
- Audit trace generation
- Non-actuating

---

## 6. Explicit Assumptions vs Enforced Invariants

### 6.1 Enforced Invariants (Code/Tests)

| Invariant | Where Enforced | Evidence |
|-----------|----------------|----------|
| Determinism (same inputs → same outputs) | `determinism_verification.py` | 50-iteration hash tests |
| Sound obeys meaning | P10 schema, P22 tests | Import restrictions |
| Observer phases cannot influence authority | P41/P50 schemas | `observer_only: Literal[True]` |
| Regime monotonicity | P6 schema | Restrict-only logic |
| P13 binding on renderers | P13 schema, renderer compliance | Explicit checks |
| No LLM in governance phases | All PO/P6-P9 code | No LLM imports |
| Ledger hash chain | Ledger tests | Chain verification |
| TTOR canonical mapper rules | TTOR tests | Rule enforcement |

### 6.2 Assumptions (Comments/Docs Only)

| Assumption | Where Stated | Status |
|------------|--------------|--------|
| PPV vectors serve as generative seeds | Phase 11 README | HYPOTHESIS |
| Phoneme → layer affinity mappings | Phase 14 README | HYPOTHESIS (needs validation) |
| Cross-layer character usefulness | Phase 14 README | UNVALIDATED |
| Accumulation convergence | Phase 14 README | UNVERIFIED |
| Executor absence | PO5 docstring | ARCHITECTURAL CHOICE |
| Phase numbering gaps (P27–P31, P34, P37) | Architecture doc | UNSPECIFIED |

### 6.3 Explicitly Marked Hypotheses

| Hypothesis | Location | Status |
|------------|----------|--------|
| "Phonemes do not carry semantics, but acquire word character through deterministic ontological routing" | Experiment Pack v1 | UNDER TEST |
| "Ontological routing can influence generative output" | Phase 11 README | EXPERIMENTAL |
| "Probabilistic generation can be governed by deterministic layers" | Phase 12 README | PARTIALLY VALIDATED (100 tests) |

---

## 7. Risk & Status Labeling

### 7.1 SAFE (Mergeable to Main)

| Component | Evidence |
|-----------|----------|
| All PO phases (PO1–PO5) | Tests present, deterministic |
| All P6–P21 phases | Tests present, governed |
| All P22–P26 phases | Observer-only, tested |
| All P32–P49 phases | Observer-only, tested |
| All P50–P54 phases | Observer-only, tested |
| MLCR Engine | v3.1, production status |
| TTOR Router | v1.4, canonical rules |
| Fusion Engine | v3.1, deterministic |
| DHA Engine | v3.0, safety filters |
| Persona Engine | v2.8.2, no content modification |
| RAG Subsystem | v3.0, pure Python |
| Ledger System | Hash chain verified |
| Core/Formulas | ZERO authority, stateless |

### 7.2 EXPERIMENTAL (Hypothesis-Based)

| Component | Evidence |
|-----------|----------|
| Phase 11 Sandbox | README: "EXPERIMENTAL SANDBOX" |
| Phase 11B.1/B.2/B.3 | Part of Phase 11 sandbox |
| Phase 12 Sandbox | "Governed Generative Layer" — not production |
| Phase 13 Sandbox | K1 Knowledge Layer — experimental |
| Phase 14 Sandbox | Phonemic-Ontological Accumulator — experimental |
| Experiment Pack v1 | Explicit hypothesis testing |
| Acoustic Unit Mapper Expressive Delta | `docs/experiments/acoustic_unit_mapper_*` |

### 7.3 OBSOLETE

| Component | Evidence |
|-----------|----------|
| Phase 1b–10 experiments | Historical development milestones |
| Legacy ledger entries | Replaced by spec-compliant versions |

### 7.4 REQUIRES GROUND-TRUTH

| Component | Required Data | Status |
|-----------|---------------|--------|
| Phoneme-only routing | `varna_bridge_map_v1.json` | AVAILABLE |
| Kosha/consonant mappings | `constants.py` | CANONICAL |
| Phase 14 layer assignment | POS tagging + override lexicon | HEURISTIC |
| Phase 14 phoneme → layer affinity | Accumulation data | NOT VALIDATED |

---

## 8. Mode Handling

### 8.1 OPEN Mode

- Used in Phase 11 sandbox only
- No governance logic
- No verification
- No ledger enforcement
- No safety claims

### 8.2 GOVERNED Mode

- Used in production pipeline (P6–P55)
- Full governance logic
- Verification mandatory
- Ledger enforcement
- Safety claims made

### 8.3 Mode Selection

Phase 12 supports both modes:
- GOVERNED mode can reject outputs that OPEN mode accepts
- Mode propagates through PPV conditioning, template retrieval, verification

---

## 9. Ledger/Audit/Replay Mechanisms

### 9.1 LedgerEntry (Spec-Compliant)

| Field | Type | Purpose |
|-------|------|---------|
| entry_id | str | Hash chain ID |
| operation | str | Operation type |
| inputs_hash | str | Canonical input hash |
| outputs_hash | str | Canonical output hash |
| timestamp | str | ISO timestamp |
| previous_entry_id | str | Chain link |

### 9.2 Operations

| Operation | Where Used |
|-----------|------------|
| `record_ledger_entry` | Spec-compliant recording |
| `record_projection` | Legacy recording |
| `verify_ledger_replay` | Replay verification |

### 9.3 Replay Guarantees

- Same inputs over same store → same ordered results (K1)
- Every operation logged (query, add, remove)
- Query results include step-by-step proof
- Indices rebuildable from atoms

---

## 10. Test Coverage Summary

| Area | Test Files | Approximate Count |
|------|------------|-------------------|
| Core phases (PO1–P54) | `tests/core_phases/`, `tests/phase11/`, etc. | ~150 files |
| Experiments | `tests/experiments/` | ~20 files |
| Formulas | `symbolu/formulas/tests/` | ~30 files |
| Subsystems | Various `tests/` subdirectories | ~85 files |
| **Total test files** | — | **285** |

### 10.1 Determinism Verification

**File:** `determinism_verification.py`

| Phase | Test | Status |
|-------|------|--------|
| Phase 13 | Enhanced SMI | ✓ PASS |
| Phase 19 | Drift Fusion | ✓ PASS |
| Phase 31 | APEL | ✓ PASS |

---

## 11. Diagrams

### 11.1 Phase Authority Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          GOVERNANCE LAYER                                │
│                     (Authority Established Here)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  PO1 → PO2 → PO3 → PO4 → PO5                                            │
│  (Grounding → Intent → Actions → Proposal → Eligibility)                │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ Authority flows down
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       REGIME & LANGUAGE LAYER                            │
├─────────────────────────────────────────────────────────────────────────┤
│  P6 → P7 → P8 → P9                                                      │
│  (Regime → Discourse → Semantic → Lexical)                              │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     ACOUSTIC LAYER (Sound ← Meaning)                     │
│                   *** Meaning NEVER obeys Sound ***                      │
├─────────────────────────────────────────────────────────────────────────┤
│  P10 → P11 → P12 → P13◄── BINDING                                       │
│  (Acoustic → Prosodic → Consistency → Safety)                           │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      ROUTING & FUSION LAYER                              │
├─────────────────────────────────────────────────────────────────────────┤
│  MLCR → TTOR → Fusion → DHA → Persona → Renderer                        │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      OBSERVER LAYER (ZERO Authority)                     │
├─────────────────────────────────────────────────────────────────────────┤
│  P17-P19, P22-P26, P32-P49, P50-P54                                     │
│  ✗ Cannot influence regime/discourse/delivery                           │
│  ✗ Cannot gate or block                                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Experimental Pipeline Integration

```
┌─────────────────────────────────────────────────────────────────┐
│              EXPERIMENTAL GENERATIVE PIPELINE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Phase-11B.3 ──────────────────────────────────────────────────  │
│    ├── Ontological Routing      (deterministic)                  │
│    ├── PPV Canonicalization     (deterministic)                  │
│    └── Template Registry        (deterministic)                  │
│    ↓                                                             │
│  K1 (Phase-13) ────────────────────────────────────────────────  │
│    └── Knowledge retrieval      (deterministic)                  │
│    ↓                                                             │
│  Phase-12 ─────────────────────────────────────────────────────  │
│    ├── PPV Encoding             (deterministic)                  │
│    ├── Template Retrieval       (deterministic)                  │
│    ├── Context Assembly         (deterministic)                  │
│    ├── LLM Generation           (PROBABILISTIC) ← only here      │
│    └── Verification             (deterministic)                  │
│    ↓                                                             │
│  OUTPUT (or GENERATION_BLOCKED)                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 12. Open Questions / Ambiguities

### 12.1 Phase Numbering Gaps

| Gap | Possible Reason |
|-----|-----------------|
| P27–P31 | UNSPECIFIED |
| P34 | UNSPECIFIED |
| P37 | UNSPECIFIED |
| P55+ | UNSPECIFIED |

### 12.2 Renderer LLM Integration

- When LLM is invoked vs. rule-based rendering: UNSPECIFIED
- Constraints on LLM output: UNSPECIFIED
- Whether LLM output is subject to P13 safety envelope: UNSPECIFIED

### 12.3 Executor Absence

PO5 states "ELIGIBLE is informational only. No executor exists."
- What mechanism would execute actions if extended: UNSPECIFIED

### 12.4 Experimental Maturity

| Experiment | Maturity |
|------------|----------|
| Phase 11 | Sandbox only |
| Phase 12 | 100 tests passing |
| Phase 13 | 55 tests passing |
| Phase 14 | 104 tests passing |

---

## 13. File Index

### 13.1 Key Configuration Files

| File | Purpose |
|------|---------|
| `conftest.py` | Pytest configuration |
| `pyproject.toml` | UNVERIFIED if present |

### 13.2 Documentation Index

| Path | Contents |
|------|----------|
| `docs/architecture/` | Architecture documentation |
| `docs/experiments/` | Experimental sandboxes |
| `docs/governance/` | Governance rules |
| `docs/phases/` | Phase merge safety reports |
| `docs/data/` | Ground-truth data files |
| `docs/subsystems/` | Subsystem documentation |

---

*This document is an archival snapshot. It does not propose improvements or reinterpret intent. Where information is unclear, it is marked UNSPECIFIED.*

---

**Document Version:** 1.0
**Generated:** 2025-12-17
**Repository:** rasaha/symbolu
