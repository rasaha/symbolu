# Sovereign & Core Integration Architecture

> **Version:** 2.0.0 | **Updated:** 2026-04-04
>
> This document describes the two completed integration tracks that connect
> external signal sources to the agentic governance runtime:
>
> - **Sovereign track (S1–S4 + activation patch):** Bridges sovereign model
>   signals (entropy, health, insight, diagnostics, guna anomalies, bhava
>   priors, governor telemetry) into governance.
> - **Core track (C1–C4 + closure patch):** Bridges core pipeline signals
>   (coherence state, UCF consciousness, generation gate, predictive drift,
>   identity resonance, adaptive continuity, counterfactual sandbox) into
>   governance.
>
> Both tracks follow the same **bridge-first, never-direct** architecture
> principle and the same signal adapter pattern (frozen Resolution, pure
> function, fail-closed, bounded penalty, stricter-only).
>
> For the full governance architecture (Layers 1–8, domain policy, shadow AI,
> etc.), see [`docs/governance/AGENTIC_ARCHITECTURE.md`](../docs/governance/AGENTIC_ARCHITECTURE.md).
>
> This document focuses specifically on how sovereign and core pipeline signals
> reach the agentic governance runtime, what is live, what is conditional,
> what is audit-only, what is replay/simulation-only, and what remains future
> work.

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
  │  Core bridges (not adapters — isolated from live path):         │
  │    counterfactual_bridge.py      (C4) — replay/simulation only  │
  │                                                                 │
  │  Core singletons:                                               │
  │    generation_gate.py            (C3) — one-time seal at boot   │
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
  │    - audit metadata enrichment (all tracks)                     │
  │    - fail-safe: all resolution wraps try/except                 │
  └─────────────────────────────────────────────────────────────────┘
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
| Temporal trajectory prediction | JEPA forecasting future semantic state | Not implemented |
| `previous_bhava` tracking | Cross-request bhava transition history | Hardcoded to `None` |
| Deeper sovereign model internals | Per-layer attention weights, gradient norms, etc. | Intentionally excluded |
| Live counterfactual analysis | Real-time what-if during authorize | Intentionally deferred |

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
| **Aggregate penalty cap** | **Caps total from all adapters** | **max 0.20** | Both | Patch |

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

### Aggregate Cap

The raw sum of all adapter penalties could theoretically reach 0.50. The
aggregate cap ensures the total penalty from all sources never exceeds 0.20:

```python
sovereign_penalty = min(
    0.20,
    entropy_resolution.confidence_penalty         # max 0.15 (S1)
    + insight_resolution.confidence_penalty        # max 0.10 (S2)
    + guna_anomaly_resolution.confidence_penalty   # max 0.05 (S4)
    + core_coherence_resolution.confidence_penalty # max 0.10 (C2)
    + ucf_resolution.confidence_penalty            # max 0.05 (C3)
    + predictive_resolution.confidence_penalty,    # max 0.05 (C4)
)
```

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

### Shared Files (both tracks)

| File | Phases | Purpose |
|------|--------|---------|
| `agentic_framework/governance_models.py` | S1+patch, C4 | Request/response models, audit event fields |
| `agentic_framework/governance_service.py` | S1–S4+patch, C1–C4+closure | Decision engine, penalty cap, all resolver wiring |
| `agentic_framework/signal_adapters/__init__.py` | S1–S4, C1–C4 | Adapter exports |

### Test Files

| File | Tests | Focus | Track |
|------|-------|-------|-------|
| `tests/test_phase_s2_integration.py` | 54 | S2 unit + integration | Sovereign |
| `tests/test_phase_s3_integration.py` | 32 | S3 unit + integration | Sovereign |
| `tests/test_phase_s4_integration.py` | 67 | S4 unit + integration | Sovereign |
| `tests/test_activation_e2e.py` | 8 | E2E sovereign activation proof | Sovereign |
| `tests/unit/core/test_phase_c4_predictive_and_counterfactual.py` | 45 | C4 adapter + bridge contracts | Core |
| `tests/unit/core/test_closure_e2e_authorize.py` | 31 | E2E core wiring + gate + cap | Core |
