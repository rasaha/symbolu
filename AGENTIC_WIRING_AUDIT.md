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
