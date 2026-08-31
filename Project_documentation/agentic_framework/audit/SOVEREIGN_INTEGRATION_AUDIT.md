# Sovereign → Agentic Framework Integration Audit

> **Status:** This pre-integration audit has been **superseded** by the
> completed S1–S4 integration. The recommendations in this document were
> used to guide the implementation. For the current architecture, see
> [`Project_documentation/agentic_framework/agentic/AGENTIC_ARCHITECTURE.md`](../agentic/AGENTIC_ARCHITECTURE.md).

**Date:** 2026-04-04
**Scope:** Every `.py` file in `agentic/sovereign/` (29 files)
**Goal:** File-by-file determination of what should be wired into the agentic framework runtime

---

## 1. Executive Summary

The `agentic/sovereign/` folder contains 29 Python files implementing the Sovereign-1 architecture — a 128D biological header system for training that projects to a 32D inference control plane. The folder mixes **training infrastructure** (loss functions, gradient scaling, training loops), **model architecture** (transformer, embeddings, attention), **runtime-relevant state computation** (observer, guna, vritti, insight gate), and **bridging/export utilities** (inference bridge, telemetry, cognade export).

**Current wiring status:**
- `inference_bridge.py` is already called by `agentic/inference/manager.py` for 128D→32D projection
- `sovereign_bridge.py` (in `agentic_framework/`, not in `sovereign/`) converts 32D→ConfidenceSignals/CoherenceState
- The pipeline is: sovereign modules → `inference_bridge` → `sovereign_bridge` → governance pipeline
- **No other sovereign file is directly imported by the agentic framework**

**Key findings:**
- **5 files** are high-value candidates for deeper integration (inference_bridge, router, telemetry, metrics, insight_gate)
- **9 files** are training-only and should NOT be wired (loss.py, sovereign_loss.py, train_loss.py, trainer.py, hierarchical_gradient_scaler.py, training/*)
- **6 files** are model architecture (embedding, transformer, phase_attention, observer, guna, vritti) — they produce state consumed downstream but are nn.Module-entangled
- **2 files** are already adequately bridged via the existing inference_bridge → sovereign_bridge pipeline
- The main gap is **runtime-accessible semantic state** — the agentic framework currently gets signals only through the 32D projection, missing richer diagnostics from metrics.py, telemetry.py, and insight_gate.py

---

## 2. Python File Inventory

### Main directory: `agentic/sovereign/` (23 files)

| # | File | Lines | PyTorch | Category |
|---|------|-------|---------|----------|
| 1 | `__init__.py` | ~120 | Re-export | Package hub |
| 2 | `reasoning_kernel.py` | ~800+ | Heavy | Model architecture |
| 3 | `inference_bridge.py` | ~250 | Minimal | **Runtime bridge** |
| 4 | `vritti.py` | ~200 | Heavy | Model architecture |
| 5 | `guna.py` | ~200 | Heavy | Model architecture |
| 6 | `observer.py` | ~300 | Heavy | Model architecture |
| 7 | `router.py` | ~200 | **None** | **Runtime utility** |
| 8 | `insight_gate.py` | ~300 | Light | Governance-relevant |
| 9 | `embedding.py` | ~250 | Heavy | Model architecture |
| 10 | `transformer.py` | ~300 | Heavy | Model architecture |
| 11 | `phase_attention.py` | ~250 | Heavy | Model architecture |
| 12 | `heartbeat.py` | ~200 | **None** | Visualization |
| 13 | `pid_governor.py` | ~300 | Heavy | Model architecture |
| 14 | `hierarchical_gradient_scaler.py` | ~350 | Heavy | Training only |
| 15 | `tagger.py` | ~300 | Light | Data preprocessing |
| 16 | `metrics.py` | ~400 | Medium | Governance-relevant |
| 17 | `loss.py` | ~200 | Heavy | Training only |
| 18 | `sovereign_loss.py` | ~300 | Heavy | Training only |
| 19 | `train_loss.py` | ~250 | Heavy | Training only |
| 20 | `stitched_objective.py` | ~400 | Heavy | Training/inference |
| 21 | `telemetry.py` | ~300 | Minimal | **Runtime utility** |
| 22 | `cognade_export.py` | ~350 | Minimal | Export tooling |
| 23 | `trainer.py` | ~350 | Heavy | Training only |

### Subdirectory: `agentic/sovereign/training/` (4 files)

| # | File | PyTorch | Category |
|---|------|---------|----------|
| 24 | `training/__init__.py` | Re-export | Training only |
| 25 | `training/stress_test.py` | Heavy | Training/test |
| 26 | `training/validation.py` | Heavy | Training/test |
| 27 | `training/inoculation.py` | Heavy | Training only |

### Subdirectory: `agentic/sovereign/tests/` (2 files)

| # | File | PyTorch | Category |
|---|------|---------|----------|
| 28 | `tests/__init__.py` | None | Test package |
| 29 | `tests/test_srk.py` | Heavy | Test suite |

---

## 3. File-by-File Audit

---

### File 1: `__init__.py`

**Classification:** EXPORT / TOOLING

#### A. Purpose
Package initialization and re-export hub for the entire Sovereign-1 architecture (v9.8.0). Re-exports all public classes/functions from submodules — loss functions, observer, PID governor, guna, transformer, router, telemetry, cognade export, training utilities, and the Reasoning Kernel (SRK).

#### B. Current usage
- Imported by any code that does `from agentic.sovereign import X`
- Used by training scripts, tests, and inference manager
- Acts as the public API surface for the entire sovereign package

#### C. Runtime value
No direct runtime value — it's a re-export convenience layer. Its value depends on which submodules are runtime-relevant.

#### D. Wiring target
Nowhere directly. The `__init__.py` should be updated as individual files get wired, to ensure clean import paths.

#### E. Wiring mechanism
No mechanism needed. Just keep exports aligned with what's wired.

#### F. Recommended action
**Keep as-is** — update exports as individual files are refactored.

#### G. Priority
**P3** — Maintenance only. No standalone action needed.

---

### File 2: `reasoning_kernel.py`

**Classification:** RUNTIME PARTIALLY WIRED (via inference_bridge downstream)

#### A. Purpose
Implements the Sovereign Reasoning Kernel (SRK) — manages 32D state across transformer layers during forward pass. Contains:
- `SovereignReasoningKernel`: Main orchestrator with layer intervention at layers 4, 7, 9, 11
- `IsomorphicMappingRouter`: Cross-domain bridge detection via fixed logic templates (deduction, induction, abduction, analogy, synthesis)
- `OntologicalBridge`: Layer 4 DNA grounding — projects hidden→Bhava, computes ontological error
- `VrittiGate`: Epistemological witness rejecting hallucinations via 5 Vritti states
- `KoshaShiftController`: Layer 9 steering toward INTELLECTUAL Kosha during reasoning
- `OPBDimensionLock`: Ontological Persistence Buffer — locks active dimensions across domain switches
- `UserOntologicalMirror`: Detects user psychological state for intervention
- `MaunaProtocol`: Silence protocol for high-uncertainty states
- `SovereignEmbedding`: 32D state-aware embedding layer
- `PhaseExtractionHook`: Extracts phase information for attention heads

#### B. Current usage
- Used during model forward pass (training and inference)
- Tested by `tests/test_srk.py`
- The 32D state it manages is what `inference_bridge.py` projects from 128D
- NOT directly imported by the agentic framework

#### C. Runtime value
**High conceptual value, but deeply entangled with PyTorch nn.Module.** The reasoning kernel IS the runtime intelligence that produces sovereign state. However, the agentic framework already consumes the output (32D state) through `inference_bridge` → `sovereign_bridge`. Directly importing the kernel into the governance layer is unnecessary — it's a model component, not a governance component.

Specific high-value extractable concepts:
- `IsomorphicMappingRouter` logic templates (pure data, could inform governance)
- `MaunaProtocol` silence decision (could be exposed as a governance signal)
- `OPBDimensionLock` dimension persistence (could inform identity stability)

#### D. Wiring target
- NOT directly into governance service or MCP gateway
- **Expose specific signals** via inference_bridge or telemetry, not the kernel itself
- Mauna protocol → could feed a "sovereign_silence" signal to ConfidenceGate
- OPB lock state → could feed identity_stability in sovereign_bridge

#### E. Wiring mechanism
- Extract pure-function diagnostics from kernel state (no nn.Module needed)
- Add optional diagnostic dict output to kernel's forward() that inference_bridge can capture
- NOT direct import — too entangled with PyTorch

#### F. Recommended action
**Bridge first** — Extract diagnostic signals (Mauna state, OPB lock, dominant logic template) into inference_bridge output, then sovereign_bridge can forward them.

#### G. Priority
**P2** — The existing 32D projection already captures most value. Additional signals are enrichment, not foundation.

---

### File 3: `inference_bridge.py`

**Classification:** RUNTIME READY — ALREADY WIRED

#### A. Purpose
Explicit 128D→32D lossy projection from training state to inference control plane. Contains:
- `ProjectionMetadata`: Documents what's lost (S-Signal, C-Signal dropped; Kosha/Vritti derived)
- `SovereignProjectionResult`: Result dataclass with inference_state (32 floats), metadata, Bhava activations, guna summary, Kosha/Vritti profiles
- `project_sovereign_to_inference()`: Main projection function — pools R-Signal (48D→12D Bhava), Guna (16D→6D), derives Kosha/Vritti from Bhava patterns
- `_derive_kosha_from_bhava()`: Fixed weight matrix for 12D Bhava → 5D Kosha
- `_derive_vritti_from_bhava()`: Distributes Bhava activation into 5 Vritti buckets

#### B. Current usage
- **Already imported by `agentic/inference/manager.py`** at line 1110
- Called in `InferenceManager.initialize_from_training_state()` to bridge training checkpoints to inference runtime
- Projection result feeds into signal reconciliation

#### C. Runtime value
**Critical** — This IS the sovereign→runtime bridge. Without it, the 128D training state cannot reach the agentic framework. The projection is principled and documented, with explicit metadata about information loss.

#### D. Wiring target
Already wired to `agentic/inference/manager.py`. Downstream: `sovereign_bridge.py` consumes the 32D output.

#### E. Wiring mechanism
Already in place: `inference_bridge.project_sovereign_to_inference()` → `InferenceManager` → `sovereign_bridge.signals_from_sovereign_state()` → `ConfidenceGate`/`SafetyContract`.

#### F. Recommended action
**Wire now (enrich)** — The projection is wired but currently only surfaces Bhava/Guna/Kosha/Vritti. Could be enriched to pass through additional diagnostics (Mauna state, OPB lock, logic template) from the reasoning kernel.

#### G. Priority
**P0** — Already wired. Enrichment is P2.

---

### File 4: `vritti.py`

**Classification:** MODEL ARCHITECTURE — TRAINING/INFERENCE nn.Module

#### A. Purpose
Implements the 5-mode cognitive controller (Vritti system):
- `VrittiState` (IntEnum): PRAMANA (fact), VIPARYAYA (error), VIKALPA (imagination), SMRITI (memory), NIDRA (dormancy)
- `PIDGovernor` (nn.Module): Converts scalar Authority to vectorized PID gains based on predicted cognitive mode
- `VrittiHead` (nn.Module): Auxiliary head predicting Vritti state from R-Signal (48D→5D)
- `VRITTI_PHYSICS`: Dict mapping each Vritti to PID coefficients (Kp, Ki, Kd)
- `TRANSITION_PENALTY_MATRIX` / `TRANSITION_PROB_MATRIX`: 5x5 Vritti transition constraints

#### B. Current usage
- Used by `pid_governor.py`, `transformer.py`, training loop
- Vritti state predictions flow into the 32D state and reach the agentic framework via inference_bridge → sovereign_bridge → `_vritti_to_confidence()`
- NOT directly imported by agentic framework

#### C. Runtime value
**Indirect only.** The Vritti state is already projected into the 32D state and consumed by sovereign_bridge. The nn.Module components are model internals. However, the **constants** (VrittiState enum, VRITTI_PHYSICS, transition matrices) have standalone value.

Specific extractable value:
- `VrittiState` enum — canonical Vritti naming (already duplicated in sovereign_bridge.py and jepa_governance.py)
- `VRITTI_PHYSICS` PID tables — could validate/enrich runtime PID-like governance
- `TRANSITION_PENALTY_MATRIX` — could inform governance regime transition constraints

#### D. Wiring target
- Constants could be extracted to a shared `sovereign_constants.py` used by both sovereign/ and agentic_framework/
- NOT the nn.Module classes — those stay in the model

#### E. Wiring mechanism
- Extract enum/constants to shared location
- Current index-based access in sovereign_bridge.py is adequate for signals

#### F. Recommended action
**Refactor first** — Extract `VrittiState`, `VRITTI_PHYSICS`, transition matrices to a shared constants module. This eliminates duplication across sovereign_bridge, jepa_governance, and vritti.py.

#### G. Priority
**P2** — Constants consolidation. Not blocking functionality.

---

### File 5: `guna.py`

**Classification:** MODEL ARCHITECTURE — TRAINING/INFERENCE nn.Module

#### A. Purpose
Computes 16D Guna Pulse from attention/hidden states using information-theoretic measures:
- `SovereignGunaComputer` (nn.Module): Computes Sattva (Shannon entropy of attention = clarity), Rajas (variance of head outputs = energy), Tamas (cosine similarity to previous state = inertia). Expands 3D→16D via learnable linear layer. Softmax-normalized for conservation.
- `GunaMonitor`: Runtime anomaly detection — tracks rolling history, detects collapse, oscillation, stagnation.

#### B. Current usage
- Used by `observer.py` to compose the 128D state
- Used in training loop for real-time Guna monitoring
- NOT directly imported by agentic framework

#### C. Runtime value
**`GunaMonitor` has standalone governance value.** It detects Guna anomalies (collapse = all states near zero, oscillation = rapid switching, stagnation = stuck) — these map directly to agentic governance signals. The nn.Module `SovereignGunaComputer` is model-internal.

#### D. Wiring target
- `GunaMonitor` anomaly detection → could feed `entropy_adapter.py` or `sovereign_bridge.py` as additional volatility/anomaly signals
- NOT the nn.Module — that stays in model

#### E. Wiring mechanism
- `GunaMonitor` is already pure Python (no nn.Module, just rolling stats)
- Could be imported directly by signal adapters
- OR: expose anomaly flags in inference_bridge projection metadata

#### F. Recommended action
**Expose via adapter** — Extract `GunaMonitor` anomaly signals (collapse, oscillation, stagnation flags) into inference_bridge output or a lightweight adapter that signal_reconciliation.py can consume.

#### G. Priority
**P2** — Enrichment. The basic Guna signal already flows through the 32D projection.

---

### File 6: `observer.py`

**Classification:** MODEL ARCHITECTURE — TRAINING/INFERENCE nn.Module

#### A. Purpose
Computes the full 128D Biological Header at each step:
- `SovereignObserver` (nn.Module): Concatenates Guna[16D] | S-Signal[32D] | R-Signal[48D] | C-Signal[32D]
- `BhavaTransitionPrior` (nn.Module): 12x12 transition mask for valid Bhava state transitions — prevents "ontological teleportation"
- `DeterministicPhonemeEncoder` (nn.Module): SHA256-based phoneme→32D encoding (deterministic, no randomness)
- `ReferentLookup` (nn.Module): S-Signal computation via WORD_TO_REFERENT dictionary

#### B. Current usage
- Core component of model forward pass — called every step to produce 128D state
- Used by training loop and by inference_bridge (which projects the 128D output)
- NOT directly imported by agentic framework

#### C. Runtime value
**Indirect.** The observer produces the 128D state that inference_bridge projects to 32D. It's the source-of-truth for sovereign state, but it's deeply entangled with model internals (attention weights, hidden states).

`BhavaTransitionPrior` has governance value — its transition constraints could inform JEPA regime transition rules.

#### D. Wiring target
- NOT directly wireable — nn.Module that runs inside model forward pass
- `BhavaTransitionPrior` transition matrix → could be extracted as governance data for jepa_governance.py

#### E. Wiring mechanism
- Extract transition matrix constants to shared location
- Observer output already flows through inference_bridge → sovereign_bridge

#### F. Recommended action
**Keep training/inference only.** Extract transition matrix constants if jepa_governance needs them.

#### G. Priority
**P3** — Observer is already doing its job. Transition matrix extraction is low-urgency.

---

### File 7: `router.py`

**Classification:** RUNTIME READY BUT UNWIRED

#### A. Purpose
Dynamic nexus selection for Virtual Nexus topology — **pure Python, no PyTorch**:
- `NexusMode` (Enum): 3 topology modes (4/8 logic-heavy, 6/6 balanced, 8/4 memory-heavy)
- `SovereignRouter`: Selects nexus position based on ontological layer, with fallback keyword routing
- `SovereignRoutingDecision` (dataclass): Extended routing decision with Bhava-to-Nexus mapping
- `ONTOLOGY_TO_NEXUS`: Dict mapping 12 ontological layers to nexus positions
- Helper functions: `is_logic_heavy()`, `is_memory_heavy()`, `get_optimal_nexus()`

#### B. Current usage
- Used by `transformer.py` for dynamic layer topology selection
- NOT imported by agentic framework
- NOT used by any governance component

#### C. Runtime value
**Medium-high.** The routing logic maps ontological context to compute topology. This is directly relevant to:
- Domain policy layer (what domain are we in → what restrictions apply)
- JEPA governance (what ontological regime → what governance mode)
- MCP gateway (is this a logic-heavy or memory-heavy operation → different risk profile)

The `ONTOLOGY_TO_NEXUS` mapping is pure data that could enrich governance decisions.

#### D. Wiring target
- `domain_policy.py` — ontological routing could inform domain action mode
- `jepa_governance.py` — nexus mode could inform regime classification
- Signal adapters — routing decision could be an input signal

#### E. Wiring mechanism
- **Direct import** — no PyTorch dependency, pure Python dataclasses and enums
- `SovereignRouter` or just `ONTOLOGY_TO_NEXUS` + helpers can be imported directly

#### F. Recommended action
**Wire now** — This is one of the easiest files to integrate. Pure Python, clean API, governance-relevant.

#### G. Priority
**P1** — Low effort, clear value for domain policy and JEPA governance enrichment.

---

### File 8: `insight_gate.py`

**Classification:** GOVERNANCE-RELEVANT — PARTIALLY EXTRACTABLE

#### A. Purpose
"Pre-Frontal Cortex" implementing two-stage deterministic epistemological gate (Formula [259]):
- `InsightGateConfig` (dataclass): Stability/risk thresholds, accuracy minimums, Vritti whitelist, Guna coherence thresholds
- `InsightGate` (nn.Module): Two-stage gate:
  1. **Eligibility**: System stability ≥ threshold, R-Accuracy ≥ min, S-Accuracy ≥ min, Vritti in allowed modes (Pramana, Smriti)
  2. **Release**: Disruption risk ≤ threshold
- Key methods: `check_eligibility()`, `check_release()`, `get_surfacing_penalty()`, `get_telemetry()`

#### B. Current usage
- Used in inference/generation to gate complex symbolic output
- NOT imported by agentic framework
- Contains both nn.Module infrastructure (EMA buffers) and governance logic

#### C. Runtime value
**High.** InsightGate's two-stage eligibility/release pattern maps directly to the agentic framework's ConfidenceGate → SafetyContract pipeline. The thresholds and logic (stability check, Vritti whitelist, risk check) are governance primitives.

Specific value:
- Eligibility check → ConfidenceGate precondition enrichment
- Release check → SafetyContract precondition enrichment
- Surfacing penalty → confidence penalty for governance decisions
- Telemetry → observability for governance audit trail

#### D. Wiring target
- `confidence_gate.py` — eligibility signals as additional ConfidenceSignals input
- `safety_contract.py` — release/risk signals as precondition enrichment
- `governance_service.py` — telemetry for audit events

#### E. Wiring mechanism
- **Refactor first**: Extract the eligibility/release logic into pure functions that take floats (not tensors)
- The config thresholds are already pure Python
- EMA drift normalization needs to be decoupled from nn.Module buffers

#### F. Recommended action
**Refactor first** — Extract `check_eligibility()` and `check_release()` into pure-function equivalents that accept pre-extracted float signals. Then wire into governance.

#### G. Priority
**P1** — High governance value, moderate refactor effort. The two-stage gate pattern is exactly what the governance pipeline needs.

---

### File 9: `embedding.py`

**Classification:** MODEL ARCHITECTURE — TRAINING ONLY

#### A. Purpose
Composite embedding layer separating learned semantic body (896D) from enforced header (128D):
- `SovereignEmbeddingConfig` (dataclass): vocab_size, d_model (1024), body/header dimension splits
- `SovereignEmbedding` (nn.Module): Body (896D learned) + Header (128D enforced R/S/C/G signals)
- `SovereignOutputHead` (nn.Module): Output prediction head for token logits + R/S/C signal heads

#### B. Current usage
- Used by `transformer.py` and `trainer.py` during model construction
- NOT imported by agentic framework

#### C. Runtime value
**None for governance.** This is a model architecture component. The embedding layer's output is consumed by the model forward pass, which eventually produces the 128D state that flows through inference_bridge.

#### D. Wiring target
Nowhere. Model architecture stays in model code.

#### E. Wiring mechanism
N/A

#### F. Recommended action
**Keep training-only.** No governance value.

#### G. Priority
**P3** — No action needed.

---

### File 10: `transformer.py`

**Classification:** MODEL ARCHITECTURE — TRAINING ONLY

#### A. Purpose
Hybrid transformer with Virtual Nexus and PID Governor:
- `SovereignTransformerConfig` (dataclass): Architecture config (1024 embed, 12 layers, 16 heads, nexus position)
- `AmbidextrousLayer` (nn.Module): Can operate in quadratic O(n²) or phase O(n) attention modes
- `SovereignTransformer` (nn.Module): Main model with dynamic nexus selection, PID gating, generation support

#### B. Current usage
- Core model architecture used by trainer
- NOT imported by agentic framework

#### C. Runtime value
**None for governance.** The transformer produces the hidden states that the observer/kernel process into 128D state. The agentic framework consumes the final projected 32D state, not the transformer internals.

#### D. Wiring target
Nowhere. Model architecture stays in model code.

#### E. Wiring mechanism
N/A

#### F. Recommended action
**Keep training-only.** No governance value.

#### G. Priority
**P3** — No action needed.

---

### File 11: `phase_attention.py`

**Classification:** MODEL ARCHITECTURE — TRAINING ONLY

#### A. Purpose
Phase memory layer seeded by R-Signal for O(n) attention scaling:
- `SovereignPhaseAttention` (nn.Module): R-Signal-driven phase rotation where same-intent tokens constructively interfere. Vritti states modulate phase stiffness (Pramana=rigid, Vikalpa=fluid).
- `SovereignPhaseTransformerLayer` (nn.Module): Full transformer layer wrapping phase attention + FFN.

#### B. Current usage
- Used by `transformer.py` for phase-mode layers (post-nexus)
- NOT imported by agentic framework

#### C. Runtime value
**None for governance.** Neural attention mechanism. Phase coherence already captured by inference_bridge.

#### D. Wiring target
Nowhere.

#### E. Wiring mechanism
N/A

#### F. Recommended action
**Keep training-only.**

#### G. Priority
**P3** — No action needed.

---

### File 12: `heartbeat.py`

**Classification:** EXPORT / TOOLING — VISUALIZATION

#### A. Purpose
Terminal-based real-time visualization of PID Governor state — **pure Python, no PyTorch**:
- `SovereignHeartbeat`: Renders Vritti mode, PID gains, Guna pulse, S-drift, brake status with ANSI colors
- `HeartbeatConfig` (dataclass): Display configuration
- `format_governor_telemetry()`: Multi-line telemetry table

#### B. Current usage
- Used during training for real-time monitoring
- NOT imported by agentic framework

#### C. Runtime value
**Low-medium.** Visualization could be useful for diagnostics but governance has its own logging.

#### D. Wiring target
Nowhere worth formal wiring.

#### F. Recommended action
**Keep separate.** Optionally use for debugging.

#### G. Priority
**P3** — Nice to have, not governance-relevant.

---

### File 13: `pid_governor.py`

**Classification:** MODEL ARCHITECTURE — TRAINING/INFERENCE nn.Module

#### A. Purpose
Control-theoretic gating at the transformer nexus:
- `PIDGovernorConfig` (dataclass): Kp/Ki/Kd defaults, authority threshold, damping
- `PIDGovernor` (nn.Module): Vritti-adaptive PID gains, dampens semantic body when authority low. Contains `VRITTI_PID_TABLE` and `ONTOLOGY_VRITTI_MAP` as class constants.
- `EmergencyBrake` (nn.Module): PD controller for catastrophic deviation

#### B. Current usage
- Used by `transformer.py` at nexus point
- NOT imported by agentic framework

#### C. Runtime value
**Constants have governance value.** `VRITTI_PID_TABLE` and `ONTOLOGY_VRITTI_MAP` are pure data useful for JEPA governance. The EmergencyBrake pattern is already implemented by SafetyContract.

#### D. Wiring target
Constants → shared constants module (same consolidation as vritti.py)

#### E. Wiring mechanism
Extract constants to shared module. nn.Module stays in model code.

#### F. Recommended action
**Refactor first** — Extract constants.

#### G. Priority
**P2** — Constants consolidation.

---

### File 14: `hierarchical_gradient_scaler.py`

**Classification:** TRAINING ONLY

#### A. Purpose
Gradient scaling with 9:3 authority/sensory layer split. `HierarchicalGradientScaler`, `DynamicRelaxationController`, `compute_s_drift()`.

#### B. Current usage
Training loop exclusively. NOT imported by agentic framework.

#### C. Runtime value
**None.** Gradient scaling is training-only.

#### D–G.
Wiring target: Nowhere. Action: **Keep training-only.** Priority: **P3.**

---

### File 15: `tagger.py`

**Classification:** DATA PREPROCESSING — SHOULD STAY SEPARATE

#### A. Purpose
Token-level signal extraction: `SovereignTokenizer` preprocesses tokens into C/S/R/G signals via SHA256 hashing, WordNet, Lesk disambiguation, POS tagging. Requires NLTK.

#### B. Current usage
Data preprocessing pipeline. NOT imported by agentic framework.

#### C. Runtime value
**Low.** At inference time, the model produces signals internally — tagger not needed.

#### D–G.
Wiring target: Nowhere. Action: **Keep separate.** Priority: **P3.**

---

### File 16: `metrics.py`

**Classification:** GOVERNANCE-RELEVANT — PARTIALLY EXTRACTABLE

#### A. Purpose
5 Patent Formulas for real-time health monitoring:
- `SovereignMetrics`: Static methods for 5-pillar health (R-Acc, S-Acc, Guna Entropy, Semantic Drift, Guna Coherence)
- `SovereignEngine` (nn.Module): Trainable loss wrapping B1/S3/S8/U1/U2
- `SovereignAlertMonitor`: State machine STABLE→ALERT→LOCKDOWN→RECOVERING
- `S8StabilityHook`: Inertial brake with dH/dt monitoring
- `compute_semantic_entropy()`, `get_entropy_status()`, `format_sovereign_dashboard()`

#### B. Current usage
Training loop for health monitoring. NOT imported by agentic framework.

#### C. Runtime value
**High for specific components:**
1. **`SovereignAlertMonitor`** — Regime state machine directly analogous to JEPA governance regimes
2. **`compute_semantic_entropy()`** — Could feed `entropy_adapter.py`
3. **`get_health_stats()`** — Richer health signals than current 32D mapping
4. **`format_sovereign_dashboard()`** — Audit trail formatting

`SovereignEngine` (nn.Module) is training-only.

#### D. Wiring target
- `SovereignAlertMonitor` → `jepa_governance.py` (regime validation)
- `compute_semantic_entropy()` → `entropy_adapter.py`
- `get_health_stats()` → `sovereign_bridge.py`

#### E. Wiring mechanism
- `SovereignAlertMonitor` is pure Python — direct import
- Split file to decouple from nn.Module SovereignEngine

#### F. Recommended action
**Refactor first** — Split into `metrics_runtime.py` (pure Python) + `metrics_training.py` (nn.Module). Wire runtime portion.

#### G. Priority
**P1** — AlertMonitor and entropy are high-value governance signals.

---

### File 17: `loss.py`

**Classification:** TRAINING ONLY

#### A. Purpose
Hardened loss function: `SovereignLossConfig`, `SovereignLoss` (nn.Module), `LegacyLossAdapter`.

#### B–G.
Training only. NOT imported by agentic framework. No runtime value. Action: **Keep training-only.** Priority: **P3.**

---

### File 18: `sovereign_loss.py`

**Classification:** TRAINING ONLY

#### A. Purpose
SRK multi-objective loss: `SovereignLoss`, score calculators, `SovereignAnnealer`, `TeleologicalOptimizer`.

#### B–G.
Training only. NOT imported by agentic framework. No runtime value. Action: **Keep training-only.** Priority: **P3.**

---

### File 19: `train_loss.py`

**Classification:** TRAINING ONLY

#### A. Purpose
Training-specific losses: `MultiObjectiveLoss`, `RSignalCoherenceLoss`, `IntentDriftMonitor`, `VrittiLoss`.

#### B–G.
Training only. NOT imported by agentic framework. No runtime value. Action: **Keep training-only.** Priority: **P3.**

---

### File 20: `stitched_objective.py`

**Classification:** RUNTIME PARTIALLY RELEVANT — NEEDS EXTRACTION

#### A. Purpose
Penalized token scoring during generation:
- `VrittiGovernor` (nn.Module): Orchestrates anomaly score (S_drift), emergency brake, telemetry
- `RedundancyPenalty`, `DomainJumpPenalty`, `TamasicInhibitor` (all nn.Module)

#### B. Current usage
Generation/inference for penalized scoring. NOT imported by agentic framework.

#### C. Runtime value
**Medium.** VrittiGovernor's S_drift and brake logic are governance-relevant. But deeply nn.Module-entangled.

#### D. Wiring target
- S_drift → `sovereign_bridge.py` as volatility signal
- Brake state → `safety_contract.py`

#### E. Wiring mechanism
Expose telemetry dict through inference_bridge output metadata.

#### F. Recommended action
**Bridge first** — Don't wire nn.Module directly. Expose telemetry via inference_bridge.

#### G. Priority
**P2** — Valuable signals but significant extraction effort.

---

### File 21: `telemetry.py`

**Classification:** RUNTIME READY BUT UNWIRED

#### A. Purpose
Real-time 128D state monitoring — **minimal PyTorch**:
- `StateSnapshot` (dataclass): Timestamped snapshot with guna, authority, vritti, anomaly flags
- `SovereignMonitor`: Structured observability of sovereign state with history and statistics
- `SovereignProfiler`: Performance timing
- `create_monitor()`: Factory function

#### B. Current usage
Training monitoring. NOT imported by agentic framework.

#### C. Runtime value
**High.** `StateSnapshot` is the right abstraction for governance audit events. `SovereignMonitor` provides exactly the diagnostic information governance needs: guna decomposition, authority, active Vritti, anomaly flags, windowed statistics.

#### D. Wiring target
- `governance_service.py` → audit event enrichment
- `sovereign_bridge.py` → richer signal extraction
- Ledger/replay layer → state snapshots for verification

#### E. Wiring mechanism
- `StateSnapshot` is a pure dataclass — directly usable
- `SovereignMonitor` needs minor adaptation for float inputs
- `create_monitor()` factory is clean

#### F. Recommended action
**Wire now** — Adapt monitor for floats. Wire StateSnapshot into governance audit.

#### G. Priority
**P1** — High observability value, low effort.

---

### File 22: `cognade_export.py`

**Classification:** EXPORT / TOOLING

#### A. Purpose
Hardware bridge — C header generation, binary serialization for PA-VPU.

#### B–G.
Hardware export. NOT imported by agentic framework. No governance value. Action: **Keep separate.** Priority: **P3.**

---

### File 23: `trainer.py`

**Classification:** TRAINING ONLY

#### A. Purpose
Complete training loop: `SovereignTrainer`, `SovereignDataset`, `RSignalGovernor`, `create_sovereign_model()`.

#### B–G.
Training only. NOT imported by agentic framework. No runtime value. Action: **Keep training-only.** Priority: **P3.**

---

### File 24: `training/__init__.py`

**Classification:** TRAINING ONLY

#### A. Purpose
Re-exports training submodule components: `InoculationTrainer`, `InoculationConfig`, `AlphaScheduler`, `BankDisambiguationTest`, `HomonymTestSuite`, `AuthorityStressTest`, and related factories/results.

#### B–G.
Re-export hub for training. No runtime value. Action: **Keep training-only.** Priority: **P3.**

---

### File 25: `training/stress_test.py`

**Classification:** TRAINING ONLY — TEST INFRASTRUCTURE

#### A. Purpose
Verifies emergency brake activation under adversarial conditions:
- `AuthorityStressTest`: Feeds high-entropy nonsense / repetitive tokens, verifies Authority < 0.3 and Tamas > 0.8
- `StressTestResult` (dataclass): Test outcome container
- Tests: entropy stress, repetition stress, adversarial stress

#### B. Current usage
Training validation. NOT imported by agentic framework.

#### C. Runtime value
**None directly.** However, the stress test patterns (detecting authority collapse, tamas spike) could inform governance test suites.

#### D–G.
Wiring target: Nowhere. Action: **Keep training-only.** Could inspire governance tests but not wire directly. Priority: **P3.**

---

### File 26: `training/validation.py`

**Classification:** TRAINING ONLY — TEST INFRASTRUCTURE

#### A. Purpose
Homonym disambiguation validation ("Hello World" test for Sovereign-1):
- `BankDisambiguationTest`: Tests "bank" in financial vs. natural contexts — passes if cosine similarity < 0.4
- `HomonymTestSuite`: Extended suite for bat, bark, light with ontological anchors
- `DisambiguationResult` (dataclass): Test outcome

#### B. Current usage
Training validation. NOT imported by agentic framework.

#### C. Runtime value
**None.** Model evaluation test.

#### D–G.
Wiring target: Nowhere. Action: **Keep training-only.** Priority: **P3.**

---

### File 27: `training/inoculation.py`

**Classification:** TRAINING ONLY

#### A. Purpose
Self-supervised training loop that "stamps" Sovereign logic into weights:
- `InoculationTrainer`: Forces model to predict Next-State deltas (not just next tokens)
- `InoculationConfig` (dataclass): Training config with alpha decay
- `AlphaScheduler`: Alpha 1.0→0.2 decay over 3 epochs

#### B. Current usage
Training only. NOT imported by agentic framework.

#### C. Runtime value
**None.** Training loop with optimizer, gradient clipping, backprop.

#### D–G.
Wiring target: Nowhere. Action: **Keep training-only.** Priority: **P3.**

---

### File 28: `tests/__init__.py`

**Classification:** TEST INFRASTRUCTURE

#### A. Purpose
Empty test package initialization (docstring only: "V9.8.0 Unit Tests").

#### B–G.
No runtime value. Action: **Keep as-is.** Priority: **P3.**

---

### File 29: `tests/test_srk.py`

**Classification:** TEST INFRASTRUCTURE

#### A. Purpose
Comprehensive pytest suite for SRK v9.8.0:
- 10 test classes, ~40 test methods
- Tests: SRKConfig, forward pass at critical layers, OPB dimension locking, UserOntologicalMirror, checkpoint persistence, sovereign loss, annealing, IsomorphicMappingRouter, full integration

#### B. Current usage
Pytest test suite. NOT imported by agentic framework.

#### C. Runtime value
**None directly.** Validates sovereign components but doesn't feed runtime.

#### D–G.
Wiring target: Nowhere. Action: **Keep as test suite.** Priority: **P3.**

---
---

## 4. Cross-File Observations

### 4.1 Classification Summary

| Classification | Files | Count |
|---------------|-------|-------|
| **RUNTIME READY — ALREADY WIRED** | inference_bridge.py | 1 |
| **RUNTIME READY BUT UNWIRED** | router.py, telemetry.py | 2 |
| **GOVERNANCE-RELEVANT (extractable)** | insight_gate.py, metrics.py | 2 |
| **RUNTIME PARTIALLY RELEVANT** | stitched_objective.py, reasoning_kernel.py | 2 |
| **MODEL ARCHITECTURE (nn.Module)** | embedding.py, transformer.py, phase_attention.py, observer.py, guna.py, vritti.py, pid_governor.py | 7 |
| **TRAINING ONLY** | loss.py, sovereign_loss.py, train_loss.py, trainer.py, hierarchical_gradient_scaler.py, training/*.py | 9 |
| **EXPORT/TOOLING** | cognade_export.py, heartbeat.py, __init__.py | 3 |
| **TEST INFRASTRUCTURE** | tests/*.py | 2 |
| **DATA PREPROCESSING** | tagger.py | 1 |

### 4.2 Duplicates and Redundancy

1. **Vritti constants are duplicated in 4+ places:**
   - `vritti.py`: `VrittiState` enum, `VRITTI_PHYSICS`, transition matrices
   - `pid_governor.py`: `VRITTI_PID_TABLE`, `ONTOLOGY_VRITTI_MAP`
   - `sovereign_bridge.py`: `VRITTI_FACT=0`, `VRITTI_ERROR=1`, etc. (index constants)
   - `jepa_governance.py`: `VRITTI_NAMES`, `OBSERVATION_VRITTIS`, `EXECUTION_VRITTIS`
   - `telemetry.py`: `VRITTI_NAMES`
   
   **Action:** Consolidate into a single `sovereign_constants.py` shared across sovereign/ and agentic_framework/.

2. **Bhava names duplicated:**
   - `telemetry.py`: `BHAVA_NAMES`
   - `sovereign_bridge.py`: Bhava slice indices
   - `observer.py`: BhavaTransitionPrior
   - `reasoning_kernel.py`: `BHAVA_NAMES`
   
   **Action:** Same consolidation.

3. **Alert/regime state machines overlap:**
   - `metrics.py`: `SovereignAlertMonitor` (STABLE→ALERT→LOCKDOWN→RECOVERING)
   - `jepa_governance.py`: `GovernanceRegime` (NORMAL→PROCESS_DRIFT→SEMANTIC_SHIFT→DUAL_ANOMALY)
   
   These are **not exact duplicates** — AlertMonitor tracks sovereign health, GovernanceRegime tracks agentic behavior. But they should be **reconciled** so AlertMonitor can inform GovernanceRegime.

4. **Entropy computation overlap:**
   - `metrics.py`: `compute_semantic_entropy()` (tensor-based)
   - `agentic/entropy/`: Canonical entropy engine (runtime)
   - `entropy_adapter.py`: Signal adapter consuming entropy
   
   **Action:** Make `entropy_adapter.py` optionally consume sovereign semantic entropy when available.

### 4.3 Training vs Runtime Split

**Clear training-only (no runtime path):** 13 files
- loss.py, sovereign_loss.py, train_loss.py, trainer.py
- hierarchical_gradient_scaler.py
- training/__init__.py, training/stress_test.py, training/validation.py, training/inoculation.py
- tests/__init__.py, tests/test_srk.py
- embedding.py (model architecture)
- tagger.py (data preprocessing)

**Clear runtime path (already producing governance signals):** 1 file
- inference_bridge.py → inference/manager.py → sovereign_bridge.py → ConfidenceGate/SafetyContract

**Runtime-capable but unwired:** 4 files
- router.py (pure Python, no obstacles)
- telemetry.py (minimal adaptation needed)
- insight_gate.py (needs pure-function extraction)
- metrics.py (needs file split)

**Model architecture — runtime-relevant but not directly wireable:** 6 files
- reasoning_kernel.py, vritti.py, guna.py, observer.py, pid_governor.py, transformer.py
- These produce the state that inference_bridge projects. They're on the runtime path inside the model but can't be directly imported by the governance layer.

### 4.4 Integration Bottlenecks

1. **PyTorch entanglement:** 16 of 29 files are nn.Module-heavy. The agentic framework is pure Python. Any wiring must go through a bridge that converts tensors→floats.

2. **The inference_bridge is the single chokepoint:** All sovereign state reaches the agentic framework through `inference_bridge.py` → `sovereign_bridge.py`. Enriching the pipeline means enriching these two files, not adding more direct imports.

3. **No live sovereign monitor in the agentic framework:** The agentic framework doesn't maintain a running `SovereignMonitor` instance. State snapshots are computed per-request. For richer diagnostics, the framework needs to instantiate and maintain a monitor.

4. **Constants duplication blocks clean wiring:** The Vritti/Bhava/Guna/Kosha constants are duplicated across both stacks, making it unclear which is canonical. A shared constants module is prerequisite.

---

## 5. Top 5 Files to Wire into the Agentic Framework

### Rank 1: `telemetry.py` — Wire Now

**Why:** Provides `StateSnapshot` (pure dataclass) and `SovereignMonitor` (structured observability) — exactly what governance audit events need. Minimal PyTorch dependency (only tensor extraction that can be adapted to floats).

**Gap without this:** The governance pipeline currently makes authorization decisions based on instantaneous 32D→ConfidenceSignals projections, but has **no structured history** of sovereign state. `GovernanceService` audit events record the decision but not the underlying cognitive state that drove it. This means:
- **Replay verification is blind** — the ledger can replay the decision but cannot verify what the model's sovereign state was at the time. There is no state snapshot attached to audit events.
- **Windowed statistics are missing** — governance can see "Vritti is currently FACT" but not "Vritti has been oscillating between FACT and ERROR for the last 20 steps." The `SovereignMonitor` tracks exactly this kind of rolling history.
- **Anomaly detection is shallow** — without the monitor's history-based anomaly detection (guna collapse, oscillation, stagnation), the framework relies solely on single-step signal thresholds. Patterns that emerge over time (gradual drift, periodic instability) are invisible.
- **Diagnostics for debugging governance decisions are absent** — when a governance decision seems wrong, there's no structured snapshot of sovereign state to inspect.

**Where:**
- `governance_service.py` → enrich `AuditEvent` with `StateSnapshot`
- `sovereign_bridge.py` → optionally use `SovereignMonitor` for windowed statistics
- Ledger/replay → `StateSnapshot` as replay-verifiable record

**How:**
1. Add a `from_floats()` classmethod to `SovereignMonitor` that accepts pre-extracted float lists instead of tensors
2. Import `StateSnapshot` in governance_service.py
3. Include snapshot in audit event metadata

### Rank 2: `router.py` — Wire Now

**Why:** Pure Python, zero PyTorch. `ONTOLOGY_TO_NEXUS` mapping and `NexusMode` enum provide ontological routing that directly enriches domain policy and JEPA governance.

**Gap without this:** The domain policy layer (`domain_policy.py`) and JEPA governance (`jepa_governance.py`) currently make decisions without knowing **what kind of cognitive task** the model is performing at the ontological level. Specifically:
- **Domain policy treats all tasks equally** — a reasoning-heavy task (O7 Reasoning, O10 Integration) and a memory-recall task (O4 Structure, O5 Cognition) get the same domain action mode. But reasoning tasks should arguably have stricter governance (higher stakes, more likely to produce novel claims) while memory tasks are lower risk.
- **JEPA governance has no ontological context** — the `ResidualGovernor` compares JEPA composite signals against runtime process state, but doesn't know whether the model is in logic-heavy mode (nexus 4/8) or memory-heavy mode (8/4). This means regime drift detection cannot distinguish between "the model shifted to deeper reasoning" (expected, benign) and "the model drifted to an unrelated cognitive mode" (suspicious).
- **The mapping already exists and is pure data** — `ONTOLOGY_TO_NEXUS` maps all 12 ontological layers to 3 nexus modes. This is not speculative; it's the same routing the model uses internally. The governance layer simply doesn't have access to it.

**Where:**
- `domain_policy.py` → use `ONTOLOGY_TO_NEXUS` to inform domain action modes
- `jepa_governance.py` → use nexus mode as additional regime signal

**How:**
1. Direct import: `from agentic.sovereign.router import ONTOLOGY_TO_NEXUS, NexusMode, is_logic_heavy, is_memory_heavy`
2. In domain_policy: map ontological layer → nexus → domain restrictions
3. In jepa_governance: logic-heavy nexus = stricter governance for reasoning tasks

### Rank 3: `metrics.py` (runtime portion) — Refactor First, Then Wire

**Why:** `SovereignAlertMonitor` provides a regime state machine (STABLE→ALERT→LOCKDOWN→RECOVERING) that can validate/inform JEPA governance regimes. `compute_semantic_entropy()` enriches the entropy adapter.

**Gap without this:** The governance pipeline has two independent regime/alert systems that don't talk to each other, and the entropy adapter lacks a sovereign-grounded entropy source:
- **JEPA governance regime is unvalidated by sovereign health** — `jepa_governance.py` classifies regimes as NORMAL/PROCESS_DRIFT/SEMANTIC_SHIFT/DUAL_ANOMALY based on JEPA composite signals, but the sovereign layer has its own health assessment (STABLE/ALERT/LOCKDOWN/RECOVERING) based on 5-pillar monitoring (R-Acc, S-Acc, Guna Entropy, Semantic Drift, Guna Coherence). These two systems can **disagree silently**: JEPA might say NORMAL while sovereign health is in ALERT because Guna coherence is deteriorating. Without cross-validation, governance decisions can be over-permissive when the model is genuinely unstable.
- **Entropy adapter uses only the canonical entropy engine** — `entropy_adapter.py` derives entropy from the `agentic/entropy/` module, which approximates incoherence from surface signals. The sovereign `compute_semantic_entropy()` computes Shannon entropy from the actual token distribution — a more direct measure of model uncertainty. Without this, the entropy penalty applied to confidence is an approximation when a ground-truth signal exists.
- **No 5-pillar health view in governance** — The sovereign health metrics (R-Accuracy, S-Accuracy, Guna Entropy, Semantic Drift, Guna Coherence) provide a richer picture than the binary JEPA regime. The governance pipeline currently cannot say "R-Signal accuracy is dropping" — it can only say "regime drifted." The 5-pillar view enables more targeted governance responses.

**Where:**
- `SovereignAlertMonitor` → `jepa_governance.py` (regime cross-validation)
- `compute_semantic_entropy()` → `entropy_adapter.py`
- `format_sovereign_dashboard()` → governance audit logging

**How:**
1. Split metrics.py into `metrics_runtime.py` (AlertMonitor, entropy, health stats) and `metrics_training.py` (SovereignEngine)
2. Adapt `compute_semantic_entropy()` to accept float lists
3. Import AlertMonitor in governance_service or jepa_governance
4. Wire entropy into entropy_adapter as an optional sovereign source

### Rank 4: `insight_gate.py` — Refactor First, Then Wire

**Why:** Two-stage eligibility/release gate (Formula [259]) maps directly to ConfidenceGate → SafetyContract. The thresholds and Vritti whitelist logic are governance primitives.

**Gap without this:** The ConfidenceGate and SafetyContract currently evaluate sovereign signals as **independent scalar thresholds**, but InsightGate implements a more sophisticated two-stage pattern that the governance pipeline is missing:
- **No eligibility pre-check in governance** — ConfidenceGate evaluates signals and produces an execution mode, but doesn't have an explicit "is the system stable enough to even consider acting?" check. InsightGate's eligibility stage does exactly this: it checks system stability, R-Signal accuracy, S-Signal accuracy, AND Vritti mode (only Pramana/Smriti allowed) before even evaluating the action. The governance pipeline jumps straight to "what execution mode?" without this stability gate.
- **No Vritti whitelist enforcement** — InsightGate explicitly blocks actions when the model is in Viparyaya (error) or Nidra (dormant) modes. The governance pipeline's `jepa_governance.py` has `OBSERVATION_VRITTIS` (viparyaya, nidra) marked as "should not execute," but this is advisory, not enforced as a hard pre-check. InsightGate makes it a fail-closed precondition.
- **No disruption risk assessment** — InsightGate's release stage computes a disruption risk score (how much would this action perturb the current state?) and blocks if risk exceeds threshold. SafetyContract checks internal_consistency, goal_alignment, reversal_risk, and identity_stability — but not "how disruptive is the proposed action to current sovereign stability?" This is a distinct signal.
- **The sovereign layer already has these thresholds tuned** — InsightGateConfig contains calibrated thresholds for stability (0.6), risk (0.4), accuracy minimums, and Guna coherence. Porting these to governance gives the framework empirically-grounded values rather than the current defaults.

**Where:**
- Eligibility signals → `confidence_gate.py` (precondition enrichment)
- Release/risk signals → `safety_contract.py` (precondition enrichment)
- Gate telemetry → `governance_service.py` (audit)

**How:**
1. Extract `check_eligibility()` and `check_release()` into pure functions that accept float dicts
2. Move `InsightGateConfig` thresholds to a governance-consumable format
3. Create `insight_adapter.py` in signal_adapters/ that wraps the pure functions
4. Wire into ConfidenceGate as additional signal source

### Rank 5: `reasoning_kernel.py` (diagnostic extraction) — Bridge First

**Why:** The kernel's Mauna protocol, OPB dimension lock, and logic template selection provide signals not currently exposed through the 32D projection.

**Gap without this:** The 32D→ConfidenceSignals projection captures Vritti, Kosha, and Guna — but **three critical reasoning-kernel signals are invisible** to the governance layer:
- **Mauna (silence) protocol is lost** — The reasoning kernel has a `MaunaProtocol` that decides when the model should be silent (high uncertainty, ontological confusion). This is a hard "don't respond" signal that the governance pipeline doesn't receive. Currently, the ConfidenceGate might produce `CAUTIOUS` mode when the kernel actually wants `BLOCKED` (silence). The result is that the framework may allow responses when the model's own reasoning kernel has determined it should stay quiet.
- **OPB dimension lock is collapsed into generic identity_stability** — The `OPBDimensionLock` tracks which specific ontological dimensions are active and carries them across domain switches with configurable decay. The `sovereign_bridge.py` maps Guna STABLE + low VELOCITY into a generic `identity_stability` score, but this misses the granular signal: "O7 Reasoning is locked at 0.85 activation and decaying at rate 0.02/step." This granular lock state would tell governance whether identity stability is driven by genuine ontological persistence or just low state velocity.
- **Active logic template is unknown to governance** — The `IsomorphicMappingRouter` selects between 5 logic templates (DEDUCTION, INDUCTION, ABDUCTION, ANALOGY, SYNTHESIS) based on cross-domain bridge detection. The governance layer doesn't know which reasoning mode is active. This matters because deductive reasoning (high confidence, verifiable) warrants different governance than abductive reasoning (speculative, lower confidence). Currently, governance treats all reasoning modes identically.
- **These signals exist but are discarded** — The inference_bridge projects 128D→32D and drops kernel diagnostics. Adding an optional diagnostics dict to the projection result is a non-breaking enrichment that makes existing information accessible.

**Where:**
- Mauna state → `sovereign_bridge.py` as "sovereign_silence" signal → ConfidenceGate
- OPB lock → `sovereign_bridge.py` as enriched identity_stability
- Active logic template → governance audit metadata

**How:**
1. Add optional diagnostic dict output to kernel's `forward()` method
2. Capture diagnostics in `inference_bridge.py` projection metadata
3. Forward enriched metadata through `sovereign_bridge.py`
4. No direct import of nn.Module — signals flow through the existing bridge

---

## 6. Files to Keep Separate (Not Wire)

| File | Why Not |
|------|---------|
| `embedding.py` | Model architecture. No governance value. Output consumed via forward pass → inference_bridge. |
| `transformer.py` | Model architecture. Hidden states flow through observer → inference_bridge. |
| `phase_attention.py` | Neural attention mechanism. Phase coherence captured in 128D state. |
| `observer.py` | Computes 128D state inside forward pass. Already consumed via inference_bridge. |
| `guna.py` (nn.Module) | SovereignGunaComputer is model-internal. Guna signals already in 32D state. GunaMonitor could be exposed separately but not the nn.Module. |
| `vritti.py` (nn.Module) | PIDGovernor/VrittiHead are model-internal. Vritti signals already in 32D state. Constants should be consolidated but the module stays. |
| `pid_governor.py` (nn.Module) | Model-internal control. EmergencyBrake pattern already in SafetyContract. |
| `loss.py` | Training-only loss computation. |
| `sovereign_loss.py` | Training-only multi-objective loss. |
| `train_loss.py` | Training-only loss extensions. |
| `trainer.py` | Training loop. |
| `hierarchical_gradient_scaler.py` | Training-only gradient management. |
| `tagger.py` | Data preprocessing with NLTK dependency. Not needed at inference. |
| `cognade_export.py` | Hardware export tooling. Orthogonal to governance. |
| `heartbeat.py` | Terminal visualization. Governance has its own logging. |
| `training/*` (3 files) | Training infrastructure: inoculation, stress tests, validation. |
| `tests/*` (2 files) | Test suites. |
| `__init__.py` | Re-export hub. Updated as needed. |
| `stitched_objective.py` | nn.Module-entangled. Telemetry should flow through inference_bridge, not direct import. |

---

## 7. Prerequisites Before Wiring

### 7.1 Shared Constants Module (Blocks: all wiring)
**Create `agentic/sovereign/constants.py`** consolidating:
- VrittiState enum + VRITTI_NAMES + VRITTI_PHYSICS + transition matrices
- BHAVA_NAMES + Bhava slice indices
- KOSHA_NAMES + Kosha slice indices
- GUNA_NAMES + Guna slice indices
- ONTOLOGY_TO_NEXUS mapping
- STATE_DIM (32), HEADER_DIM (128)

Then update sovereign_bridge.py, jepa_governance.py, telemetry.py, router.py, etc. to import from this single source.

### 7.2 Metrics File Split (Blocks: metrics wiring)
Split `metrics.py` into:
- `metrics_runtime.py`: SovereignAlertMonitor, compute_semantic_entropy, get_entropy_status, get_health_stats, format_sovereign_dashboard
- `metrics_training.py`: SovereignEngine, SovereignLossConfig (the metrics.py one), S8StabilityHook, S8BrakeState

### 7.3 InsightGate Pure-Function Extraction (Blocks: insight_gate wiring)
Extract from `insight_gate.py`:
- `check_eligibility_pure(stability, r_acc, s_acc, vritti_mode, config)` → bool
- `check_release_pure(risk, config)` → bool
- `compute_surfacing_penalty_pure(...)` → float

These accept floats, not tensors. The nn.Module InsightGate stays for model use.

### 7.4 Telemetry Float Adapter (Blocks: telemetry wiring)
Add to `SovereignMonitor`:
- `log_state_from_floats(guna_3d, authority, bhava_12, vritti_5, ...)` method
- Or create `SovereignMonitorLite` that accepts only Python floats

### 7.5 InferenceBridge Enrichment (Blocks: reasoning_kernel diagnostic wiring)
Extend `SovereignProjectionResult` to optionally include:
- `diagnostics: Dict[str, Any]` field for kernel diagnostic signals (Mauna state, OPB lock, logic template)
- This requires the reasoning kernel to output a diagnostic dict during forward()

---

## 8. Recommended Phased Integration Plan

### Phase S1: Foundation (Constants + Telemetry)
**Goal:** Establish shared vocabulary and observability

1. Create `sovereign/constants.py` with consolidated Vritti/Bhava/Kosha/Guna constants
2. Update all consumers (sovereign_bridge, jepa_governance, telemetry, router) to use shared constants
3. Add float-input support to `SovereignMonitor` / `StateSnapshot`
4. Wire `StateSnapshot` into `GovernanceService` audit events
5. Wire `router.py` (ONTOLOGY_TO_NEXUS) into domain_policy.py

**Effort:** Low. Pure Python, no nn.Module changes.
**Risk:** None. Additive, no behavior change.

### Phase S2: Governance Signal Enrichment
**Goal:** Wire sovereign health and epistemological signals into governance

1. Split `metrics.py` into runtime/training halves
2. Wire `SovereignAlertMonitor` into jepa_governance as regime advisor
3. Wire `compute_semantic_entropy()` into entropy_adapter as optional sovereign source
4. Extract InsightGate pure functions
5. Create `insight_adapter.py` signal adapter
6. Wire eligibility/release signals into ConfidenceGate/SafetyContract

**Effort:** Medium. File splits and pure-function extraction.
**Risk:** Low. New signal sources are additive and bounded.

### Phase S3: Reasoning Diagnostics
**Goal:** Surface deeper sovereign intelligence signals

1. Add diagnostic dict output to `SovereignReasoningKernel.forward()`
2. Capture diagnostics in `inference_bridge.py` projection metadata
3. Forward Mauna state, OPB lock, logic template through sovereign_bridge
4. Add diagnostic signals to ConfidenceSignals (new optional fields)
5. Wire VrittiGovernor telemetry (S_drift, brake state) through inference_bridge

**Effort:** Medium-high. Requires model code changes.
**Risk:** Medium. Modifying model forward() path needs testing.

### Phase S4: Advanced / Optional
**Goal:** Full semantic-state integration for specialized governance

1. GunaMonitor anomaly detection → entropy_adapter enrichment
2. BhavaTransitionPrior matrix → jepa_governance transition constraints
3. VrittiGovernor redundancy/domain-jump patterns → governance heuristics
4. Consider whether `SovereignAlertMonitor` should become the canonical regime state machine (replacing or informing JEPA's)

**Effort:** High. Requires deeper architectural decisions.
**Risk:** Medium. Potential for over-wiring.

---

## Summary Decision Matrix

| File | Wire? | When | Where | How | Priority |
|------|-------|------|-------|-----|----------|
| inference_bridge.py | Already wired | — | inference/manager.py | — | P0 |
| telemetry.py | **Yes** | Phase S1 | governance_service, sovereign_bridge | Float adapter | P1 |
| router.py | **Yes** | Phase S1 | domain_policy, jepa_governance | Direct import | P1 |
| metrics.py (runtime) | **Yes** | Phase S2 | jepa_governance, entropy_adapter | File split first | P1 |
| insight_gate.py | **Yes** | Phase S2 | confidence_gate, safety_contract | Pure-function extraction | P1 |
| reasoning_kernel.py | Diagnostics only | Phase S3 | sovereign_bridge via inference_bridge | Bridge enrichment | P2 |
| stitched_objective.py | Telemetry only | Phase S3 | sovereign_bridge via inference_bridge | Bridge enrichment | P2 |
| vritti.py | Constants only | Phase S1 | shared constants module | Extract constants | P2 |
| pid_governor.py | Constants only | Phase S1 | shared constants module | Extract constants | P2 |
| guna.py | GunaMonitor only | Phase S4 | entropy_adapter | Adapter extraction | P2 |
| observer.py | Transition matrix only | Phase S4 | jepa_governance | Extract constants | P3 |
| embedding.py | No | — | — | — | — |
| transformer.py | No | — | — | — | — |
| phase_attention.py | No | — | — | — | — |
| heartbeat.py | No | — | — | — | — |
| cognade_export.py | No | — | — | — | — |
| tagger.py | No | — | — | — | — |
| loss.py | No | — | — | — | — |
| sovereign_loss.py | No | — | — | — | — |
| train_loss.py | No | — | — | — | — |
| trainer.py | No | — | — | — | — |
| hierarchical_gradient_scaler.py | No | — | — | — | — |
| training/* | No | — | — | — | — |
| tests/* | No | — | — | — | — |

