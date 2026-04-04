# Agentic Policy Folder — File-Level Architectural Audit

**Date:** 2026-04-04
**Scope:** Every `.py` file under `agentic/policy/` (16 files, ~4,678 lines)
**Purpose:** Determine what each file does, whether it is live or dormant, and how it relates to the agentic framework runtime and product roadmap.

---

## File Inventory

| # | File | Lines | Status | Runtime? |
|---|------|-------|--------|----------|
| 1 | `__init__.py` | 53 | Live | Yes — package facade |
| 2 | `domain_profiles.py` | 197 | Live | Yes — all policy decisions flow through this |
| 3 | `governance_binding.py` | 23 | Dormant | No — zero consumers |
| 4 | `phase32_hardening.py` | 321 | Dormant | No — tests only |
| 5 | `interaction_modes.py` | 258 | Live | Yes — 30+ importers |
| 6 | `layer_visibility_policy.py` | 459 | Dormant | No — tests only, but complete RBAC |
| 7 | `insight_window_gating.py` | 600 | Live | Yes — called by policy_engine.py |
| 8 | `session_policy.py` | 221 | Live | Yes — called by session_processing.py |
| 9 | `preferences.py` | 33 | Dormant | No — zero consumers |
| 10 | `trading_guardrail_engine.py` | 232 | Live | Yes — called by session_processing.py |
| 11 | `policy_engine.py` | 909 | Live | Yes — core policy engine |
| 12 | `insight_window/__init__.py` | 151 | Live | Yes — P32 pipeline integration |
| 13 | `insight_window/insight_gating_engine.py` | 371 | Live | Yes — P32 engine |
| 14 | `insight_window/insight_envelope.py` | 410 | Live | Yes — P32 schema |
| 15 | `insight_window/insight_gating_formula.py` | 401 | Live | Yes — locked P32 formula |
| 16 | `licensing/__init__.py` | 39 | Dormant | No — zero consumers |

---

## File-by-File Audit

### 1. `__init__.py`
- **Purpose:** Package facade; re-exports `compute_policy_flags`, `get_domain_profile`, `InteractionMode`, `resolve_interaction_mode`
- **Status:** Live runtime
- **Action:** Keep; expand exports as control-plane APIs emerge
- **Priority:** P2

### 2. `domain_profiles.py`
- **Purpose:** Hardcoded per-domain policy config (trading, therapy, identity, generic). Thresholds, mapper preferences, formula modes, interaction mode defaults.
- **Status:** Live runtime — used by policy_engine, session_processing, 6+ integration tests
- **Action:** P0 — extract from hardcoded dict to versionable config. This is the #1 blocker for policy externalization.
- **Priority:** P0

### 3. `governance_binding.py`
- **Purpose:** Pure re-export facade for P53 policy binding from symbolu_core
- **Status:** Dormant — zero consumers. P55/P54 import directly from symbolu_core.
- **Action:** Wire now OR deprecate. Depends on import topology decision.
- **Priority:** P1 (decision-level, not implementation)

### 4. `phase32_hardening.py`
- **Purpose:** Governance verification functions for P32 acoustic safety invariants
- **Status:** Dormant — test-only. Logic duplicated inline in insight_window_gating.py.
- **Action:** Refactor first — deduplicate inline copies to use this module
- **Priority:** P2

### 5. `interaction_modes.py`
- **Purpose:** InteractionMode enum + resolution cascade (admin > user > domain default)
- **Status:** Live runtime — imported across 30+ files including API server and preferences
- **Action:** Expose via governance API (mode control endpoint)
- **Priority:** P1

### 6. `layer_visibility_policy.py`
- **Purpose:** Complete RBAC enforcement for ontological layers. Fail-closed, hash-stable, frozen contracts.
- **Status:** Dormant — tests only. NOT imported by any runtime code.
- **Action:** Wire now — this is ready-to-use governance enforcement infrastructure
- **Priority:** P0

### 7. `insight_window_gating.py`
- **Purpose:** Original v1.0 insight window gating system (UCF-based). Called by policy_engine.py.
- **Status:** Live runtime
- **Action:** Keep runtime-only. Later: consolidate with insight_window/ subfolder.
- **Priority:** P2

### 8. `session_policy.py`
- **Purpose:** SessionPolicyFlags from SessionSummary. Deterministic session health classification.
- **Status:** Live runtime — called by session_processing.py
- **Action:** Expose via dashboard API. Parameterize thresholds for simulation.
- **Priority:** P1

### 9. `preferences.py`
- **Purpose:** Pure re-export facade for preference models from symbolu_core
- **Status:** Dormant — zero consumers
- **Action:** Wire later — only useful after governance API exists
- **Priority:** P2

### 10. `trading_guardrail_engine.py`
- **Purpose:** Trading-specific risk flags (tension, momentum, volatility). Pure deterministic.
- **Status:** Live runtime — called by session_processing.py
- **Action:** Expose via dashboard/governance API
- **Priority:** P1

### 11. `policy_engine.py`
- **Purpose:** Core policy engine. compute_policy_flags() — the single most important function.
- **Status:** Live runtime — called by output_processing.py
- **Action:** P0 — expose via governance service; extract hardcoded thresholds for externalization
- **Priority:** P0

### 12-15. `insight_window/` subfolder
- **Purpose:** Pipeline-native P32 insight gating (engine + schema + locked formula)
- **Status:** Live runtime — used by P32 pipeline integration
- **Action:** Keep runtime-only. Later: consolidate with insight_window_gating.py (root)
- **Priority:** P2

### 16. `licensing/__init__.py`
- **Purpose:** Pure re-export facade for license validation from symbolu_core
- **Status:** Dormant — zero consumers
- **Action:** Wire later (P3) when license-gated governance features ship
- **Priority:** P3

---

## Key Cross-File Findings

### Overlapping Systems
- **Two insight window systems** with different formulas, schemas, and integration paths
- **Acoustic hardening duplicated** in 3 places

### Dormant Facades (3 files, zero consumers)
- `governance_binding.py`, `preferences.py`, `licensing/__init__.py`
- All re-export from symbolu_core but nobody routes through them

### Hardcoded Configuration (blocking externalization)
- `domain_profiles.py` — hardcoded dicts
- `policy_engine.py` — hardcoded thresholds
- `insight_gating_formula.py` — locked weights

### Cross-Boundary Coupling
- `symbolu_core.service.preferences` imports `InteractionMode` from `agentic.policy` (reverse dependency)

---

## Top 10 Files to Wire/Promote

1. `domain_profiles.py` — extract to versionable config
2. `policy_engine.py` — expose via governance service
3. `layer_visibility_policy.py` — wire to GovernanceService
4. `interaction_modes.py` — expose mode control via API
5. `session_policy.py` — expose via dashboard API
6. `trading_guardrail_engine.py` — expose via dashboard API
7. `insight_window/` subfolder — expose schema in audit trail
8. `phase32_hardening.py` — deduplicate; promote for governance audit
9. `governance_binding.py` — decide import topology; wire or delete
10. `insight_window_gating.py` — consolidate into insight_window/ package

---

## Recommended Phased Integration Plan

### Phase P0: Foundation
- Extract domain_profiles.py from hardcoded dicts to versionable config
- Wire layer_visibility_policy.py into GovernanceService
- Decide import topology for facades

### Phase P1: Service Exposure
- Wrap policy_engine.py, session_policy.py, trading_guardrail_engine.py in API
- Expose interaction mode control in governance API
- Add audit trail hooks

### Phase P2: Consolidation & Simulation
- Consolidate two insight window systems
- Deduplicate hardening logic
- Parameterize thresholds for simulation
- Build policy replay path

### Phase P3: Operator Control Plane
- Policy deployment lifecycle with versioned profiles
- Approval queue for policy changes
- Dashboard backend
- Tenant-scoped policies

### Phase P4: Governance Maturity
- Formula versioning (A/B)
- Policy replay dashboard
- License-gated features
- Delete dead facades
