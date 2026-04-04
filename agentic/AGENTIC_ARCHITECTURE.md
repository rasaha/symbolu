# Sovereign Integration Architecture

> **Version:** 1.0.0 | **Updated:** 2026-04-04
>
> This document describes the sovereign-to-governance integration as implemented
> across phases S1–S4 and the activation patch.
>
> For the full governance architecture (Layers 1–8, domain policy, shadow AI,
> etc.), see [`docs/governance/AGENTIC_ARCHITECTURE.md`](../docs/governance/AGENTIC_ARCHITECTURE.md).
>
> This document focuses specifically on how sovereign model signals reach the
> agentic governance runtime, what is live, what is conditional, and what
> remains future work.

---

## Architecture Principle: Bridge-First, Never Direct

Governance does **not** directly import PyTorch-heavy sovereign model internals.
All sovereign signals reach governance through a layered bridge architecture:

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  SOVEREIGN MODEL INTERNALS (PyTorch-heavy)                      │
  │  sovereign/reasoning_kernel.py, observer.py, guna.py, etc.      │
  │  ── These are NEVER imported by the governance runtime ──       │
  └──────────────────────────┬──────────────────────────────────────┘
                             │
                             │  128D → 32D projection
                             │  (sovereign/inference_bridge.py)
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  INFERENCE BRIDGE LAYER                                         │
  │  sovereign/inference_bridge.py                                  │
  │                                                                 │
  │  ProjectionMetadata (plain dict):                               │
  │    reasoning_diagnostics  (S3)  — kernel diagnostic summary     │
  │    guna_anomalies         (S4)  — temporal guna anomaly flags   │
  │    governor_telemetry     (S4)  — PID governor telemetry        │
  └──────────────────────────┬──────────────────────────────────────┘
                             │
                             │  ProjectionMetadata dict
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  PURE-PYTHON RUNTIME-SAFE MODULES (no torch dependency)         │
  │                                                                 │
  │  sovereign_diagnostics.py   (S3)  — diagnostic normalization    │
  │  sovereign_guna_anomaly.py  (S4)  — guna anomaly detection      │
  │  sovereign_bhava_priors.py  (S4)  — bhava transition matrix     │
  └──────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  SOVEREIGN BRIDGE (agentic_framework/sovereign_bridge.py)       │
  │                                                                 │
  │  Normalizes raw sovereign data into governance-typed structs:   │
  │    SovereignDiagnosticContext  (S3)                              │
  │    GunaAnomalyContext          (S4)                              │
  │    governor_telemetry_from_projection()  (S4)                   │
  │    bhava_transition_from_diagnostics()   (S4)                   │
  │    signals_from_sovereign_state()        (S1)                   │
  │    coherence_from_sovereign_state()      (S1)                   │
  └──────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  SIGNAL ADAPTERS (agentic_framework/signal_adapters/)           │
  │                                                                 │
  │  Convert bridge outputs into bounded governance effects:        │
  │    sovereign_health_adapter.py   (S2) — health/entropy signals  │
  │    insight_adapter.py            (S2) — insight gate resolution  │
  │    guna_anomaly_adapter.py       (S4) — anomaly penalty/bias    │
  │    vritti_adapter.py             (S1) — vritti signal resolution │
  │    entropy_adapter.py            (S1) — entropy resolution      │
  │                                                                 │
  │  Every adapter produces:                                        │
  │    - bounded confidence penalty (non-negative, capped)          │
  │    - optional escalation bias (stricter-only)                   │
  │    - reason codes for audit                                     │
  │    - safe defaults on failure                                   │
  └──────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  GOVERNANCE SERVICE (agentic_framework/governance_service.py)   │
  │                                                                 │
  │  Consumes adapter outputs at decision time:                     │
  │    - confidence adjustments (bounded, capped aggregate)         │
  │    - escalation overrides (stricter-only)                       │
  │    - audit metadata enrichment                                  │
  │    - fail-safe: all sovereign resolution wraps try/except       │
  └─────────────────────────────────────────────────────────────────┘
```

**Key boundary:** The `sovereign/` package (with its `__init__.py` that eagerly
imports torch-heavy modules) is never imported by anything in the governance
runtime path. Pure-Python runtime-safe modules (`sovereign_diagnostics.py`,
`sovereign_guna_anomaly.py`, `sovereign_bhava_priors.py`) live as siblings
outside the `sovereign/` package to avoid the torch import chain.

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

Not all sovereign signals are always active. The system has three activation
tiers, and the documentation must not conflate them.

### Tier 1: Live and Default-On (Always Active)

These signals are computed on every `GovernanceService.authorize()` call,
regardless of whether sovereign projection metadata is present.

| Signal | Phase | Effect |
|--------|-------|--------|
| Vritti resolution (real or fallback) | S1 | Governs JEPA composite vritti axis |
| Entropy resolution | S1 | Bounded confidence penalty (max 0.15) |
| Sovereign telemetry in audit | S1 | Audit enrichment |
| Sovereign health resolution | S2 | Audit enrichment |
| Insight gate resolution | S2 | Bounded confidence penalty (max 0.10) |

When upstream signals are unavailable (no `chitta_vritti` data, no entropy
source), these adapters fall back to approximation or neutral defaults.
Audit metadata records whether real or fallback sources were used.

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

### Tier 3: Future / Not Yet Wired

| Signal | Description | Status |
|--------|-------------|--------|
| Temporal trajectory prediction | JEPA forecasting future semantic state | Not implemented |
| `previous_bhava` tracking | Cross-request bhava transition history | Hardcoded to `None` |
| Deeper sovereign model internals | Per-layer attention weights, gradient norms, etc. | Intentionally excluded |

---

## Behavior-Affecting vs Audit-Only

Sovereign signals have two distinct roles in governance. The documentation
must not conflate signals that change decisions with signals that only
enrich the audit trail.

### Behavior-Affecting Signals

These signals can change the governance decision (confidence, escalation,
execution mode). All effects are **stricter-only** — they can only reduce
confidence or increase escalation, never relax governance.

| Signal | Effect | Bound | Phase |
|--------|--------|-------|-------|
| Entropy penalty | Reduces confidence | max 0.15 | S1 |
| Insight penalty | Reduces confidence | max 0.10 | S2 |
| Guna collapse penalty | Reduces confidence | 0.03 | S4 |
| Guna oscillation penalty | Reduces confidence | 0.02 | S4 |
| Guna collapse escalation | Bumps escalation +1 | Single step | S4 |
| Mauna active | Adds caution reason code | Informational | S3 |
| **Aggregate sovereign penalty** | **Caps total penalty** | **max 0.20** | Activation patch |

### Audit-Only Signals

These signals appear in `AuditEvent` fields for forensic analysis, replay,
and human review. They do **not** change any governance decision.

| Signal | Audit Field | Phase |
|--------|-------------|-------|
| Sovereign telemetry | `sovereign_telemetry` | S1 |
| Sovereign health snapshot | `sovereign_health` | S2 |
| Sovereign insight snapshot | `sovereign_insight` | S2 |
| Reasoning diagnostic context | `sovereign_diagnostics` | S3 |
| OPB lock/unlock tracking | within `sovereign_diagnostics` | S3 |
| Vritti rejection flag | within `sovereign_diagnostics` | S3 |
| Bhava transition audit | `sovereign_bhava_transition` | S4 |
| Governor telemetry | `sovereign_governor_telemetry` | S4 |
| Guna anomaly snapshot | `sovereign_guna_anomalies` | S4 |

The distinction matters: audit-only signals provide observability without
governance risk. A bug in audit-only data cannot change a decision.
Behavior-affecting signals are more sensitive and are therefore bounded,
capped, and wrapped in fail-safe try/except blocks.

---

## Sovereign Penalty Safety Model

Sovereign-derived confidence penalties are layered with multiple safety
boundaries to prevent over-penalization.

### Per-Adapter Caps

Each adapter independently caps its own penalty:

| Adapter | Individual Cap | Rationale |
|---------|---------------|-----------|
| Entropy adapter | 0.15 | Entropy uncertainty is informational, not conclusive |
| Insight adapter | 0.10 | Insight gate is heuristic, not proof |
| Guna anomaly adapter | 0.05 | Temporal anomalies are noisy |

### Aggregate Cap (Activation Patch)

Even with individual caps, the raw sum could reach 0.30. The aggregate cap
ensures the total sovereign-derived penalty never exceeds 0.20:

```python
sovereign_penalty = min(0.20, sum_of_all_adapter_penalties)
```

This protects against pathological stacking where multiple noisy signals
simultaneously fire, which could otherwise drop confidence unreasonably.

### Fail-Safe Defaults

Every sovereign resolver wraps its logic in `try/except`:

```python
def _resolve_guna_anomaly_signal(jepa_assessment):
    try:
        # ... extract and resolve ...
    except Exception:
        return GunaAnomalyResolution()  # zero penalty, no escalation
```

If any sovereign signal resolution fails, it returns a neutral default
(zero penalty, no bias, available=False). This means sovereign integration
cannot crash or corrupt the governance decision path.

### Stricter-Only Invariant

All sovereign effects are stricter-only:
- Confidence penalties are non-negative (penalty ≥ 0)
- Escalation bias only bumps up, never down
- No sovereign signal can relax a governance decision
- No sovereign signal can override a DENY to ALLOW

---

## Current Limitations and Conditionality

### Metadata Presence

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

### `previous_bhava` Is Not Tracked

Bhava transition priors (`sovereign_bhava_priors.py`) evaluate the
transition from `previous_bhava` to `current_bhava`. Currently,
`previous_bhava` is hardcoded to `None` in `governance_service.py`.
This means bhava transition audit data captures only the current bhava,
not cross-request transition quality. Implementing cross-request bhava
tracking would require session-level state.

### Sovereign-Side Constant Duplication

Some sovereign model files may still define constants internally that
overlap with shared authorities (e.g., guna labels, bhava names).
Governance runtime consumers now use shared constants from
`sovereign_constants.py`, but the model-internal definitions have not
been fully deduplicated. This is a code hygiene issue, not a correctness
issue — the governance side uses the right values.

### Intentionally Excluded Sovereign Internals

The following sovereign model internals are **deliberately** not wired
into governance:

| Component | Why Excluded |
|-----------|-------------|
| Per-layer attention weights | Too noisy, no clear governance semantics |
| Gradient norms / training signals | Training-only, not meaningful at inference |
| Raw 128D state vector | Governance doesn't need tensor-level detail |
| `nn.Module` internals (observer, guna, vritti modules) | PyTorch dependency boundary |
| PID governor internal state (beyond telemetry) | Telemetry passthrough is sufficient |

These are excluded by design, not by oversight. The bridge architecture
extracts semantically meaningful summaries and discards implementation
detail.

### Audit-Only Signals By Design

Several S4 signals (bhava transition, governor telemetry) are audit-only
by design — they provide observability but do not change governance
decisions. This is intentional: not every signal justifies governance
authority. Promoting audit-only signals to behavior-affecting status
would require rigorous justification and new bounded adapter logic.

---

## Test Evidence

### Coverage Summary

| Test Suite | Tests | Focus |
|------------|-------|-------|
| `test_phase_s2_integration.py` | 54 | S2 adapters, bounded effects, backward compat |
| `test_phase_s3_integration.py` | 32 | S3 diagnostics, bridge contracts, torch isolation |
| `test_phase_s4_integration.py` | 67 | S4 anomaly/prior/telemetry, adapters, fallbacks |
| `test_activation_e2e.py` | 8 | True E2E `authorize()` proving S3/S4 activation |
| `test_jepa_governance.py` | ~100+ | JEPA composite, regimes, governance service integration |

### What the E2E Tests Prove

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

### What Is NOT Tested

- No tests verify that a specific production caller always supplies
  projection metadata (this depends on deployment configuration)
- No tests cover cross-request `previous_bhava` tracking (not implemented)
- No tests cover the full model→bridge→governance path with live PyTorch
  model inference (tests use synthetic metadata dicts)

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
| `agentic_framework/governance_models.py` | S1+patch | No | AuthorizationRequest.sovereign_projection_metadata |
| `agentic_framework/governance_service.py` | S1–S4+patch | No | Decision engine, penalty cap, resolver wiring |

### Test Files

| File | Tests | Focus |
|------|-------|-------|
| `tests/test_phase_s2_integration.py` | 54 | S2 unit + integration |
| `tests/test_phase_s3_integration.py` | 32 | S3 unit + integration |
| `tests/test_phase_s4_integration.py` | 67 | S4 unit + integration |
| `tests/test_activation_e2e.py` | 8 | E2E sovereign activation proof |
