# Agentic Architecture Wiring & Enhancement Audit

**Date:** 2026-04-03
**Scope:** 12 folders under `agentic/` — 388 Python files
**Method:** Code inspection, import tracing, runtime path analysis

---

## 1. Executive Summary

The `agentic/` codebase contains **two distinct runtime systems** operating in parallel:

1. **Symbol-U Pipeline** (deterministic, formula-driven) — served via FastAPI at `/symbolu/analyze`
2. **Agentic Framework** (LLM-wrapping, cognitively-modeled) — served via governance API at `:8100`

Of the 12 audited folders:
- **6 are on active runtime paths** (chitta_vritti, identity, motivation, temporal, api, llm)
- **2 are optionally wired** behind feature flags (guna_modulation, dha)
- **2 are training-time / experimental** (sovereign, inference)
- **1 has real engines buried under dead facades** (core)
- **1 is substantial but fully self-contained** (entropy)

### Critical Findings

| Finding | Severity |
|---------|----------|
| Vritti logic duplicated across 5 modules | HIGH |
| Semantic state split between sovereign/ (training) and inference/ (runtime) with no bridge | CRITICAL |
| core/ top-level facade is dead code (NotImplementedError stubs) | MEDIUM |
| inference/ is extensive (25 files) but orphaned from all runtime paths | HIGH |
| Guna computation exists in 4 independent implementations | HIGH |
| Entropy has 3 modules (1 real, 1 modulation-specific, 1 dead stub) | MEDIUM |

---

## 2. Current Runtime Architecture Map

```
HTTP POST /symbolu/analyze
    |
    v
SymbolUPipeline.execute(UserRequest)
    |-- Phase 1-10: Mechanical pipeline (deterministic)
    |     |-- core/coherence/ (CoherenceEngine)        <-- ACTIVE
    |     |-- core/entropy/ (EntropyEngine)             <-- STUB (dead)
    |     |-- core/smi/ (SMIEngine)                     <-- ACTIVE
    |     |-- core/stitching/ (StitchingEngine)         <-- ACTIVE
    |     |-- core/bhava/ (BhavaGeometry)               <-- ACTIVE
    |
    |-- Session Processing:
    |     |-- identity/ (compute_identity_signature)    <-- ACTIVE
    |     |-- motivation/ (compute_motivation_flow)     <-- ACTIVE
    |     |-- chitta_vritti/ (ChittaVrittiEngine)       <-- ACTIVE
    |
    |-- Optional (feature-flagged):
    |     |-- temporal/ (TemporalBhavaTracker + CDI)    <-- ACTIVE when use_lam=True
    |     |-- guna_modulation/ (EntropyModulation)      <-- ACTIVE when v2_7_enabled
    |     |-- dha/ (DHAEngine)                          <-- ACTIVE when dha_formula_enabled
    |
    |-- Fusion Renderer:
    |     |-- llm/ (LLMClient + validator)              <-- ACTIVE (optional LLM)
    |
    |-- Output:
          |-- api/ (build_unified_output)               <-- ACTIVE
          |-- entropy/ (cross-domain gating)            <-- ACTIVE

NOT ON RUNTIME PATH:
    - sovereign/        (training-time only)
    - inference/        (orphaned experimental)
    - core/interface.py (dead facade)
    - core/pipeline.py  (dead facade)

SEPARATE RUNTIME (Agentic Framework on :8100):
    - agentic_framework/governance_service.py
    - agentic_framework/mcp_gateway.py
    - agentic_framework/jepa_governance.py
```

---

## 3. Folder-by-Folder Audit

### 3.1 `entropy/` — Cross-Domain Entropy Gating

**Intended Role:**
Structural coherence regulation via tier-aware entropy gating. Computes guna entropy (variance from balanced state), kosha entropy (layer distance), and cross-domain entropy (12D structural distance). Gates output based on tier thresholds (Tier 1 = diagnostic only, Tier 2 = modulation, Tier 3 = full blocking).

**Actual Implementation Status:** SUBSTANTIAL (1,468 LOC across 7 files)
- `EntropyEngine.evaluate()`: Full 3-path entropy computation with weighted combination
- `compute_guna_entropy()`: Deterministic formula — normalized variance from balanced state
- `compute_kosha_entropy()`: Layer distance metric across 5 koshas
- `compute_cross_domain_entropy()`: 12D structural distance with incompatibility detection
- All frozen dataclasses, zero ML/randomness, pure deterministic math
- Strong explainability with trace entries for every computation

**Runtime Wiring Status:** ACTIVE but limited scope
- Used in benchmarking suite (`comprehensive_benchmark.py`)
- Referenced by `posture/` for coherence regulation
- NOT in core model forward pass — auxiliary telemetry/evaluation path
- Self-describes as "Not a safety system. No autonomy, learning, judgment, or policy enforcement"

**Key Dependencies:**
- Depends on: standard library only (fully self-contained)
- Depended on by: posture/, benchmarks, optionally training pipelines
- No circular dependencies

**Main Gaps:**
- NOT wired as a runtime gate despite having full gating logic (ALLOW / MODULATE / BLOCK)
- Tier 3 BLOCK path exists in code but no evidence it's triggered in production pipeline
- `core/entropy/` is a dead stub that should either delegate to this or be removed

**Priority:** IMPORTANT BUT UNDERWIRED
**Action:** Wire now — connect Tier 3 gating into the main pipeline output path; deprecate `core/entropy/` stub

---

### 3.2 `sovereign/` — Sovereign State Training Engine

**Intended Role:**
Training-time sovereign state computation. Decomposes 128D state into [16D Guna | 32D S-Signal | 48D R-Signal | 32D C-Signal]. Provides control-theoretic gating (PID governor), loss functions, and a full reasoning kernel (SRK V9.8.0). Conceptual home of the semantic state.

**Actual Implementation Status:** EXTENSIVE (13,725 LOC across 25 files)
- `SovereignLoss`: Weighted MSE per component with R-Signal weighted 5x to prevent "Signal Washing"
- `PIDGovernor`: Control loop with vritti-aware PID tables (5 modes × 3 params)
- `SovereignReasoningKernel` (V9.8.0): 2,173 lines — IsomorphicMappingRouter, OntologicalBridge, WitnessArbitrator, VrittiGate, KoshaShiftController
- `StitchedObjective`: Patent formulas [001]-[008] with aspect weighting, vritti coupling, redundancy/domain-jump penalties
- `InoculationTrainer`: 15,128 lines of adversarial training (bank disambiguation, homonym tests)
- Real nn.Module implementations with learnable parameters throughout

**Runtime Wiring Status:** TRAINING-TIME CRITICAL (feature-flagged)
- Loaded when `--enable_sovereign_loss` or `--use_sovereign_loss` flags set
- `SovereignLoss` in training forward pass (lines 2911-2917 of train.py)
- `SovereignEngine` in loss computation loop
- SRK used in generation if enabled
- NOT on inference-time pipeline (no bridge to runtime)

**Key Dependencies:**
- Depends on: PyTorch (nn.Module, tensors), entropy types (optional)
- Depended on by: `symbolu_training/` (main training loop), `inference/` (SRK config)
- Exports to hardware: `cognade_export.py` generates C headers for FPGA/ASIC

**Main Gaps:**
- **CRITICAL**: No bridge from training-time sovereign state (128D) to inference-time state (32D in `inference/sovereign_state_monitor.py`). These are separate representations.
- `sovereign/vritti.py` duplicates vritti logic that exists in `chitta_vritti/vritti.py`
- `sovereign/guna.py` duplicates guna computation in `guna_modulation/guna_derivation.py`
- Reasoning kernel (SRK) is massive but its inference-time activation path is unclear

**Priority:** CORE RUNTIME CRITICAL (for training); NEEDS CONSOLIDATION (for vritti/guna duplication)
**Action:** Refactor first — build explicit sovereign→inference state bridge; consolidate vritti/guna with canonical modules

---

### 3.3 `inference/` — Inference Orchestration Engine

**Intended Role:**
Master inference-time orchestration. Manages evolutionary inference, CSR safety guards, metacognitive monitoring, guna approximation, sovereign scoring, binding cache, and Appendix F experimental stages (0-7F). Intended as the inference-time counterpart to sovereign/.

**Actual Implementation Status:** SUBSTANTIAL but mixed maturity (9,883 LOC across 25 files)
- **Production-grade core:**
  - `InferenceManager` (1,290 LOC): Orchestrates 6+ sub-engines across 5 modes (FAST/STANDARD/FULL/SAFE/SOVEREIGN)
  - `EvolutionaryInferenceEngine` (530 LOC): nn.Module with learnable karma seed projection
  - `BindingCacheInferenceEngine` (695 LOC): V10.0 intent tracking with phase angles
  - `SovereignStateMonitor` (556 LOC): 32D state tracking [Bhava 0:12 | Kosha 12:17 | Vritti 17:22 | Guna 22:28]
  - `CSRInferenceGuard` (518 LOC): Safety layer with entropy monitoring
- **Experimental (Appendix F stages 0-7F):**
  - 7 files, 100-674 LOC each, some with TODO comments
  - CoherenceAwareDecoder (111 LOC) is minimal
  - GenerationTracer (674 LOC) is substantial

**Runtime Wiring Status:** WEAKLY WIRED
- `MistralCGGenerationTracer` used during training when enabled
- `BhavaVectorCompressor` imported by `symbolu_core/ontological/symbolu12_llm.py`
- `interpretive_state` imported by `agentic_framework/jepa_governance.py`
- **BUT**: Only 2-3 external imports found across entire repo
- InferenceManager itself is NOT called from any traced runtime entry point
- Appendix F stages are NOT wired into any pipeline

**Key Dependencies:**
- Depends on: PyTorch, sovereign/ (SRK config), internal cross-references
- Depended on by: training (generation tracer), agentic_framework (interpretive_state), symbolu_core (BhavaVectorCompressor)
- 32D sovereign state representation NOT reconciled with sovereign/'s 128D training state

**Main Gaps:**
- **HIGH**: InferenceManager is a fully built orchestrator that nothing calls
- 32D vritti slice [17:22] is never reconciled with `chitta_vritti/` module computations
- No clear activation path from main pipeline to inference/ modules
- Appendix F is research-grade, needs maturation before wiring

**Priority:** IMPORTANT BUT UNDERWIRED
**Action:** Wire now (core engines) / wire later (Appendix F) — connect InferenceManager to generation path; bridge 32D state to chitta_vritti

---

### 3.4 `chitta_vritti/` — Cross-Layer Coherence & Cognitive Modes

**Intended Role:**
Compute 5 cognitive mode distributions (pramana, viparyaya, vikalpa, smrti, nidra) from cross-layer coherence analysis. Provides readiness scoring, projection pipeline, and full evaluation framework.

**Actual Implementation Status:** PRODUCTION-GRADE (2,300+ LOC across 14 files)
- `ChittaVrittiEngine.compute()`: Full orchestration — fast-path optimization, nidra fallback, full computation path
- `VrittiComputer`: Real mathematical transforms per mode:
  - Pramana: `coherence × (1 - entropy/threshold) × (1 - motion)`
  - Viparyaya: High-fracture detection with opposition magnitude scaling
  - Vikalpa: Variance-based branching with entropy coupling
  - Smrti: Temporal delta tracking with decay accumulation
  - Nidra: Layer presence counting
- `CoherenceComputer`: Cross-layer cosine similarity, pairwise fracture analysis
- `Projector`: Linear random projection with L2 normalization, 4 specialized projectors
- `evaluation/`: Full ML metrics — AUC-ROC, Spearman correlation, calibration, A/B comparison
- Consumer vs Enterprise tier configurations

**Runtime Wiring Status:** FULLY ACTIVE
- `symbolu_core/presentation/signals.py`: TYPE_CHECKING imports ChittaVrittiInputs/Result
- `symbolu_core/presentation/session.py`: Decorates session objects with CV results
- `symbolu_core/hybrid/router.py`: Routes decisions based on CV scores
- `agentic_framework/jepa_governance.py`: Uses CV coupling for governance composite state

**Key Dependencies:**
- Depends on: standard library, numpy (for projection)
- Depended on by: presentation layer, hybrid router, JEPA governance
- No circular dependencies

**Main Gaps:**
- **HIGH DUPLICATION**: Vritti computed independently in `core/smi/vritti_mapping.py`, `sovereign/reasoning_kernel.py`, `sovereign/vritti.py`, `inference/sovereign_state_monitor.py`
- These parallel implementations are NOT aliases — each has independent computation logic
- No single canonical vritti authority despite chitta_vritti/ being the most complete

**Priority:** CORE RUNTIME CRITICAL
**Action:** Wire now — establish chitta_vritti/ as the canonical vritti authority; refactor duplicates in sovereign/, inference/, core/smi/ to consume from here

---

### 3.5 `identity/` — Identity Signature Classification

**Intended Role:**
Classify session-level identity signatures from multi-turn session context. Detects 8 identity types (self_anchoring, self_expansion, self_fragmentation, self_suppression, self_integration, self_dissonance, self_discovery, neutral_identity) via rule-based feature extraction.

**Actual Implementation Status:** PRODUCTION-GRADE (847 LOC across 2 files)
- `compute_identity_signature()`: Main entry — extracts real metrics from session_summary
- 7 rule groups (A-G), each with multi-condition detection:
  - `_detect_self_anchoring()`: coherence >= 0.65, persona_drift <= 0.40, rising_coherence
  - `_detect_self_integration()`: breakthrough + stabilization events, HRM+LAM synergy (highest priority, confidence 0.85-0.95)
  - `_detect_self_fragmentation()`: persona_drift > 0.55, oscillating coherence via sign-change counting
- Deterministic tiebreaking by confidence then priority order
- Real feature extraction: coherence_timeline, mapper_sets, events, temporal arcs
- Confidence is NOT constant — scaled by feature magnitudes (e.g., `0.70 + min(current_coherence * 0.15, 0.15)`)

**Runtime Wiring Status:** FULLY ACTIVE
- Called from `symbolu_core/mechanical/pipeline/session_processing.py` → `_process_identity_signature()`
- Lazy-loaded: `from agentic.identity.identity_signature_engine import compute_identity_signature`
- Sets `ctx.identity_signature` for downstream consumption
- Consumed by: trading guardrail engine, motivation flow engine
- Wrapped in fail-safe try/except — pipeline continues if identity processing fails

**Key Dependencies:**
- Depends on: standard library only (fully self-contained)
- Depended on by: session_processing pipeline, motivation/ (uses identity_signature as input), trading guardrails
- Sequential dependency: must run BEFORE motivation/

**Main Gaps:**
- No tier-specific configuration variants (unlike chitta_vritti which has Consumer/Enterprise)
- Only 2 external import sites — could be consumed more broadly
- No evaluation framework (unlike chitta_vritti's extensive evaluation/)

**Priority:** CORE RUNTIME CRITICAL
**Action:** Document only — fully wired and functioning; consider adding tier configs and evaluation harness in future

---

### 3.6 `motivation/` — Motivation Flow Classification

**Intended Role:**
Classify session-level motivation flow from multi-turn context + identity signature. Detects 8 motivation types (hope_driven, fear_driven, avoidance_driven, expansion_driven, stabilization_driven, overcorrection, assertion_driven, ambiguous_motivation).

**Actual Implementation Status:** PRODUCTION-GRADE (865 LOC across 2 files)
- `compute_motivation_flow()`: Main entry — structurally parallel to identity engine
- 7 rule groups (A-G) with multi-condition detection:
  - `_detect_hope_driven()`: coherence_delta > 0.12, breakthrough_events, low_volatility < 0.45
  - `_detect_fear_driven()`: fragmentation_events, high_volatility > 0.55, defensive_patterns (LCM > 40% without LAM)
  - `_detect_overcorrection()`: sharp_oscillations >= 2 sign changes, rapid_mapper_flips >= 2
- Same deterministic tiebreaking pattern as identity/
- Takes `identity_signature` as input feature — couples the two engines

**Runtime Wiring Status:** FULLY ACTIVE
- Called from `session_processing.py` → `_process_motivation_flow()`
- Runs AFTER identity classification (sequential dependency)
- Sets `ctx.motivation_profile` in pipeline context
- Consumed by: trading guardrails for formula-aware safety checks
- Fail-safe try/except wrapper

**Key Dependencies:**
- Depends on: standard library, identity/ (receives identity_signature)
- Depended on by: trading guardrails, session context
- No circular dependencies

**Main Gaps:**
- Same limitations as identity/ — no tier configs, no evaluation framework
- Structurally very similar to identity/ — potential for shared base class or engine pattern
- Only consumed by trading guardrails — could inform more downstream decisions

**Priority:** CORE RUNTIME CRITICAL
**Action:** Document only — fully wired and functioning; consider shared engine abstraction with identity/ in future

---

### 3.7 `temporal/` — Temporal Tracking & Cross-Domain Intelligence

**Intended Role:**
Sliding-window temporal tracking of consciousness state evolution, cross-domain pattern detection (13 universal patterns), and stateful pattern lifecycle management (P38). Provides temporal trend analysis, state classification, and pattern sequence matching.

**Actual Implementation Status:** SUBSTANTIAL (2,328 LOC across 6 files)
- `TemporalBhavaTracker` (841 LOC): Sliding-window tracking with SMI, bhava_id, kosha, ontology. Linear regression trends. State classification (TENSE/RECOVERING/STABLE). Recovery pattern detection.
- `CrossDomainIntelligence` (538 LOC): 13 universal patterns across 6 domains (finance, medicine, psychology, education, legal, corporate). Weighted rule-based scoring from SMI, bhava, kosha, ontology + temporal trends.
- `CrossDomainPatternTracker` (P38, 674 LOC): Stateful wrapper — pattern onset/sustain/exit/recurrence lifecycle. 8 hand-curated sequences (escalation/entrenchment/resolution). Full/partial sequence matching. 10D aspect vector derivation.
- `PatternSequenceRules` (149 LOC): 8 locked sequences — frozen, no inference
- `PatternAspectDerivation` (128 LOC): 10-dimensional aspect vector (ENTROPY, CAUSALITY, AGENCY, BALANCE, FLOW, CONSTRAINT, EMERGENCE, FEEDBACK, HIERARCHY, THRESHOLD)

**Runtime Wiring Status:** ACTIVE (conditional)
- Integrated into LAM pipeline via `symbolu_core/mechanical/lam/` shim
- Singleton instances: `TemporalBhavaTracker`, `CrossDomainIntelligence`
- Called by `maybe_run_lam()` when `use_lam=True` or tension > 0.4
- Outputs stored in `ctx.lam_map`
- Depends on `symbolu_core.formulas.*` (external: SMI, bhava_gap, tension_corridor, vritti_momentum)

**Key Dependencies:**
- Depends on: `symbolu_core.formulas.*` (resonance, TTOR, SMI, phase 14 extensions)
- Depended on by: LAM pipeline, 20+ test files
- No circular dependencies

**Main Gaps:**
- Temporal is distributed across multiple modules (temporal/, core/coherence/temporal_arc_tracer.py, core/bhava/temporal_bhava.py) — NOT duplication but progressive layering that could benefit from clearer hierarchy
- Pattern sequences are hand-curated and frozen — no mechanism to learn new sequences
- CDI pattern scoring uses weighted rules — no feedback on accuracy

**Priority:** CORE RUNTIME CRITICAL (when LAM enabled)
**Action:** Wire now — consider always-on temporal tracking (not just when tension > 0.4); unify temporal hierarchy documentation

---

### 3.8 `guna_modulation/` — Entropy Modulation & State Evolution

**Intended Role:**
Compute output intensity modulation via canonical equation `OUTPUT = BASE × E` where `E = G × P × T` (Guna coefficient × Policy scalar × Tier scalar). Also provides bounded state evolution (v2.7), mirror balance detection, causal layer analysis, concept readiness monitoring, and experimental reasoning (DPO, Tree-of-Thoughts, MCTS).

**Actual Implementation Status:** VERY EXTENSIVE (14,678 LOC across 25 files)
- **Core (production):**
  - `EntropyModulationEngine` (541 LOC): Canonical E = G×P×T with tier configs
  - `StateEvolutionEngine` (948 LOC): v2.7 bounded θ_t update with 3 modes (IMMEDIATE, LOW_PASS_FILTER, BAYESIAN)
  - `SignalWiring` (758 LOC): Operator-configurable entropy (GUNA/DIMENSIONAL/KOSHA) and motion (SEMANTIC/STRUCTURAL/EXPERIENTIAL/COMPOSITE) signals
  - `GunaDerviation` (309 LOC): Sattva/Rajas/Tamas vector computation
  - `PipelineIntegration` (475 LOC): Pipeline integration layer
- **Advanced (v2.7+):**
  - `MirrorBalance` (1,941 LOC): Self-referential balance detection via signal mirrors
  - `RecursiveSelfImprovement` (908 LOC): Belief tracking + failure pattern detection (NOT learning)
  - `CausalLayer` (888 LOC): Do-calculus on fixed pipeline DAG (SIGNAL→SEMANTIC→GUNA→FUSION→STATE→CALIBRATION→OUTPUT)
  - `ConceptReadiness` (836 LOC): Coherence/entropy/drift monitoring for safe concept detection
  - `ExperimentalReasoning` (841 LOC): DPO, ToT, MCTS — explicitly marked "No learning. Exploration only."

**Runtime Wiring Status:** OPTIONALLY WIRED (feature-flagged)
- Activated via `v2_7_enabled` flag
- NOT wired into main pipeline by default
- Can run in DISABLED mode (identity/no-op operation)
- Only 1 external import found: `symbolu_training/training/unified/training_state.py` (VarianceConfidence)
- Standard library only — fully self-contained, no ML/LLM dependencies

**Key Dependencies:**
- Depends on: standard library only (dataclasses, typing, enum, math)
- Depended on by: training_state (optional), pipeline when v2_7 enabled
- All formulas hand-specified, deterministic, invertible

**Main Gaps:**
- **HIGH**: Guna derivation duplicated in `sovereign/guna.py` (training) and `inference/guna_inference.py` (inference) — three independent guna implementations
- `posture/_guna_mapping.py` is a 4th guna variant (deliberately hidden/private)
- MirrorBalance, CausalLayer, ConceptReadiness are sophisticated but have zero external consumers
- ExperimentalReasoning (DPO/ToT/MCTS) is exploration-only with no runtime path
- v2.7 state evolution could replace heuristic approaches elsewhere but isn't connected

**Priority:** IMPORTANT BUT UNDERWIRED
**Action:** Wire now (core E=G×P×T) / refactor first (consolidate guna derivation) / wire later (advanced modules)

---

### 3.9 `dha/` — Delivery Harmonization Algorithm

**Intended Role:**
Compute delivery modulation `D = T × I × R` (Tier scalar × Intensity × Restraint). Determines tone weights (sweet/jolt/metaphor), intensity from coherence+motion, and restraint from contradiction signals. Sole authority for tone/delivery modulation.

**Actual Implementation Status:** COMPLETE (2,727 LOC across 8 files)
- `DHAEngine` (440 LOC): Core `D = T × I × R` with deterministic softmax tone logits
- `SignalExtraction` (727 LOC): Priority-ordered signal mapping from 4 sources (MLCR → Observables → computed → defaults). Complete audit trail of signal sources.
- `DHAMath` (499 LOC): All closed-form math — entropy normalization (3 modes), softmax3, intensity/restraint formulas
- `DHAConfig` (351 LOC): Immutable tier configs (Enterprise T1: 1.0, T2: 0.9, Consumer: 0.85)
- `Integration` (324 LOC): Pipeline integration stage with graceful no-op when disabled
- Standard library only, no ML dependencies

**Runtime Wiring Status:** INTEGRATED (optional, lazy-loaded)
- Disabled by default (`enabled=False`)
- Activated via `dha_formula_enabled` flag in request metadata
- Called from orchestrator after Fusion, before Renderer
- Lazy-loaded via `@lru_cache(maxsize=1)` in orchestrator
- Tier-specific config selection based on request metadata
- `posture/modulation.py` calls `maybe_run_dha()` internally

**Key Dependencies:**
- Depends on: standard library only (fully self-contained)
- Depended on by: pipeline orchestrator, posture/modulation
- No circular dependencies; clean separation from guna_modulation (DHA owns tone, guna_mod owns intensity)

**Main Gaps:**
- Disabled by default — most users never see DHA modulation
- Signal extraction has graceful defaults for missing signals — could mask real signal gaps
- No feedback loop to validate whether tone weights improve output quality

**Priority:** IMPORTANT BUT UNDERWIRED
**Action:** Wire now — consider enabling by default (at least Tier 1 diagnostic mode); validate signal extraction coverage

---

### 3.10 `llm/` — LLM Interface Boundary Layer

**Intended Role:**
One-way authority boundary between Symbol-U Core (deterministic) and LLM Layer (optional renderer). Enforces contract-driven interface with strict validation preventing the LLM from mutating governance state.

**Actual Implementation Status:** SUBSTANTIAL (1,493 LOC across 4 files)
- `types.py` (222 LOC): Frozen dataclasses — `RenderRequest` → `RenderResponse`. Forbidden access patterns: `{"score", "rank", "search_trace", "policy_internal"}`. 7 failure modes (FM-1 through FM-6).
- `providers.py` (681 LOC): `LLMClient` with tier-based model selection (Consumer→Haiku/Flash, Power→Sonnet/Pro, Admin→Sonnet/Pro). Two async providers (Anthropic, Google). Lazy loading, graceful degradation if API keys missing.
- `validator.py` (477 LOC): 8 independent validators (INV-1 through INV-7). Enforces: no new tokens, no new layers, no constraint mutation, no governance override. Pattern-based detection + hash integrity checks.

**Runtime Wiring Status:** FULLY ACTIVE
- Imported by `symbolu_core/renderer/render_entry.py` (core rendering path)
- Imported by `agentic_framework/llm_adapters.py`
- Imported by `api/unified_api.py`
- Validator runs on every LLM response in the fusion rendering path

**Key Dependencies:**
- Depends on: anthropic SDK, google-generativeai SDK (both optional)
- Depended on by: renderer, agentic_framework, api/
- No circular dependencies

**Main Gaps:**
- Provider layer is straightforward but not pluggable (hardcoded Anthropic + Google)
- No streaming support visible
- Validator patterns are static — no mechanism to evolve validation rules

**Priority:** CORE RUNTIME CRITICAL
**Action:** Document only — fully wired, functioning as intended boundary layer

---

### 3.11 `api/` — External API & Observability Layer

**Intended Role:**
Zero-LLM, deterministic, rule-based API functions for coherence metrics and unified pipeline output. Presentation layer that observes but never modifies pipeline behavior.

**Actual Implementation Status:** SUBSTANTIAL (2,120 LOC across 3 files)
- `unified_api.py` (1,742 LOC): `UnifiedOutput` dataclass combining 50+ pipeline fields. `build_unified_output()` extracts from all layers: fusion (symbolic/practical/mirror), DHA insights, TTOR routing, MLCR activation, mapper profiles, entropy measures, coherence report, session memory, identity signature, motivation profile.
- `coherence_api.py` (360 LOC): `get_coherence_report()` → JSON, `get_turn_summary()` (single-turn metadata), `get_multi_turn_overview()` (trend analysis + rule-based recommendations). Slope calculation for drift/temporal_arc/volatility.

**Runtime Wiring Status:** FULLY ACTIVE
- Imported by `symbolu_core/service/api_server.py` (HTTP endpoints)
- Called on every pipeline execution for output serialization
- Exposed via `/symbolu/analyze` endpoint
- Dashboard-ready bands (stable/unstable, low/high drift) from Phase 20+

**Key Dependencies:**
- Depends on: llm/ types, pipeline context types
- Depended on by: api_server (HTTP layer), pipeline output
- No circular dependencies

**Main Gaps:**
- Purely observational — no ability to feed API insights back into pipeline decisions
- `get_multi_turn_overview()` has rule-based recommendations that could inform session policy but don't

**Priority:** CORE RUNTIME CRITICAL
**Action:** Document only — fully wired; consider feedback path from multi-turn insights to session policy in future

---

### 3.12 `core/` — Core Computation Engine (Mixed: Facades + Real Engines)

**Intended Role:**
Central computation engine for the Symbol-U pipeline. Intended as the canonical home for coherence, entropy, SMI, stitching, bhava, consciousness, and predictive engines.

**Actual Implementation Status:** MIXED — dead facades + real subdirectory engines
- **DEAD FACADES (never called):**
  - `interface.py`: All methods raise `NotImplementedError("Symbol-U formula to be added later.")`
  - `pipeline.py`: All methods raise `NotImplementedError`
  - `__init__.py`: Exports only CoreInterface + CorePipeline (the dead facades)
- **REAL ENGINES (active):**
  - `coherence/`: CoherenceEngine, CoherenceState, temporal_arc_tracer — ACTIVE in pipeline
  - `smi/`: SMIEngine, aspect mapping, acoustic mapping — ACTIVE in pipeline
  - `stitching/`: StitchingEngine for candidate scoring — ACTIVE in pipeline
  - `bhava/`: BhavaGeometry, TemporalBhava — ACTIVE in pipeline
  - `consciousness/`: UCFResolver, UCFFormula — ACTIVE
  - `predictive/`: PredictivePersonaDriftReport, IdentityResonanceMemory — ACTIVE
  - `regulators/`: Three-force decision framework — ACTIVE
  - `energy/`: Energy word detection — SUPPORTING
- **INFRASTRUCTURE:**
  - `constants.py` (8 KB): Formula constants used across engines
  - `models.py` (2.9 KB): Shared data types (SyllableAnalysis, WordAnalysis, EntropyState, BhavaState)
  - `formula_drift_tests/`: 19 integration test files for formula regression
  - `generation_gate.py`, `ledger_generation_attest.py`: Generation safety checks

**Runtime Wiring Status:** SPLIT
- Real engines (coherence/, smi/, stitching/, bhava/) are FULLY ACTIVE on main pipeline
- Top-level facades (interface.py, pipeline.py) are DEAD CODE — never instantiated
- `core/entropy/` is a DEAD STUB — replaced by `agentic/entropy/` in practice
- `core/smi/vritti_mapping.py` contains duplicate vritti logic (should delegate to chitta_vritti/)

**Key Dependencies:**
- Depends on: standard library, symbolu_core.formulas
- Depended on by: symbolu_core/mechanical/pipeline/*, agentic_framework/*, api/
- `core/entropy/` creates confusion — imported nowhere but name collides with `agentic/entropy/`

**Main Gaps:**
- **MEDIUM**: Top-level facade is dead code creating false architectural impression
- `core/entropy/` should be removed or redirected to `agentic/entropy/`
- `core/smi/vritti_mapping.py` duplicates chitta_vritti/ logic
- No unified export from core/ that reflects what's actually active vs dead

**Priority:** CORE RUNTIME CRITICAL (subdirectory engines) / NEEDS CONSOLIDATION (facades)
**Action:** Refactor first — remove dead facades (interface.py, pipeline.py); remove or redirect core/entropy/; update __init__.py to export real engines; consolidate vritti_mapping into chitta_vritti/

---

## 4. Cross-Cutting Observations

### 4.1 Duplicated Logic

| Concept | Locations | Canonical Module | Duplicates |
|---------|-----------|-----------------|------------|
| **Vritti (5 cognitive modes)** | 5 modules | `chitta_vritti/` | `core/smi/vritti_mapping.py`, `sovereign/vritti.py`, `sovereign/reasoning_kernel.py` (VrittiGate), `inference/sovereign_state_monitor.py` (32D slice [17:22]) |
| **Guna (S/R/T)** | 4 modules | `guna_modulation/guna_derivation.py` | `sovereign/guna.py` (16D training), `inference/guna_inference.py` (approximation), `posture/_guna_mapping.py` (private, deliberate) |
| **Entropy computation** | 3 modules | `entropy/entropy_engine.py` | `core/entropy/` (dead stub), `guna_modulation/entropy_modulation_engine.py` (complementary — modulation intensity, not gating) |
| **Temporal state** | 3 locations | `temporal/temporal_bhava_tracker.py` | `core/coherence/temporal_arc_tracer.py` (arc scoring), `core/bhava/temporal_bhava.py` (state abstraction) — progressive layering, not true duplication |

**Verdict:** Vritti and Guna duplication are the most damaging. Each independent implementation can drift, producing inconsistent state across training, inference, and runtime layers.

### 4.2 Approximations Replacing Intended Modules

| Intended Module | What's Actually Used Instead | Where |
|----------------|------------------------------|-------|
| `inference/InferenceManager` | Direct model.generate() calls without orchestration | Generation paths bypass the fully-built manager |
| `entropy/` Tier 3 blocking | No blocking gate exists on output path | Pipeline has no entropy-based output blocking |
| `guna_modulation/` E=G×P×T | Heuristic intensity scaling in renderer | Renderer uses approximate intensity without canonical formula |
| `guna_modulation/MirrorBalance` | No mirror balance detection at runtime | Asymmetry goes undetected |
| `guna_modulation/CausalLayer` | No causal attribution in pipeline | Debugging uses log-tracing instead of do-calculus |

### 4.3 Architecture Drift

1. **Sovereign state split**: Training produces 128D state; inference monitors 32D state. No explicit projection/bridge exists. These evolved independently and now represent different abstractions of "sovereign state."

2. **Core facade abandoned**: `core/interface.py` and `core/pipeline.py` were intended as the unified API for all core engines, but real engines bypassed them and are imported directly from subdirectories. The facade became dead code.

3. **Entropy authority fragmented**: The architecture intends `entropy/` as the entropy authority, but `core/entropy/` exists as a confusing dead stub, and `guna_modulation/` has its own entropy modulation path. The boundaries between "entropy gating" and "entropy-based modulation" are clear in code but not in architecture docs.

4. **Inference orphaned from pipeline**: `inference/` was designed as the inference-time counterpart to `sovereign/` (training), but the main pipeline never adopted `InferenceManager`. Instead, generation happens through direct model calls, leaving the orchestrator unused.

### 4.4 Integration Bottlenecks

1. **Session processing is the main integration point** — identity, motivation, and chitta_vritti all wire through `session_processing.py`. Adding more modules here requires careful ordering and fail-safe wrapping.

2. **Feature flags gate too much** — dha, guna_modulation, and temporal are all behind flags. This means the "full architecture" is rarely exercised as a complete system. Integration testing of the full stack requires all flags enabled.

3. **No unified state bus** — modules pass state via pipeline context (`ctx`) attributes set independently. There's no schema or contract for what `ctx` must contain after each phase, making it fragile to reordering.

---

## 5. Top 5 Wiring Opportunities

### Opportunity 1: CONNECT InferenceManager to Generation Path
**Module:** `inference/`
**Current state:** Fully built orchestrator (1,290 LOC, 5 modes) that nothing calls
**Wire to:** Model generation path in symbolu_core
**Impact:** Enables sovereign scoring, CSR safety guards, metacognitive monitoring, and binding cache during inference — all currently bypassed
**Prerequisite:** Verify InferenceManager's 5 modes (FAST/STANDARD/FULL/SAFE/SOVEREIGN) don't degrade generation latency
**Priority:** P0 — this is the single largest wiring gap

### Opportunity 2: BRIDGE Sovereign 128D → Inference 32D State
**Module:** `sovereign/` → `inference/`
**Current state:** Training produces 128D state; inference monitors 32D state; no projection exists
**Wire to:** Create explicit state projection layer (128D → 32D) as part of checkpoint export
**Impact:** Unifies training and inference representations; enables inference/ modules to consume real trained state instead of approximations
**Prerequisite:** Define canonical 32D slice semantics relative to 128D decomposition [16D Guna | 32D S-Signal | 48D R-Signal | 32D C-Signal]
**Priority:** P0 — foundational for inference/ to be meaningful

### Opportunity 3: ENABLE DHA and Entropy Gating by Default
**Module:** `dha/`, `entropy/`
**Current state:** Both fully implemented but disabled by default
**Wire to:** Enable DHA in diagnostic mode (Tier 1) by default; enable entropy gating on output path
**Impact:** Every request gets tone/delivery modulation and coherence gating without opt-in. Currently, most users get no DHA/entropy benefit.
**Prerequisite:** Validate that diagnostic-mode DHA adds negligible latency; ensure entropy Tier 1 (diagnostic only) has no behavioral side effects
**Priority:** P1 — low risk, high observability gain

### Opportunity 4: CONSOLIDATE Vritti to Single Authority
**Module:** `chitta_vritti/` (canonical) vs 4 duplicates
**Current state:** 5 independent vritti implementations
**Wire to:** Make `chitta_vritti/` the single computation source; `sovereign/`, `inference/`, `core/smi/` consume its output
**Impact:** Eliminates state inconsistency across layers; simplifies maintenance; ensures runtime vritti matches training vritti
**Prerequisite:** Audit whether sovereign/reasoning_kernel.py VrittiGate needs training-time gradients through vritti (if so, keep sovereign/ version but sync formulas)
**Priority:** P1 — architectural hygiene with real consistency benefits

### Opportunity 5: WIRE guna_modulation E=G×P×T into Renderer
**Module:** `guna_modulation/`
**Current state:** Canonical intensity formula exists but renderer uses heuristic scaling
**Wire to:** Replace heuristic intensity in renderer with `EntropyModulationEngine.compute_output_intensity()`
**Impact:** Principled, tier-aware, policy-scaled output intensity instead of ad-hoc scaling
**Prerequisite:** Ensure E=G×P×T produces values compatible with current renderer expectations; add integration test
**Priority:** P1 — replaces heuristic with designed formula

---

## 6. Concrete Next-Step Recommendations

### Immediate (Wire Now)

| # | Action | Files to Modify | Estimated Scope |
|---|--------|----------------|-----------------|
| 1 | Connect `InferenceManager` to generation path | `symbolu_core/ontological/symbolu12_llm.py`, `inference/manager.py` | Medium — wire existing orchestrator, add config flag |
| 2 | Enable DHA in Tier 1 diagnostic mode by default | `dha/config.py`, orchestrator pipeline config | Small — flip default flag |
| 3 | Enable entropy gating on output path | `entropy/entropy_engine.py`, pipeline output stage | Small — add gating check at output boundary |
| 4 | Wire `guna_modulation/` E=G×P×T into renderer | Renderer intensity path, `guna_modulation/pipeline_integration.py` | Medium — replace heuristic with formula call |

### Refactor First

| # | Action | Files to Modify | Estimated Scope |
|---|--------|----------------|-----------------|
| 5 | Build sovereign 128D → inference 32D state bridge | New: `sovereign/inference_bridge.py`, checkpoint export | Medium — define projection, add to training export |
| 6 | Consolidate vritti to `chitta_vritti/` as canonical | `core/smi/vritti_mapping.py`, `sovereign/vritti.py`, `inference/sovereign_state_monitor.py` | Medium — redirect imports, deprecate independent computations |
| 7 | Consolidate guna to `guna_modulation/guna_derivation.py` as canonical | `sovereign/guna.py`, `inference/guna_inference.py` | Medium — same pattern as vritti consolidation |
| 8 | Clean up `core/` facades | `core/__init__.py`, `core/interface.py`, `core/pipeline.py` | Small — remove dead code, update exports |
| 9 | Remove or redirect `core/entropy/` | `core/entropy/` | Small — delete dead stub |

### Wire Later

| # | Action | Rationale |
|---|--------|-----------|
| 10 | `guna_modulation/MirrorBalance` | Sophisticated (1,941 LOC) but needs consumer; wire after core E=G×P×T is live |
| 11 | `guna_modulation/CausalLayer` | Do-calculus auditing; wire after pipeline observability is improved |
| 12 | `inference/` Appendix F stages | Research-grade; mature individual stages before wiring |
| 13 | `temporal/` always-on mode | Currently tension-gated; consider enabling baseline temporal tracking for all requests |

### Document Only (No Wiring Change)

| # | Module | Reason |
|---|--------|--------|
| 14 | `identity/` | Fully wired, functioning correctly |
| 15 | `motivation/` | Fully wired, functioning correctly |
| 16 | `llm/` | Fully wired, functioning as boundary layer |
| 17 | `api/` | Fully wired, functioning as observability layer |

### Not Worth Wiring Now

| # | Module/Component | Reason |
|---|-----------------|--------|
| 18 | `guna_modulation/ExperimentalReasoning` | Explicitly marked "No learning. Exploration only." — research tool, not runtime |
| 19 | `guna_modulation/RecursiveSelfImprovement` | Observational tracking only — no actionable output |
| 20 | `core/interface.py` + `core/pipeline.py` | Dead facades — delete rather than wire |

---

## Summary Classification Table

| Folder | Priority | Status | Action |
|--------|----------|--------|--------|
| `chitta_vritti/` | CORE RUNTIME CRITICAL | Fully active | Wire now (make canonical vritti authority) |
| `identity/` | CORE RUNTIME CRITICAL | Fully active | Document only |
| `motivation/` | CORE RUNTIME CRITICAL | Fully active | Document only |
| `llm/` | CORE RUNTIME CRITICAL | Fully active | Document only |
| `api/` | CORE RUNTIME CRITICAL | Fully active | Document only |
| `core/` | CORE RUNTIME CRITICAL / NEEDS CONSOLIDATION | Active engines + dead facades | Refactor first |
| `temporal/` | CORE RUNTIME CRITICAL (when LAM) | Conditionally active | Wire now (consider always-on) |
| `sovereign/` | CORE RUNTIME CRITICAL (training) | Training-active | Refactor first (build inference bridge) |
| `entropy/` | IMPORTANT BUT UNDERWIRED | Active but limited | Wire now (output gating) |
| `dha/` | IMPORTANT BUT UNDERWIRED | Implemented, disabled | Wire now (enable default) |
| `inference/` | IMPORTANT BUT UNDERWIRED | Built but orphaned | Wire now (core) / wire later (Appendix F) |
| `guna_modulation/` | IMPORTANT BUT UNDERWIRED | Optional, feature-flagged | Wire now (E=G×P×T) / wire later (advanced) |

---
---

# Phased Wiring Roadmap

**Date:** 2026-04-03
**Purpose:** Action-oriented integration plan to turn partially-connected modules into a coherent runtime architecture
**Method:** Grounded in code inspection of governance control plane, pipeline orchestrator, renderer path, and session processing

---

## 1. Executive Summary

The agentic architecture has **two critical wiring deficits**:

1. **The governance control plane uses crude approximations** where real modules exist. GovernanceService, SafeMCPGateway, and JEPA governance construct fake vritti distributions from 2-3 scalar signals (`approximate_vritti()`) and fake OLM layer weights from 6 scalars (`approximate_layer_weights()`). Meanwhile, `chitta_vritti/` computes production-grade 5-mode distributions and `sovereign/` manages a 128D consciousness tensor — neither feeds governance.

2. **The output modulation path is structurally incomplete.** DHA computes tone weights but the renderer never applies them. `guna_modulation/` has a canonical intensity formula (`E = G×P×T`) but the renderer uses no intensity scaling at all. Entropy signals are computed by MLCR but never gate or modulate output.

**The governance plane is leaving ~60% of available signal capacity unused.** The output path has formulas that produce values nothing consumes.

### What This Roadmap Does

Sequences 20 concrete wiring actions across 5 phases:
- **Phase 0**: Remove dead code and consolidate duplicated logic (prerequisite cleanup)
- **Phase 1**: Replace governance approximations with real signal bridges (highest leverage)
- **Phase 2**: Wire output modulation path (DHA + guna_modulation + entropy into renderer)
- **Phase 3**: Connect session-level enrichments to governance (identity, motivation, temporal)
- **Phase 4**: Advanced modules and experimental integration (MirrorBalance, CausalLayer, Appendix F)

---

## 2. Current Architectural Bottlenecks

### Bottleneck 1: Governance Runs on Approximations

**Where:** `agentic_framework/jepa_governance.py` lines ~120-180

GovernanceService calls `jepa_governance_check()` which constructs:
- `approximate_layer_weights(quality, coherence, consistency, alignment)` → fake 12-layer OLM weights from 4 scalars
- `approximate_vritti(quality, coherence, confidence)` → fake 5-vritti distribution from 3 scalars

These approximations drive:
- JEPA regime classification (NORMAL / PROCESS_DRIFT / SEMANTIC_SHIFT / DUAL_ANOMALY)
- Domain policy evaluation (vritti × ontology × regime → action mode)
- Shadow AI semantic mismatch escalation

**Impact:** Governance decisions are made on proxy signals while real signals exist but are disconnected.

**What exists but isn't consumed:**
| Real Module | Signal It Produces | Currently Used Instead |
|-------------|-------------------|----------------------|
| `chitta_vritti/` | 5-vritti distribution (pramana, viparyaya, vikalpa, smrti, nidra) | `approximate_vritti()` from 3 scalars |
| `sovereign/` | 128D consciousness tensor [16D Guna \| 32D S-Signal \| 48D R-Signal \| 32D C-Signal] | `approximate_layer_weights()` from 4 scalars |
| `entropy/` | Cross-domain entropy with tier gating (ALLOW/MODULATE/BLOCK) | Raw `coherence_score` only |
| `identity/` | 8-type identity classification with confidence | Not consumed by governance at all |
| `motivation/` | 8-type motivation classification | Not consumed by governance at all |

### Bottleneck 2: Output Path Has No Intensity Modulation

**Where:** `symbolu_core/mechanical/pipeline/orchestrator.py` Stage 4 (DHA) → Stage 5 (Renderer)

Pipeline stage ordering:
```
MLCR → HRM/LCM/LAM → Persona → Fusion → DHA → Renderer → Output
```

DHA (Stage 4) computes `DHAResult` with:
- `D` (delivery factor), `tone_weights` (sweet/jolt/metaphor), `intensity`, `restraint`

But the Renderer (Stage 5) **never reads these values**:
- `FusionRenderer.render()` has no `intensity` parameter
- `VarnaHybridRenderer` has no entropy-driven scaling
- `IntegratedRenderedOutput` has no `delivery_factor` field
- Formula DHA (guna_modulation E=G×P×T) is disabled by default and its output is stored in `adaptation_notes` — a dead-letter field

**Impact:** DHA computes delivery modulation that nothing applies. The renderer produces output with no principled intensity/tone control.

### Bottleneck 3: Vritti Duplication Prevents Canonical Authority

**Where:** 5 independent vritti implementations

| Location | What It Computes | Used By |
|----------|-----------------|---------|
| `chitta_vritti/vritti.py` | Full 5-mode with real math (coherence × entropy × motion) | Presentation, hybrid router |
| `core/smi/vritti_mapping.py` | Independent VrittiMapper | SMI engine |
| `sovereign/vritti.py` | Training-time vritti state | Sovereign loss |
| `sovereign/reasoning_kernel.py` | VrittiGate in SRK | Training (SRK) |
| `inference/sovereign_state_monitor.py` | 32D slice [17:22] | Inference state (orphaned) |

No module trusts another's vritti output. Each computes its own. This means governance could use `chitta_vritti/` output, but `sovereign/` and `inference/` would still diverge.

### Bottleneck 4: No Pipeline Context Contract

**Where:** `PipelineContext` dataclass in `symbolu_core/mechanical/pipeline/models.py`

Modules set `ctx` attributes independently:
- `ctx.identity_signature` set by session_processing
- `ctx.motivation_profile` set by session_processing
- `ctx.dha` set by DHA stage
- `ctx.coherence_state` set by coherence observer

But there's no schema defining what must be present after each phase. Adding new module outputs (entropy gate result, guna modulation state) to `ctx` requires:
1. Adding the field to PipelineContext
2. Setting it in the right pipeline stage
3. Ensuring downstream consumers handle `None` (not yet computed)

This isn't blocking but makes wiring fragile. Every new integration requires defensive `Optional` handling.

---

## 3. Folder-by-Folder Action Classification

| Folder | Action | Category | Rationale |
|--------|--------|----------|-----------|
| `chitta_vritti/` | **Wire immediately** | Semantic-state core | Replace `approximate_vritti()` in JEPA governance with real CV output. Coupling matrix already imported but fed fake data. |
| `entropy/` | **Wire immediately** | Governance control support | Tier-aware gating logic (ALLOW/MODULATE/BLOCK) is fully built. Add to ConfidenceSignals and output gate. |
| `dha/` | **Wire immediately** | Delivery/output modulation | Tone weights and delivery factor computed but never consumed by renderer. Flip default to enabled. |
| `guna_modulation/` | **Wire immediately** (core E=G×P×T) | Delivery/output modulation | Replace heuristic intensity with canonical formula. Advanced modules (MirrorBalance, CausalLayer) wait. |
| `identity/` | **Prepare interfaces now, wire later** | Governance control support | Fully active in session processing but governance doesn't consume it. Add to ConfidenceSignals as enrichment. |
| `motivation/` | **Prepare interfaces now, wire later** | Governance control support | Same as identity/ — computed but governance-blind. Wire after identity/ proves the pattern. |
| `temporal/` | **Prepare interfaces now, wire later** | Semantic-state core | Active in LAM but governance doesn't consume temporal signals. Wire after JEPA gets real vritti/OLM. |
| `sovereign/` | **Refactor then wire** | Semantic-state core | 128D state should project to inference 32D. Vritti/guna duplicates must consolidate first. |
| `inference/` | **Refactor then wire** | Runtime execution support | InferenceManager is built but orphaned. Needs sovereign bridge (128D→32D) before it's meaningful. |
| `core/` | **Merge/deprecate** (facades only) | Infrastructure layer | Delete dead facades. Redirect core/entropy/ to entropy/. Consolidate core/smi/vritti_mapping into chitta_vritti/. Real subdirectory engines stay. |
| `llm/` | **No action needed** | Infrastructure layer | Fully wired boundary layer. Functioning correctly. |
| `api/` | **No action needed** | Infrastructure layer | Fully wired observability. Functioning correctly. |

---

## 4. Phased Wiring Roadmap

### Phase 0: Prerequisite Cleanup (Remove Dead Code, Consolidate Duplicates)

**Goal:** Eliminate confusion from dead code and establish canonical authorities for vritti and guna before wiring real signals into governance.

**Folders in scope:** `core/`, `chitta_vritti/`, `sovereign/`, `inference/`, `guna_modulation/`

**Actions:**

| # | Action | Files | Why First |
|---|--------|-------|-----------|
| 0.1 | Delete `core/interface.py` and `core/pipeline.py` (dead facades) | `core/interface.py`, `core/pipeline.py`, `core/__init__.py` | Dead code creates false architectural impression. No imports exist. Safe to delete. |
| 0.2 | Delete or redirect `core/entropy/` stub to `entropy/` | `core/entropy/` directory | Dead stub (all NotImplementedError). Collides with real `entropy/` module. |
| 0.3 | Update `core/__init__.py` to export real engines | `core/__init__.py` | Currently exports only dead facades. Should export CoherenceEngine, SMIEngine, etc. |
| 0.4 | Make `chitta_vritti/` the canonical vritti authority | `core/smi/vritti_mapping.py` | Replace VrittiMapper's independent computation with delegation to `chitta_vritti/vritti.py`. Keep interface, change implementation. |
| 0.5 | Sync vritti formulas in `sovereign/vritti.py` | `sovereign/vritti.py` | Training-time vritti must use same formulas as runtime. Import from `chitta_vritti/` or explicitly document why formulas differ (gradient requirements). |
| 0.6 | Make `guna_modulation/guna_derivation.py` the canonical guna authority | `inference/guna_inference.py` | Replace independent guna approximation with import from canonical module. `sovereign/guna.py` stays separate (needs nn.Module for gradients) but formulas should be synced. |

**Prerequisites:** None — this is the foundation.

**Risks:**
- `sovereign/vritti.py` and `sovereign/guna.py` may need training-time gradients through their computations. If so, they cannot simply import from non-PyTorch modules. **Mitigation:** Keep sovereign/ versions but extract shared formula constants into a `_shared_formulas.py` that both consume.
- `core/smi/vritti_mapping.py` may be called in performance-critical path. **Mitigation:** Profile before changing; `chitta_vritti/` has fast-path optimization already.

**Success Criteria:**
- `core/__init__.py` exports only active engines
- `core/entropy/` directory removed
- Only 2 vritti implementations remain: `chitta_vritti/` (runtime canonical) and `sovereign/` (training, synced formulas)
- Only 2 guna implementations remain: `guna_modulation/` (runtime canonical) and `sovereign/` (training, synced formulas)
- All tests pass

---

### Phase 1: Replace Governance Approximations with Real Signals (Highest Leverage)

**Goal:** Replace `approximate_vritti()` and `approximate_layer_weights()` in JEPA governance with real module outputs. This is the single highest-leverage wiring change — it makes governance decisions based on actual semantic state instead of proxy signals.

**Folders in scope:** `chitta_vritti/`, `entropy/`, `agentic_framework/`

**Actions:**

| # | Action | Files | Detail |
|---|--------|-------|--------|
| 1.1 | Create vritti signal adapter for governance | New: `agentic_framework/signal_adapters/vritti_adapter.py` | Extract stable interface: `get_vritti_distribution(ctx) -> Dict[str, float]`. If `ctx` has `chitta_vritti_result`, use real distribution. Else fall back to current `approximate_vritti()`. Graceful degradation preserves existing behavior. |
| 1.2 | Replace `approximate_vritti()` call in `jepa_governance.py` | `agentic_framework/jepa_governance.py` ~line 150 | Replace `vritti_dist = approximate_vritti(quality, coherence, confidence)` with `vritti_dist = vritti_adapter.get_vritti_distribution(ctx)`. The R[v,a] coupling matrix call (`get_aspect_weights()`) already exists and is already imported — it just needs real input. |
| 1.3 | Add entropy signal to ConfidenceSignals | `agentic_framework/confidence_gate.py` | Add `entropy_normalized: float` field to ConfidenceSignals. Populate from `entropy/EntropyEngine.evaluate()` result. Use in confidence aggregation (currently weighted 0.0 — increment to 0.05-0.10). |
| 1.4 | Add entropy gate result to governance context | `agentic_framework/governance_service.py` | After JEPA check, add entropy gate check: if `EntropyGate.BLOCK`, escalate authorization to DENIED regardless of other signals. Only active for Tier 3 configs. |
| 1.5 | Wire ChittaVrittiResult into PipelineContext for governance | `symbolu_core/mechanical/pipeline/models.py` | Ensure `ctx.chitta_vritti_result` is populated before governance check runs. Currently CV runs in session processing (after governance). **Must reorder or compute CV earlier in pipeline.** |

**Prerequisites:** Phase 0 complete (canonical vritti authority established).

**Risks:**
- **Pipeline ordering conflict (1.5)**: ChittaVrittiEngine currently runs in session processing (post-governance). To feed governance, it must run earlier — either in MLCR phase or as a pre-governance signal computation. **Mitigation:** Add a lightweight `compute_vritti_preview()` that runs on available signals before governance, with full CV computation still happening in session processing. Governance gets a preview; session processing gets the full result.
- **Entropy Tier 3 blocking (1.4)**: Could unexpectedly block requests in high-entropy cross-domain scenarios. **Mitigation:** Deploy as Tier 1 (diagnostic only) first. Monitor entropy gate decisions for 2 weeks. Upgrade to Tier 2/3 after validation.

**Success Criteria:**
- `jepa_governance_check()` receives real 5-vritti distribution when available
- JEPA regime classification accuracy improves (testable via existing JEPA test suite)
- Entropy gate result appears in governance audit trail
- No latency regression (vritti preview adds <5ms)
- Fallback to approximation works when CV result unavailable

---

### Phase 2: Wire Output Modulation Path (DHA + Guna + Entropy → Renderer)

**Goal:** Make the renderer actually apply DHA tone weights, guna-derived intensity, and entropy-based modulation instead of ignoring them.

**Folders in scope:** `dha/`, `guna_modulation/`, `entropy/`

**Actions:**

| # | Action | Files | Detail |
|---|--------|-------|--------|
| 2.1 | Enable DHA by default (Tier 1 diagnostic) | `dha/config.py`, orchestrator pipeline config | Change `enabled=False` to `enabled=True` for Tier 1. DHA computes and records tone/intensity/restraint but does not modify output in diagnostic mode. |
| 2.2 | Add `delivery_factor` field to `IntegratedRenderedOutput` | `symbolu_core/mechanical/pipeline/renderer_integration.py` ~line 71 | Add `delivery_factor: float = 1.0` and `tone_profile: Optional[Dict[str, float]] = None`. Renderer populates from `ctx.dha`. |
| 2.3 | Wire DHA tone weights into FusionRenderer | `symbolu_core/mechanical/pipeline/renderer_integration.py` ~line 336 | Pass `ctx.dha.tone_weights` to FusionRenderer. Use to bias layer prominence: `sweet` → higher `practical_bias`, `jolt` → higher `symbolic_bias`, `metaphor` → higher `mirror_truth_bias`. |
| 2.4 | Enable formula DHA (guna_modulation E=G×P×T) by default | Orchestrator, `guna_modulation/pipeline_integration.py` | Change `dha_formula_enabled` default from `False` to `True`. Formula DHA runs alongside structural DHA — computes `E = G×P×T` for principled intensity scaling. |
| 2.5 | Wire E=G×P×T intensity into renderer | `renderer_integration.py` | Read `ctx.dha.adaptation_notes["formula_dha"]["E"]` (or `ctx.dha.adaptation_notes["formula_dha"]["D"]`). Apply as intensity multiplier to output prominence. `D < 0.5` → reduce output intensity (more restrained). `D > 0.8` → full intensity. |
| 2.6 | Add entropy-driven output annotation | `renderer_integration.py` or output processing | Attach entropy gate result (ALLOW/MODULATE/BLOCK) to output metadata. If MODULATE: add caution signal to output. If BLOCK (Tier 3 only): suppress output. |

**Prerequisites:** Phase 0 (guna consolidation); Phase 1 not strictly required but recommended.

**Risks:**
- **DHA tone weights may not improve output quality (2.3)**: Tone-to-bias mapping is a design decision, not a formula. **Mitigation:** Start with small bias adjustments (±0.05). A/B test with and without. chitta_vritti evaluation framework can measure coherence impact.
- **Formula DHA may produce unexpected intensity values (2.5)**: If `E = G×P×T` produces values outside renderer expectations. **Mitigation:** Clamp to [0.3, 1.0] — never fully suppress, never amplify beyond 1.0.
- **Enabling DHA by default may add latency (2.1)**: DHA is lazy-loaded via `@lru_cache`. **Mitigation:** First invocation pays ~10ms init cost; subsequent calls are cached. Measure in staging.

**Success Criteria:**
- DHA runs on every request (Tier 1 diagnostic minimum)
- `IntegratedRenderedOutput` carries `delivery_factor` and `tone_profile`
- Formula DHA (E=G×P×T) computes on every request
- Renderer layer bias is influenced by tone weights
- Output metadata includes entropy gate annotation
- No latency regression >15ms p99

---

### Phase 3: Connect Session Enrichments to Governance (Identity, Motivation, Temporal)

**Goal:** Make governance decisions aware of session-level signals (identity signature, motivation flow, temporal trajectory) that are currently computed but never consulted for authorization.

**Folders in scope:** `identity/`, `motivation/`, `temporal/`

**Actions:**

| # | Action | Files | Detail |
|---|--------|-------|--------|
| 3.1 | Add identity + motivation to ConfidenceSignals | `agentic_framework/confidence_gate.py` | Add fields: `identity_classification: Optional[str]`, `motivation_state: Optional[str]`, `identity_confidence: Optional[float]`, `motivation_confidence: Optional[float]`. Populate from `ctx.identity_signature` and `ctx.motivation_profile`. |
| 3.2 | Use identity/motivation in ShadowAI semantic mismatch | `agentic_framework/shadow_ai.py` | Shadow AI has 13 risk factors including `identity_confidence`. Wire real `identity_signature.confidence` instead of default. If identity shows `self_fragmentation` with high confidence, escalate shadow containment. |
| 3.3 | Enrich ApprovalContext with session signals | `agentic_framework/approval_workflow.py` | Include `identity_signature`, `motivation_profile` in ApprovalContext snapshot. Enables approval routing logic: "fragmented identity + fear-driven motivation → require senior approval." |
| 3.4 | Add temporal bhava to JEPA composite | `agentic_framework/jepa_governance.py` | When `ctx.lam_map` exists (temporal active), extract `temporal_state` (TENSE/RECOVERING/STABLE) and `pattern_tracker_report`. Use temporal state to modulate JEPA regime: TENSE + SEMANTIC_SHIFT → escalate to DUAL_ANOMALY. |
| 3.5 | Wire temporal always-on (remove tension > 0.4 gate) | Orchestrator LAM stage | Currently `maybe_run_lam()` runs only when `use_lam=True` or `long_arc_tension > 0.4`. Change to always run `TemporalBhavaTracker.add_entry()` for state tracking (lightweight). Full CDI + pattern tracking still gated by tension threshold. |
| 3.6 | Add identity/motivation policy sections to PolicyBundle | `agentic_framework/policy_bundle.py` | Add `IdentityPolicy` section (identity drift tolerance per domain) and `MotivationPolicy` section (motivation state constraints). Enables per-domain rules like "in finance domain, self_fragmentation → block high-risk actions." |

**Prerequisites:** Phase 1 (governance consuming real vritti/entropy). Phase 0 not strictly required but recommended.

**Risks:**
- **Identity/motivation signals are session-level, not turn-level (3.1)**: These classify multi-turn patterns. First turn of a session has `neutral_identity` / `ambiguous_motivation`. **Mitigation:** Only use for enrichment (soft signal), not hard gating, until 3+ turns of session context exist.
- **Temporal always-on may add latency (3.5)**: `TemporalBhavaTracker.add_entry()` does sliding-window tracking. **Mitigation:** Profile; tracker is O(window_size) which is bounded. Skip CDI + pattern tracking when tension is low.
- **Over-constraining governance (3.2, 3.6)**: Adding too many signals to governance may create unexpected interaction effects. **Mitigation:** Deploy as observational enrichments first (logged but not gating). Graduate to gating after calibration.

**Success Criteria:**
- ConfidenceSignals carries identity + motivation when available
- Shadow AI risk assessment uses real identity confidence
- ApprovalContext includes session-level classification
- Temporal tracker runs on every request (lightweight mode)
- PolicyBundle supports domain-specific identity/motivation rules
- No false-positive authorization denials from new signals

---

### Phase 4: Sovereign-Inference Bridge and Advanced Modules

**Goal:** Unify training-time and inference-time state representations. Wire advanced guna_modulation modules. Mature inference/ Appendix F stages.

**Folders in scope:** `sovereign/`, `inference/`, `guna_modulation/` (advanced modules)

**Actions:**

| # | Action | Files | Detail |
|---|--------|-------|--------|
| 4.1 | Build sovereign 128D → inference 32D state projection | New: `sovereign/inference_bridge.py` | Define canonical projection: 128D [16D Guna \| 32D S-Signal \| 48D R-Signal \| 32D C-Signal] → 32D [Bhava 0:12 \| Kosha 12:17 \| Vritti 17:22 \| Guna 22:28]. Add to checkpoint export so inference/ loads projected state. |
| 4.2 | Connect InferenceManager to generation path | `symbolu_core/ontological/symbolu12_llm.py`, `inference/manager.py` | Wire InferenceManager as optional orchestrator around model.generate(). Start with FAST mode (minimal overhead). CSRInferenceGuard provides safety layer. |
| 4.3 | Reconcile inference 32D vritti [17:22] with chitta_vritti/ | `inference/sovereign_state_monitor.py` | Sovereign state monitor's vritti slice should be validated against `chitta_vritti/` output. Add consistency check: if drift > threshold, log warning. |
| 4.4 | Wire MirrorBalance as observability diagnostic | `guna_modulation/mirror_balance.py` | Add to pipeline observability (not gating). Detect guna/entropy/motion asymmetry. Report in coherence_report. |
| 4.5 | Wire CausalLayer for pipeline audit trail | `guna_modulation/causal_layer.py` | Add do-calculus attribution to pipeline debug output. Enable via `causal_audit_enabled` flag. Not on default path. |
| 4.6 | Evaluate Appendix F stages for maturation | `inference/` Appendix F files | Review each stage (0-7F). Promote stages with >200 LOC and real logic to "candidate for wiring." Leave stubs (e.g., CoherenceAwareDecoder at 111 LOC) as experimental. |

**Prerequisites:** Phase 0 (consolidation), Phase 1 (governance signals), Phase 2 (output path).

**Risks:**
- **Sovereign bridge projection may lose information (4.1)**: 128D → 32D is lossy. **Mitigation:** Use learned projection (linear layer trained alongside sovereign loss) rather than hard slicing. Validate reconstruction error.
- **InferenceManager latency (4.2)**: Orchestrating 6 sub-engines adds overhead. **Mitigation:** FAST mode skips metacognition, sovereign scoring, and binding cache. Measure before enabling STANDARD/FULL modes.
- **Appendix F maturity (4.6)**: Some stages are research-grade with TODOs. **Mitigation:** Don't wire anything from Appendix F into production without individual review. Keep behind explicit flags.

**Success Criteria:**
- Checkpoint export includes 32D projected state
- InferenceManager orchestrates generation in FAST mode without latency regression
- 32D vritti slice validated against chitta_vritti output
- MirrorBalance reports visible in coherence dashboard
- CausalLayer attribution available via debug flag
