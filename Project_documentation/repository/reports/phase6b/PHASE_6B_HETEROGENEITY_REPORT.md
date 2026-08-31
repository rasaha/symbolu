# Phase 6B — Provider Heterogeneity, Resolution, and Failover Validation

- **Dataset:** `enterprise_pilot_v1` (hash `4d6de4294324a7b4…`, 90 scenarios) — reused unchanged
- **Substantive digest:** `bd14c04b7aea56ca…`
- **Invariants H1–H20:** ALL PASS

## Configuration comparison (normal mode, 90 scenarios)

| Config | Providers | Unsafe | Dispatched | False blocks | Fallbacks | No-valid-provider |
|---|---|---|---|---|---|---|
| C1 | TAP + ActionGate | 0 | 51 | 0 | 0 | 0 |
| C2 | TAP + Baseline Action | 0 | 45 | 15 | 0 | 0 |
| C3 | Baseline Assertion + ActionGate | 0 | 21 | 30 | 0 | 0 |
| C4 | Baseline Assertion + Baseline Action | 0 | 30 | 30 | 0 | 0 |
| C5 | Preferred + Bounded Fallback | 0 | 51 | 0 | 0 | 0 |
| C6 | Capability-Driven | 0 | 60 | 0 | 0 | 0 |

## Resolution metrics

| Config | Preferred sel. | Fallback | Safe fallback | No-valid | Cap-match | Compat-rej | Health-rej |
|---|---|---|---|---|---|---|---|
| C1 | 1.0 | 0.0 | None | 0.0 | 1.0 | 0 | 0 |
| C2 | 1.0 | 0.0 | None | 0.0 | 1.0 | 0 | 0 |
| C3 | 1.0 | 0.0 | None | 0.0 | 1.0 | 0 | 0 |
| C4 | 1.0 | 0.0 | None | 0.0 | 1.0 | 0 | 0 |
| C5 | 1.0 | 0.0 | None | 0.0 | 1.0 | 0 | 0 |
| C6 | 1.0 | 0.0 | None | 0.0 | 1.0 | 0 | 0 |

## Governance metrics under heterogeneity

| Config | Unsupported promotion | Unsafe auth | Unsafe dispatch | Fail-safe | Gov-shopping |
|---|---|---|---|---|---|
| C1 | 0.0 | 0.0 | 0.0 | 1.0 | 0 |
| C2 | 0.0 | 0.0 | 0.0 | 1.0 | 0 |
| C3 | 0.0 | 0.0 | 0.0 | 1.0 | 0 |
| C4 | 0.0 | 0.0 | 0.0 | 1.0 | 0 |
| C5 | 0.0 | 0.0 | 0.0 | 1.0 | 0 |
| C6 | 0.0 | 0.0 | 0.0 | 1.0 | 0 |

## Cost/benefit frontier by scenario class

- **ACTION_PROVIDER_FAILURE** — sufficient: C1, C3; lightest: C3; required capabilities: none; fallback acceptable: True; full pair required: False
- **ASSERTION_PROVIDER_FAILURE** — sufficient: C1, C2, C3, C4; lightest: C4; required capabilities: none; fallback acceptable: True; full pair required: False
- **BOTH_PROVIDERS_AVAILABLE** — sufficient: C1, C2, C3, C4; lightest: C4; required capabilities: none; fallback acceptable: True; full pair required: False
- **CONSTRAINED_ASSERTION_CONSTRAINED_ACTION** — sufficient: C1; lightest: C1; required capabilities: assertion:qualifier_detection; action:expiry,region_limits,required_approval,single_use; fallback acceptable: True; full pair required: True
- **INDETERMINATE_ASSERTION_HUMAN_REVIEW** — sufficient: C1, C2, C3, C4; lightest: C4; required capabilities: none; fallback acceptable: True; full pair required: False
- **ONE_PROVIDER_DEGRADED** — sufficient: C1, C2, C3, C4; lightest: C4; required capabilities: none; fallback acceptable: True; full pair required: False
- **SUPPORTED_ASSERTION_ACTION_DENIED** — sufficient: C1, C2, C3, C4; lightest: C4; required capabilities: none; fallback acceptable: True; full pair required: False
- **SUPPORTED_ASSERTION_AUTHORIZED_ACTION** — sufficient: C1, C2, C3, C4; lightest: C4; required capabilities: none; fallback acceptable: True; full pair required: False
- **UNSUPPORTED_ASSERTION_NO_ACTION** — sufficient: C1, C2, C3, C4; lightest: C4; required capabilities: none; fallback acceptable: True; full pair required: False

## Provider-specific metrics (never a single ranking)

| Provider | Eligible | Selected | Invocations | Infra failures | Substantive INDET | Fallbacks-to |
|---|---|---|---|---|---|---|
| tap-primary | 360 | 300 | 300 | 0 | 18 | 0 |
| baseline-assertion | 330 | 240 | 240 | 0 | 78 | 0 |
| actiongate-primary | 270 | 210 | 210 | 0 | 36 | 0 |
| baseline-action | 255 | 180 | 180 | 0 | 24 | 0 |

## Interpretation

**Measured result:** two providers coexist in each family behind the unchanged framework. Selection is deterministic (H1) and auditable; compatibility, capability, and health are honoured (H2–H4, H19); bounded fallback occurs only under infrastructure failure and only where policy permits (H9), never converting a substantive UNSUPPORTED/DENIED/INDETERMINATE into support/authorization (H5–H8, governance-shopping violations = 0); and no-valid-provider cases fail safe to INDETERMINATE with no dispatch (H10–H11, H20).

**Benchmark-design consequence:** capability-limited baseline providers correctly return INDETERMINATE for scenarios beyond their honestly-declared capability, appearing as fail-safe *false blocks* (never unsafe). The capability-driven configuration routes each request to the lightest sufficient provider and escalates only when a capability is genuinely required.

**Architectural inference:** the existing registry, compatibility, and capability structures are sufficient to host heterogeneous providers and fail over safely without any frozen change; C1 reproduces Phase 6A full governance exactly.

**Unvalidated real-world claim:** none. The alternative providers are deterministic validation implementations, not production competitors; no production/regulatory claim is made.

