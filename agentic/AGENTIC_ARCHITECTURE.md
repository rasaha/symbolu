# Agentic Architecture: Signal Integration & Policy Control Plane

> **Version:** 5.0.0 | **Updated:** 2026-04-04
>
> This document describes the five completed internal tracks that connect
> external signal sources, ontological structure, policy infrastructure,
> and safety enforcement to the agentic governance runtime:
>
> - **Sovereign track (S1–S4 + activation patch):** Bridges sovereign model
>   signals (entropy, health, insight, diagnostics, guna anomalies, bhava
>   priors, governor telemetry) into governance.
> - **Core track (C1–C4 + closure patch):** Bridges core pipeline signals
>   (coherence state, UCF consciousness, generation gate, predictive drift,
>   identity resonance, adaptive continuity, counterfactual sandbox) into
>   governance.
> - **Ontology track (O1–O4):** Canonicalizes the 12-layer ontological
>   structure, extracts safety validators, builds signal adapters for 10D
>   backbone encoding/similarity/balance, and wires the first ontology
>   consumer (mirror-pair balance) into the governance decision path.
> - **Policy track (P0–P4 + closure patch):** Builds the profile-backed
>   policy computation, simulation/comparison, lifecycle/deployment, and
>   read-only backend control-plane layer that sits alongside governance.
> - **Safety track (S0–S5):** Promotes dormant safety governance-pattern
>   primitives (`safety/governance_patterns/`) into live enforcement,
>   governance-consumed signals, and lifecycle-preparatory monitoring.
>   Progresses from truthfulness cleanup through runtime boundary
>   enforcement, bounded governance signal activation, and pre-action
>   rollback-watch capture.
>
> **Sovereign and Core** follow a **bridge-first, never-direct** architecture
> and feed signals into the governance runtime decision path.
>
> **Ontology** follows an **adapter-first, fail-closed** architecture:
> canonical enum source → portable safety validators → lazy-import signal
> adapters → bounded governance consumer.
>
> **Policy** follows a **layered backend** architecture: typed profile
> foundations → runtime policy engines → service wrapper → simulation →
> lifecycle/deployment → read-only control-plane queries.
>
> **Safety** follows an **honest-activation** architecture: truthfulness
> cleanup → real boundary enforcement → bounded adapter activation →
> lifecycle-preparatory monitoring. Each phase activates only what the
> surrounding architecture genuinely supports; nothing is faked.
>
> All five tracks are **closed as internal layers**. None yet constitutes a
> full external API product, dashboard UI, or tenant-scoped admin platform.
>
> For the full governance architecture (Layers 1–8, domain policy, shadow AI,
> etc.), see [`docs/governance/AGENTIC_ARCHITECTURE.md`](../docs/governance/AGENTIC_ARCHITECTURE.md).
>
> This document focuses on how sovereign signals, core pipeline signals,
> ontological structure signals, policy infrastructure, and safety
> enforcement reach the agentic governance runtime — what is live, what is
> conditional, what is audit-only, what is simulation-only, what is
> backend/control-plane-only, what is lifecycle-preparatory, and what
> remains future work.

---

## Architecture Principle: Bridge-First, Never Direct

Governance does **not** directly import PyTorch-heavy sovereign model internals
or numpy-heavy core pipeline engines. All signals reach governance through a
layered bridge architecture with two parallel input tracks:

```
  SOVEREIGN TRACK (S1–S4)                  CORE PIPELINE TRACK (C1–C4)
  ========================                 ===========================

  ┌───────────────────────┐                ┌───────────────────────────┐
  │ SOVEREIGN INTERNALS   │                │ CORE PIPELINE INTERNALS   │
  │ (PyTorch-heavy)       │                │ (numpy-heavy)             │
  │ reasoning_kernel.py   │                │ coherence_state.py        │
  │ observer.py, guna.py  │                │ ucf.py                    │
  │ ── NEVER imported ──  │                │ persona_drift.py          │
  └─────────┬─────────────┘                │ identity_resonance.py     │
            │                              │ adaptive_continuity.py    │
            │ 128D → 32D projection        │ counterfactual_engine.py  │
            │ (inference_bridge.py)         │ ── NEVER imported ──     │
            ▼                              └─────────┬─────────────────┘
  ┌───────────────────────┐                          │
  │ INFERENCE BRIDGE      │                          │ duck-typed reports/states
  │ ProjectionMetadata:   │                          │ via getattr() + None defaults
  │  reasoning_diagnostics│                          │
  │  guna_anomalies       │                          │
  │  governor_telemetry   │                          │
  └─────────┬─────────────┘                          │
            │                                        │
            ▼                                        │
  ┌───────────────────────┐                          │
  │ PURE-PYTHON MODULES   │                          │
  │ sovereign_diagnostics │                          │
  │ sovereign_guna_anomaly│                          │
  │ sovereign_bhava_priors│                          │
  └─────────┬─────────────┘                          │
            │                                        │
            ▼                                        │
  ┌───────────────────────┐                          │
  │ SOVEREIGN BRIDGE      │                          │
  │ sovereign_bridge.py   │                          │
  │ → typed structs       │                          │
  └─────────┬─────────────┘                          │
            │                                        │
            ▼                                        ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  SIGNAL ADAPTERS (agentic_framework/signal_adapters/)           │
  │                                                                 │
  │  Sovereign adapters:                                            │
  │    vritti_adapter.py             (S1) — vritti signal resolution │
  │    entropy_adapter.py            (S1) — entropy resolution      │
  │    sovereign_health_adapter.py   (S2) — health/entropy signals  │
  │    insight_adapter.py            (S2) — insight gate resolution  │
  │    guna_anomaly_adapter.py       (S4) — anomaly penalty/bias    │
  │                                                                 │
  │  Core adapters:                                                 │
  │    coherence_state_adapter.py    (C2) — coherence/drift signals │
  │    ucf_adapter.py                (C3) — UCF consciousness       │
  │    predictive_signals_adapter.py (C4) — P35+P36+P37 signals     │
  │                                                                 │
  │  Ontology adapters:                                             │
  │    ontology_adapter.py           (O4) — 10D balance signal      │
  │    phase4a_adapter.py            (O3) — varna-layer lookup      │
  │                                                                 │
  │  Core bridges (not adapters — isolated from live path):         │
  │    counterfactual_bridge.py      (C4) — replay/simulation only  │
  │                                                                 │
  │  Core singletons:                                               │
  │    generation_gate.py            (C3) — one-time seal at boot   │
  │                                                                 │
  │  Safety adapters:                                                │
  │    plasticity_adapter.py         (S2-safety) — sigmoid gate     │
  │    readiness_adapter.py          (S3-safety) — multi-criterion  │
  │    policy_engine_adapter.py      (S4-safety) — per-agent policy │
  │    rollback_adapter.py           (S5-safety) — pre-action watch │
  │                                                                 │
  │  Every adapter produces:                                        │
  │    - frozen Resolution dataclass                                │
  │    - bounded confidence penalty (non-negative, capped)          │
  │    - optional escalation bias (stricter-only)                   │
  │    - reason codes for audit                                     │
  │    - safe defaults on failure (fail-closed)                     │
  └──────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  GOVERNANCE SERVICE (agentic_framework/governance_service.py)   │
  │                                                                 │
  │  Consumes all adapter outputs at decision time:                 │
  │    - confidence adjustments (bounded, aggregate cap = 0.20)     │
  │    - escalation overrides (stricter-only)                       │
  │    - generation gate check (C3, fail-closed)                    │
  │    - agent policy check (S4-safety, hard deny on violation)     │
  │    - rollback watch capture (S5-safety, audit-only)             │
  │    - audit metadata enrichment (all tracks)                     │
  │    - fail-safe: all resolution wraps try/except                 │
  └─────────────────────────────────────────────────────────────────┘
```

```
  POLICY TRACK (P0–P4)
  ====================

  ┌──────────────────────────────────────────────────────────────┐
  │  P0: PROFILE FOUNDATIONS                                     │
  │    DomainProfile (frozen typed schema, 40+ fields)           │
  │    ProfileRegistry (singleton, 4 builtins)                   │
  │    domain_profiles.py (get_domain_profile() entry point)     │
  │    layer_visibility_policy.py → governance_service.py        │
  │    provisional facades (governance_binding, preferences,     │
  │    licensing) — dormant by design                            │
  └──────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  P1/P2: RUNTIME ENGINES + SIMULATION                         │
  │    policy_engine.py → compute_policy_flags() [live runtime]  │
  │    session_policy.py → compute_session_policy_flags()        │
  │    trading_guardrail_engine.py → compute_trading_guardrails()│
  │    interaction_modes.py → resolve_interaction_mode()         │
  │    policy_simulation.py → simulate/compare [sim-only]        │
  │    PolicyService → structured wrapper + audit                │
  └──────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  P3: LIFECYCLE / DEPLOYMENT                                  │
  │    PolicyLifecycleManager (in-memory state machine)          │
  │    DRAFT → VALIDATED → ACTIVE → SUPERSEDED → ARCHIVED       │
  │    stage / validate / activate / rollback                    │
  │    approval-ready payload hooks (not full execution)         │
  │    simulation_summary linked to deployment records           │
  └──────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  P4: BACKEND CONTROL PLANE (read-only)                       │
  │    PolicyControlPlane — operator query surface                │
  │    system snapshot / domain status / health report            │
  │    deployment history / approval history / simulation history │
  │    tenant_id passthrough (preparation, not full scoping)     │
  └──────────────────────────────────────────────────────────────┘
```

**Key boundaries:**

1. **Sovereign boundary:** The `sovereign/` package (with its `__init__.py` that
   eagerly imports torch-heavy modules) is never imported by anything in the
   governance runtime path. Pure-Python runtime-safe modules
   (`sovereign_diagnostics.py`, `sovereign_guna_anomaly.py`,
   `sovereign_bhava_priors.py`) live as siblings outside the `sovereign/`
   package to avoid the torch import chain.

2. **Core pipeline boundary:** Core adapters use `importlib` to load their
   modules directly (bypassing `signal_adapters/__init__.py` which transitively
   imports numpy via `jepa_governance.py`). All core adapters consume duck-typed
   inputs via `getattr()` with `None` defaults — they never import pipeline
   engine classes.

3. **Counterfactual isolation:** The counterfactual bridge
   (`counterfactual_bridge.py`) is NOT imported by `governance_service.py`. It
   exists solely for downstream replay, approval-workflow what-if analysis, and
   audit simulation tools.

4. **Safety boundary:** The `safety/` package contains both enforcement
   modules (GCC guards, ledger invariants) and governance-pattern primitives
   (plasticity gate, readiness checker, policy engine, rollback monitor).
   Enforcement modules are called directly at constrained boundaries.
   Governance-pattern primitives are consumed through signal adapters in
   `signal_adapters/`, following the same frozen-resolution pattern as
   sovereign/core/ontology adapters. The `safety/` package never imports
   PyTorch or numpy.

5. **Policy boundary:** The `policy/` package is a self-contained backend layer.
   `governance_service.py` has two touchpoints: (a) `check_layer_visibility()`
   uses `layer_visibility_policy.py` for RBAC, (b) `get_policy_service()` lazily
   creates a `PolicyService` for audit retrieval. Policy engines
   (`compute_policy_flags`, etc.) are also called directly by pipeline consumers
   outside of `PolicyService`. Policy lifecycle (P3) and control-plane (P4)
   have no production callers yet — they are ready for future API/dashboard
   integration.

---

## S1–S4 Integration Phases

Sovereign integration was implemented as a staged ladder, with each phase
adding capabilities while preserving all prior invariants.

### Phase S1: Foundation Wiring

**Scope:** Shared constants, router integration, float-friendly telemetry,
sovereign telemetry in governance audit.

**What was implemented:**

| Component | Description | Status |
|-----------|-------------|--------|
| Shared sovereign constants | `SOVEREIGN_CONSTANTS` used by both sovereign and governance | Live, default-on |
| Router/nexus context | Sovereign router context available to governance | Live, default-on |
| Float-friendly telemetry | Stabilized float precision in guna derivation pipeline | Live, default-on |
| Sovereign telemetry in audit | `AuditEvent.sovereign_telemetry` field populated | Live, default-on |
| Vritti signal adapter | Prefers real `chitta_vritti` signals, falls back to approximation | Live, default-on |
| Entropy signal adapter | Entropy as real governance input with bounded penalty | Live, default-on |

**Governance effect:** S1 signals are always active. They provide the baseline
signal path (vritti, entropy) that all later phases build upon.

### Phase S2: Runtime-Safe Sovereign Metrics

**Scope:** Runtime-safe sovereign health/entropy/alert-state signals and
pure-function insight gate with bounded governance enrichment.

**What was implemented:**

| Component | Description | Status |
|-----------|-------------|--------|
| `sovereign_health_adapter.py` | Pure-Python health/entropy/alert resolution | Live, default-on |
| `insight_adapter.py` | Pure-Python insight gate resolution | Live, default-on |
| Sovereign health in audit | `AuditEvent.sovereign_health` field | Live, default-on |
| Sovereign insight in audit | `AuditEvent.sovereign_insight` field | Live, default-on |
| Bounded entropy penalty | Max 0.15 confidence penalty from entropy | Live, default-on |
| Bounded insight penalty | Max 0.10 confidence penalty from insight | Live, default-on |

**Governance effect:** S2 enrichments are always computed. They produce
bounded confidence penalties and escalation bias that make governance
stricter when sovereign health or insight signals indicate concern.

**Key design:** S2 adapters are pure functions with no torch dependency.
They consume plain dicts/dataclasses and return governance-typed resolutions.
Failure in any adapter returns neutral defaults (zero penalty, no escalation).

### Phase S3: Reasoning-Kernel Diagnostics

**Scope:** Reasoning-kernel diagnostic export through the inference bridge
into governance and audit.

**What was implemented:**

| Component | Description | Status |
|-----------|-------------|--------|
| `sovereign_diagnostics.py` | Pure-Python diagnostic normalization | Live when metadata present |
| `ProjectionMetadata.reasoning_diagnostics` | Bridge carries diagnostic dict | Live when metadata present |
| `SovereignDiagnosticContext` | Governance-typed diagnostic summary | Live when metadata present |
| `diagnostics_from_projection()` | Bridge → governance diagnostic conversion | Live when metadata present |
| `AuditEvent.sovereign_diagnostics` | Diagnostic data in audit trail | Live when metadata present |
| Mauna/silence governance effect | Mauna active → caution reason code | Behavior-affecting when present |
| OPB stability tracking | Lock/unlock dimension churn → audit | Audit-only |
| Vritti rejection tracking | Vritti filter rejections → audit | Audit-only |

**Governance effect:** S3 diagnostics are available **when
`sovereign_projection_metadata` is present on the `AuthorizationRequest`**.
When present, mauna/silence signals can add caution codes. Other diagnostic
fields are audit-only enrichment.

**Conditionality:** If no projection metadata is supplied (e.g., the caller
doesn't have access to sovereign kernel state), all S3 fields default to
safe neutral values. The system never fails or degrades because of absent
diagnostics.

### Phase S4: Anomaly, Prior, and Telemetry Integration

**Scope:** Runtime-safe guna anomaly detection, bhava transition priors,
governor telemetry passthrough, bounded anomaly penalties.

**What was implemented:**

| Component | Description | Status |
|-----------|-------------|--------|
| `sovereign_guna_anomaly.py` | Pure-Python temporal guna anomaly detection | Live when metadata present |
| `sovereign_bhava_priors.py` | Pure-Python 12x12 bhava transition matrix | Live when metadata present |
| `guna_anomaly_adapter.py` | Anomaly → bounded penalty + escalation bias | Behavior-affecting when present |
| `GunaAnomalyContext` | Governance-typed anomaly summary | Live when metadata present |
| `guna_anomalies_from_projection()` | Bridge → governance anomaly conversion | Live when metadata present |
| `bhava_transition_from_diagnostics()` | Prior → transition audit | Audit-only |
| `governor_telemetry_from_projection()` | PID governor data → audit | Audit-only |
| `AuditEvent.sovereign_guna_anomalies` | Anomaly data in audit trail | Live when metadata present |
| `AuditEvent.sovereign_bhava_transition` | Transition audit data | Audit-only |
| `AuditEvent.sovereign_governor_telemetry` | Governor telemetry data | Audit-only |

**Governance effects (behavior-affecting):**

| Signal | Confidence Penalty | Escalation Bias | Cap |
|--------|-------------------|-----------------|-----|
| Guna collapse | 0.03 | Yes (bump +1) | — |
| Guna oscillation | 0.02 | No | — |
| Guna stagnation | 0.00 | No | — |
| Combined (collapse + oscillation) | max 0.05 | Yes | Adapter-level cap |

**Conditionality:** Same as S3 — requires `sovereign_projection_metadata`
with a `guna_anomalies` sub-dict. When absent, all S4 fields default to
safe neutral values.

---

## C1–C4 Core Integration Phases

Core integration bridges the internal pipeline's coherence, consciousness,
generation control, and predictive signals into governance. Like the sovereign
track, each phase builds on prior phases while preserving all invariants.

### Phase C1: Foundation — Generation Gate + Adapter Pattern

**Scope:** Establish the signal adapter pattern, generation gate singleton,
and the governance service's core signal resolution infrastructure.

**What was implemented:**

| Component | Description | Status |
|-----------|-------------|--------|
| Signal adapter pattern | Frozen Resolution + pure function + fail-closed convention | Live, default-on |
| `generation_gate.py` | One-time seal singleton (ENABLED/DISABLED/UNSEALED) | Live, default-on |
| Generation gate check in `authorize()` | Fail-closed: UNSEALED or DISABLED → deny generative actions | Live, default-on |
| `_is_generative_action()` | Action-type classifier for gate applicability | Live, default-on |
| Generation gate audit field | `AuditEvent.generation_gate` populated on every call | Live, default-on |

**Governance effect:** The generation gate is always evaluated. If unsealed
(boot incomplete) or disabled, generative actions are denied. The gate is
a hard safety control, not a soft signal — it produces DENY decisions, not
confidence penalties.

**Key design:** The generation gate is a **singleton with one-time seal**.
Once `seal(ENABLED)` or `seal(DISABLED)` is called at boot, the state is
permanent for the process lifetime. `_reset()` exists only for test isolation.

### Phase C2: Coherence State Signals

**Scope:** Bridge core pipeline `CoherenceState` into governance as bounded
signals covering coherence level, persona drift, identity stability, and
continuity health.

**What was implemented:**

| Component | Description | Status |
|-----------|-------------|--------|
| `coherence_state_adapter.py` | Pure-function adapter for CoherenceState | Live, default-on |
| `CoherenceStateResolution` | Frozen governance-safe view of coherence | Live, default-on |
| Coherence penalty | Low coherence → up to 0.05 penalty | Behavior-affecting |
| Drift penalty | High persona drift → up to 0.05 penalty | Behavior-affecting |
| Drift escalation | HIGH drift risk band → escalation bias | Behavior-affecting |
| Identity/continuity signals | Identity stability, continuity health | Audit-only |
| `AuditEvent.core_coherence` | Full coherence snapshot in audit trail | Live, default-on |

**Governance effects (behavior-affecting):**

| Signal | Confidence Penalty | Escalation Bias | Cap |
|--------|-------------------|-----------------|-----|
| Low coherence (< 0.3) | 0.05 | No | — |
| Moderate coherence (0.3–0.5) | 0.02 | No | — |
| High persona drift (> 0.7) | 0.05 | Yes (bump +1) | — |
| Moderate persona drift (0.4–0.7) | 0.02 | No | — |
| Combined max | — | — | 0.10 adapter cap |

**Key design:** C2 penalizes on **current/stateful** drift posture from
`CoherenceState` (persona_drift, drift_risk_band). This is distinct from
C4's P35 which penalizes on **predictive/forecast** drift. Both may fire
simultaneously — this is intentional and bounded by the aggregate cap.

### Phase C3: UCF Consciousness + Generation Gate Enforcement

**Scope:** Bridge the Unified Consciousness Formula (UCF) score into
governance and wire generation gate enforcement into the authorize path.

**What was implemented:**

| Component | Description | Status |
|-----------|-------------|--------|
| `ucf_adapter.py` | Pure-function adapter for UCF state | Live, default-on |
| `UCFResolution` | Frozen governance-safe view of UCF | Live, default-on |
| UCF penalty | Unstable UCF → up to 0.05 penalty | Behavior-affecting |
| UCF escalation | Critical UCF band → escalation bias | Behavior-affecting |
| `AuditEvent.ucf_signal` | UCF snapshot in audit trail | Live, default-on |
| Generation gate wiring | `_check_generation_gate()` in authorize path | Live, default-on |
| `AuditEvent.generation_gate` | Gate state in audit trail | Live, default-on |

**Governance effects (behavior-affecting):**

| Signal | Confidence Penalty | Escalation Bias | Cap |
|--------|-------------------|-----------------|-----|
| UCF critical (< 0.2) | 0.05 | Yes (bump +1) | — |
| UCF unstable (0.2–0.4) | 0.03 | No | — |
| UCF marginal (0.4–0.6) | 0.01 | No | — |
| Adapter cap | — | — | 0.05 |

### Phase C4: Predictive Signals + Counterfactual Bridge

**Scope:** Bridge predictive persona drift (P35), identity resonance memory
(P36), and adaptive continuity (P37) into governance. Provide a counterfactual
sandbox bridge for replay/simulation (not live).

**What was implemented:**

| Component | Description | Status |
|-----------|-------------|--------|
| `predictive_signals_adapter.py` | Combined P35+P36+P37 adapter | Live, default-on |
| `PredictiveSignalsResolution` | Frozen governance-safe view | Live, default-on |
| P35 drift penalty | Predicted HIGH risk → 0.03 penalty | Behavior-affecting |
| P35 drift escalation | HIGH risk band → escalation bias | Behavior-affecting |
| P37 continuity penalty | Fragmenting mode → 0.02 penalty | Light behavior |
| P36 identity resonance | Resonance index, stability band | Audit-only |
| `AuditEvent.predictive_signals` | Predictive snapshot in audit trail | Live, default-on |
| `counterfactual_bridge.py` | P25 sandbox wrapper | Replay/simulation-only |
| `AuditEvent.counterfactual` | Reserved field (intentionally empty) | Replay/simulation-only |

**Governance effects (behavior-affecting):**

| Signal | Confidence Penalty | Escalation Bias | Cap |
|--------|-------------------|-----------------|-----|
| P35 HIGH drift risk | 0.03 | Yes (bump +1) | — |
| P35 moderate drift risk | 0.01 | No | — |
| P37 fragmenting continuity | 0.02 | No | — |
| P37 strained continuity | 0.005 | No | — |
| P36 (any state) | 0.00 | No | — |
| Combined P35+P37 max | — | — | 0.05 adapter cap |

**Combined adapter rationale:** P35/P36/P37 form a dependency chain (P37
depends on P35+P36 outputs). Grouping them in one adapter avoids redundant
resolution and keeps governance wiring simple.

**Counterfactual isolation:** The counterfactual bridge is NOT imported by
`governance_service.py`. The `AuditEvent.counterfactual` field is
**intentionally never populated** by `authorize()`. It exists for downstream
replay, approval-workflow what-if analysis, and audit simulation tools that
attach counterfactual results to audit events after the fact.

**Signal classification within C4:**

| Signal | Classification | Rationale |
|--------|---------------|-----------|
| P35 predictive drift | BEHAVIOR-AFFECTING | Forecast drift risk justifies bounded penalty |
| P37 adaptive continuity | LIGHT BEHAVIOR | Fragmenting mode indicates instability |
| P36 identity resonance | AUDIT-ONLY | Resonance is observational, not actionable |
| P25 counterfactual | REPLAY/SIMULATION-ONLY | What-if analysis, never live |

---

## C Closure Patch: Audit Findings Resolution

A strict post-integration audit of C1-C4 identified five gaps. All were
resolved in a focused closure patch.

### Finding 1: No E2E authorize() Tests for C2/C3/C4

**Problem:** Core signal adapters had unit tests, but no tests called
`GovernanceService.authorize()` end-to-end to prove signals flow through
the full decision path.

**Fix:** 31 E2E tests in `test_closure_e2e_authorize.py` across 7 test
classes proving C2/C3/C4 signal wiring, combined stacking, aggregate cap,
and generation gate behavior.

### Finding 2: Dormant Counterfactual Field

**Problem:** `AuditEvent.counterfactual` existed but was always `None`,
without documentation explaining whether this was a bug or design intent.

**Fix:** Explicit documentation on the field confirming it is intentionally
never populated by `authorize()` — it exists for replay/simulation tools.

### Finding 3: Aggregate Penalty Cap Not Tested With C2/C3/C4

**Problem:** The aggregate cap test only covered sovereign adapters. With
C2/C3/C4 adding penalties, the cap needed verification with all sources.

**Fix:** Two dedicated tests verify the cap holds when all six penalty
sources fire simultaneously (entropy + insight + guna + C2 + C3 + C4).

### Finding 4: Generation Gate Tests Used Source-String Inspection

**Problem:** Initial generation gate tests checked source code strings
rather than testing actual behavior.

**Fix:** 14 behavioral tests for `_is_generative_action()`,
`_check_generation_gate()`, and full `authorize()` gate enforcement.

### Finding 5: C2/C4 Drift Overlap Not Documented

**Problem:** Both C2 and C4 penalize drift, risking confusion about
double-counting.

**Fix:** Inline DRIFT OVERLAP NOTE in `governance_service.py` and
documentation in `predictive_signals_adapter.py` explaining that C2
penalizes current/stateful drift while C4 penalizes predictive/forecast
drift — complementary signals, not duplicates, bounded by aggregate cap.

---

## Activation Patch: Making S3/S4 Live

### The Problem

After S3 and S4 were implemented, a strict code-inspection audit revealed
that all S3/S4 signals were **dormant** — structurally integrated but never
reaching governance at runtime.

**Root cause:** `JEPACompositeSignal` (a frozen dataclass in
`jepa_governance.py`) had no `projection_metadata` field. All downstream
resolvers used `getattr(composite, "projection_metadata", None)`, which
always returned `None`. S3/S4 signals were correctly wired through the
bridge and adapters, but the JEPA composite — the handoff point into
governance — silently dropped them.

### The Fix (3 Parts)

**Part 1: Wire `projection_metadata` through the JEPA path**

```
  AuthorizationRequest
    .sovereign_projection_metadata: Optional[Dict]   ← new field
         │
         ▼
  GovernanceService._run_jepa_check()
    passes projection_metadata to safe_jepa_governance_check()
         │
         ▼
  jepa_governance_check()
    passes projection_metadata to build_jepa_composite()
         │
         ▼
  JEPACompositeSignal
    .projection_metadata: Optional[Any] = None       ← new field
         │
         ▼
  _resolve_diagnostic_context(assessment)
    reads composite.projection_metadata               ← now non-None
    → SovereignDiagnosticContext (available=True)
         │
  _resolve_guna_anomaly_signal(assessment)
    reads composite.projection_metadata               ← now non-None
    → GunaAnomalyResolution (available=True)
         │
  _resolve_s4_audit_metadata(assessment, ...)
    reads composite.projection_metadata               ← now non-None
    → bhava_transition_dict, governor_telemetry_dict
```

**Part 2: Aggregate sovereign penalty cap**

Before the activation patch, sovereign-derived confidence penalties could
stack without bound:

```
  entropy penalty     max 0.15
  insight penalty     max 0.10
  guna anomaly        max 0.05
  ─────────────────────────────
  theoretical max     0.30   ← uncapped
```

The activation patch adds an explicit aggregate cap:

```python
sovereign_penalty = min(
    0.20,                                    # aggregate cap
    entropy_penalty + insight_penalty + guna_penalty,
)
effective_confidence = max(
    0.0,
    raw_confidence + jepa_adjustment - sovereign_penalty,
)
```

This ensures sovereign signals cannot reduce confidence by more than 0.20
in aggregate, even if all three penalty sources fire simultaneously.

**Part 3: End-to-end activation proof**

Eight E2E tests in `test_activation_e2e.py` prove the activation is live:

| Test | What It Proves |
|------|----------------|
| `test_s3_diagnostics_populated_via_authorize` | `reasoning_diagnostics` → `sovereign_diagnostics` in audit |
| `test_s3_diagnostics_absent_without_metadata` | No metadata → `sovereign_diagnostics` is None (safe default) |
| `test_s4_guna_anomalies_populated_via_authorize` | `guna_anomalies` → `sovereign_guna_anomalies` in audit |
| `test_s4_guna_anomalies_absent_without_metadata` | No anomalies → field is None |
| `test_s4_governor_telemetry_populated_via_authorize` | `governor_telemetry` → `sovereign_governor_telemetry` in audit |
| `test_combined_s3_s4_all_populated` | Full metadata → all S3+S4 audit fields populated |
| `test_guna_collapse_applies_confidence_penalty` | Guna collapse measurably reduces confidence |
| `test_aggregate_sovereign_penalty_capped_at_020` | Penalty sum > 0.20 → effective cap at 0.20 |

These tests call `GovernanceService.authorize()` end-to-end, not unit-level
mocks. They prove that:
1. Metadata flows from request → composite → resolvers → audit
2. Behavioral effects (confidence penalty) are measurable
3. The aggregate cap is enforced
4. Absence of metadata produces safe neutral defaults

### What Changed (Files)

| File | Change |
|------|--------|
| `jepa_governance.py` | Added `projection_metadata` field to `JEPACompositeSignal`, threaded through `build_jepa_composite()` and `jepa_governance_check()` |
| `governance_models.py` | Added `sovereign_projection_metadata` field to `AuthorizationRequest` |
| `governance_service.py` | `_run_jepa_check()` passes metadata; aggregate penalty cap in confidence calculation |
| `tests/test_jepa_governance.py` | Updated `test_confidence_adjustment_isolated` to account for guna + cap |
| `tests/test_activation_e2e.py` | 8 new E2E tests proving S3/S4 activation |

---

## O1–O4 Ontology Integration Phases

The ontology track canonicalizes the 12-layer ontological structure, extracts
portable safety validators, builds fail-closed signal adapters for the 10D
backbone, and wires the first real ontology consumer into governance.

Unlike the sovereign and core tracks which bridge heavy upstream engines
(PyTorch, numpy), the ontology track bridges **rule-based, pure-Python**
backbone encoders (`encoder.py`, `similarity.py`, `mirror_pairs.py`) that
have no heavy dependencies. The adapters still use lazy imports and
fail-closed semantics to maintain the same isolation guarantees.

### What Ontology IS vs IS NOT

| Ontology IS | Ontology IS NOT |
|-------------|-----------------|
| 12-member enum (`OntologicalLayer`) with patent-exact values 1–12 | An ML model or learned embedding space |
| Rule-based text → 10D vector encoding (regex patterns per dimension) | A neural encoder or transformer |
| Deterministic mirror-pair balance (5 pairs, `balance_score` 0.0–1.0) | A probabilistic or stochastic signal |
| Frozen varna-layer lookup against JSON substrate | A dynamic knowledge graph |
| One governance consumer (balance → penalty + escalation) | A comprehensive ontology reasoning engine |
| Adapter-first, fail-closed signal pipeline | A direct import into governance |

### Phase O1: OntologicalLayer Canonicalization

**Scope:** Eliminate duplicate `OntologicalLayer` enum definitions. Establish
a single canonical source with all import paths resolving to the same class.

| Component | Description | Status |
|-----------|-------------|--------|
| `ontology/layers/ontology_layer.py` | Canonical source: 12-member enum, `ALL_LAYERS`, `GATED_LAYERS` | Live, canonical |
| `ontology/projection/api_models.py` | Removed local enum, imports from canonical source | Live, re-export |
| `ontology/router/ontological_router_r1.py` | Removed local enum, imports from canonical source | Live, re-export |
| `symbolu/ontology/` mirrors | Identical canonicalization applied to parallel mirror package | Live, mirror |

**O1 invariant:** `OntologicalLayer` is defined in exactly one place
(`layers/ontology_layer.py`). All other modules import from it. AST
verification tests confirm no independent definitions exist.

### Phase O2: Safety Validators + Signal Adapters

**Scope:** Extract portable runtime safety validators from `projection/validators.py`.
Build signal adapters for 10D backbone encoding and similarity.

| Component | Description | Status |
|-----------|-------------|--------|
| `ontology/safety.py` | `check_no_forbidden_modules()`, `check_no_timestamp_words()` | Live, portable |
| `signal_adapters/ontology_adapter.py` | `resolve_ontology_encoding()` — lazy 10D encode | Adapter, available |
| `signal_adapters/ontology_adapter.py` | `resolve_ontology_similarity()` — lazy similarity | Adapter, available |

**Key design:** Adapters use lazy imports inside `try/except`, returning
frozen `Resolution` dataclasses with `available=False` on failure. The
backbone modules (`encoder.py`, `similarity.py`) are never directly imported
by governance code.

### Phase O3: Phase4a Lookup + Mirror-Pair Balance Adapter

**Scope:** Build fail-closed adapters for varna-layer lookups (phase4a) and
10D mirror-pair balance signals.

| Component | Description | Status |
|-----------|-------------|--------|
| `signal_adapters/phase4a_adapter.py` | `resolve_varna_lookup()`, `resolve_varna_exists()` | Adapter, available |
| `signal_adapters/ontology_adapter.py` | `resolve_ontology_balance()` — lazy mirror-pair balance | Adapter, available |

**Mirror-pair balance:** The 10D backbone has 5 mirror pairs
(ACTION↔ABSOLUTE, IDENTITY↔TRANSCENDENCE, etc.). `compute_balance()`
produces a `BalanceReport` with `balance_score` (0.0–1.0),
`dominant_state`, and `propagation_needed` count. The adapter wraps this
in a frozen `OntologyBalanceResolution` dataclass.

### Phase O4: First Governance Consumer (Balance Signal)

**Scope:** Wire `resolve_ontology_balance()` into `GovernanceService.authorize()`
as the first real ontology consumer, following the exact same adapter→penalty→escalation
pattern used by all existing signal adapters.

| Component | Description | Status |
|-----------|-------------|--------|
| `OntologyBalanceGovernanceSignal` | Frozen dataclass in `governance_service.py` | Live |
| `_resolve_ontology_balance_signal()` | Resolver: content → balance → penalty + escalation | Live |
| `governance_models.py` | `AuditEvent.ontology_balance` field | Live |
| `governance_service.py` | Wired into `_evaluate()` penalty aggregate + escalation + audit | Live |

**Governance effects:**

| Effect | Trigger | Bound |
|--------|---------|-------|
| Confidence penalty (linear) | `balance_score < 0.35` | max 0.05 |
| Escalation bias (+1 level) | `balance_score < 0.20` | Single step, cap at confirm |

**Content input:** `action_type + " " + tool_name` from the `AuthorizationRequest`.
This is always available (no upstream dependency), deterministic, and produces
a stable 10D encoding for the proposed action.

**Fail-closed:** Any error in ontology resolution → `available=False`,
zero penalty, no escalation bias. The governance decision proceeds as if
the ontology track does not exist.

---

## P0–P4 Policy Productization Phases

The policy track builds the profile-backed policy computation, simulation,
lifecycle, and backend control-plane layer. Unlike the sovereign/core tracks
which feed signals into the governance decision path, the policy track provides
**domain-specific policy computation, operational tooling, and backend
queryability** as a self-contained internal layer.

### Phase P0: Domain Profile Externalization Foundation

**Scope:** Replace hardcoded dict-based domain profiles with a typed, versioned,
registry-backed profile system. Wire layer visibility into governance. Clarify
dormant facades.

| Component | Description | Status |
|-----------|-------------|--------|
| `DomainProfile` | Frozen dataclass (40+ fields), dict-compatible backward access | Live, default-on |
| `ProfileRegistry` | Singleton with 4 builtins (trading, therapy, identity, generic) | Live, default-on |
| `domain_profiles.py` | `get_domain_profile()` public API over registry | Live, default-on |
| `layer_visibility_policy.py` | Deterministic RBAC via `ExposureGate` | Live via `governance_service.py` |
| `governance_binding.py` | Provisional facade, zero runtime consumers | Dormant (provisional) |
| `preferences.py` | Provisional facade, bypassed by `policy_engine.py` | Dormant (provisional) |
| `licensing/__init__.py` | Provisional facade, no license gates exist | Dormant (provisional) |

**Key design:** `DomainProfile` supports both `profile.min_coherence` and
`profile["min_coherence"]` access, preserving backward compatibility. All
existing consumers continue to work without changes.

### Phase P1: Policy Service / Runtime Exposure

**Scope:** Wrap all policy engines in a structured, auditable service boundary.
Expose interaction mode, session policy, and trading guardrails as
governance-ready backend outputs.

| Component | Description | Status |
|-----------|-------------|--------|
| `PolicyService` | Service wrapper with structured result envelopes | Service/backend |
| `compute_policy()` | Wraps `compute_policy_flags()` with metadata + audit | Service/backend |
| `resolve_interaction_mode()` | Interaction mode with override precedence | Service/backend |
| `compute_session_policy()` | Session-level policy computation | Service/backend |
| `compute_trading_guardrails()` | Trading risk guardrails | Service/backend |
| In-memory audit log | Max 1000 entries, decision_id hashing, non-persistent | Service/backend |
| `GovernanceService` integration | Lazy `get_policy_service()` + `get_policy_audit_log()` | Live (read-only) |

**Caller reality:** `PolicyService.compute_policy()` wraps
`compute_policy_flags()` with audit/metadata. Some pipeline consumers call
`compute_policy_flags()` directly, bypassing the service wrapper. Both paths
use the same `ProfileRegistry` and produce identical flags. The audit log is
only populated when callers use the service wrapper.

### Phase P2: Simulation-Friendly Parameterization

**Scope:** Parameterize hardcoded policy thresholds, build simulation/comparison
paths, make insight-window split operationally explicit.

| Component | Description | Status |
|-----------|-------------|--------|
| 19 parameterized thresholds | Moved from hardcoded to `DomainProfile` fields | Live runtime |
| `policy_simulation.py` | `simulate_policy()`, `compare_policy()`, session/trading variants | Simulation-only |
| Threshold extraction | `_extract_thresholds_from_profile()` for session/trading overrides | Simulation-only |
| Insight-window status metadata | `INSIGHT_WINDOW_STATUS` on both dual paths | Documentation-only |

**Parameterized thresholds (19 fields):**

| Category | Count | Examples |
|----------|-------|---------|
| Policy engine rules | 9 | `deep_reflection_max_drift`, `stability_coherence_stable` |
| Session policy | 7 | `session_coherence_stable`, `session_grounding_drift` |
| Trading guardrails | 3 | `trading_resonance_floor`, `trading_coherence_floor` |

**Still hardcoded (by design):** VMF/ATH presentation hints (non-critical),
insight-window canonical v1.0 formula thresholds (locked).

### Phase P3: Policy Lifecycle / Deployment Model

**Scope:** Introduce explicit lifecycle state machine, activation/rollback,
approval hooks, deployment records with simulation linkage.

| Component | Description | Status |
|-----------|-------------|--------|
| `ProfileStatus` enum | DRAFT → VALIDATED → ACTIVE → SUPERSEDED → ARCHIVED | Lifecycle |
| `DeploymentRecord` | Frozen dataclass with actor/rationale/approval/simulation metadata | Lifecycle |
| `PolicyLifecycleManager` | `stage` / `validate` / `activate` / `rollback` | Lifecycle |
| Builtin rollback | Synthetic SUPERSEDED records for builtins on first replacement | Lifecycle |
| `request_activation_approval()` | Approval-ready payload (not full execution) | Lifecycle |
| `simulation_summary` linkage | Flows from validate → activate, queryable | Lifecycle |

**State is in-memory only.** All lifecycle history (deployment records,
candidates) is lost on process restart. Durable persistence is future work.

**Approval integration is payload/hook-ready.** `request_activation_approval()`
produces structured payloads but does not create or track approvals. Integration
with an external approval workflow is left to the caller.

### Phase P4: Backend Control Plane (Read-Only)

**Scope:** Expose operator-ready query surfaces for policy state, health,
deployment/approval/simulation history.

| Component | Description | Status |
|-----------|-------------|--------|
| `PolicyControlPlane` | Read-only query surface over registry + lifecycle + audit | Control-plane |
| `get_system_snapshot()` | All-domains view with builtin/custom/fallback counts | Control-plane |
| `get_domain_status()` | Per-domain active profile, candidate, deployment info | Control-plane |
| `get_health_report()` | Stale candidate detection, fallback domain warnings | Control-plane |
| `get_active_profiles_summary()` | Lightweight all-domains active profile view | Control-plane |
| `get_deployment_history()` | Filtered deployment records | Control-plane |
| `get_approval_history()` | Lifecycle audit entries (filtered by event type) | Control-plane |
| `get_simulation_history()` | Records with attached simulation summaries | Control-plane |
| `tenant_id` passthrough | All surfaces accept tenant_id (preparation only) | Future |

**All P4 queries are read-only and audit-neutral** — they do not create audit
entries or modify state.

**Tenant_id is passthrough only.** The parameter exists on all query interfaces
as preparation for future tenant-scoping, but no filtering or scoping logic is
implemented.

---

## P Closure Patch: Audit Findings Resolution

A strict post-integration audit of P0-P4 identified three gaps. All were
resolved in a focused closure patch.

### Finding 1: No End-to-End Lifecycle → Policy Output Proof

**Problem:** Tests verified that activation changed the `ProfileRegistry` profile
object, but no test proved that `compute_policy_flags()` actually produced
different output after activation, or that rollback reverted the output.

**Fix:** Three end-to-end tests in `TestLifecyclePolicyOutputProof`:
1. Activate a lenient profile → verify `needs_grounding` changes from True to
   False → rollback → verify it reverts to True
2. Activate a strict profile → verify `stability_status` changes → rollback →
   verify it reverts
3. Same proof through `PolicyService.compute_policy()` (service path)

### Finding 2: Fragile Builtin Profile Detection

**Problem:** `PolicyControlPlane._is_builtin_profile()` used a hardcoded set
`{"trading", "therapy", "identity", "generic"}` that could drift if builtins
were added or renamed.

**Fix:** Replaced with `_get_builtin_profiles()` which derives builtins from a
fresh `ProfileRegistry()` snapshot (the authoritative source).

### Finding 3: Weak Simulation/Comparison Assertions

**Problem:** Several P2 tests only verified that `changed_flags` existed as a
key, not that it contained the expected flags or that flag values differed in
the expected direction.

**Fix:** Strengthened comparison tests to verify actual flag values
(`baseline.needs_grounding=True`, `candidate.needs_grounding=False`), verify
specific changed flag names, and verify exact deployment counts.

---

## Safety Integration Track (S0–S5)

The safety track promotes dormant governance-pattern primitives from
`safety/governance_patterns/` into live enforcement, bounded governance
signals, and lifecycle-preparatory monitoring. Unlike the sovereign/core
tracks (which bridge heavy upstream engines), the safety track activates
**pure-Python safety modules** that were structurally present but never
consumed at runtime.

### What Safety IS vs IS NOT

| Safety IS | Safety IS NOT |
|-----------|---------------|
| Real boundary enforcement for GCC and ledger invariants (S1) | A broad fully automated rollback execution system |
| Real governance consumption of plasticity/readiness/policy signals (S2–S4) | A complete post-action lifecycle engine |
| Real rollback-watch capture in the most truthful form the architecture supports (S5) | A fully activated `safety_bounds.py` enforcement layer |
| Honest deprecation/marking of dead facades (S0) | A full safety control-plane product |
| Bounded, fail-safe signal integration following the adapter pattern | A replacement for policy/core/governance layers |
| Progression from dormant code to live governance usage | A full external admin/operator safety product |

### Safety Capability Truth Table

| Module | Classification | Status | Consumed By |
|--------|---------------|--------|-------------|
| `safety/gcc_runtime_guard.py` | **Runtime boundary enforcement** | ACTIVE (S1) | Ontological router, phase layer map, constrained module boundaries |
| `safety/gcc_ledger_invariant.py` | **Runtime boundary enforcement** | ACTIVE (S1) | `LedgerStore.append()`, `LedgerEntryStore.append()` |
| `safety/gcc_static_scanner.py` | **CI/build-time enforcement** | ACTIVE (pre-S0) | CI pipeline, not runtime framework logic |
| `safety/governance_patterns/plasticity_gate.py` | **Live governance signal** | ACTIVE (S2) | `GovernanceService.authorize()` via `plasticity_adapter.py` |
| `safety/governance_patterns/readiness_checker.py` | **Live governance signal** | ACTIVE (S3) | `GovernanceService.authorize()` via `readiness_adapter.py` |
| `safety/governance_patterns/policy_engine.py` | **Pre-authorize policy guard** | ACTIVE (S4) | `GovernanceService.authorize()` via `policy_engine_adapter.py` |
| `safety/governance_patterns/rollback_monitor.py` | **Lifecycle-preparatory / audit-visible** | ACTIVE (S5) | `GovernanceService.authorize()` via `rollback_adapter.py` |
| `safety/governance_patterns/safety_bounds.py` | **Future / dormant** | DORMANT | No consumer — awaits action-magnitude payload model |
| `safety/governance_patterns/approval_manager.py` | **Deprecated** | DEPRECATED (S0) | Superseded by `agentic_framework/approval_workflow.py` |
| `safety/escalation_signals.py` | **Facade / unused** | UNUSED (S0) | No runtime consumers; explicitly marked |
| `safety/output_gate.py` | **Facade / unused** | UNUSED (S0) | No runtime consumers; explicitly marked |
| `safety/rate_limiter.py` | **Facade / unused** | UNUSED (S0) | No runtime consumers; explicitly marked |
| `safety/acoustic_safety/__init__.py` | **Facade / unused** | UNUSED (S0) | No runtime consumers; explicitly marked |
| `safety/pipeline_guards/__init__.py` | **Facade / unused** | UNUSED (S0) | No runtime consumers; explicitly marked |

### Safety Folder Role

`agentic/safety/` is now a mix of:
- **Real source-of-truth enforcement modules** — GCC runtime guard and
  ledger invariant (S1), enforced at actual constrained boundaries
- **Activated governance-pattern primitives** — plasticity gate (S2),
  readiness checker (S3), policy engine (S4), rollback monitor (S5),
  consumed by `GovernanceService.authorize()` through signal adapters
- **Explicitly deprecated/unused surfaces** — approval manager (S0),
  dead facades (S0), all honestly marked with STATUS headers
- **One still-dormant primitive** — `safety_bounds.py`, awaiting the
  framework-level action-magnitude payload model that would make it real

`agentic/agentic_framework/` consumes selected safety capabilities through:
- **Direct enforcement hooks** — GCC guards called at module boundaries
- **Signal adapters** — `signal_adapters/plasticity_adapter.py`,
  `readiness_adapter.py`, `policy_engine_adapter.py`, `rollback_adapter.py`
- **Governance decision logic** — penalties, escalation biases, hard denies
- **Audit metadata** — structured audit fields on `AuditEvent`

### Safety Progression: S0 → S5

The safety track moved from dormant code and facades into live
governance/runtime usage through six phases:

```
  S0: Truthfulness       S1: GCC enforcement    S2: Plasticity gate
  ──────────────────     ──────────────────     ──────────────────
  Mark dead facades      gcc_runtime_guard      plasticity_gate.py
  Deprecate approval_    enforced at real        → live governance
  manager. Honest        boundaries.             signal (penalty
  status markers.        gcc_ledger_invariant    + escalation).
                         enforced at ledger      Fail-closed.
                         writes. Opaque ID
                         support added.

  S3: Readiness gate     S4: Policy engine      S5: Rollback watch
  ──────────────────     ──────────────────     ──────────────────
  readiness_checker.py   policy_engine.py       rollback_monitor.py
  → live governance      → early pre-authorize  → lifecycle-
  signal (penalty        guard. Hard deny       preparatory. Pre-
  + escalation).         on violation.          action snapshot.
  Multi-criterion.       Fail-safe (no          Audit-visible.
  Cooldown honestly      engine = allow).       No automatic
  disabled.                                     rollback execution.
```

### Phase S0: Truthfulness Cleanup

**Scope:** Mark dead safety facades as honestly unused. Deprecate the
superseded approval manager.

| Component | Change | Status |
|-----------|--------|--------|
| `safety/escalation_signals.py` | Added `STATUS: UNUSED` marker | Unused |
| `safety/output_gate.py` | Added `STATUS: UNUSED` marker | Unused |
| `safety/rate_limiter.py` | Added `STATUS: UNUSED` marker | Unused |
| `safety/acoustic_safety/__init__.py` | Added `STATUS: UNUSED` marker | Unused |
| `safety/pipeline_guards/__init__.py` | Added `STATUS: UNUSED` marker | Unused |
| `safety/governance_patterns/approval_manager.py` | Added `DEPRECATED` marker | Deprecated |

**Important truth:** These surfaces were structurally present but had zero
runtime consumers. They were not real safety protections — they were facades.
S0 makes this explicit rather than leaving readers to discover it.

### Phase S1: Real GCC Enforcement

**Scope:** Wire GCC (Generative Containment Constraint) guards at actual
constrained module boundaries. Wire ledger invariant checks at actual
ledger write boundaries. Add opaque identifier support so structural IDs
(artifact IDs, span IDs) pass validation while free-form expressive content
remains blocked.

| Component | Description | Status |
|-----------|-------------|--------|
| `gcc_runtime_guard.py` | `assert_non_expressive()` now fires at real return boundaries | Runtime enforcement |
| `gcc_ledger_invariant.py` | `assert_ledger_entry_valid()` now fires at real ledger writes | Runtime enforcement |
| Opaque ID support | `_is_opaque_id()` — alphanumeric+hyphens+underscores+dots, ≤64 chars | Added to both guards |
| `OntologicalLayerRouter.project()` | GCC guard on return value | Enforced |
| `get_layers_for_phase()` | GCC guard on return value | Enforced |
| `LedgerStore.append()` / `LedgerEntryStore.append()` | Ledger invariant guard before writes | Enforced |

**Important truth:** Before S1, GCC was tested logic and CI-time scanning
only. After S1, GCC materially guards real constrained outputs and ledger
writes at runtime. This is a meaningful escalation from "tested" to
"enforced."

### Phase S2: PlasticityGate Activation

**Scope:** Promote `plasticity_gate.py` from dormant to active governance
signal. Create `plasticity_adapter.py`. Wire into `GovernanceService.authorize()`.

| Component | Description | Status |
|-----------|-------------|--------|
| `plasticity_adapter.py` | `resolve_plasticity_signal()` — sigmoid gate evaluation | Live governance signal |
| `PlasticityResolution` | Frozen dataclass: plasticity, resistance, misalignment, penalty, escalation | Live governance signal |
| Confidence penalty | Low plasticity → max 0.04 penalty | Behavior-affecting |
| Escalation bias | Critical plasticity (< 0.35) → +1 escalation | Behavior-affecting |
| `AuditEvent.plasticity_gate` | Structured audit field | Live |

**Governance effects:**

| Signal | Trigger | Penalty | Escalation | Cap |
|--------|---------|---------|------------|-----|
| Low plasticity | < 0.50 | Linear up to 0.04 | No | 0.04 |
| Critical plasticity | < 0.35 | 0.04 | Yes (+1 level) | 0.04 |

**Inputs:** Resistance derived from `semantic_stability` or `coherence_score`
(from C2). Misalignment derived from `persona_drift` (from C2). Fresh
`PlasticityGate` per call (stateless). Fail-closed: if coherence unavailable,
zero penalty and no bias.

### Phase S3: ReadinessChecker Activation

**Scope:** Promote `readiness_checker.py` from dormant to active governance
signal. Create `readiness_adapter.py`. Wire into `GovernanceService.authorize()`.

| Component | Description | Status |
|-----------|-------------|--------|
| `readiness_adapter.py` | `resolve_readiness_signal()` — multi-criterion gate | Live governance signal |
| `ReadinessResolution` | Frozen dataclass: status, ready, plasticity, stability, penalty, escalation | Live governance signal |
| Confidence penalty | NOT_READY → 0.03; DEGRADED → 0.02 | Behavior-affecting |
| Escalation bias | NOT_READY → +1 escalation | Behavior-affecting |
| `AuditEvent.readiness_check` | Structured audit field | Live |

**Readiness criteria evaluated:**

| Criterion | Source | Status |
|-----------|--------|--------|
| Plasticity ≥ min threshold (0.30) | S2 plasticity resolution | **Active** |
| Stability / coherence level | C2 core coherence | **Active** |
| No blocking escalations | Current escalation level | **Active** |
| Cooldown since last action | Cross-request state | **Honestly disabled** (`min_time_since_action_seconds=0.0`) |

**Important truth:** Cooldown is conceptually supported by `ReadinessChecker`
but is honestly disabled because `GovernanceService` has no cross-request
state. This is documented in the adapter, not hidden.

### Phase S4: PolicyEngine Activation

**Scope:** Promote `policy_engine.py` from dormant to active pre-authorize
guard. Create `policy_engine_adapter.py`. Wire into
`GovernanceService.authorize()` as an early step.

| Component | Description | Status |
|-----------|-------------|--------|
| `policy_engine_adapter.py` | `resolve_policy_check()` — per-agent policy evaluation | Live pre-authorize guard |
| `AgentPolicyResolution` | Frozen dataclass: allowed, hard_deny, violations, reason_codes | Live pre-authorize guard |
| Hard deny | Policy violation → governance DENY, overrides all signals | Behavior-affecting |
| `AuditEvent.agent_policy` | Structured audit field | Live |

**Policy capabilities:**

| Capability | Description | Effect |
|-----------|-------------|--------|
| Action denylist | Explicitly denied action types per agent | Hard deny |
| Action allowlist | Only listed actions permitted | Hard deny for unlisted |
| Blackout windows | Time-range blocking (hour/weekday) | Hard deny during window |
| Rate limiting | Max actions per sliding window | Hard deny on exceeded |
| Per-agent overrides | Agent-specific policy overriding defaults | Scoped rules |

**Important truth:** This is an opt-in pre-authorize policy guard, not a
global default-deny system. Fail-safe: absence of configured policy engine
means all actions are allowed by default. This is deliberate — unlike other
adapters which fail-closed (absent = neutral), the policy engine fails-safe
(absent = permitted).

### Phase S5: RollbackMonitor Activation (Lifecycle-Preparatory)

**Scope:** Promote `rollback_monitor.py` from dormant to active in the
most honest form the current architecture supports. Since
`GovernanceService` is authorize-only with no post-action execution
lifecycle, S5 provides lifecycle-preparatory monitoring, not full automatic
rollback.

| Component | Description | Status |
|-----------|-------------|--------|
| `rollback_adapter.py` | `resolve_rollback_snapshot()` — pre-action signal capture | Lifecycle-preparatory |
| `RollbackSnapshotResolution` | Frozen dataclass: watch_started, pre_action_signals, watch_id | Lifecycle-preparatory |
| Pre-action snapshot | Captures confidence, plasticity, coherence at decision time | Audit-visible |
| `AuditEvent.rollback_watch` | Structured audit field with snapshot data | Audit-visible |
| Monitor registration | `RollbackWatch` started, available for external `check()` | External caller required |

**What S5 provides:**
- Pre-action signal snapshot captured at authorize-time
- Watch registered with `RollbackMonitor` (if configured)
- Audit-visible rollback watch metadata in governance audit event
- External callers can later call `monitor.check(current_signals)` to
  detect degradation

**What S5 does NOT provide:**
- No automatic rollback execution (requires execution lifecycle)
- No post-action signal re-evaluation on the authorize path
- No background monitoring thread
- No confidence penalty or escalation bias (purely observational)

**Important truth:** `GovernanceService` is authorize-only. There is no
execution callback, no post-action signal feedback loop, and no mechanism
for automatic rollback. S5 captures the pre-action state honestly and
leaves the post-action check to future infrastructure. Rollback monitoring
is active in a preparatory and auditable sense, not as automatic rollback
automation.

---

## Live vs Conditional: The Truth Table

Not all signals are always active. The system has four activation tiers,
and the documentation must not conflate them.

### Tier 1: Live and Default-On (Always Active)

These signals are computed on every `GovernanceService.authorize()` call,
regardless of whether upstream data is present. Adapters fall back to
approximation or neutral defaults when upstream data is unavailable.

| Signal | Track | Phase | Effect |
|--------|-------|-------|--------|
| Vritti resolution (real or fallback) | Sovereign | S1 | Governs JEPA composite vritti axis |
| Entropy resolution | Sovereign | S1 | Bounded confidence penalty (max 0.15) |
| Sovereign telemetry in audit | Sovereign | S1 | Audit enrichment |
| Sovereign health resolution | Sovereign | S2 | Audit enrichment |
| Insight gate resolution | Sovereign | S2 | Bounded confidence penalty (max 0.10) |
| Generation gate check | Core | C1/C3 | Hard deny for generative actions when gate closed |
| Coherence state resolution | Core | C2 | Bounded confidence penalty (max 0.10) |
| UCF consciousness resolution | Core | C3 | Bounded confidence penalty (max 0.05) |
| Predictive signals resolution | Core | C4 | Bounded confidence penalty (max 0.05) |
| Ontology balance resolution | Ontology | O4 | Bounded confidence penalty (max 0.05) |
| Plasticity gate resolution | Safety | S2-safety | Bounded confidence penalty (max 0.04) |
| Readiness check resolution | Safety | S3-safety | Bounded confidence penalty (max 0.03) |
| Agent policy check | Safety | S4-safety | Hard deny on policy violation |
| Rollback watch snapshot | Safety | S5-safety | Audit enrichment (no penalty) |

**Note on core adapter defaults:** When no pipeline report/state is available
(e.g., the caller didn't run the core pipeline), all core adapters resolve
with `available=False`, zero penalty, no escalation. The system degrades
gracefully — absent signals never weaken governance.

### Tier 2: Live When Sovereign Projection Metadata Is Present

These signals activate **only** when the caller supplies
`sovereign_projection_metadata` on the `AuthorizationRequest`. This
metadata originates from the sovereign inference bridge
(`ProjectionMetadata`) and must be explicitly threaded by the caller.

| Signal | Phase | Effect | Requires Key |
|--------|-------|--------|-------------|
| Reasoning diagnostics | S3 | Mauna → caution code; rest audit-only | `reasoning_diagnostics` |
| Guna anomaly detection | S4 | Confidence penalty (max 0.05) + escalation bias | `guna_anomalies` |
| Bhava transition audit | S4 | Audit-only | `reasoning_diagnostics` (for `dominant_bhava`) |
| Governor telemetry | S4 | Audit-only | `governor_telemetry` |

**When metadata is absent:** All Tier 2 resolvers return safe defaults
(available=False, zero penalty, no escalation, None audit dicts). The
governance decision proceeds exactly as if S3/S4 did not exist.

**Important nuance:** The architecture now *can* consume these signals live.
Whether they *are* consumed depends on whether the caller's runtime path
produces and passes `ProjectionMetadata`. Not every possible caller or
pipeline mode necessarily does this.

### Tier 3: Replay / Simulation Only (Never Live)

These components exist for downstream analysis tools but are **never**
invoked on the live `authorize()` path.

| Signal | Track | Phase | Purpose |
|--------|-------|-------|---------|
| Counterfactual sandbox bridge | Core | C4 | What-if analysis for approval workflows |
| `AuditEvent.counterfactual` field | Core | C4 | Attached post-hoc by replay tools |

The counterfactual bridge (`counterfactual_bridge.py`) is not imported by
`governance_service.py`. Its output is never attached during live decisions.

### Tier 4: Future / Not Yet Wired

| Signal | Description | Status |
|--------|-------------|--------|
| Session enrichment: identity signature | `session_enrichment_adapter._resolve_identity()` consumes `metadata["identity_signature"]` | Bridge-ready, not bridge-fed (see §Pipeline ↔ Governance below) |
| Session enrichment: motivation profile | `session_enrichment_adapter._resolve_motivation()` consumes `metadata["motivation_profile"]` | Bridge-ready, not bridge-fed |
| Session enrichment: temporal summary | `session_enrichment_adapter._resolve_temporal()` consumes `metadata["temporal_summary"]` | Bridge-ready, not bridge-fed |
| Temporal trajectory prediction | JEPA forecasting future semantic state | Not implemented |
| `previous_bhava` tracking | Cross-request bhava transition history | Hardcoded to `None` |
| Deeper sovereign model internals | Per-layer attention weights, gradient norms, etc. | Intentionally excluded |
| Live counterfactual analysis | Real-time what-if during authorize | Intentionally deferred |

### Policy Track: Capability Classification

The policy track capabilities span six distinct tiers — from live runtime
through to future work. This table classifies every major policy capability.

| Capability | Tier | Description |
|------------|------|-------------|
| `compute_policy_flags()` | **Live runtime** | Called by pipeline consumers on every policy evaluation |
| `compute_session_policy_flags()` | **Live runtime** | Called with session summary data |
| `compute_trading_guardrails()` | **Live runtime** | Called with trading context data |
| `resolve_interaction_mode()` | **Live runtime** | Domain + override → active mode |
| `get_domain_profile()` | **Live runtime** | Registry lookup (fallback to generic) |
| `ExposureGate.evaluate()` | **Live runtime** | RBAC layer visibility, wired into governance |
| `DomainProfile` threshold fields | **Live runtime** | 19 P2 thresholds used by policy engines |
| `PolicyService.compute_policy()` | **Service/backend** | Structured wrapper with audit (optional caller path) |
| `PolicyService` audit log | **Service/backend** | In-memory, max 1000 entries, non-persistent |
| `GovernanceService.get_policy_audit_log()` | **Service/backend** | Read-only retrieval from attached PolicyService |
| `simulate_policy()` | **Simulation-only** | Evaluate policy under alternate profile |
| `compare_policy()` | **Simulation-only** | Side-by-side baseline vs candidate diff |
| `simulate_session_policy()` | **Simulation-only** | Session policy with threshold overrides |
| `simulate_trading_guardrails()` | **Simulation-only** | Trading guardrails with threshold overrides |
| `PolicyLifecycleManager.stage_candidate()` | **Lifecycle** | Stage candidate profile (DRAFT) |
| `PolicyLifecycleManager.validate_candidate()` | **Lifecycle** | Mark validated, attach simulation |
| `PolicyLifecycleManager.activate()` | **Lifecycle** | Promote to registry, supersede previous |
| `PolicyLifecycleManager.rollback()` | **Lifecycle** | Revert to previous active profile |
| `request_activation_approval()` | **Lifecycle** | Approval-ready payload (not execution) |
| `DeploymentRecord` history | **Lifecycle** | In-memory deployment event records |
| `PolicyControlPlane.get_system_snapshot()` | **Control-plane** | All-domains policy state overview |
| `PolicyControlPlane.get_domain_status()` | **Control-plane** | Per-domain status query |
| `PolicyControlPlane.get_health_report()` | **Control-plane** | Stale candidates, fallback warnings |
| `PolicyControlPlane.get_deployment_history()` | **Control-plane** | Filtered deployment records |
| `PolicyControlPlane.get_approval_history()` | **Control-plane** | Lifecycle audit entries |
| `PolicyControlPlane.get_simulation_history()` | **Control-plane** | Records with simulation summaries |
| `tenant_id` on all P4 surfaces | **Future** | Passthrough parameter, no scoping logic |
| Durable persistence for lifecycle state | **Future** | Currently in-memory only |
| Full approval workflow execution | **Future** | Currently payload/hook-ready only |
| External governance API / dashboard | **Future** | No HTTP endpoints, no UI |
| Insight-window consolidation | **Future** | Two active paths, consolidation deferred |
| `governance_binding.py` promotion | **Future** | Provisional facade, zero consumers |
| `preferences.py` promotion | **Future** | Provisional facade, bypassed by policy_engine |
| `licensing/__init__.py` promotion | **Future** | Provisional facade, no license gates |

---

## Signal Classification Hierarchy

Signals have four distinct roles in governance, forming a strictness hierarchy.
The documentation must not conflate signals that change decisions with signals
that only enrich the audit trail.

### Behavior-Affecting Signals

These signals can change the governance decision (confidence, escalation,
execution mode). All effects are **stricter-only** — they can only reduce
confidence or increase escalation, never relax governance.

| Signal | Effect | Bound | Track | Phase |
|--------|--------|-------|-------|-------|
| Entropy penalty | Reduces confidence | max 0.15 | Sovereign | S1 |
| Insight penalty | Reduces confidence | max 0.10 | Sovereign | S2 |
| Guna collapse penalty | Reduces confidence | 0.03 | Sovereign | S4 |
| Guna oscillation penalty | Reduces confidence | 0.02 | Sovereign | S4 |
| Guna collapse escalation | Bumps escalation +1 | Single step | Sovereign | S4 |
| Mauna active | Adds caution reason code | Informational | Sovereign | S3 |
| Generation gate (DENY) | Hard deny for generative actions | Binary | Core | C1/C3 |
| C2 coherence penalty | Reduces confidence | max 0.05 | Core | C2 |
| C2 drift penalty | Reduces confidence | max 0.05 | Core | C2 |
| C2 drift escalation | Bumps escalation +1 | Single step | Core | C2 |
| C3 UCF penalty | Reduces confidence | max 0.05 | Core | C3 |
| C3 UCF escalation | Bumps escalation +1 | Single step | Core | C3 |
| C4 P35 drift penalty | Reduces confidence | max 0.03 | Core | C4 |
| C4 P35 drift escalation | Bumps escalation +1 | Single step | Core | C4 |
| O4 balance penalty | Reduces confidence | max 0.05 | Ontology | O4 |
| O4 balance escalation | Bumps escalation +1 | Single step | Ontology | O4 |
| S2 plasticity penalty | Reduces confidence | max 0.04 | Safety | S2-safety |
| S2 plasticity escalation | Bumps escalation +1 | Single step, < 0.35 | Safety | S2-safety |
| S3 readiness penalty (NOT_READY) | Reduces confidence | 0.03 | Safety | S3-safety |
| S3 readiness penalty (DEGRADED) | Reduces confidence | 0.02 | Safety | S3-safety |
| S3 readiness escalation | Bumps escalation +1 | NOT_READY only | Safety | S3-safety |
| S4 policy engine (DENY) | Hard deny for policy violations | Binary | Safety | S4-safety |
| **Aggregate penalty cap** | **Caps total from all adapters** | **max 0.20** | All | Patch |

### Light Behavior Signals

Small penalties that indicate instability but are not strong enough to
justify escalation.

| Signal | Effect | Bound | Track | Phase |
|--------|--------|-------|-------|-------|
| C4 P37 fragmenting | Reduces confidence | 0.02 | Core | C4 |
| C4 P37 strained | Reduces confidence | 0.005 | Core | C4 |

### Audit-Only Signals

These signals appear in `AuditEvent` fields for forensic analysis, replay,
and human review. They do **not** change any governance decision.

| Signal | Audit Field | Track | Phase |
|--------|-------------|-------|-------|
| Sovereign telemetry | `sovereign_telemetry` | Sovereign | S1 |
| Sovereign health snapshot | `sovereign_health` | Sovereign | S2 |
| Sovereign insight snapshot | `sovereign_insight` | Sovereign | S2 |
| Reasoning diagnostic context | `sovereign_diagnostics` | Sovereign | S3 |
| OPB lock/unlock tracking | within `sovereign_diagnostics` | Sovereign | S3 |
| Vritti rejection flag | within `sovereign_diagnostics` | Sovereign | S3 |
| Bhava transition audit | `sovereign_bhava_transition` | Sovereign | S4 |
| Governor telemetry | `sovereign_governor_telemetry` | Sovereign | S4 |
| Guna anomaly snapshot | `sovereign_guna_anomalies` | Sovereign | S4 |
| C2 identity stability | within `core_coherence` | Core | C2 |
| C2 continuity health | within `core_coherence` | Core | C2 |
| C4 P36 identity resonance | within `predictive_signals` | Core | C4 |
| S2 plasticity gate snapshot | `plasticity_gate` | Safety | S2-safety |
| S3 readiness check snapshot | `readiness_check` | Safety | S3-safety |
| S4 agent policy snapshot | `agent_policy` | Safety | S4-safety |
| S5 rollback watch snapshot | `rollback_watch` | Safety | S5-safety |

### Replay / Simulation-Only Signals

These components are never invoked on the live path. They exist for
downstream analysis, approval workflows, and audit replay tools.

| Signal | Audit Field | Track | Phase |
|--------|-------------|-------|-------|
| Counterfactual sandbox | `counterfactual` (always None live) | Core | C4 |

The classification hierarchy matters: behavior-affecting signals are bounded,
capped, and wrapped in fail-safe try/except. Audit-only signals provide
observability without governance risk — a bug in audit-only data cannot
change a decision. Replay/simulation-only signals are fully isolated from
the live path.

---

## Penalty Safety Model

All signal-derived confidence penalties (sovereign and core) are layered
with multiple safety boundaries to prevent over-penalization.

### Per-Adapter Caps

Each adapter independently caps its own penalty:

| Adapter | Track | Individual Cap | Rationale |
|---------|-------|---------------|-----------|
| Entropy adapter | Sovereign | 0.15 | Entropy uncertainty is informational, not conclusive |
| Insight adapter | Sovereign | 0.10 | Insight gate is heuristic, not proof |
| Guna anomaly adapter | Sovereign | 0.05 | Temporal anomalies are noisy |
| Coherence state adapter (C2) | Core | 0.10 | Coherence + drift combined |
| UCF adapter (C3) | Core | 0.05 | Consciousness stability is heuristic |
| Predictive signals adapter (C4) | Core | 0.05 | P35 + P37 combined |
| Ontology balance adapter (O4) | Ontology | 0.05 | Mirror-pair imbalance |
| Plasticity adapter (S2-safety) | Safety | 0.04 | Sigmoid gate closing |
| Readiness adapter (S3-safety) | Safety | 0.03 | Multi-criterion not-ready |

### Aggregate Cap

The raw sum of all adapter penalties could theoretically reach 0.57+. The
aggregate cap ensures the total penalty from all sources never exceeds 0.20:

```python
sovereign_penalty = min(
    0.20,
    entropy_resolution.confidence_penalty         # max 0.15 (S1)
    + insight_resolution.confidence_penalty        # max 0.10 (S2)
    + guna_anomaly_resolution.confidence_penalty   # max 0.05 (S4)
    + core_coherence_resolution.confidence_penalty # max 0.10 (C2)
    + ucf_resolution.confidence_penalty            # max 0.05 (C3)
    + predictive_resolution.confidence_penalty     # max 0.05 (C4)
    + ontology_balance_signal.confidence_penalty   # max 0.05 (O4)
    + plasticity_resolution.confidence_penalty,    # max 0.04 (S2-safety)
)
# Readiness penalty (S3-safety, max 0.03) is added incrementally
# and re-capped at 0.20 after the initial aggregate.
```

**Note:** The S4-safety policy engine does not contribute a confidence
penalty — it produces a hard DENY override. The S5-safety rollback monitor
does not contribute any penalty — it is purely observational/audit.

This protects against pathological stacking where multiple noisy signals
simultaneously fire, which could otherwise drop confidence unreasonably.

### Drift Overlap: C2 vs C4 (Intentional)

Both C2 and C4 include drift-related penalties:
- **C2** penalizes on **current/stateful** drift posture from `CoherenceState`
  (persona_drift, drift_risk_band) — up to 0.05 penalty
- **C4 P35** penalizes on **predictive/forecast** drift risk from
  `PredictivePersonaDriftReport` (predicted_drift_score) — up to 0.03 penalty

Both may contribute simultaneously when both signals are present. This is
**intentional**: current drift and predicted drift are complementary signals,
not duplicates. The aggregate cap (0.20) bounds the combined effect.

### Fail-Safe Defaults

Every resolver wraps its logic in `try/except`:

```python
def _resolve_guna_anomaly_signal(jepa_assessment):
    try:
        # ... extract and resolve ...
    except Exception:
        return GunaAnomalyResolution()  # zero penalty, no escalation
```

If any signal resolution fails, it returns a neutral default (zero penalty,
no bias, available=False). Signal integration cannot crash or corrupt the
governance decision path.

### Stricter-Only Invariant

All signal effects are stricter-only:
- Confidence penalties are non-negative (penalty ≥ 0)
- Escalation bias only bumps up, never down
- No signal can relax a governance decision
- No signal can override a DENY to ALLOW
- Generation gate produces hard DENY, never softens

---

## Current Limitations and Conditionality

### Sovereign Metadata Presence

S3/S4 signals require `sovereign_projection_metadata` on the
`AuthorizationRequest`. This metadata must be explicitly provided by the
caller. The governance service does not manufacture it.

In practice, this metadata originates from:
1. `sovereign/inference_bridge.py` — `project_sovereign_to_inference()` produces `ProjectionMetadata`
2. The caller serializes it to a dict and attaches it to the request

If the caller's runtime path does not include the sovereign inference
bridge (e.g., lightweight pipeline modes, or callers that don't have
access to model internals), S3/S4 signals will be absent and the system
operates with S1/S2 enrichments only.

### Core Pipeline Data Availability

Core adapters (C2/C3/C4) resolve against duck-typed pipeline
report/state objects passed to the governance service's internal
resolution helpers. When the core pipeline hasn't run (or hasn't
produced reports), all core adapters resolve with `available=False`,
zero penalty, no escalation. This is the expected degraded mode.

The core adapters never import pipeline engine classes — they use
`getattr()` with `None` defaults. This means any object with the
expected attribute names will work, enabling both real pipeline outputs
and synthetic test fixtures.

### Generation Gate Boot Requirement

The generation gate (`generation_gate.py`) must be sealed at boot time
via `GenerationGate.seal(ENABLED)` or `GenerationGate.seal(DISABLED)`.
If the gate is never sealed (UNSEALED state), all generative actions are
denied. This is a deliberate fail-closed design — the system is safe
by default even if boot is incomplete.

### `previous_bhava` Is Not Tracked

Bhava transition priors (`sovereign_bhava_priors.py`) evaluate the
transition from `previous_bhava` to `current_bhava`. Currently,
`previous_bhava` is hardcoded to `None` in `governance_service.py`.
This means bhava transition audit data captures only the current bhava,
not cross-request transition quality. Implementing cross-request bhava
tracking would require session-level state.

### Counterfactual Bridge Is Simulation-Only

The counterfactual bridge (`counterfactual_bridge.py`) provides P25
sandbox functionality but is deliberately excluded from the live
`authorize()` path. The `AuditEvent.counterfactual` field is reserved
for downstream replay and approval-workflow tools that attach results
post-hoc. Promoting counterfactual analysis to the live path would
require latency budgeting and governance authority justification.

### Sovereign-Side Constant Duplication

Some sovereign model files may still define constants internally that
overlap with shared authorities (e.g., guna labels, bhava names).
Governance runtime consumers now use shared constants from
`sovereign_constants.py`, but the model-internal definitions have not
been fully deduplicated. This is a code hygiene issue, not a correctness
issue — the governance side uses the right values.

### Intentionally Excluded Internals

The following internals are **deliberately** not wired into governance:

| Component | Why Excluded |
|-----------|-------------|
| Per-layer attention weights | Too noisy, no clear governance semantics |
| Gradient norms / training signals | Training-only, not meaningful at inference |
| Raw 128D state vector | Governance doesn't need tensor-level detail |
| `nn.Module` internals (observer, guna, vritti modules) | PyTorch dependency boundary |
| PID governor internal state (beyond telemetry) | Telemetry passthrough is sufficient |
| Live counterfactual analysis | Latency-prohibitive for real-time decisions |
| Core pipeline engine classes | Numpy dependency boundary — duck-typed instead |

These are excluded by design, not by oversight. The bridge architecture
extracts semantically meaningful summaries and discards implementation
detail.

### Audit-Only / Replay-Only Signals By Design

Several signals are audit-only or replay-only by design — they provide
observability but do not change governance decisions:

- **Audit-only:** S4 bhava transition, governor telemetry; C2 identity
  stability, continuity health; C4 P36 identity resonance
- **Replay-only:** C4 counterfactual sandbox

This is intentional: not every signal justifies governance authority.
Promoting audit-only signals to behavior-affecting status would require
rigorous justification and new bounded adapter logic.

### Safety Track Limitations

| Limitation | Details | Status |
|-----------|---------|--------|
| **`safety_bounds.py` remains dormant** | Requires an action-magnitude payload model that does not exist. The framework has no concept of action size/magnitude to clamp against. | Future work |
| **Rollback is lifecycle-preparatory** | `GovernanceService` is authorize-only. No post-action execution callback, no automatic rollback execution. S5 captures pre-action snapshots; external callers must call `check()`. | By design (honest) |
| **Readiness cooldown disabled** | `ReadinessChecker` supports cooldown between actions, but `GovernanceService` has no cross-request state. `min_time_since_action_seconds=0.0` (disabled, documented). | Future work |
| **Dead facades still present** | S0 marked them as UNUSED but did not delete them. They remain as inert code with explicit status markers. | By design |
| **No stateful safety tracking** | Safety signals (plasticity, readiness) are computed fresh per request. No cross-request trend tracking. | Future work |
| **Policy engine is opt-in** | `PolicyEngine` must be explicitly passed to `GovernanceService`. No engine configured = all actions allowed (fail-safe). | By design |
| **GCC opaque IDs are heuristic** | `_is_opaque_id()` uses a pattern-based check (alphanum+hyphens+underscores+dots, ≤64 chars). Edge cases could theoretically pass or fail incorrectly. | By design |
| **Safety folder dual copies** | `symbolu/safety/` and `agentic/safety/` maintain parallel copies of GCC modules. No automated sync. | Code hygiene |

### Ontology Track Limitations

| Limitation | Details | Status |
|-----------|---------|--------|
| **Rule-based encoding** | 10D backbone uses regex patterns, not learned embeddings. Encoding quality depends on pattern coverage. | By design |
| **Single consumer** | Only `resolve_ontology_balance()` is wired into governance (O4). Encoding and similarity adapters (O2) are available but have no governance consumer. | Future work |
| **Content input is action labels** | Balance is computed from `action_type + tool_name`, not rich semantic content. This produces stable but coarse-grained signals. | By design |
| **No cross-request state** | Each balance computation is stateless. No tracking of balance trends across requests. | Future work |
| **Validator duplication** | `ontology/safety.py` (O2) duplicates constants from `projection/validators.py`. Both sources agree, but deduplication is incomplete. | Code hygiene |
| **Mirror package sync** | `symbolu/ontology/` mirrors `agentic/ontology/` manually. No automated sync mechanism. | By design |

### Policy Track Limitations

The policy track (P0–P4) is closed as an internal backend/control-plane layer,
not as a full external product. The following limitations are known and
intentional:

| Limitation | Details | Status |
|-----------|---------|--------|
| **In-memory lifecycle state** | All `PolicyLifecycleManager` history and candidates are lost on process restart. No database or file persistence. | Future work |
| **In-memory audit log** | `PolicyService` audit log is capped at 1000 entries with silent eviction. Not persistent. | Future work |
| **Approval is payload-only** | `request_activation_approval()` produces structured payloads but does not execute or track approvals end-to-end. | Future work |
| **No production P3/P4 callers** | Lifecycle management and control-plane queries are tested but have no production callers outside tests. Ready for API/dashboard integration. | Future work |
| **Service-vs-direct compute** | `PolicyService.compute_policy()` wraps `compute_policy_flags()` with audit. Some consumers call `compute_policy_flags()` directly, bypassing audit. Both produce identical flags. | By design |
| **Dual insight-window paths** | `insight_window_gating.py` (policy-engine path) and `insight_window/` (pipeline-native P32 path) coexist with different schemas. Both active, consolidation deferred. | Future work |
| **Dormant provisional facades** | `governance_binding.py`, `preferences.py`, `licensing/__init__.py` are re-export facades with zero runtime consumers. Honestly marked "provisional." | By design (defer/remove later) |
| **Tenant scoping** | `tenant_id` parameter exists on all P4 query surfaces as passthrough. No filtering, scoping, or tenant management logic. | Future work |
| **No external API** | No HTTP endpoints, REST/GraphQL API, or dashboard UI. Policy layer is internal-only. | Future work |

### How the Five Tracks Connect

The sovereign, core, ontology, policy, and safety tracks serve complementary
roles in the broader governance architecture:

```
  SOVEREIGN TRACK   CORE TRACK     ONTOLOGY TRACK  SAFETY TRACK     POLICY TRACK
  (S1–S4)           (C1–C4)        (O1–O4)         (S0–S5)          (P0–P4)
  ─────────────     ──────────     ──────────────  ──────────────   ───────────
  signal extract    signal extract enum + 10D      boundary guard   policy compute
  + bounded gov     + bounded gov  balance signal  + gov signals    simulation, CP
  enrichments       enrichments                    + policy guard
                                                   + rollback watch

      │                  │              │               │                │
      │ confidence       │ confidence   │ confidence    │ penalties      │ policy flags
      │ penalties        │ penalties    │ penalty       │ hard deny      │ session policy
      │ escalation       │ generation   │ escalation    │ escalation     │ trading guards
      │ audit data       │ gate + audit │ audit data    │ audit data     │ interaction modes
      ▼                  ▼              ▼               ▼                │
  ┌───────────────────────────────────────────────────────────┐       │
  │  GovernanceService.authorize()                            │       │
  │  (live governance decision path)                          │◀──────┘
  │                                                           │ layer visibility
  │  Produces: ALLOW / DENY / ESCALATE                        │ policy audit log
  │  + enriched AuditEvent with all track signals             │
  └───────────────────────────────────────────────────────────┘

  The policy track also provides independent capabilities:
  - Policy simulation/comparison (standalone, not via governance)
  - Lifecycle management (stage/validate/activate/rollback)
  - Backend control-plane queries (health, history, snapshots)

  The safety track also provides independent capabilities:
  - GCC boundary enforcement at constrained module outputs (S1)
  - Ledger invariant enforcement at write boundaries (S1)
  - Rollback watch for external post-action monitoring (S5)
```

**Key distinctions:**
- **Sovereign, core, and ontology** tracks feed signals into the governance
  decision path (confidence adjustments, escalation biases, generation gate).
- **Safety** track provides both boundary enforcement (GCC/ledger, S1) and
  governance signals (plasticity/readiness penalties, policy hard-deny,
  rollback watch audit). It spans both runtime guard and adapter patterns.
- **Policy** track provides domain-specific policy computation and
  operational tooling alongside governance. Only `layer_visibility_policy.py`
  and the policy audit log directly connect to `governance_service.py`.

---

## Pipeline ↔ Governance Authorization: Bridge Status

The mechanical pipeline (`symbolu_core/mechanical/pipeline/orchestrator.py`)
and the agentic governance authorization system (`GovernanceService.authorize()`)
are **architecturally adjacent but operationally disconnected**. No bridge
exists between them today.

### What Each System Does

**Mechanical pipeline** — synchronous in-process request processing:
- PO1–PO5 pre-acoustic governance (grounding, intent, action constraints)
- MLCR → HRM/LCM/LAM → Persona → Fusion → DHA → Renderer
- Session processing (policy flags, memory, recap, intent arc,
  identity signature, motivation profile, trading guardrails)
- Output processing → unified API response

**Governance authorization service** — tool/action authorization decisions:
- Confidence gating with bounded signal penalties
- Tool risk classification (READ_ONLY → PRIVILEGED)
- Sovereign, core, ontology, and policy signal consumption
- Safety contract preconditions
- External-facing `POST /authorize` endpoint via FastAPI

### Current Bridge State: Not Connected

`GovernanceService.authorize()` has **zero production callers** from the
mechanical pipeline:

- `symbolu_core/mechanical/` has no imports of `GovernanceService` or
  `AuthorizationRequest`
- The orchestrator does not call any agentic governance function
- The FastAPI `/authorize` endpoint (`governance_api.py`) exists but is
  not started or called by any pipeline code
- PO1–PO5 inside the pipeline are the pipeline's **own** pre-acoustic
  governance — they are unrelated to `GovernanceService.authorize()`

**P52 status:** Phase 52 (`p52_governance_adapter/`) defines a
`GovernanceRequest` data contract as a future interface socket. However:
- P52 is **never invoked** from the orchestrator
- P52 explicitly "does NOT send [the request] anywhere"
- P52's invariant states "When P52 is removed, system behavior is
  bitwise identical"
- P52's `GovernanceRequest` is a **different type** from
  `AuthorizationRequest` (different fields, different schema)

P52 is an interface definition, not a live bridge.

### Identity Signature Engine: Live in Pipeline, Inactive in Governance

The identity signature engine (`agentic/identity/identity_signature_engine.py`)
is **live and useful** within the mechanical pipeline:

| Consumer | Location | Status |
|----------|----------|--------|
| Session processing | `session_processing.py` → `ctx.identity_signature` | **Live** — computed on every session |
| Motivation engine | `motivation_engine.py` | **Live** — uses identity signature as input |
| Trading guardrail engine | `trading_guardrail_engine.py` | **Live** — reads `ctx.identity_signature` |
| Unified API output | `unified_api.py` | **Live** — serialized to API response |

On the governance side, `session_enrichment_adapter._resolve_identity()` is
**structurally ready** to consume identity signatures:
- Recognizes `self_fragmentation` and `self_dissonance` as instability types
- Applies bounded confidence penalty (max 0.05)
- Returns safe defaults when identity data is absent

But this path reads from `AuthorizationRequest.metadata["identity_signature"]`,
which is **never populated** because no code constructs an `AuthorizationRequest`
from pipeline context.

### Session Enrichment: Bridge-Ready, Not Bridge-Fed

The governance service calls `_resolve_session_enrichment(request)` on every
`authorize()` invocation (Step 2b in `_evaluate()`). This resolver reads five
well-known keys from `request.metadata`:

| Metadata Key | Governance Consumer | Pipeline Producer | Bridge Status |
|-------------|-------------------|------------------|---------------|
| `identity_signature` | `_resolve_identity()` → penalty for fragmentation/dissonance | `ctx.identity_signature` via `compute_identity_signature()` | **Not bridged** |
| `identity_resonance_state` | `_resolve_identity()` → stability band | `ctx.identity_resonance_memory_snapshot` | **Not bridged** |
| `motivation_profile` | `_resolve_motivation()` → penalty for risk-relevant types | `ctx.motivation_profile` via `compute_motivation_profile()` | **Not bridged** |
| `temporal_summary` | `_resolve_temporal()` → penalty for temporal tension | Temporal tracker `get_pattern_summary()` | **Not bridged** |
| `coherence_state` | `_resolve_temporal()` → tension index | `ctx.coherence_state` | **Not bridged** |

All five signals are produced within the mechanical pipeline and have
working governance-side consumers. None currently cross the boundary.

### Why This Is Not a Simple Metadata Patch

Connecting these systems requires more than adding a field to a dict:

1. **No `AuthorizationRequest` is constructed anywhere in the pipeline.**
   The pipeline produces `RenderedOutput`, not authorization requests.
2. **The two systems serve different purposes.** The pipeline processes
   natural language queries through cognitive mappers. Governance
   authorization evaluates tool-use safety for external agents.
3. **Calling `GovernanceService.authorize()` from the pipeline** would
   require mapping pipeline concepts (intent, persona, mappers) to
   authorization concepts (action_type, tool_name, agency_level).
4. **Latency and blocking** — `authorize()` is designed for pre-action
   decisions, not mid-pipeline enrichment.

### Future Work

Building this bridge is a deliberate architectural integration project:

| Task | Scope | Prerequisite |
|------|-------|-------------|
| Define when/why the pipeline should invoke governance authorization | Architecture decision | Clarity on whether pipeline actions need tool-risk authorization |
| Map pipeline context to `AuthorizationRequest` fields | Translation layer | Architecture decision above |
| Thread session enrichment signals into metadata | Metadata bridge | Translation layer above |
| Activate P52 as the live bridge (or replace with direct integration) | Orchestrator change | All of the above |

Until this bridge is built, session enrichment adapters (identity,
motivation, temporal) resolve with zero penalty and safe defaults —
exactly as designed by fail-closed semantics.

---

## Inference CG Metadata ↔ MCP Gateway: Enrichment Seam

Separate from the pipeline↔authorize bridge above, a second bridge
connects **CG-capable LLM adapters** to the **MCP gateway's governance
path**. Unlike the pipeline bridge, this one is wired and production-
ready on the MCP side.

### What this seam does

When a CG-capable LLM adapter (e.g. `MistralCGAdapter`) generates,
it stores a snapshot of the 32D sovereign state in
`adapter.last_cg_metadata`. That dict can be handed directly to
`SafeMCPGateway.call_tool_simple()`, which attaches canonical
governance signals derived from the sovereign state before the
standard gateway/governance path runs.

### Producer: `MistralCGAdapter.last_cg_metadata`

After each `generate(...)` call, the adapter populates a dict with
this wire contract:

| Key | Type | Required | Notes |
|-----|------|----------|-------|
| `state` | 32-float sovereign state | **Yes** | Full 32D layout (bhava/kosha/vritti/guna) |
| `delta_S` | 32-float state delta | No | `None` means "velocity unknown" (not fabricated) |
| `delta_bhava` | optional | No | Adapter-specific extension slot |
| `intent_phase` | optional | No | Adapter-specific extension slot |

The demo (`examples/cg_tool_demo.py`) ships a zero-dependency
`DemoCGAdapter` that produces exactly this wire shape for local
validation without a real checkpoint.

### Bridge helpers (`agentic/agentic_framework/sovereign_bridge.py`)

Pure translation functions, no orchestration:

- `entropy_from_sovereign_state(state, delta_S=..., tier_name=...)`
  → canonical `EntropyResult`
- `vritti_from_sovereign_state(state, delta_S=..., tier=...)`
  → canonical `ChittaVrittiResult`
- `projection_metadata_from_sovereign_result(projection_result)`
  → `sovereign_projection_metadata` dict (only when the caller
  already holds a real `SovereignProjectionResult`; MCP/tool-use
  path does not hold one today — see "What this seam does NOT
  produce" below)
- `governance_inputs_from_cg_metadata(cg_metadata, tier=...)`
  → `{"entropy_result": ..., "vritti_result": ...}` (calls the two
  state helpers above; does **not** include projection metadata)

**What this seam does NOT produce:** no `sovereign_projection_metadata`
is fabricated from CG metadata. `MistralCGAdapter` stores the raw 32D
state, not a full `SovereignProjectionResult`. Honest absence, not
invention.

### Request-boundary seam
(`agentic/agentic_framework/request_enrichment.py`)

One reusable helper standardizes the translation for any request-
boundary caller:

```python
build_governance_enrichment_kwargs(
    *,
    cg_metadata: Optional[Dict[str, Any]] = None,
    tier: str = "consumer",
) -> Dict[str, Any]
```

- Returns `{}` when `cg_metadata` is `None` (neutral-when-absent, so
  callers can splat unconditionally).
- Otherwise returns `{"entropy_result": ..., "vritti_result": ...}`
  via `governance_inputs_from_cg_metadata`.
- Lazy-imports the bridge so the default (unenriched) path stays
  torch-free.

**Request-boundary rules** (pinned by the helper; see
`docs/REQUEST_BOUNDARY_CONVENTION.md`):

1. Attach `entropy_result` and `vritti_result` when live CG metadata
   is available.
2. Return a neutral / no-op enrichment (`{}`) when CG metadata is
   absent — callers splat unconditionally; governance falls back to
   its pre-existing approximation path.
3. **Never fabricate** `sovereign_projection_metadata`. A real
   `SovereignProjectionResult` producer is required; the MCP/tool-use
   path has none, so the field is intentionally omitted.
4. Fail-closed behavior on the governance consumer side is
   preserved — unenriched calls still go through the pre-Phase-1
   approximation; enriched calls go through the real-signal branch.

Today this helper is consumed by `SafeMCPGateway.call_tool_simple()`.
Tomorrow it will be splatted into `AuthorizationRequest(**...)` once
a production caller exists for that path (see below).

### Consumer: `SafeMCPGateway.call_tool_simple(...)`

```python
async def call_tool_simple(
    self,
    tool_name: str,
    parameters: Dict[str, Any],
    quality_score: float = 0.5,
    coherence_score: float = 0.5,
    *,
    cg_metadata: Optional[Dict[str, Any]] = None,
    tier: str = "consumer",
) -> MCPToolResult
```

When `cg_metadata` is provided, the gateway calls the request-boundary
seam, attaches `entropy_result` (formal `MCPToolCall` field) and
`vritti_result` (duck-typed attribute, read via `getattr` by the
governance consumer), and then runs the normal gateway path unchanged.
The audit record reflects the real signal source
(`vritti_signal_source="real"`, `entropy_available=True`) rather than
the fallback approximation.

### Current enrichment status

| Side | Status |
|------|--------|
| **MCP gateway (`call_tool_simple`)** | **Wired and production-ready.** Accepts `cg_metadata`, attaches real signals, routes through the existing governance consumer path. |
| **`AuthorizationRequest`** | **Seam ready, no honest production caller yet.** The replay harness (`policy_replay._event_to_request`) cannot be enriched without fidelity violation; the FastAPI `/authorize` endpoint receives requests from external callers and cannot synthesize `cg_metadata`. No component today simultaneously holds a `MistralCGAdapter` and constructs an `AuthorizationRequest`. |

### Demo as executable proof: `examples/cg_tool_demo.py`

This demo is **not a product runtime**. It is the smallest honest
end-to-end exerciser of the seam. It proves the full path:

```
generation → adapter.last_cg_metadata → build_governance_enrichment_kwargs
  → SafeMCPGateway.call_tool_simple(cg_metadata=...)
  → governance evaluation → audit record
```

Running the demo prints an audit entry with
`vritti_signal_source="real"` and `entropy_available=True`, proving
the CG-derived signals were consumed by governance (not the
approximation fallback). Swapping `DemoCGAdapter` for
`create_adapter("mistral_cg", ...)` is a one-line change — the
surrounding flow stays identical.

A smoke test (`tests/test_cg_tool_demo.py`) pins the demo's behavior
as a regression guard for the full seam.

### Owner component: `CGToolDispatcher`
(`agentic/agentic_framework/cg_tool_dispatcher.py`)

The smallest honest owner component that holds both an adapter and a
gateway and composes them:

```python
from agentic.agentic_framework.cg_tool_dispatcher import CGToolDispatcher

dispatcher = CGToolDispatcher(adapter, gateway, tier="consumer")
result = await dispatcher.dispatch(
    tool_name="file_read", parameters={"path": "/tmp/x"},
)
```

`dispatch(...)` reads the adapter's **current** `last_cg_metadata`
on every call and forwards it through `gateway.call_tool_simple`.
When the adapter has not yet generated (`last_cg_metadata == {}`),
the dispatcher calls the gateway with `cg_metadata=None`, preserving
the pre-Phase-1 no-CG path exactly. The dispatcher adds no policy of
its own — tier is pass-through, scores are pass-through.

This component formalizes the ad-hoc composition the demo performs
inline. A CG-capable production runtime can now hold a dispatcher
instead of re-implementing the compose step.

### Composition factory: `build_cg_mcp_agent(...)`

Thin, one-knob factory (same file) that composes the full runtime
from a single adapter. It is a **composition helper, not a new
orchestrator**:

```python
from agentic.agentic_framework.cg_tool_dispatcher import build_cg_mcp_agent

agent = build_cg_mcp_agent(
    adapter=adapter,                     # the only thing that changes
    gateway=None,                        # default: mock MCP gateway
    action_type_to_tool=None,            # default mapping (see below)
    tier="consumer",
    allow_stub=False,                    # warns if adapter.IS_STUB
)
```

What it does:
- builds (or accepts) a `SafeMCPGateway`;
- builds a `CGToolDispatcher` around the adapter+gateway;
- constructs an `AgenticLLMWrapper` with the dispatcher injected
  and the action-type→tool mapping pinned;
- logs a WARNING when the adapter reports `IS_STUB=True` and
  `allow_stub=False`.

The substitution seam: swap `adapter=` between
`StubCGLLMAdapter` (dev/test) and `MistralCGAdapter` (real CG). No
other wiring changes — same `SafetyGate`, same `_execute_actions`,
same dispatcher, same gateway, same audit log.

For the concrete end-to-end runtime diagram see
`agentic/agentic_framework/docs/RUNTIME_MCP_PATH.md`. For the
runnable `inference_mistral.py --cg` CLI see
`agentic/agentic_framework/docs/CG_RUNTIME_RUNBOOK.md`.

### Stub adapter vs real adapter

Two concrete adapters currently satisfy the `_CGCapableAdapter`
protocol (`last_cg_metadata: dict` refreshed per `call()` with at
least a 32D `state`):

| Adapter             | Provenance                       | Purpose                               |
|---------------------|----------------------------------|---------------------------------------|
| `StubCGLLMAdapter`  | deterministic fixture            | dev/test wiring proofs                |
| `MistralCGAdapter`  | real local CG inference          | real runtime proof path               |

`StubCGLLMAdapter` (`llm_adapters.py`) carries explicit class-level
stub markers:

```python
class StubCGLLMAdapter(MockLLMAdapter):
    IS_STUB: bool = True
    STATE_PROVENANCE: str = "deterministic_stub"
```

These markers exist so the stub cannot silently pass for a real CG
signal. `build_cg_mcp_agent(...)` reads `adapter.IS_STUB` and emits a
WARNING unless `allow_stub=True` is explicit. `MistralCGAdapter` does
**not** carry these markers, so on the real path the warning never
fires.

Semantically:
- **stub path proves wiring** — dispatcher ownership, gateway
  composition, `_execute_actions` routing, audit shape;
- **real adapter path proves runtime shape under live inference**
  but requires torch + transformers + a CG-capable checkpoint and
  is operator-validated (not repo-validated — see "Runtime Proof
  Status" below).

### Agent-side wiring: `AgenticLLMWrapper` dispatcher hook

`AgenticLLMWrapper` (`agent.py`) is the runtime host — not
`ReflectiveGenerator`, which is an internal component of the
wrapper. Dispatcher injection is:

- **optional and default-off.** The wrapper accepts
  `dispatcher=None` and an `action_type_to_tool=None` kwarg, and
  constructs fine without either. Existing callers are unchanged.
- **hooked at `_execute_actions`.** When a dispatcher IS injected,
  `_execute_actions` routes each planned action through
  `CGToolDispatcher.dispatch(...)` if and only if (a) the action's
  type is in `action_type_to_tool`, and (b) `SafetyGate` marked
  that action type as allowed this turn. Unmapped or disallowed
  actions fall through to the pre-existing placeholder path.
- **ordering-pinned.** `SafetyGate` always runs before
  `_execute_actions`; if the turn-level contract is ineligible,
  the dispatcher is never reached.

This is the only change to the agent path. No orchestrator was
added, no reasoning loop was moved, and the non-dispatcher path is
byte-identical to before.

### Default action-type → tool mapping

`cg_tool_dispatcher.py` exposes:

```python
DEFAULT_ACTION_TYPE_TO_TOOL = {
    "search":   "search",
    "compute":  "compute",
    "validate": "validate",
}
```

This is **the minimal honest default**, not a universal ontology of
all future actions/tools. It exists so `build_cg_mcp_agent(...)`
has a non-None default the runtime can actually exercise, and so
the mock gateway in `create_mock_mcp_gateway` has a matching set
of registered tools. Callers with their own ontology pass their
own mapping; nothing in the runtime hardcodes these three.

### CLI path: `inference_mistral.py --cg`

`agentic/agentic_framework/inference_mistral.py` now carries an
opt-in CG-runtime path alongside the existing Mistral API path.

| Flag                | Meaning                                                                        |
|---------------------|--------------------------------------------------------------------------------|
| `--cg`              | Opt into the CG runtime (MistralCGAdapter → dispatcher → gateway).             |
| `--cg-model`        | HuggingFace checkpoint id for `MistralCGWrapper` (default `Mistral-7B-v0.3`).  |
| `--cg-quantize`     | `4bit` / `8bit` (requires `bitsandbytes`).                                     |
| `--cg-device`       | Device-map strategy for `MistralCGWrapper` (default `auto`).                   |
| `--cg-allow-stub`   | **Dev/test only.** Falls back to `StubCGLLMAdapter` if the heavy stack is missing. Must not be described as real inference. |

Rules:
- default non-`--cg` behavior is **unchanged** — still uses
  `MistralAdapter` against the hosted API;
- `--cg` is the opt-in real runtime proof path; without
  `--cg-allow-stub` it exits with an actionable error if the
  inference stack is missing (no silent stub fallback);
- the opt-in smoke test
  (`tests/test_inference_mistral_cg_smoke.py`, gated on
  `SYMBOLU_RUN_CG_SMOKE=1`) is a **wiring** proof using the stub
  fallback; it is not a CI proof of local checkpoint inference.

### Runtime Proof Status

**Fully proved** (regression baseline on this branch):

- MCP-side enrichment path (`build_governance_enrichment_kwargs`
  → `call_tool_simple` → audit with `vritti_signal_source="real"`).
- Dispatcher ownership and per-call metadata refresh
  (`CGToolDispatcher`).
- Agent runtime wiring (`AgenticLLMWrapper._execute_actions` →
  dispatcher under `SafetyGate` ordering).
- Stub-backed end-to-end execution of the full `run()` pipeline
  into mock MCP.
- Request-boundary enrichment seam (`request_enrichment.py`
  attach/omit rules).
- Runtime factory composition (`build_cg_mcp_agent(...)`) with
  `IS_STUB` warning behavior.

**Partially proved**:

- `inference_mistral.py --cg` through a **real** local
  `MistralCGAdapter`: the wiring, factory composition and CLI
  dispatch are proved here; **real local inference** requires an
  external torch + checkpoint + GPU environment and is
  operator-validated, not repo-validated. See
  `docs/CG_RUNTIME_RUNBOOK.md` and `scripts/run_cg_gpu.sh`.

**Intentionally deferred**:

- `AuthorizationRequest`-side runtime ownership (no production
  caller holds both a `MistralCGAdapter` and an
  `AuthorizationRequest`).
- Live `SovereignProjectionResult` producer on the MCP path.
- Attachment of `sovereign_projection_metadata` on any live
  request-builder path.
- Broader runtime adoption outside this CLI (voice and other
  subsystems have not been migrated).
- Mirror retirement: `symbolu/agentic_framework/` still mirrors
  `agentic/agentic_framework/`; the final migration collapse has
  not happened.

### What this seam does NOT claim

- Not a reflective agent. `CGToolDispatcher` is a two-line compose
  step, not a reasoning loop.
- Not a pipeline bridge. Orthogonal to the Pipeline↔Authorize
  section above.
- Not an `AuthorizationRequest` enrichment path. That half of the
  seam is ready in code but has no honest production caller yet.
- Not a production-adopted runtime beyond the
  `inference_mistral.py --cg` CLI. Other callers of
  `AgenticLLMWrapper` exist in tests and demos only.

---

## Running the CG Runtime on GPU

This section is the operational companion to
`docs/CG_RUNTIME_RUNBOOK.md`. It shows the exact steps to stand up
`inference_mistral.py --cg` against a **real** `MistralCGAdapter`
(local inference through `MistralCGWrapper`) on a CUDA host, plus
the canonical helper script `scripts/run_cg_gpu.sh`.

Before this section: you already know the runtime wiring
(`RUNTIME_MCP_PATH.md`) and the CLI flags (`CG_RUNTIME_RUNBOOK.md`).
This section is just "how do I actually run it end-to-end on a GPU."

### What this runs

```
user query
    │
    ▼
python -m agentic.agentic_framework.inference_mistral --cg
    │
    ▼
create_cg_agent(...)
    │ torch+transformers+MistralCGWrapper available?
    │   yes → MistralCGAdapter (real inference)
    │   no  → (exit 1, unless --cg-allow-stub)
    ▼
build_cg_mcp_agent(adapter=..., allow_stub=False)
    │
    ▼
AgenticLLMWrapper.run(query)
    → SafetyGate → _execute_actions → CGToolDispatcher
    → SafeMCPGateway (with live entropy_result + vritti_result)
    → AgentResult
```

### Host requirements

| Requirement                                  | Why                                                |
|----------------------------------------------|----------------------------------------------------|
| CUDA-capable GPU + working `nvidia-smi`      | `MistralCGWrapper` loads weights onto GPU.         |
| VRAM: ~15 GB un-quantized / ~8 GB 8-bit / ~5 GB 4-bit | 7B-class checkpoint.                               |
| Python ≥ 3.10                                | Match framework baseline.                          |
| `torch`, `transformers>=4.40`, `accelerate`, `safetensors`, `sentencepiece` | Inference stack.          |
| `bitsandbytes`                               | Only if `--cg-quantize {4bit,8bit}` is used.       |
| `symbolu_training.training.unified.mistral_wrapper` importable | Supplies `MistralCGWrapper`.       |
| HuggingFace token (if checkpoint is gated)   | e.g. `mistralai/*` models.                         |

### Canonical helper: `scripts/run_cg_gpu.sh`

Committed at `scripts/run_cg_gpu.sh`. It:

1. verifies the GPU with `nvidia-smi`;
2. installs the inference stack (plus `bitsandbytes` if quantizing);
3. logs into HuggingFace using `HF_TOKEN` if set;
4. runs the opt-in **wiring smoke** with the stub fallback
   (`SYMBOLU_RUN_CG_SMOKE=1`) so you learn about wiring bugs
   before the GPU load starts;
5. invokes `inference_mistral.py --cg` against the real
   `MistralCGAdapter` in REPL / demo / single-query mode.

Full script listing:

```bash
#!/usr/bin/env bash
# scripts/run_cg_gpu.sh
set -euo pipefail

: "${CG_MODEL:=mistralai/Mistral-7B-v0.3}"
: "${CG_QUANTIZE:=4bit}"
: "${CG_DEVICE:=auto}"
: "${REPO_ROOT:=$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
: "${PY:=python}"

cd "$REPO_ROOT"

echo "== GPU =="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv || {
    echo "nvidia-smi not found — are you on a GPU host?"; exit 1;
}

echo "== Installing inference stack =="
$PY -m pip install --quiet --upgrade pip
$PY -m pip install --quiet \
    "torch" "transformers>=4.40" "accelerate" \
    "safetensors" "sentencepiece"
if [[ "$CG_QUANTIZE" == "4bit" || "$CG_QUANTIZE" == "8bit" ]]; then
    $PY -m pip install --quiet "bitsandbytes"
fi

if [[ -n "${HF_TOKEN:-}" ]]; then
    $PY -c "from huggingface_hub import login; login('$HF_TOKEN')"
fi

echo "== Wiring smoke (stub, no GPU work) =="
SYMBOLU_RUN_CG_SMOKE=1 $PY -m pytest -q \
    agentic/agentic_framework/tests/test_inference_mistral_cg_smoke.py

echo "== Real CG runtime: $CG_MODEL (quantize=${CG_QUANTIZE:-none}, device=$CG_DEVICE) =="
QUANT_FLAG=()
[[ -n "$CG_QUANTIZE" ]] && QUANT_FLAG=(--cg-quantize "$CG_QUANTIZE")

MODE="${1:-}"
case "$MODE" in
    demo)
        $PY -m agentic.agentic_framework.inference_mistral --cg \
            --cg-model "$CG_MODEL" "${QUANT_FLAG[@]}" \
            --cg-device "$CG_DEVICE" --demo --verbose ;;
    ""|interactive)
        $PY -m agentic.agentic_framework.inference_mistral --cg \
            --cg-model "$CG_MODEL" "${QUANT_FLAG[@]}" \
            --cg-device "$CG_DEVICE" --verbose ;;
    *)
        $PY -m agentic.agentic_framework.inference_mistral --cg \
            --cg-model "$CG_MODEL" "${QUANT_FLAG[@]}" \
            --cg-device "$CG_DEVICE" --verbose --query "$MODE" ;;
esac
```

### Steps to run

**1. Prepare the GPU host**

```bash
git clone <repo-url>
cd symbolu
git checkout claude/add-cg-metadata-enrichment-5J7il
nvidia-smi            # confirm GPU + driver
```

**2. (Optional) Create a fresh Python env**

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
```

**3. Make sure `symbolu_training` is importable**

The CG adapter depends on `MistralCGWrapper` from
`symbolu_training.training.unified.mistral_wrapper`. Install the
`symbolu` / `symbolu_training` package into the active env, or run
from the repo root so it's on `PYTHONPATH`.

**4. Set HuggingFace auth**

```bash
export HF_TOKEN=hf_xxx
```

Required only if the checkpoint is gated (Mistral's official
checkpoints are).

**5. Run the helper script**

```bash
chmod +x scripts/run_cg_gpu.sh

# Interactive REPL, 4-bit quantized (default)
./scripts/run_cg_gpu.sh

# Multi-turn demo
./scripts/run_cg_gpu.sh demo

# Single query
./scripts/run_cg_gpu.sh "Compare self-attention vs linear attention briefly."

# 8-bit
CG_QUANTIZE=8bit ./scripts/run_cg_gpu.sh demo

# Un-quantized (needs ~15 GB VRAM)
CG_QUANTIZE= ./scripts/run_cg_gpu.sh

# Different checkpoint
CG_MODEL=mistralai/Mistral-7B-Instruct-v0.3 ./scripts/run_cg_gpu.sh demo
```

**6. What you should see**

- `== GPU ==` banner lists your card.
- Dependency install completes quietly.
- `== Wiring smoke (stub, no GPU work) ==` reports **1 passed**. If
  this fails, stop — it is a code/wiring bug, not an environment
  bug, and running the real model will not fix it.
- `== Real CG runtime: … ==` banner, then `MistralCGWrapper` loads
  the checkpoint (first run downloads weights, subsequent runs use
  HF cache).
- Each turn prints the `AgenticLLMWrapper` result with coherence
  metrics and (with `--verbose`) the full pipeline details. Under
  the hood every dispatched action type routes through
  `CGToolDispatcher` → `SafeMCPGateway` with live CG-derived
  `entropy_result` + `vritti_result`.

### Running without the helper script

The helper is only a convenience. You can run the CLI directly:

```bash
python -m agentic.agentic_framework.inference_mistral --cg \
    --cg-model mistralai/Mistral-7B-v0.3 \
    --cg-quantize 4bit \
    --cg-device auto \
    --verbose \
    --query "Your question here."
```

### Troubleshooting

| Symptom                                                     | Cause / fix                                                                              |
|-------------------------------------------------------------|------------------------------------------------------------------------------------------|
| `nvidia-smi not found`                                      | Not a CUDA host. Use a GPU VM or fall back to `--cg-allow-stub` (dev only).              |
| `ImportError: MistralCGWrapper`                             | `symbolu_training` not installed / not on `PYTHONPATH`.                                  |
| `401 Unauthorized` from HuggingFace                         | Set `HF_TOKEN`; for gated models, accept the license on the HF model card first.         |
| `OutOfMemoryError` at model load                            | Use `CG_QUANTIZE=4bit` (or `8bit`), or pick a smaller checkpoint.                        |
| `bitsandbytes` install fails                                | Needs matching CUDA. Skip quantization (`CG_QUANTIZE=`) to bypass.                       |
| Wiring smoke passes but real run fails                      | Environment issue (CUDA / checkpoint / token). Code path is fine.                        |
| Wiring smoke fails                                          | Code bug on the branch. Do **not** proceed to real-inference run.                        |
| Real run silently uses the stub                             | Can't happen without `--cg-allow-stub`. CLI exits with actionable error instead.         |

### What this proves when it runs green

- The full `inference_mistral.py --cg` path is runnable on real
  hardware against a real CG-capable checkpoint.
- `adapter.last_cg_metadata` is populated from live inference, not
  a fixture — every MCP tool dispatched during the session carries
  real CG-derived `entropy_result` + `vritti_result` into
  governance.
- The substitution seam from `build_cg_mcp_agent(...)` holds at the
  boundary between stub and real adapters without any other wiring
  change.

### What this does NOT prove

- Does not prove `sovereign_projection_metadata` attachment (still
  deferred — no producer wired on this path).
- Does not prove `AuthorizationRequest`-side enrichment (still
  deferred — no honest caller).
- Does not constitute a correctness evaluation of the governance
  decisions themselves; it only pins the **wiring and data-flow**
  end to end.

---

## Test Evidence

### Coverage Summary

| Test Suite | Tests | Focus | Track |
|------------|-------|-------|-------|
| `test_phase_s2_integration.py` | 54 | S2 adapters, bounded effects, backward compat | Sovereign |
| `test_phase_s3_integration.py` | 32 | S3 diagnostics, bridge contracts, torch isolation | Sovereign |
| `test_phase_s4_integration.py` | 67 | S4 anomaly/prior/telemetry, adapters, fallbacks | Sovereign |
| `test_activation_e2e.py` | 8 | True E2E `authorize()` proving S3/S4 activation | Sovereign |
| `test_jepa_governance.py` | ~100+ | JEPA composite, regimes, governance service integration | Sovereign |
| `test_phase_c4_predictive_and_counterfactual.py` | 45 | C4 adapter contracts, P35/P36/P37, counterfactual bridge | Core |
| `test_closure_e2e_authorize.py` | 31 | E2E authorize proving C2/C3/C4, aggregate cap, generation gate | Core |
| `test_policy_engine.py` | 31 | Policy engine rules, thresholds, boundary conditions | Policy |
| `test_policy_p0.py` | 45 | Schema, registry, backward compat, layer visibility | Policy |
| `test_policy_p1.py` | 49 | Service wrapper, audit logging, interaction mode | Policy |
| `test_policy_p2.py` | 47 | Simulation paths, comparison, threshold parameterization | Policy |
| `test_policy_p3.py` | 59 | Lifecycle transitions, activation/rollback, E2E output proof | Policy |
| `test_policy_p4.py` | 58 | Control-plane queries, health report, tenant passthrough | Policy |
| `test_session_policy.py` | 20 | Session stability, grounding, reflection | Policy |
| `test_trading_formula_guardrails.py` | 22 | Trading risk thresholds, boundary conditions | Policy |
| `test_phase15_interaction_modes.py` | 35 | Interaction mode resolution, override precedence | Policy |
| `tests/ontology_router/test_ontological_layer_canonical.py` | 13 | O1 canonical enum, identity, AST, router compat | Ontology |
| `tests/unit/ontology/test_ontology_safety.py` | 24 | O2 safety validators, boundary conditions | Ontology |
| `tests/unit/ontology/test_ontology_adapter.py` | 34 | O2 encoding/similarity adapter contracts | Ontology |
| `tests/unit/ontology/test_phase4a_adapter.py` | 22 | O3 varna lookup adapter, fail-closed | Ontology |
| `tests/unit/ontology/test_ontology_balance.py` | 21 | O3 balance adapter, resolution contract | Ontology |
| `tests/unit/ontology/test_ontology_governance_consumer.py` | 30 | O4 E2E governance consumer, penalty, escalation | Ontology |
| `tests/test_s1_gcc_boundary_enforcement.py` | 19 | S1 GCC guard at real boundaries, opaque IDs, ledger invariants | Safety |
| `tests/test_s2_plasticity_gate_integration.py` | 28 | S2 plasticity adapter contract, bounded effects, E2E authorize | Safety |
| `tests/test_s3_readiness_integration.py` | 31 | S3 readiness adapter, multi-criterion, cooldown truth, E2E authorize | Safety |
| `tests/test_s4_policy_engine_integration.py` | 22 | S4 policy engine adapter, allow/deny, blackout, rate limit, E2E authorize | Safety |
| `tests/test_s5_rollback_monitor_integration.py` | 27 | S5 rollback adapter, watch lifecycle, signal snapshot, E2E authorize | Safety |

### What the Sovereign E2E Tests Prove

The `test_activation_e2e.py` tests are the definitive proof that S3/S4
signals are no longer dormant:

1. **Data reaches audit** — Calling `authorize()` with projection metadata
   produces non-None `sovereign_diagnostics`, `sovereign_guna_anomalies`,
   and `sovereign_governor_telemetry` on the audit event.

2. **Behavioral effects are measurable** — Guna collapse reduces
   `confidence_score` relative to a clean baseline.

3. **Aggregate cap is enforced** — The penalty cap of 0.20 is verified
   against raw penalty sums that could exceed it.

4. **Absence is safe** — Without metadata, all fields default to None
   and governance proceeds normally.

### What the Core E2E Tests Prove

The `test_closure_e2e_authorize.py` tests prove C1-C4 signals are live:

1. **C2 wiring** — `authorize()` populates `core_coherence` on the audit
   event with coherence and drift data. Low coherence measurably reduces
   confidence. High drift produces escalation bias.

2. **C3 wiring** — `authorize()` populates `ucf_signal` on the audit event.
   Critical UCF measurably reduces confidence with correct provenance.

3. **C4 wiring** — `authorize()` populates `predictive_signals` on the
   audit event. High drift risk measurably reduces confidence.

4. **Combined stacking** — When C2+C3+C4 all fire, penalties stack correctly.
   `counterfactual` is always None on live decisions.

5. **Aggregate cap with all sources** — When all six penalty sources fire
   (entropy + insight + guna + C2 + C3 + C4), the cap holds at 0.20 and
   confidence never goes below 0.0.

6. **Generation gate behavior** — 14 tests prove `_is_generative_action()`
   classification, `_check_generation_gate()` logic for all three states
   (ENABLED/DISABLED/UNSEALED), and full `authorize()` gate enforcement.

7. **Drift overlap documentation** — Tests verify inline documentation
   strings exist in both `governance_service.py` and
   `predictive_signals_adapter.py`.

### What the Ontology Tests Prove

The ontology test suite (144 tests across 6 files) proves:

1. **O1 canonical source** — `OntologicalLayer` is defined in exactly one
   place. All import paths (`layers`, `projection`, `router`) resolve to
   the same class object. AST verification confirms no independent
   definitions. Router and projection behavior is unchanged.

2. **O2 safety validators** — `check_no_forbidden_modules()` and
   `check_no_timestamp_words()` correctly detect violations and pass
   clean input. Boundary conditions tested.

3. **O2/O3 adapter contracts** — All three adapter functions
   (`resolve_ontology_encoding`, `resolve_ontology_similarity`,
   `resolve_ontology_balance`) return frozen Resolution dataclasses with
   `available`, `source_detail` provenance. Fail-closed on errors.

4. **O3 varna lookup** — `resolve_varna_lookup()` returns correct
   interaction data for valid varna-layer pairs. Returns
   `available=False` for unknown pairs. Crash-safe.

5. **O4 governance consumer** — `OntologyBalanceGovernanceSignal` is
   frozen with correct defaults. `_resolve_ontology_balance_signal()`
   produces bounded penalties (max 0.05), escalation bias below 0.20.
   Six E2E tests call `GovernanceService().authorize()` proving: audit
   provenance, audit event field populated, low balance reduces
   confidence, unavailable preserves baseline, critical balance triggers
   escalation, adapter crash survival.

### What the Safety Tests Prove

The safety test suite (127 tests across 5 files) proves:

1. **S1 boundary enforcement** — GCC `assert_non_expressive()` fires at
   real constrained boundaries (ontological router, phase layer map). Ledger
   `assert_ledger_entry_valid()` fires at real write boundaries. Opaque IDs
   (artifact IDs, span IDs) pass validation. Expressive content is still
   blocked.

2. **S2 plasticity as governance signal** — `resolve_plasticity_signal()`
   returns frozen `PlasticityResolution` with bounded penalty (max 0.04).
   Low plasticity reduces confidence. Critical plasticity triggers escalation.
   Three E2E tests call `GovernanceService.authorize()` proving: penalty
   measurably reduces confidence, audit fields populated, fail-closed on
   absent coherence.

3. **S3 readiness as governance signal** — `resolve_readiness_signal()`
   returns frozen `ReadinessResolution` with bounded penalty (max 0.03).
   NOT_READY status reduces confidence and triggers escalation. DEGRADED
   reduces confidence without escalation. READY has zero penalty. Cooldown
   is honestly disabled and tested. Four E2E tests through
   `GovernanceService.authorize()`.

4. **S4 policy engine as pre-authorize guard** — `resolve_policy_check()`
   returns frozen `AgentPolicyResolution`. Denied actions produce hard deny
   overriding governance decision. Allowlist blocks unlisted actions.
   Blackout windows block by time. Rate limiting blocks after max. Per-agent
   overrides work. Five E2E tests through `GovernanceService.authorize()`.

5. **S5 rollback watch as lifecycle-preparatory** — `resolve_rollback_snapshot()`
   returns frozen `RollbackSnapshotResolution`. Pre-action signals captured
   correctly. Monitor registration creates active watches. External callers
   can detect degradation via `check()`. Five E2E tests through
   `GovernanceService.authorize()` proving: no-monitor baseline unchanged,
   snapshot captured in audit, watches registered, governance decision
   unaffected by monitor presence, full lifecycle (authorize → external check).

6. **Fail-safe/fail-closed preserved** — All adapters return safe defaults
   when their upstream dependencies are unavailable. No safety signal
   crashes the governance path. Policy engine absence means all-allowed.
   Rollback monitor absence means no snapshot.

7. **Regression safety** — Each phase includes regression tests verifying
   prior behavior is unchanged when the new safety signal is absent.

### What Is NOT Tested

- No tests verify that a specific production caller always supplies
  projection metadata (this depends on deployment configuration)
- No tests cover cross-request `previous_bhava` tracking (not implemented)
- No tests cover the full model→bridge→governance path with live PyTorch
  model inference (tests use synthetic metadata dicts)
- No tests invoke the counterfactual bridge during `authorize()` (by design
  — it is replay/simulation-only)
- No tests cover real core pipeline output objects (tests use duck-typed
  synthetic fixtures)
- No tests verify ontology encoding/similarity adapters as governance
  consumers (O2 adapters are available but have no governance wiring)
- No tests cover balance trends across multiple requests (stateless)
- No tests verify that the 10D regex patterns produce meaningful
  encodings for all possible action types (pattern coverage is untested)

### What Is NOT Tested (Safety)

- No tests verify full post-action rollback execution (no execution lifecycle)
- No tests cover cross-request readiness cooldown (disabled by design)
- No tests cover `safety_bounds.py` activation (dormant, awaiting payload model)
- No tests verify GCC enforcement at every possible constrained boundary
  (only the boundaries wired in S1 are tested)
- No boundary-condition tests for opaque ID length exactly at 64 chars
- No tests cover concurrent policy engine access (thread-safe by lock, untested)

### What the Policy Tests Prove

The policy test suite (366 tests across 9 files) proves:

1. **Profile foundation** — `DomainProfile` dict-compatible access, registry
   CRUD, builtin fallback, JSON round-trip, immutability.

2. **Runtime policy engines** — All 9 policy rules produce correct flags for
   boundary conditions. Stability classification, grounding triggers, and
   interaction mode resolution verified with exact value assertions.

3. **Parameterization** — 19 thresholds produce identical behavior to pre-P2
   hardcoded values when using defaults. Custom thresholds measurably change
   policy output.

4. **Simulation correctness** — `simulate_policy()` with custom profile changes
   `needs_grounding`. `compare_policy()` produces correct `changed_flags` with
   verified flag value directions (baseline `True`, candidate `False`).

5. **Lifecycle state machine** — All valid/invalid transitions tested. Activation
   updates registry. Rollback restores previous profile. Candidate cleared after
   activation. Approval payload has correct structure and values.

6. **End-to-end lifecycle → policy output proof** — Activating a custom profile
   changes `compute_policy_flags()` output (verified on `needs_grounding` and
   `stability_status`). Rolling back reverts the output to baseline. Proven both
   through direct engine calls and through `PolicyService.compute_policy()`.

7. **Control-plane queries** — System snapshot returns all domains. Health report
   detects stale candidates and fallback domains. Deployment/approval/simulation
   history queries work with filtered results. Tenant_id passes through.

8. **Backward compatibility** — Each phase (P1-P4) includes regression tests
   verifying prior phase exports, registry behavior, and policy engine output
   remain unchanged.

### What Is NOT Tested (Policy)

- No tests verify lifecycle state persistence (state is in-memory only)
- No tests verify approval workflow execution (payload-only)
- No tests cover concurrent lifecycle operations (single-threaded only)
- No boundary-condition tests at exact threshold values (e.g., 0.5499 vs 0.5500)
- No tests verify that specific production callers use `PolicyService` vs direct
  `compute_policy_flags()` (this depends on consumer code)

---

## File Reference

### Sovereign Integration Files (by phase)

| File | Phase | PyTorch | Purpose |
|------|-------|---------|---------|
| `agentic_framework/sovereign_bridge.py` | S1–S4 | No | Bridge normalization layer |
| `sovereign/inference_bridge.py` | S1–S4 | Minimal | 128D→32D projection + metadata |
| `sovereign_diagnostics.py` | S3 | No | Diagnostic normalization |
| `sovereign_guna_anomaly.py` | S4 | No | Guna anomaly detection |
| `sovereign_bhava_priors.py` | S4 | No | Bhava transition priors |
| `agentic_framework/signal_adapters/vritti_adapter.py` | S1 | No | Vritti resolution |
| `agentic_framework/signal_adapters/entropy_adapter.py` | S1 | No | Entropy resolution |
| `agentic_framework/signal_adapters/sovereign_health_adapter.py` | S2 | No | Health resolution |
| `agentic_framework/signal_adapters/insight_adapter.py` | S2 | No | Insight resolution |
| `agentic_framework/signal_adapters/guna_anomaly_adapter.py` | S4 | No | Anomaly penalty/bias |
| `agentic_framework/jepa_governance.py` | S1+patch | No | JEPA composite + regime + projection_metadata |

### Core Integration Files (by phase)

| File | Phase | numpy | Purpose |
|------|-------|-------|---------|
| `agentic_framework/signal_adapters/generation_gate.py` | C1/C3 | No | One-time seal singleton |
| `agentic_framework/signal_adapters/coherence_state_adapter.py` | C2 | No | Coherence/drift signals |
| `agentic_framework/signal_adapters/ucf_adapter.py` | C3 | No | UCF consciousness signals |
| `agentic_framework/signal_adapters/predictive_signals_adapter.py` | C4 | No | P35+P36+P37 signals |
| `agentic_framework/signal_adapters/counterfactual_bridge.py` | C4 | No | Replay/simulation bridge |

### Policy Track Files (by phase)

| File | Phase | Purpose |
|------|-------|---------|
| `policy/profile_schema.py` | P0 | `DomainProfile`, `ProfileRegistry`, singleton |
| `policy/domain_profiles.py` | P0 | `get_domain_profile()` public API |
| `policy/layer_visibility_policy.py` | P0 | RBAC `ExposureGate`, wired into governance |
| `policy/governance_binding.py` | P0 | Provisional facade (dormant) |
| `policy/preferences.py` | P0 | Provisional facade (dormant) |
| `policy/licensing/__init__.py` | P0 | Provisional facade (dormant) |
| `policy/policy_engine.py` | P0+P2 | `compute_policy_flags()` — 9 rules, parameterized thresholds |
| `policy/interaction_modes.py` | P0 | `resolve_interaction_mode()` cascade |
| `policy/session_policy.py` | P0+P2 | `compute_session_policy_flags()` — 4 rules, parameterized |
| `policy/trading_guardrail_engine.py` | P0+P2 | `compute_trading_guardrails()` — 3 risk rules, parameterized |
| `policy/insight_window_gating.py` | P0 | Insight window (policy-engine path), canonical v1.0 |
| `policy/insight_window/__init__.py` | P0 | Insight window (pipeline-native P32 path) |
| `policy/policy_service.py` | P1+P3+P4 | `PolicyService` — structured wrapper + audit + lifecycle + CP |
| `policy/policy_simulation.py` | P2 | `simulate_policy()`, `compare_policy()`, session/trading variants |
| `policy/policy_lifecycle.py` | P3 | `PolicyLifecycleManager`, `DeploymentRecord`, `ProfileStatus` |
| `policy/policy_control_plane.py` | P4 | `PolicyControlPlane`, `PolicyHealthReport`, `PolicyDomainStatus` |
| `policy/__init__.py` | P0–P4 | Public exports, version 1.5.0 |

### Ontology Integration Files (by phase)

| File | Phase | Heavy deps | Purpose |
|------|-------|-----------|---------|
| `ontology/layers/ontology_layer.py` | O1 | No | Canonical `OntologicalLayer` enum (12 members) |
| `ontology/projection/api_models.py` | O1 | No | Re-exports canonical enum (local def removed) |
| `ontology/router/ontological_router_r1.py` | O1 | No | Re-exports canonical enum (local def removed) |
| `ontology/safety.py` | O2 | No | Portable safety validators |
| `ontology/backbone/encoder.py` | O2 (upstream) | No | Rule-based text → 10D encoding |
| `ontology/backbone/similarity.py` | O2 (upstream) | No | 10D vector similarity |
| `ontology/backbone/mirror_pairs.py` | O3 (upstream) | No | 5 mirror pairs, `compute_balance()` |
| `ontology/phase4a/lookup.py` | O3 (upstream) | No | Varna-layer lookup against JSON substrate |
| `agentic_framework/signal_adapters/ontology_adapter.py` | O2+O3 | No | Encoding, similarity, balance adapters |
| `agentic_framework/signal_adapters/phase4a_adapter.py` | O3 | No | Varna lookup adapter |

### Safety Integration Files (by phase)

| File | Phase | Purpose |
|------|-------|---------|
| `safety/gcc_runtime_guard.py` | S1 | Runtime GCC enforcement + opaque ID support |
| `safety/gcc_ledger_invariant.py` | S1 | Runtime ledger invariant enforcement + opaque ID support |
| `safety/gcc_static_scanner.py` | Pre-S0 | CI/build-time GCC enforcement (not runtime) |
| `safety/governance_patterns/plasticity_gate.py` | S2 | Sigmoid permission-to-act gate |
| `safety/governance_patterns/readiness_checker.py` | S3 | Multi-criterion readiness gate |
| `safety/governance_patterns/policy_engine.py` | S4 | Per-agent action policy (allow/deny/blackout/rate-limit) |
| `safety/governance_patterns/rollback_monitor.py` | S5 | Post-action signal degradation watcher |
| `safety/governance_patterns/safety_bounds.py` | — | Dormant (awaits action-magnitude payload model) |
| `safety/governance_patterns/approval_manager.py` | S0 | Deprecated (superseded by approval_workflow.py) |
| `agentic_framework/signal_adapters/plasticity_adapter.py` | S2 | Plasticity → bounded governance signal |
| `agentic_framework/signal_adapters/readiness_adapter.py` | S3 | Readiness → bounded governance signal |
| `agentic_framework/signal_adapters/policy_engine_adapter.py` | S4 | Policy check → hard deny resolution |
| `agentic_framework/signal_adapters/rollback_adapter.py` | S5 | Pre-action snapshot → audit-visible watch |

### Shared Files (all tracks)

| File | Phases | Purpose |
|------|--------|---------|
| `agentic_framework/governance_models.py` | S1+patch, C4, O4, S2–S5 safety | Request/response models, audit event fields |
| `agentic_framework/governance_service.py` | S1–S4+patch, C1–C4+closure, P0+P1, O4, S2–S5 safety | Decision engine, penalty cap, layer visibility, policy audit, ontology balance, safety signals |
| `agentic_framework/signal_adapters/__init__.py` | S1–S4, C1–C4, O2–O3, S2–S5 safety | Adapter exports |

### Test Files

| File | Tests | Focus | Track |
|------|-------|-------|-------|
| `tests/test_phase_s2_integration.py` | 54 | S2 unit + integration | Sovereign |
| `tests/test_phase_s3_integration.py` | 32 | S3 unit + integration | Sovereign |
| `tests/test_phase_s4_integration.py` | 67 | S4 unit + integration | Sovereign |
| `tests/test_activation_e2e.py` | 8 | E2E sovereign activation proof | Sovereign |
| `tests/unit/core/test_phase_c4_predictive_and_counterfactual.py` | 45 | C4 adapter + bridge contracts | Core |
| `tests/unit/core/test_closure_e2e_authorize.py` | 31 | E2E core wiring + gate + cap | Core |
| `tests/unit/policy/test_policy_engine.py` | ~70 | Policy engine rules, boundary conditions | Policy |
| `tests/unit/policy/test_policy_p0.py` | ~35 | Schema, registry, layer visibility, facades | Policy |
| `tests/unit/policy/test_policy_p1.py` | ~40 | Service wrapper, audit, interaction mode | Policy |
| `tests/unit/policy/test_policy_p2.py` | ~50 | Simulation, comparison, parameterization | Policy |
| `tests/unit/policy/test_policy_p3.py` | ~59 | Lifecycle, activation/rollback, E2E output proof | Policy |
| `tests/unit/policy/test_policy_p4.py` | ~58 | Control-plane, health, tenant passthrough | Policy |
| `tests/unit/policy/test_session_policy.py` | ~18 | Session stability, grounding | Policy |
| `tests/unit/policy/test_trading_formula_guardrails.py` | ~22 | Trading risk thresholds | Policy |
| `tests/unit/policy/test_phase15_interaction_modes.py` | ~24 | Interaction mode resolution | Policy |
| `tests/ontology_router/test_ontological_layer_canonical.py` | 13 | O1 canonical enum, identity, AST | Ontology |
| `tests/unit/ontology/test_ontology_safety.py` | 24 | O2 safety validators | Ontology |
| `tests/unit/ontology/test_ontology_adapter.py` | 34 | O2 encoding/similarity adapters | Ontology |
| `tests/unit/ontology/test_phase4a_adapter.py` | 22 | O3 varna lookup adapter | Ontology |
| `tests/unit/ontology/test_ontology_balance.py` | 21 | O3 balance adapter | Ontology |
| `tests/unit/ontology/test_ontology_governance_consumer.py` | 30 | O4 E2E governance consumer | Ontology |
| `tests/test_s1_gcc_boundary_enforcement.py` | 19 | S1 GCC+ledger enforcement | Safety |
| `tests/test_s2_plasticity_gate_integration.py` | 28 | S2 plasticity integration | Safety |
| `tests/test_s3_readiness_integration.py` | 31 | S3 readiness integration | Safety |
| `tests/test_s4_policy_engine_integration.py` | 22 | S4 policy engine integration | Safety |
| `tests/test_s5_rollback_monitor_integration.py` | 27 | S5 rollback monitor integration | Safety |
