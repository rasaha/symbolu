# Ontology Wiring & Runtime Integration Audit

**Date**: 2026-04-04
**Scope**: All 41 `.py` files under `agentic/ontology/`
**Method**: File-by-file read + full codebase import tracing

---

## Executive Summary

`agentic/ontology/` contains **41 Python files** across 7 subpackages totaling **~12,000+ LOC**. Every non-`__init__` file is substantial — there are **zero stubs, zero dead files**. Code quality is consistently high: deterministic, immutable, fail-closed, no-ML.

**The wiring picture is stark**:

| Category | Files | ~LOC | Runtime Consumers |
|----------|-------|------|-------------------|
| backbone/ | 15 | 7,500 | Only `symbolu_core/engine/` (3 files) |
| contracts/layers/ledger | 5 | 525 | Router + policy (internal loop) |
| phase4a/ | 5 | 1,500 | Experiments only |
| projection/ | 7 | 1,100 | **Zero external** |
| router/ | 3 | 870 | **`ontological_router_r1.py` only** (ledger, acoustic) |

Of 41 files, only **~5 are on genuine runtime paths** outside `ontology/` itself.

---

## File Inventory

### backbone/ (15 substantial files, ~7,500 LOC)

| File | Lines | Purpose | Consumers | Status |
|------|-------|---------|-----------|--------|
| `__init__.py` | 236 | Facade exporting 60+ APIs | symbolu_core/engine only | Authoritative facade |
| `backbone/__init__.py` | 31 | 10D architecture docstring | Nobody | Reference doc |
| `encoder.py` | 538 | 10D text→vector encoding (Dimension enum, DimensionalVector, encode_10d) | agi_context.py | **Authoritative, underwired** |
| `extractors.py` | 618 | Directional dimension extractors (10 concrete extractors, ProjectionDirection) | rag_integration.py internal | Authoritative, underwired |
| `experiential.py` | 490 | Transferable reasoning patterns (ExperientialObject, ExperientialStore) | agi_context.py | Authoritative, underwired |
| `similarity.py` | 574 | Cross-domain 10D similarity (5 metrics, CrossDomainMatch) | agi_context.py, learning_pipeline | **Authoritative, underwired** |
| `mirror_pairs.py` | 500 | 5 mirror pair balance + event tagging (MirrorPair, BalanceReport) | agi_context.py | Authoritative, underwired |
| `phoneme_validator.py` | 836 | Dual-gate validation: semantic + phoneme (ValidationReport) | agi_context.py | Authoritative, underwired |
| `learning_pipeline.py` | 578 | Gate→store learning flow (learn_from_event, retrieve_similar) | agi_context.py | Authoritative, underwired |
| `cross_domain_config.py` | 514 | Admin policy for domain-pair learning (DomainPairPolicy, CrossDomainConfig) | learning_pipeline.py | Authoritative, disconnected from policy/ |
| `persona_tracker.py` | 510 | User behavior tracking (PersonaProfile, PersonaStore) | agi_context.py | Authoritative, needs privacy framework |
| `user_inclination.py` | 325 | User preference modeling (ReasoningStyle, DomainAffinity) | reasoning_synthesizer.py | Authoritative, needs product decisions |
| `reasoning_synthesizer.py` | 525 | Multi-source reasoning synthesis (SynthesisResult) | agi_context.py | Authoritative, underwired |
| `insight_suggester.py` | 675 | Personalized insight generation (InsightMode, PersonalInsight) | agi_context.py | Authoritative, underwired |
| `reasoning_extractor.py` | 387 | Content reasoning extraction (ExtractedPattern, CausalChain) | No direct consumer | Authoritative, unwired |
| `rag_integration.py` | 509 | 10D-aware RAG retrieval (OntologicalRAGIndex) | No direct consumer | Authoritative, needs RAG infra |

### contracts/ (1 substantial file)

| File | Lines | Purpose | Consumers | Status |
|------|-------|---------|-----------|--------|
| `projection_contract.py` | 188 | Immutable projection request/response contracts (ProjectionRequest, ProjectionResponse) | router/layer_router.py, policy/layer_visibility_policy.py | **Authoritative and live** |

### layers/ (1 substantial file)

| File | Lines | Purpose | Consumers | Status |
|------|-------|---------|-----------|--------|
| `ontology_layer.py` | 87 | 12-layer patent-exact enum (OntologicalLayer, GATED_LAYERS) | 6 consumers (router, contracts, ledger, policy) | **Authoritative and live — but triplicated** |

### ledger/ (1 substantial file)

| File | Lines | Purpose | Consumers | Status |
|------|-------|---------|-----------|--------|
| `ledger_adapter.py` | 225 | Deterministic SHA-256 ledger span generation (LedgerSpan) | router/layer_router.py | **Authoritative and live** |

### phase4a/ (5 substantial files, ~1,500 LOC)

| File | Lines | Purpose | Consumers | Status |
|------|-------|---------|-----------|--------|
| `errors.py` | 177 | 7 fail-fast exception types (Phase4AError hierarchy) | loader, lookup, checksums | Authoritative |
| `loader.py` | 598 | Loads 3 frozen JSON files with checksum verification | lookup.py, experiments | **Authoritative, underconsumed** |
| `ontology_checksums.py` | 206 | Hardcoded SHA-256 registry for 5 frozen files | loader.py | Authoritative |
| `lookup.py` | 299 | Deterministic (varna, layer)→VarnaLayerInteraction lookup | experiments, dynamics/phase5 | **Authoritative, underconsumed** |
| `models.py` | 211 | Frozen dataclasses (VarnaLayerInteraction, ValidationReport) | lookup, loader | Authoritative |

### projection/ (7 files, ~1,100 LOC)

| File | Lines | Purpose | Consumers | Status |
|------|-------|---------|-----------|--------|
| `engine.py` | 291 | Main projection orchestrator: validate→dispatch→respond | **Zero external** (tests only) | Schema/reference |
| `api_models.py` | 195 | Frozen request/response models + duplicate OntologicalLayer | Internal only | **Needs OntologicalLayer dedup** |
| `attest.py` | 71 | Determinism verification (runs projection 50x) | None external | CI/validation utility |
| `validators.py` | 311 | Bans forbidden NLP modules, enforces no-timestamp/no-freetext | engine.py internal | **Safety invariant — wire to safety/** |
| `layers/meta_observing.py` | 73 | Project onto WITNESSES layer | None direct (OLM references by name) | Wire when projection activated |
| `layers/unifying.py` | 87 | Project onto UNIFYING layer | None direct | Wire when projection activated |
| `layers/thinking.py` | 69 | Project onto COGNITION layer | None direct | Wire when projection activated |

### router/ (3 substantial files, ~870 LOC)

| File | Lines | Purpose | Consumers | Status |
|------|-------|---------|-----------|--------|
| `phase_layer_map.py` | 162 | Immutable 9 Phase→12 Layer mapping | layer_router.py, tests | **Authoritative and live** |
| `layer_router.py` | 214 | Stateless router using contracts+ledger+phase_layer_map | Tests only (via symbolu) | Authoritative, underwired |
| `ontological_router_r1.py` | 490 | Self-contained R1 router with hint system + ABSOLVING gate | **Runtime: ledger_store, ledger_replay_verifier, p10_acoustic** | **Authoritative and live** |

---

## Source-of-Truth Matrix

| Area | File(s) | Classification |
|------|---------|---------------|
| 12 Ontological Layers | `layers/ontology_layer.py` | Authoritative but triplicated |
| Phase→Layer Mapping | `router/phase_layer_map.py` | Authoritative and live |
| Projection Contracts | `contracts/projection_contract.py` | Authoritative and live |
| Ledger Attestation | `ledger/ledger_adapter.py` | Authoritative and live |
| Production Router | `router/ontological_router_r1.py` | Authoritative and live |
| 10D Encoding | `backbone/encoder.py` | Authoritative but underwired |
| Cross-Domain Similarity | `backbone/similarity.py` | Authoritative but underwired |
| Experiential Storage | `backbone/experiential.py` | Authoritative but underwired |
| Learning Pipeline | `backbone/learning_pipeline.py` | Authoritative but underwired |
| Phoneme Validation | `backbone/phoneme_validator.py` | Authoritative but underwired |
| Frozen Ontology Substrate | `phase4a/` (loader, checksums, lookup) | Authoritative but underconsumed |
| Projection Engine | `projection/engine.py` + layers | Schema/reference only |
| Safety Validators | `projection/validators.py` | Authoritative but unwired outside projection |

---

## Critical Issues

### 1. OntologicalLayer Triplication
Three independent copies of the 12-layer enum:
- `layers/ontology_layer.py` (canonical)
- `projection/api_models.py` (duplicate)
- `router/ontological_router_r1.py` (duplicate, self-contained)

### 2. agentic/ vs symbolu/ Parallel
Every file in `agentic/ontology/` has a mirror in `symbolu/ontology/`. Tests use `symbolu.*` paths. Which is canonical?

### 3. backbone/ Isolation
~7,500 LOC of production-quality code with zero imports from `agentic_framework/`, `core/`, `policy/`, or `sovereign/`.

### 4. projection/ Island
~1,100 LOC with zero external runtime consumers. The OLM system references projection concepts by name but doesn't import the code.

---

## Top 10 Files to Wire or Promote

1. **`router/ontological_router_r1.py`** — Already live; consolidate OntologicalLayer import → P0
2. **`layers/ontology_layer.py`** — Deduplicate; make single source → P0
3. **`backbone/encoder.py`** — Wire to `agentic_framework/signal_adapters/` → P0
4. **`backbone/similarity.py`** — Wire alongside encoder → P0
5. **`projection/validators.py`** — Extract `check_no_forbidden_modules()` to `agentic/safety/` → P1
6. **`phase4a/lookup.py`** — Wire to governance/policy for varna-layer lookups → P1
7. **`backbone/learning_pipeline.py`** — Wire to framework memory/learning → P1
8. **`backbone/mirror_pairs.py`** — Wire to `core/coherence/` via adapter → P1
9. **`contracts/projection_contract.py`** — Already wired; extend incrementally → P1
10. **`backbone/insight_suggester.py`** — Wire to `proactive_scheduler.py` → P2

---

## Recommended Phased Integration Plan

### O1: Source-of-Truth Cleanup (immediate)
- Deduplicate OntologicalLayer → single canonical in `layers/ontology_layer.py`
- Update `projection/api_models.py` and `router/ontological_router_r1.py` to import from canonical
- Resolve or document the `agentic/` vs `symbolu/` parallel structure
- Verify all checksums in `phase4a/ontology_checksums.py` are current

### O2: Safety & Structural Wiring (next sprint)
- Extract `check_no_forbidden_modules()` from `projection/validators.py` → `agentic/safety/`
- Wire `backbone/encoder.py` + `backbone/similarity.py` into `agentic_framework/signal_adapters/ontology_adapter.py`
- Wire `phase4a/lookup.py` into governance service for varna-layer lookups

### O3: Governance & Policy Integration (following sprint)
- Wire `backbone/learning_pipeline.py` into framework memory/learning path
- Wire `backbone/mirror_pairs.py` → `core/coherence/` via adapter
- Connect `backbone/cross_domain_config.py` to `policy/` admin controls
- Wire `backbone/insight_suggester.py` → `proactive_scheduler.py`

### O4: Projection & Advanced Surfaces (future)
- Activate `projection/engine.py` with real consumers (governance audit, simulation)
- Wire projection layers into OLM mechanical system (currently name-referenced only)
- Expose `backbone/rag_integration.py` when RAG infrastructure is deployed
- Connect persona/inclination modules when privacy framework exists

---

## Special Findings

### Which ontology files are the true source of ontological semantics?
- `layers/ontology_layer.py` — 12-layer structural sequence
- `router/phase_layer_map.py` — phase→layer mapping
- `backbone/encoder.py` — 10D dimensional semantics
- `phase4a/models.py` — varna-layer interaction semantics

### Are ontology concepts duplicated elsewhere?
- OntologicalLayer is triplicated within ontology/ itself
- `agentic_framework/olm_bridge.py` references ontology layer names as strings
- `core/coherence/` solves similar problems to `backbone/mirror_pairs.py` but independently
- No direct import-level duplication between ontology/ and framework/core/policy/sovereign

### Are there dead abstractions giving false importance?
- `projection/` appears important but has zero external consumers
- `backbone/` appears important but is only reachable through `symbolu_core/engine/`
- Neither is truly "dead" — both are tested and maintained — but both are dormant from `agentic/` perspective

### If ontology semantics are approximated elsewhere, where?
- `core/coherence/coherence_engine.py` approximates balance concepts (vs `backbone/mirror_pairs.py`)
- `agentic_framework/signal_adapters/` builds adapter patterns that could wrap backbone modules
- `sovereign/` has its own routing/inference logic independent of ontology router
- `policy/` has its own domain profiles independent of `backbone/cross_domain_config.py`
