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
