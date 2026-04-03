# Agentic Governance Architecture

> **Version:** 3.0.0 | **Updated:** 2026-04-03
>
> This document describes the governance architecture **as currently built**.
> Components marked **(planned)** are design-only and not yet implemented.

---

## Layered Architecture Overview

The governance system is organized into five built layers:

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  LAYER 1: SEMANTIC STATE                                        │
  │  Derives the cognitive-semantic state of the system              │
  │                                                                  │
  │  Ontology signal (12-layer OLM weights)                          │
  │  Vritti signal (5-mode cognitive distribution)                   │
  │  JEPA composite (ontology + vritti integration)                  │
  │  Residual signal (semantic–runtime mismatch)                     │
  │  Governance regime (NORMAL / PROCESS_DRIFT / SEMANTIC_SHIFT /    │
  │                      DUAL_ANOMALY / UNKNOWN)                     │
  │                                                                  │
  │  Modules: jepa_governance.py, olm_bridge.py, sovereign_bridge.py │
  │  Signals: chitta_vritti/, sovereign/                              │
  └──────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  LAYER 2: DOMAIN SEMANTIC POLICY                                │
  │  Translates semantic state into domain-specific action posture   │
  │                                                                  │
  │  DomainProfile (declarative: matrix, rules, tool perms,          │
  │                  thresholds, vritti guard)                        │
  │  DomainPolicyInterpreter (stateless runtime translator)          │
  │  DomainRegistry (profile lookup, fail-closed)                    │
  │  DomainActionMode (ALLOW → … → BLOCKED, 7 modes)                │
  │  Stricter-only invariant: domain can restrict, never relax       │
  │                                                                  │
  │  Module: domain_policy.py                                        │
  │  Profiles: finance, devops, research (built-in)                  │
  └──────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  LAYER 3: SHADOW AI CONTROL                                     │
  │  Governs provenance, sanctionedness, and containment posture     │
  │                                                                  │
  │  ProvenanceStatus (APPROVED / UNVERIFIED / SHADOW /              │
  │                    QUARANTINED / REVOKED)                         │
  │  ShadowRegistry (asset lookup, pattern match, provider index)    │
  │  ShadowRiskFactors (13 visible factors + composite score)        │
  │  ShadowContainmentMode (9 modes: ALLOW → … → BLOCKED)           │
  │  ShadowPolicyRule (10 declarative rules, stricter-only)          │
  │  safe_resolve_shadow_policy() (fail-closed wrapper)              │
  │  Stricter-only: shadow can restrict, never relax governance      │
  │                                                                  │
  │  Module: shadow_ai.py                                            │
  │  Shared helpers: resolve_shadow_asset_id(), is_memory_write_intent() │
  └──────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  LAYER 4: CORE GOVERNANCE / ENFORCEMENT                         │
  │  Makes and enforces ALLOW / DENY / DEFER decisions               │
  │                                                                  │
  │  GovernanceService (authorization engine)                        │
  │  SafeMCPGateway (tool execution gating)                          │
  │  SafetyContract (7-precondition safety check)                    │
  │  ConfidenceGate (multi-signal confidence evaluation)             │
  │  Escalation / human-in-the-loop                                  │
  │  Pipeline guards (P15, P16, P55)                                 │
  │                                                                  │
  │  Modules: governance_service.py, mcp_gateway.py,                 │
  │           confidence_gate.py, safety_contract.py                 │
  └──────────────────────────┬──────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  LAYER 5: EXECUTION / RUNTIME                                   │
  │  Tool calls, memory writes, external actions, audit persistence  │
  │                                                                  │
  │  MCP client execution, timeout/error handling                    │
  │  GovernanceAuditStore (durable event persistence)                │
  │  LedgerEntryStore (hash-chained append-only ledger)              │
  │  Posture modulation / output gating                              │
  └─────────────────────────────────────────────────────────────────┘
```

---

## Package Map

```
agentic/
├── agentic_framework/    CORE   Governance orchestration hub
│   ├── governance_service.py      Authorization engine (Steps 1-9)
│   ├── confidence_gate.py         Confidence evaluation & gating
│   ├── mcp_gateway.py             Safe MCP tool execution gateway
│   ├── safety_contract.py         7-precondition safety contract
│   ├── jepa_governance.py         JEPA composite signal & regime classification
│   ├── domain_policy.py           Domain Semantic Policy Layer
│   ├── shadow_ai.py               Shadow AI Control Layer (provenance, containment)
│   ├── governance_models.py       Shared data models (request/response/audit)
│   ├── governance_adapter.py      P52 governance request assembly (facade → symbolu_core)
│   ├── sovereign_bridge.py        128D sovereign tensor → confidence signals
│   ├── olm_bridge.py              12-layer OLM → governance signals & risk
│   └── governance_api.py          API entry point for authorization
│
├── safety/               CORE   Hard safety constraints & guards
│   ├── pipeline_guards/           P15 authority, P16 regression, P55 execution boundary
│   ├── acoustic_safety/           P13 acoustic safety resolver
│   ├── governance_patterns/       6 standalone governance primitives (see below)
│   ├── output_gate.py             GovernedGate ALLOW/BLOCK/WARN
│   ├── gcc_runtime_guard.py       GCC phase-exit enforcement
│   ├── rate_limiter.py            Sliding-window rate limiter (facade → symbolu_core)
│   └── escalation_signals.py      P6/P7 escalation directives (facade → symbolu_core)
│
├── policy/               CORE   Policy evaluation & domain profiles
│   ├── policy_engine.py           Domain-specific policy evaluation
│   ├── governance_binding.py      P53 governance binding (facade → symbolu_core)
│   ├── licensing/                 License gating (facade → symbolu_core)
│   ├── preferences.py             Admin preferences (facade → symbolu_core)
│   ├── domain_profiles.py         Per-domain policy profiles
│   └── interaction_modes.py       Interaction mode configuration
│
├── posture/              CORE   Behavioral modulation & readiness
│   ├── governance_readiness.py    P51 governance readiness (facade → symbolu_core)
│   ├── modulation.py              Posture modulation engine
│   └── audit.py                   Posture application audit records
│
├── ledger/               CORE   Immutable audit trail
│   ├── governance_audit_store.py  Durable governance event persistence
│   ├── audit_trace.py             P54 compliance records (facade → symbolu_core)
│   ├── ledger_store.py            Hash-chained append-only ledger
│   └── ledger_replay_verifier.py  Deterministic replay verification
│
├── entropy/              INTEGRATE  Cross-domain coherence regulation
├── core/                 INTEGRATE  Intelligence engine (SMI, stitching, bhava)
├── identity/             INTEGRATE  Identity signature classification
├── motivation/           INTEGRATE  Motivational driver classification
├── sovereign/            INTEGRATE  Cognitive state management (128D tensor)
├── inference/            INTEGRATE  Inference-time bridge (CSR guard, metacog)
├── chitta_vritti/        INTEGRATE  5-element vritti distribution
├── temporal/             INTEGRATE  Temporal bhava & cross-domain patterns
├── guna_modulation/      INTEGRATE  Guna-aware entropy modulation
├── dha/                  INTEGRATE  Delivery harmonization (tone/restraint)
├── llm/                  INTEGRATE  One-way LLM authority boundary
└── api/                  INTEGRATE  External observability API
```

---

## Canonical Governance Flow (End-to-End)

```
                         ┌─────────────────────────────────┐
                         │        ENTRY POINTS              │
                         │                                  │
                         │  ① POST /authorize  (HTTP API)   │
                         │  ② SafeMCPGateway.call_tool()    │
                         │  ③ SafetyGate.check()            │
                         └──────────┬───────────────────────┘
                                    │
                                    ▼
               ┌────────────────────────────────────────┐
               │  P51  GOVERNANCE READINESS              │
               │  posture/governance_readiness            │
               │                                         │
               │  Is the pipeline structurally ready?     │
               │  • Phase completeness                    │
               │  • Determinism verified                  │
               │  • Authority integrity intact             │
               │  • Explainability available               │
               │                                          │
               │  → READY / CONDITIONAL / NOT_READY       │
               └──────────┬─────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   GOVERNANCE SERVICE  (agentic_framework/governance_service)     │
│   Authorization Engine                                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 1: RISK CLASSIFICATION                              │    │
│  │         ToolRiskClassifier.classify(tool_name)            │    │
│  │         → READ_ONLY / WRITE / EXECUTE /                   │    │
│  │           DESTRUCTIVE / PRIVILEGED                        │    │
│  └────────────────────┬─────────────────────────────────────┘    │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 2: FORBIDDEN CAPABILITY CHECK  ●━━━━━━━━━━━▶ DENY   │    │
│  │         7 hard-blocked capabilities:                      │    │
│  │         destructive_file_ops, network_attacks,            │    │
│  │         credential_access, privilege_escalation,          │    │
│  │         system_modification, data_exfiltration,           │    │
│  │         malware_execution                                 │    │
│  └────────────────────┬─────────────────────────────────────┘    │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 3: CONFIDENCE GATING                                │    │
│  │         ConfidenceGate.evaluate(signals)                  │    │
│  │                                                           │    │
│  │         Aggregation weights:                              │    │
│  │           quality(30%) + coherence(25%) +                 │    │
│  │           stability(25%) + action(20%)                    │    │
│  │                                                           │    │
│  │         → ExecutionMode:                                  │    │
│  │           FULL / CAUTIOUS / CONFIRM_REQUIRED / BLOCKED    │    │
│  │         → EscalationLevel:                                │    │
│  │           NONE / NOTIFY / CONFIRM / HALT                  │    │
│  └────────────────────┬─────────────────────────────────────┘    │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 4: SAFETY CONTRACT                                  │    │
│  │         7 preconditions, ALL must pass:                   │    │
│  │                                                           │    │
│  │         ✓ internal_consistency  ≥ 0.60                    │    │
│  │         ✓ goal_alignment        ≥ 0.60                    │    │
│  │         ✓ reversal_risk         ≤ 0.40                    │    │
│  │         ✓ identity_stability    ≥ 0.60                    │    │
│  │         ✓ no blocking_factors                             │    │
│  │         ✓ agency_level ∈ {FULL, CONFIRM}                  │    │
│  │         ✓ no forbidden capabilities                       │    │
│  │                                                           │    │
│  │         → eligible = (0 violations)                       │    │
│  └────────────────────┬─────────────────────────────────────┘    │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 5: DECISION MERGE (baseline)                        │    │
│  │                                                           │    │
│  │   forbidden_cap ──────────────────────────────▶ DENY      │    │
│  │   not eligible ───────────────────────────────▶ DENY      │    │
│  │   BLOCKED execution mode ─────────────────────▶ DENY      │    │
│  │   requires_human (CONFIRM/HALT) ──────────────▶ DEFER     │    │
│  │   all passed ─────────────────────────────────▶ ALLOW     │    │
│  │                                                           │    │
│  └────────────────────┬─────────────────────────────────────┘    │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 5b: JEPA SEMANTIC-COGNITIVE GOVERNANCE CHECK        │    │
│  │          (jepa_governance.py)                             │    │
│  │                                                           │    │
│  │  Constructs JEPA composite signal:                        │    │
│  │    OntologySignal (12-layer weights → primary layer)      │    │
│  │    VrittiSignal (5-mode distribution → primary vritti)    │    │
│  │    JEPACompositeSignal (integrated confidence, alignment) │    │
│  │                                                           │    │
│  │  Compares composite against RuntimeProcessState:          │    │
│  │    → ResidualSignal (semantic–runtime mismatch)           │    │
│  │    → GovernanceRegime:                                    │    │
│  │        NORMAL / PROCESS_DRIFT / SEMANTIC_SHIFT /          │    │
│  │        DUAL_ANOMALY / UNKNOWN                             │    │
│  │                                                           │    │
│  │  May override baseline decision (stricter only):          │    │
│  │    ALLOW → DEFER, ALLOW/DEFER → DENY                     │    │
│  │    Never relaxes: DENY cannot become ALLOW                │    │
│  │                                                           │    │
│  │  safe_jepa_governance_check() — never returns None,       │    │
│  │  never raises. Failure → UNKNOWN regime.                  │    │
│  └────────────────────┬─────────────────────────────────────┘    │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 5c: JEPA OVERRIDE APPLICATION                       │    │
│  │          Applies confidence adjustment, execution mode    │    │
│  │          override, escalation override. Each only applied │    │
│  │          if JEPA is stricter than gate decision.          │    │
│  └────────────────────┬─────────────────────────────────────┘    │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 5d: DOMAIN SEMANTIC POLICY LAYER                    │    │
│  │          (domain_policy.py)                               │    │
│  │                                                           │    │
│  │  resolve_domain_policy(assessment, registry, domain_id)   │    │
│  │                                                           │    │
│  │  Evaluation pipeline (each step can only restrict):       │    │
│  │    1. Action coherence matrix (regime × action_category)  │    │
│  │    2. Blocked action category check                       │    │
│  │    3. Coherence rules (all matching fire)                 │    │
│  │    4. Tool permission (most-restrictive-match)            │    │
│  │    5. Threshold checks (alignment, confidence, residual)  │    │
│  │    6. Vritti execution guard                              │    │
│  │    7. Merge all modes (strictest wins)                    │    │
│  │    8. Fail-closed default if nothing matched              │    │
│  │                                                           │    │
│  │  → DomainActionMode:                                      │    │
│  │      ALLOW / READ_ONLY / DRAFT_ONLY / CONFIRM_REQUIRED / │    │
│  │      SANDBOX_ONLY / MEMORY_WRITE_DENIED / BLOCKED         │    │
│  │                                                           │    │
│  │  Domain can only restrict, never relax:                   │    │
│  │    BLOCKED → DENY                                         │    │
│  │    CONFIRM/SANDBOX/MEMORY → DEFER (if was ALLOW)          │    │
│  │    READ_ONLY/DRAFT → DEFER (if was ALLOW)                 │    │
│  │                                                           │    │
│  │  No domain configured → no-op (step skipped)              │    │
│  └────────────────────┬─────────────────────────────────────┘    │
│                       ▼                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Step 5e: SHADOW AI CONTROL LAYER                         │    │
│  │          (shadow_ai.py)                                   │    │
│  │                                                           │    │
│  │  safe_resolve_shadow_policy():                            │    │
│  │    1. Registry lookup (exact → pattern → provider)        │    │
│  │    2. Provenance classification:                          │    │
│  │       APPROVED / UNVERIFIED / SHADOW /                    │    │
│  │       QUARANTINED / REVOKED                               │    │
│  │    3. Risk factor computation (13 visible factors)        │    │
│  │    4. Policy rule evaluation (10 declarative rules)       │    │
│  │    4b. max_risk_level enforcement                         │    │
│  │    4c. blocked_capabilities enforcement                   │    │
│  │    5. Semantic mismatch escalation                        │    │
│  │       (approved asset behaving incoherently)              │    │
│  │    6. JEPA regime escalation                              │    │
│  │       (dual_anomaly/unknown → QUARANTINED)                │    │
│  │    7. Fail-closed defaults per provenance:                │    │
│  │       SHADOW/REVOKED → BLOCKED (mutating) or READ_ONLY    │    │
│  │       QUARANTINED → BLOCKED (mutating) or QUARANTINED     │    │
│  │       UNVERIFIED → BLOCKED (destructive) or CONFIRM       │    │
│  │    8. Rationale & audit assembly                          │    │
│  │                                                           │    │
│  │  → ShadowContainmentMode (9 modes):                       │    │
│  │      ALLOW / OBSERVE_ONLY / READ_ONLY / DRAFT_ONLY /      │    │
│  │      SANDBOX_ONLY / MEMORY_WRITE_DENIED /                 │    │
│  │      REQUIRE_CONFIRMATION / QUARANTINED / BLOCKED         │    │
│  │                                                           │    │
│  │  Shadow can only restrict, never relax:                   │    │
│  │    BLOCKED/QUARANTINED → DENY                             │    │
│  │    Intermediate modes → DEFER (if was ALLOW)              │    │
│  │    ALLOW → no change                                      │    │
│  │                                                           │    │
│  │  Fail-closed: resolver exception → BLOCKED + error audit  │    │
│  │  No shadow registry → no-op (step skipped)                │    │
│  └────────────────────┬─────────────────────────────────────┘    │
│                       ▼                                          │
│  Steps 6-9: Build rationale (includes JEPA + domain + shadow     │
│             codes) → confidence summary → audit event (includes  │
│             JEPA + domain + shadow snapshot) → assemble           │
│             AuthorizationResponse                                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ FAIL-CLOSED: Any exception in Steps 1-9                  │    │
│  │ → DENY + BLOCKED + HALT + confidence=0.0                 │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         │  AuthorizationResponse
                         │  { ALLOW / DENY / DEFER }
                         │
                         ▼
               ┌─────────────────────────────────┐
               │  P53  GOVERNANCE BINDING         │
               │  policy/governance_binding        │
               │                                   │
               │  Injects ALLOW/DENY/DEFER into    │
               │  pipeline as GovernanceBinding-    │
               │  Envelope. "A plug, not a judge." │
               │  Records decision verbatim.       │
               └──────────┬────────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────────┐
          │  PIPELINE GUARDS                   │
          │  safety/pipeline_guards/            │
          │                                    │
          │  P15: Authority regression guard    │
          │       Intent/regime/posture MUST    │
          │       NOT mutate after P15          │
          │                                    │
          │  P16: Contract regression guard     │
          │       Hash-based PO1-P15 integrity  │
          │       Detects any unauthorized      │
          │       mutation                      │
          │                                    │
          │  P55: Execution boundary            │
          │       Deny-by-default. Requires:    │
          │       • Governance provenance (P53)  │
          │       • Audit record (P54)           │
          │       • Action in allow-list         │
          │       → AUTHORIZE or DENY            │
          └──────────┬────────────────────────┘
                     │
                     ▼
          ┌───────────────────────────────────┐
          │  P13  ACOUSTIC SAFETY              │
          │  safety/acoustic_safety/            │
          │                                    │
          │  "Last safety lock before sound"    │
          │  Detects & caps:                    │
          │  • Emotion amplification            │
          │  • Certainty escalation             │
          │  • Authority signaling              │
          │  • Prosodic manipulation            │
          │  → SAFE / CAUTION / BLOCKED         │
          └──────────┬────────────────────────┘
                     │
                     ▼
          ┌───────────────────────────────────┐
          │  OUTPUT GATE                       │
          │  safety/output_gate                 │
          │                                    │
          │  GovernedGate evaluates P12 audit   │
          │  GOVERNED mode:                     │
          │    CRITICAL → BLOCK (fail-closed)   │
          │    ≥2 MAJOR → BLOCK                 │
          │    1 MAJOR  → WARN                  │
          │    MINOR    → ALLOW                 │
          │                                    │
          │  → ALLOW / BLOCK / WARN             │
          │                                    │
          │  If BLOCK → fallback response       │
          │  "I need to reconsider."            │
          └──────────┬────────────────────────┘
                     │
                     ▼
          ┌───────────────────────────────────┐
          │  AUDIT TRAIL                       │
          │  ledger/                            │
          │                                    │
          │  P54: ComplianceAuditRecord         │
          │       Determinism hash for          │
          │       verifiable execution          │
          │                                    │
          │  LedgerEntryStore:                  │
          │       Hash-chained, append-only     │
          │       Immutable audit ledger         │
          │                                    │
          │  LedgerReplayVerifier:              │
          │       Deterministic replay check     │
          └────────────────────────────────────┘
```

---

## Orthogonal Safety Layers (Always Active)

```
┌──────────────────────────────────────────────────────────────┐
│  GCC RUNTIME GUARD  (safety/gcc_runtime_guard)                │
│  Applied at every constrained phase exit (Phases 1b-9)        │
│  Enforces: all intermediate outputs are non-expressive         │
│  Violation → GCCViolationError (immediate halt)                │
│  Independent of governance flow — always active                │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  RATE LIMITER  (safety/rate_limiter)                           │
│  API boundary: sliding-window, per-IP                          │
│  60 requests/minute default → 429 on exceeded                  │
│  Independent of governance flow — always active                │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  ESCALATION SIGNALS  (safety/escalation_signals)              │
│  PresentationDirective.escalate_to_human                       │
│  P6/P7 regime: HOLD / DE_ESCALATE / CLARIFY                   │
│  Triggers human-in-the-loop when confidence insufficient       │
└──────────────────────────────────────────────────────────────┘
```

---

## Governance Patterns Pipeline (safety/governance_patterns/)

Six standalone governance primitives extracted from infrastructure governance
and rewritten for AI agent governance.  No external dependencies — these are
agentic-native implementations.

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    GOVERNANCE PATTERNS PIPELINE                     │
  │                                                                     │
  │   ① PolicyEngine          Configurable allow/deny enforcement       │
  │      policy_engine.py      • Action-type allowlists / denylists     │
  │      OLM: O1, O6           • Blackout windows (time-based blocks)   │
  │                             • Rate limiting (sliding window)         │
  │              │                                                       │
  │              ▼                                                       │
  │   ② SafetyBounds           Hard non-negotiable action limits        │
  │      safety_bounds.py      • Max action magnitude (clamping)        │
  │      OLM: O3, O4           • Min action magnitude (noise floor)     │
  │                             • Cooldown enforcement                   │
  │              │                                                       │
  │              ▼                                                       │
  │   ③ PlasticityGate         Sigmoid permission-to-act gate           │
  │      plasticity_gate.py    • Double-EMA smoothing (no flicker)      │
  │      OLM: O5, O10          • P_t = σ(k_r·R_t - k_m·M_t + b_p)     │
  │                             • Output range [~0.27, 1.0]             │
  │              │                                                       │
  │              ▼                                                       │
  │   ④ ReadinessChecker       Multi-criterion readiness gate           │
  │      readiness_checker.py  • Plasticity ≥ min_plasticity            │
  │      OLM: O9, O7           • Cooldown elapsed                       │
  │                             • No pending escalations                 │
  │              │                                                       │
  │              ▼                                                       │
  │   ⑤ ApprovalManager        Human-in-the-loop lifecycle              │
  │      approval_manager.py   • PENDING → APPROVED / DISMISSED / EXPIRED│
  │      OLM: O8, O9           • TTL auto-expiry                        │
  │                             • Full audit trail (who, when, why)      │
  │              │                                                       │
  │              ▼                                                       │
  │        [ACTION EXECUTES]                                            │
  │              │                                                       │
  │              ▼                                                       │
  │   ⑥ RollbackMonitor        Post-action degradation rollback         │
  │      rollback_monitor.py   • Grace period → monitor window          │
  │      OLM: O12, O11         • Signal degradation detection (>15%)    │
  │                             • Auto-rollback + post-rollback cooldown │
  │                             • Watched signals: confidence,           │
  │                               governance_strength, coherence         │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## OLM Bridge (agentic_framework/olm_bridge.py)

Maps the patent-exact 12-layer Ontological Layer Model to governance modules.

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │              12-LAYER OLM → GOVERNANCE MAPPING                      │
  │                                                                     │
  │  LOWER 6 — EXECUTION LAYERS (governance CONSTRAINS these)           │
  │  ─────────────────────────────────────────────────────────          │
  │  O1  POTENTIAL   → policy/           Capability gating              │
  │  O2  IDENTITY    → safety/           Identity guards                │
  │  O3  EXECUTION   → safety/           Execution boundary (P55)       │
  │  O4  STRUCTURE   → safety/           Regression guard (P16)         │
  │  O5  COGNITION   → agentic_framework/ Confidence gate              │
  │  O6  AGENCY      → policy/           Governance binding (P53)       │
  │                                                                     │
  │  UPPER 6 — GOVERNANCE LAYERS (these PERFORM governance)             │
  │  ─────────────────────────────────────────────────────────          │
  │  O7  REASONING   → safety/           Admissibility (P15/P16)        │
  │  O8  PURPOSE     → policy/           Constraint alignment (P53)     │
  │  O9  WITNESSES   → posture/          Observation/readiness (P51)    │
  │  O10 UNIFYING    → agentic_framework/ Coherence (confidence gate)  │
  │  O11 INTEGRATION → ledger/           Audit consolidation (P54)      │
  │  O12 ABSOLVING   → safety/           Termination boundary (P55)     │
  │                                                                     │
  │  EXECUTION RISK DETECTION                                           │
  │  ─────────────────────────────────────────────────────────          │
  │  O1 active without O8  → ungoverned_potential                       │
  │  O2 active without O7  → unverified_identity                        │
  │  O3 active without O12 → unbounded_execution                        │
  │  O4 active without O7  → unchecked_structure                        │
  │  O5 active without O9  → unwitnessed_cognition                      │
  │  O6 active without O8  → misaligned_agency                          │
  │                                                                     │
  │  RISK LEVELS                                                        │
  │  ─────────────────────────────────────────────────────────          │
  │  CRITICAL  gov < 0.15 AND exec > 0.50  → DENY                      │
  │  HIGH      gov < 0.30 OR 3+ gaps       → DEFER (human confirm)     │
  │  MODERATE  1-2 gaps OR exec-dominant    → CAUTIOUS (monitor)        │
  │  LOW       all 12 layers governed       → ALLOW                     │
  └─────────────────────────────────────────────────────────────────────┘
```

### OLM Bridge Functions

| Function | Input | Output | Purpose |
|----------|-------|--------|---------|
| `signals_from_olm()` | OLM layer weights | `ConfidenceSignals` | Feed 12 layers into confidence gate |
| `governance_signals_from_olm()` | OLM layer weights | `OLMGovernanceSignals` | Per-layer weights + gap/risk detection |
| `governance_risk_from_olm()` | OLM layer weights | `OLMGovernanceRisk` | Risk level + confidence adjustment |
| `olm_to_readiness_input()` | OLM output | dict | P51 readiness supplement |

### OLM v1 (10-layer) Backwards Compatibility

```
  v1.0 (10 layers)          v2.0 (12 layers)
  ─────────────────         ─────────────────
  O1_action          →      O3_EXECUTION
  O2_tagging         →      O2_IDENTITY
  O3_forming         →      O4_STRUCTURE
  O4_thinking        →      O5_COGNITION
  O5_directing       →      O6_AGENCY
  O6_reasoning       →      O7_REASONING
  O7_purposing       →      O8_PURPOSE
  O8_meta_observing  →      O9_WITNESSES
  O9_unifying        →      O10_UNIFYING
  O10_absolving      →      O12_ABSOLVING
  (missing)          →      O1_POTENTIAL  (defaults to 0.0)
  (missing)          →      O11_INTEGRATION (defaults to 0.0)
```

---

## MCP Gateway Flow (Tool Execution)

```
  MCPToolCall arrives
       │
       ▼
  ┌─ Step 1: Risk classify ──────────────────────┐
  │  READ_ONLY / WRITE / EXECUTE /               │
  │  DESTRUCTIVE / PRIVILEGED                     │
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 2: Forbidden check ───▶ BLOCKED ───────┐
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 3: Confidence gate ────────────────────┐
  │  Maps risk → action_complexity/reversibility  │
  │  Gate → ConfidenceGateDecision                │
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 4: JEPA governance check ──────────────┐
  │  safe_jepa_governance_check()                 │
  │  → GovernanceRegime + confidence adjustment   │
  │  + escalation/execution mode overrides        │
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 5: Domain Semantic Policy ─────────────┐
  │  resolve_domain_policy()                      │
  │  Computed BEFORE JEPA regime handling so       │
  │  domain is always in audit.                    │
  │  → DomainActionMode + audit dict              │
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 6: JEPA regime + domain merge ─────────┐
  │  Non-NORMAL regime:                            │
  │    DENY → BLOCKED (domain can upgrade)         │
  │    DEFER → block non-read, escalate read       │
  │  NORMAL regime: domain enforcement only:       │
  │    BLOCKED → GatewayDecision.BLOCKED           │
  │    CONFIRM/SANDBOX/MEMORY → ESCALATE           │
  │    READ_ONLY/DRAFT → block non-read tools      │
  │    ALLOW → proceed                             │
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 6b: Shadow AI Control ─────────────────┐
  │  safe_resolve_shadow_policy()                  │
  │  Uses tool_name as asset identity              │
  │  → ShadowContainmentMode                      │
  │    BLOCKED/QUARANTINED → BLOCKED (early return)│
  │    Intermediate modes → ESCALATE (early return)│
  │    ALLOW → proceed                             │
  │  Shadow audit fields in AuditEntry             │
  │  No shadow registry → skip                     │
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 7: Min confidence ────▶ BLOCKED ───────┐
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 8: Escalation ───────▶ CONFIRM/HALT ──┐
  │  NOTIFY: inform human (non-blocking)          │
  │  CONFIRM: request approval → deny/timeout     │
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 9: Execute tool ──────────────────────┐
  │  mcp_client.call_tool() with timeout         │
  │  → ALLOWED / TIMEOUT / ERROR                 │
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 10: Audit ───────────────────────────┐
  │  AuditEntry (JEPA + domain + shadow fields) │
  │  → in-memory audit_log                      │
  │  → GovernanceAuditStore (durable)           │
  │  Shadow assessment embedded in              │
  │  request_snapshot for durable persistence   │
  └─────────────────────────────────────────────┘
```

---

## Decision Points Summary

### Core Governance Pipeline (17 decision points)

| # | Decision Point | Outcomes | Module |
|---|---------------|----------|--------|
| 1 | P51 Readiness | READY / CONDITIONAL / NOT_READY | posture/ |
| 2 | Forbidden capability | DENY (hard block) | agentic_framework/ |
| 3 | Confidence gate mode | FULL / CAUTIOUS / CONFIRM / BLOCKED | agentic_framework/ |
| 4 | Confidence escalation | NONE / NOTIFY / CONFIRM / HALT | agentic_framework/ |
| 5 | Safety contract (7 checks) | eligible=True/False | agentic_framework/ |
| 6 | Governance merge (baseline) | **ALLOW / DENY / DEFER** | agentic_framework/ |
| 6b | JEPA regime classification | NORMAL / PROCESS_DRIFT / SEMANTIC_SHIFT / DUAL_ANOMALY / UNKNOWN | jepa_governance.py |
| 6c | JEPA override | stricter-only adjustment to decision, confidence, escalation | jepa_governance.py |
| 6d | Domain policy evaluation | DomainActionMode (7 modes) | domain_policy.py |
| 6e | Domain override | stricter-only: BLOCKED→DENY, CONFIRM→DEFER, etc. | domain_policy.py |
| 6f | Shadow provenance classification | APPROVED / UNVERIFIED / SHADOW / QUARANTINED / REVOKED | shadow_ai.py |
| 6g | Shadow containment mode | 9 modes: ALLOW → … → BLOCKED | shadow_ai.py |
| 6h | Shadow override | stricter-only: BLOCKED/QUARANTINED→DENY, intermediate→DEFER | shadow_ai.py |
| 7 | P53 Binding | bound=True/False | policy/ |
| 8 | P15 Authority guard | pass / violation | safety/ |
| 9 | P16 Regression guard | pass / violation | safety/ |
| 10 | P55 Execution boundary | authorize / deny | safety/ |
| 11 | P13 Acoustic safety | SAFE / CAUTION / BLOCKED | safety/ |
| 12 | Output gate | ALLOW / BLOCK / WARN | safety/ |
| 13 | GCC runtime | pass / GCCViolationError | safety/ |

### Governance Patterns Pipeline (6 decision points)

| # | Decision Point | Outcomes | Module |
|---|---------------|----------|--------|
| GP1 | Policy Engine | allowed=True/False + violations | safety/governance_patterns/ |
| GP2 | Safety Bounds | clamped magnitude + cooldown | safety/governance_patterns/ |
| GP3 | Plasticity Gate | plasticity [0.27, 1.0] | safety/governance_patterns/ |
| GP4 | Readiness Checker | READY / NOT_READY / DEGRADED | safety/governance_patterns/ |
| GP5 | Approval Manager | PENDING → APPROVED / DISMISSED / EXPIRED | safety/governance_patterns/ |
| GP6 | Rollback Monitor | MONITORING → STABLE / DEGRADED / ROLLED_BACK | safety/governance_patterns/ |

### OLM Bridge (4 risk classifications)

| # | Decision Point | Outcomes | Module |
|---|---------------|----------|--------|
| OLM1 | OLM governance risk | LOW / MODERATE / HIGH / CRITICAL | agentic_framework/ |
| OLM2 | Execution risk detection | 6 cross-layer risk patterns | agentic_framework/ |
| OLM3 | Governance gap detection | per-layer gap/suppressed flags | agentic_framework/ |
| OLM4 | Confidence adjustment | [−0.30, 0.0] penalty | agentic_framework/ |

---

## Audit Logging Locations

| Location | Type | Persistence |
|----------|------|-------------|
| GovernanceService._audit_log | Per-decision events (JEPA + domain + shadow snapshot) | In-memory |
| GovernanceAuditStore | Canonical governance events (shadow in request_snapshot) | Durable (persistent) |
| SafeMCPGateway.audit_log | Per-tool-call entries (JEPA + domain + shadow fields) | In-memory |
| LedgerEntryStore | Hash-chained append-only | Persistent |
| P54 ComplianceAuditRecord | Determinism-hashed records | Per-pipeline-run |
| Posture audit | Posture application records | Per-modulation |
| ApprovalManager.history | Governance decision lifecycle (who/when/why) | In-memory |
| RollbackMonitor.history | Post-action watch verdicts | In-memory |
| PolicyEngine._action_log | Rate-limit action history | In-memory |

Both GovernanceService and SafeMCPGateway persist to `GovernanceAuditStore` when
configured, via `event_from_governance_decision()` and `event_from_mcp_audit()`
respectively. Audit events include full JEPA regime data, domain policy
snapshots, and shadow AI assessment data in `request_snapshot` for durable
forensic analysis. Shadow assessment is embedded via `shadow_assessment` and
`shadow_overrode` fields in `request_snapshot`.

---

## Inter-Module Dependency Graph

```
                    governance_api.py
                         │
                         ▼
                 governance_service.py ──→ governance_audit_store.py
                    │           │
                    │           ├──→ jepa_governance.py
                    │           │        (ontology + vritti → composite → regime)
                    │           │
                    │           ├──→ domain_policy.py
                    │           │        (JEPA assessment → domain mode)
                    │           │
                    │           └──→ shadow_ai.py
                    │                    (provenance + containment → shadow assessment)
                    │
                    ▼           
                 mcp_gateway.py ──→ governance_audit_store.py
                    │
                    ├──→ jepa_governance.py
                    ├──→ domain_policy.py
                    └──→ shadow_ai.py
                    
            confidence_gate  (used by both service and gateway)
            safety_contract  (standalone)
            
            sovereign_bridge → confidence_gate
                 ▲
                 │
            sovereign/  (128D cognitive state tensor)

            olm_bridge → confidence_gate
                 ▲
                 │
            symbolu_core.mechanical.olm/  (12-layer OLM engine)

  SEMANTIC STATE PATH:
    jepa_governance.py  (standalone — no external deps)
      Uses: GovernanceRegime, RuntimeActionCategory, OntologySignal,
            VrittiSignal, JEPACompositeSignal, ResidualSignal
      Produces: JEPAGovernanceAssessment

  DOMAIN POLICY PATH:
    domain_policy.py  (depends on jepa_governance for types)
      Uses: JEPAGovernanceAssessment, GovernanceRegime
      Produces: DomainPolicyResult, DomainActionMode
      Profiles: FINANCE_PROFILE, DEVOPS_PROFILE, RESEARCH_PROFILE

  SHADOW AI PATH:
    shadow_ai.py  (standalone — no external deps)
      Uses: ProvenanceStatus, ShadowRegistry, ShadowPolicyRule
      Produces: ShadowAssessment, ShadowContainmentMode
      Shared: resolve_shadow_asset_id(), is_memory_write_intent()
      Wrapper: safe_resolve_shadow_policy() (fail-closed)

  LEGACY POLICY PATH:
    policy_engine.py → domain_profiles, interaction_modes
    governance_binding.py → symbolu_core.mechanical.p53
    licensing/            → symbolu_core.licensing
    preferences.py        → symbolu_core.service.preferences

  POSTURE PATH:
    posture/ → modulation, audit, governance_readiness
    governance_readiness.py → symbolu_core.mechanical.p51

  LEDGER PATH:
    governance_audit_store.py → GovernanceAuditEvent (durable)
    ledger_store.py → ledger_replay_verifier
    audit_trace.py → symbolu_core.mechanical.p54

  SAFETY PATH:
    gcc_runtime_guard.py  (standalone — phase exit enforcement)
    pipeline_guards/      → symbolu_core.mechanical.p15, p16, p55
    output_gate.py        → symbolu_core.presentation.governed_gate
    acoustic_safety/      → symbolu_core.mechanical.p13
    rate_limiter.py       → symbolu_core.service.security
    escalation_signals.py → symbolu_core.presentation.types

  GOVERNANCE PATTERNS PATH (standalone — no external dependencies):
    governance_patterns/
    ├── policy_engine.py      (standalone)
    ├── safety_bounds.py      (standalone)
    ├── plasticity_gate.py    (standalone)
    ├── readiness_checker.py  (standalone)
    ├── approval_manager.py   (standalone)
    └── rollback_monitor.py   (standalone)
```

---

## Top-Level Package Layout

```
symbolu/                  SHIM   Backwards-compat import redirector
│                                (_SymboluFinder meta-path hook)
│
├── agentic/              GOVERNANCE   5 CORE + 12 INTEGRATE modules
│                                      + governance patterns + OLM bridge
│                                      + JEPA governance + domain policy
│
├── symbolu_core/         SUBSTRATE    17 SUPPLY modules (reasoning engine)
│                                      presentation, mechanical, service, etc.
│
├── cloud_controller/     PRODUCT      Standalone K8s scaling controller
│                                      (separate product, no agentic deps)
│
├── symbolu_extensions/   EXTENSIONS   Experimental / add-on modules
│
└── symbolu_training/     TRAINING     Training data & curriculum
```

---

## JEPA Composite Semantic-Cognitive Signal Layer

**Module:** `agentic_framework/jepa_governance.py`

### What JEPA Is (In This Architecture)

JEPA in the governance context is a **composite semantic-cognitive state layer**,
not a trajectory predictor. It integrates two orthogonal signal structures:

- **Vertical axis: Ontology** — The 12-layer Ontological Layer Model (OLM).
  Each layer carries a weight reflecting its current activation.
  The ontology signal captures *structural position* in the governance hierarchy.

- **Horizontal axis: Vritti** — The 5-mode cognitive distribution (pramana,
  viparyaya, vikalpa, smrti, nidra). The vritti signal captures the *cognitive
  quality* of the current process state.

These are combined into a `JEPACompositeSignal` with:
- `ontology_vritti_alignment` — how well the structural and cognitive signals agree
- `integrated_confidence` — joint confidence from both axes
- `stability` — temporal stability of the composite

### What JEPA Does

The composite is compared against the actual `RuntimeProcessState` (what the
system is actually doing: tool name, action category, risk level, agency level)
to produce a `ResidualSignal` — a measure of semantic-runtime mismatch.

The residual determines the `GovernanceRegime`:

| Regime | Meaning | Governance Effect |
|--------|---------|-------------------|
| NORMAL | Semantic state matches runtime behavior | No override |
| PROCESS_DRIFT | Runtime behavior drifting from semantic state | Degrade: block writes, escalate reads |
| SEMANTIC_SHIFT | Semantic state itself has shifted unexpectedly | Degrade: block writes, escalate reads |
| DUAL_ANOMALY | Both semantic and runtime are anomalous | Hard block |
| UNKNOWN | JEPA check failed or produced no signal | Hard block (fail-closed) |

### What JEPA Is Not

JEPA in this governance layer is **not** a temporal trajectory predictor in the
sense of Meta's JEPA (Joint Embedding Predictive Architecture). The Hybrid
Phase-JEPA training architecture (see `docs/design/HYBRID_PHASE_JEPA_DESIGN.md`)
does implement latent-space prediction for the model training pathway. The
governance layer borrows the name to describe its composite signal integration,
not to claim trajectory forecasting capability.

Future work may add temporal prediction to the governance JEPA layer, but the
current implementation is snapshot-based: it evaluates the current state, not
a predicted future state.

### Key Data Structures

| Type | Purpose |
|------|---------|
| `OntologySignal` | 12-layer weights + primary layer + governance/execution strength |
| `VrittiSignal` | 5-mode distribution + primary vritti + coherence + score |
| `JEPACompositeSignal` | Integrated ontology + vritti + alignment + confidence |
| `RuntimeProcessState` | What is actually happening (tool, action, risk, agency) |
| `ResidualSignal` | Semantic–runtime mismatch magnitude + regime |
| `JEPAGovernanceAssessment` | Full assessment: composite + runtime + residual + regime + overrides |
| `GovernanceRegime` | Enum: NORMAL / PROCESS_DRIFT / SEMANTIC_SHIFT / DUAL_ANOMALY / UNKNOWN |

---

## Domain Semantic Policy Layer

**Module:** `agentic_framework/domain_policy.py`

### Why It Exists

The semantic state layer tells you *what state you are in* (regime, vritti,
ontology, residual). But it does not tell you *what that state means
behaviorally in a specific domain*. A `PROCESS_DRIFT` regime in a financial
services context should block all writes. The same regime in a devops context
might only require draft-mode writes.

The Domain Semantic Policy Layer bridges this gap. It translates general
semantic-cognitive governance signals into domain-specific allowed behavior.

### What It Consumes

- `JEPAGovernanceAssessment` (regime, composite, runtime state, residual)
- Domain profile configuration (declarative data)
- Tool name (for tool-specific permissions)

### What It Produces

- `DomainPolicyResult` with full audit trail:
  - `mode`: the resulting `DomainActionMode`
  - `matrix_mode`, `rule_modes`, `tool_mode`, `threshold_mode`: per-source modes
  - `fired_rules`, `reason_codes`, `rationale`: audit data

### Design Principles

1. **Declarative-first**: Domain profiles are data structures (`DomainProfile`),
   not code. The interpreter is stateless and profile-agnostic.

2. **Fail-closed**: Missing domain, missing rule, or interpretation failure
   produces `BLOCKED`. The `default_mode` on `DomainProfile` is `BLOCKED`.

3. **Stricter-only**: Every evaluation source can only make the result more
   restrictive. The merge uses `_stricter()` (highest severity wins). Domain
   policy can restrict a governance decision but never relax it.

4. **Most-restrictive-match**: Tool permissions use most-restrictive-match
   semantics. A broad `file_*: ALLOW` cannot shadow a narrow
   `file_delete: BLOCKED`.

5. **Domain-adaptive**: The same `DomainPolicyInterpreter` code, different
   behavior per domain. Profiles define the domain's stance.

### DomainActionMode — 7 Modes, 3 Enforcement Tiers

| Mode | Severity | Enforcement Tier |
|------|----------|------------------|
| ALLOW | 0 | Tier A: proceed |
| READ_ONLY | 1 | Tier B: block non-read tools, escalate reads |
| DRAFT_ONLY | 2 | Tier B: block non-read tools, escalate reads |
| CONFIRM_REQUIRED | 3 | Tier B: escalate (require human confirmation) |
| SANDBOX_ONLY | 4 | Tier B: escalate (require human confirmation) |
| MEMORY_WRITE_DENIED | 5 | Tier B: escalate (require human confirmation) |
| BLOCKED | 6 | Tier C: hard block |

Within Tier B, the semantic labels (CONFIRM vs SANDBOX vs MEMORY_WRITE_DENIED)
communicate *intent* to human reviewers and audit consumers, but produce
identical enforcement behavior at the execution layer. See "Current Limitations"
below.

### Built-in Profiles

| Profile | Domain | Key Posture |
|---------|--------|-------------|
| `FINANCE_PROFILE` | Financial services | Destructive always blocked; drift blocks all writes; viparyaya blocked; alignment critical at 0.70 |
| `DEVOPS_PROFILE` | Coding & DevOps | Reads/writes OK in normal; destructive sandboxed; deploy blocked in drift; `db_drop*` always blocked |
| `RESEARCH_PROFILE` | Research & support | Read-heavy; writes draft-only; vikalpa allowed for reads; memory denied on drift |

### Integration Points

- **GovernanceService** (Step 5d): After JEPA override, domain policy is applied.
  Domain can downgrade ALLOW→DEFER or ALLOW→DENY. Domain rationale appears in
  `rationale_codes` (prefix `DOMAIN:`) and `rationale` string. Domain audit dict
  is in `request_snapshot.domain_policy`.

- **SafeMCPGateway** (Steps 5-6): Domain result is computed before JEPA regime
  handling, so it is always present in audit even for non-NORMAL regimes. Domain
  can upgrade JEPA DEFER→DENY (e.g. domain BLOCKED + JEPA DEFER → DENY).

---

## Shadow AI Control Layer

**Module:** `agentic_framework/shadow_ai.py`

### What Shadow AI Means

In agentic systems, not all AI assets (models, tools, plugins, memory stores)
are equally trustworthy. Some are sanctioned and registry-verified. Others are
unverified, experimental, or operating outside their approved semantic-governance
boundary. The distinction between "approved" and "shadow" is not just an
inventory question — it is a **governance state**.

An approved model operating outside its sanctioned domain, or a registered tool
producing outputs inconsistent with its declared capability, behaves like shadow
AI even if it appears in the registry. The Shadow AI Control Layer treats both
provenance problems AND semantic mismatch as shadow AI signals.

### Architectural Position

The Shadow AI Control Layer sits between the Domain Semantic Policy Layer and
the Core Governance/Enforcement Layer (Layer 3 in the stack). It consumes:

- JEPA governance regime (for semantic mismatch scoring)
- Domain policy result (for domain mismatch scoring)
- Asset identity (tool name, actor ID, provider)
- Runtime context (action category, risk level, mutation/memory intent)

It produces:

- `ShadowAssessment` with full provenance, risk, containment, and audit data
- `ShadowContainmentMode` (one of 9 modes)
- Reason codes for audit (prefixed `SHADOW:`)
- Shadow audit dict embedded in `request_snapshot` for durable persistence

### Provenance Model (5 States)

| Status | Meaning | Default Posture |
|--------|---------|-----------------|
| APPROVED | Sanctioned, registry-verified, active | ALLOW (unless semantic mismatch) |
| UNVERIFIED | Not in registry, identity unknown | CONFIRM (mutating) or ALLOW (read-only) |
| SHADOW | Known unsanctioned or domain-violated | BLOCKED (mutating) or READ_ONLY |
| QUARANTINED | Actively flagged, under investigation | BLOCKED (mutating) or QUARANTINED (read-only) |
| REVOKED | Previously approved, now revoked | BLOCKED (always) |

### Trust Levels

| Level | Severity | Meaning |
|-------|----------|---------|
| TRUSTED | 0 | Fully trusted, sanctioned |
| LIMITED | 1 | Partially trusted, some restrictions |
| UNTRUSTED | 2 | Not trusted, significant restrictions |
| BLOCKED | 3 | Blocked, no trust |

### Containment Modes (9 Modes, 3 Governance Tiers)

| Mode | Severity | Governance Tier |
|------|----------|-----------------|
| ALLOW | 0 | Tier A: proceed |
| OBSERVE_ONLY | 1 | Tier B: DEFER |
| READ_ONLY | 2 | Tier B: DEFER |
| DRAFT_ONLY | 3 | Tier B: DEFER |
| SANDBOX_ONLY | 4 | Tier B: DEFER |
| MEMORY_WRITE_DENIED | 5 | Tier B: DEFER |
| REQUIRE_CONFIRMATION | 6 | Tier B: DEFER |
| QUARANTINED | 7 | Tier C: DENY |
| BLOCKED | 8 | Tier C: DENY |

Within Tier B, the 6 intermediate modes produce identical enforcement (DEFER)
but carry distinct semantic labels preserved in audit for human review. The
`ShadowGovernanceMapping` dataclass provides full metadata including the
original containment mode and operational constraint hint.

### Registry Model

`ShadowRegistry` maintains sanctioned AI asset entries (`ShadowRegistryEntry`):

- Exact-match and glob-pattern lookup
- Provider-based lookup
- Per-entry: provenance, trust level, asset type, allowed domains,
  allowed/blocked capabilities, max risk level
- Immutable entries (frozen dataclass), dict copy on init
- Unknown assets return `None`, triggering fail-closed classification

### Risk Factors (13 Visible)

Each `ShadowRiskFactors` instance exposes 13 individually auditable factors:

`provenance_risk`, `identity_confidence`, `domain_mismatch`, `action_risk`,
`tool_risk`, `semantic_governance_mismatch`, `domain_policy_mismatch`,
`hidden_intelligence_path`, `memory_write_risk`, `external_side_effects`,
`execution_privilege`, `unexpected_usage`, `behavioral_anomaly`

These are combined into a weighted `composite_score` but never collapsed
before audit — each factor is individually visible.

### Policy Rules (10 Built-in)

Declarative `ShadowPolicyRule` instances. Conditions left empty are wildcards.
All matching rules fire (stricter-only merge). Built-in rules cover:

1. Unverified/shadow + privileged/destructive → BLOCKED
2. Unapproved MCP server/tool → QUARANTINED
3. Untrusted memory write → MEMORY_WRITE_DENIED
4. Unverified + mutation → REQUIRE_CONFIRMATION
5. Shadow browser AI + finance + mutation → BLOCKED
6. Revoked → BLOCKED (always)
7. Approved + high semantic mismatch → QUARANTINED
8. Unverified + research → READ_ONLY
9. Shadow/unverified + sensitive domain (finance/healthcare/legal) + mutation → BLOCKED
10. Blocked trust level → BLOCKED (always)

### Fail-Closed Behavior

- **Unknown assets:** Classified as SHADOW/UNTRUSTED via heuristic
  (`_classify_unknown_asset()`). Mutating → BLOCKED, read-only → READ_ONLY.
- **QUARANTINED assets:** Mutating → BLOCKED, read-only → QUARANTINED (DENY).
- **Resolver exceptions:** `safe_resolve_shadow_policy()` catches all exceptions
  and returns BLOCKED with `SHADOW_RESOLVER_ERROR` reason code.

### Integration Points

- **GovernanceService** (Step 5e): After domain policy. Uses
  `safe_resolve_shadow_policy()`. Shadow DENY overrides to DENY. Shadow DEFER
  overrides ALLOW to DEFER. Shadow reason codes prefixed `SHADOW:` in rationale.
  Shadow audit dict in `request_snapshot`.

- **SafeMCPGateway** (Step 6b): After domain/JEPA merge. Uses
  `safe_resolve_shadow_policy()`. BLOCKED/QUARANTINED → early return BLOCKED.
  Intermediate modes → early return ESCALATE. Shadow audit in `AuditEntry`.

- **GovernanceAuditStore**: Both `event_from_governance_decision()` and
  `event_from_mcp_audit()` embed shadow assessment and `shadow_overrode` flag
  in `request_snapshot` for durable persistence.

### Shared Helpers

| Function | Purpose |
|----------|---------|
| `resolve_shadow_asset_id(tool_name, actor_id)` | Canonical asset ID resolution (prefers tool_name) |
| `is_memory_write_intent(action_type, tool_name)` | Unified memory-write detection heuristic |
| `safe_resolve_shadow_policy(**kwargs)` | Fail-closed wrapper around `resolve_shadow_policy()` |
| `shadow_containment_to_governance(mode)` | Map containment → ALLOW/DENY/DEFER string |
| `shadow_containment_to_governance_mapping(mode)` | Rich mapping with containment metadata |

### What Shadow AI Is NOT

- Not a marketplace or plugin store
- Not a binary allow/deny list — it is a governance state with graduated posture
- Not purely inventory-based — behavioral mismatch matters, not just registration
- Not an ML detector — it is declarative-first (registry + rules)

---

## Four-Level Governance Logic (Summary)

This section summarizes the four-level governance architecture as a quick
reference.

### Level 1: Semantic State (what state are we in?)

```
  Ontology signal        → 12-layer structural position
  Vritti signal          → 5-mode cognitive quality
  JEPA composite         → integrated confidence + alignment
  Residual signal        → semantic–runtime mismatch
  Governance regime      → NORMAL / PROCESS_DRIFT / SEMANTIC_SHIFT /
                           DUAL_ANOMALY / UNKNOWN
```

### Level 2: Domain Translation (what does that state mean here?)

```
  Domain profiles        → declarative posture per domain
  Action coherence matrix → (regime × action_category) → mode
  Coherence rules        → conditional mode overrides
  Tool permissions       → per-tool mode restrictions
  Domain thresholds      → alignment/confidence/residual gates
  Vritti guard           → block unsafe vritti for writes
```

### Level 3: Shadow AI Control (is this asset trustworthy?)

```
  Provenance status      → APPROVED / UNVERIFIED / SHADOW / QUARANTINED / REVOKED
  Trust level            → TRUSTED / LIMITED / UNTRUSTED / BLOCKED
  Asset registry         → sanctioned lookup with pattern matching
  Risk factors           → 13 individually auditable factors
  Policy rules           → 10 declarative rules (stricter-only merge)
  Containment mode       → 9 graduated modes (ALLOW → … → BLOCKED)
  Semantic mismatch      → approved assets behaving outside boundary
```

### Level 4: Enforcement (what do we do about it?)

```
  GovernanceService      → ALLOW / DENY / DEFER
  SafeMCPGateway         → ALLOWED / BLOCKED / ESCALATE
  SafetyContract         → eligible = True/False
  ConfidenceGate         → ExecutionMode + EscalationLevel
  Escalation             → human-in-the-loop confirmation
  Audit                  → durable + in-memory event persistence
```

---

## Current Limitations

This section documents known gaps between the architecture's semantic design
and its current implementation. These are intentional transparency disclosures,
not bugs.

1. **JEPA is composite state, not temporal prediction.** The governance JEPA
   layer evaluates the *current* semantic-cognitive state snapshot. It does not
   predict future state trajectories. The name "JEPA" reflects the signal
   integration pattern (joint embedding of ontology + vritti), not trajectory
   forecasting. Future temporal prediction may be added.

2. **Domain action modes partially collapse at enforcement.** The 7
   `DomainActionMode` values map to 3 distinct enforcement tiers at the
   execution layer. Within Tier B, `CONFIRM_REQUIRED`, `SANDBOX_ONLY`, and
   `MEMORY_WRITE_DENIED` produce identical enforcement (escalate/block). Within
   Tier B, `READ_ONLY` and `DRAFT_ONLY` produce identical enforcement (block
   non-read tools). The semantic distinctions are preserved in audit and
   rationale for human review.

3. **Shadow containment modes partially collapse at governance.** The 9
   `ShadowContainmentMode` values map to 3 governance tiers: ALLOW (1 mode),
   DENY (2 modes), DEFER (6 modes). The 6 intermediate DEFER modes
   (`OBSERVE_ONLY` through `REQUIRE_CONFIRMATION`) produce identical
   governance enforcement but carry distinct semantic labels for audit.
   `ShadowGovernanceMapping` provides richer metadata for consumers that
   need to differentiate.

4. **Domain and shadow profiles are built-in, not dynamically loadable.** The
   three domain profiles (finance, devops, research) are defined in
   `domain_policy.py`. Shadow registry entries and policy rules are
   configured in code. There is no runtime profile loading, versioning,
   or hot-reload capability. See "Next Productization Layers" below.

5. **GovernanceAuditStore is optional.** When not configured, audit events
   exist only in-memory (`_audit_log` / `audit_log`). Durable persistence
   requires explicit `audit_store` injection at construction time.

6. **Shadow AI is declarative, not ML-based.** The Shadow AI Control Layer
   uses registry lookup and declarative policy rules, not machine learning
   or behavioral analysis. Semantic mismatch detection relies on JEPA
   regime signals, not trained anomaly detectors.

---

## Next Productization Layers (Planned)

> **Status:** Design phase. None of the following layers are implemented.

The following layers represent the next planned productization steps beyond
the current built governance stack. They are listed here for architectural
context and roadmap clarity, not as claims of current capability.

### Layer 6: Policy Control Plane

**Purpose:** Externalize governance policy from code into versioned,
deployable policy bundles.

| Capability | Description |
|------------|-------------|
| **Versioned policy bundles** | Domain profiles, shadow rules, and risk thresholds as versioned configuration artifacts |
| **Scoped overrides** | Per-tenant, per-environment, or per-domain policy overrides without code changes |
| **Policy hot-reload** | Runtime policy updates without service restart |
| **Policy audit trail** | Who changed what policy, when, and why |
| **Policy validation** | Pre-deployment validation that policy changes preserve stricter-only invariants |

**Why it matters:** Currently, domain profiles and shadow rules are defined
in Python source (`domain_policy.py`, `shadow_ai.py`). Productization requires
non-developer policy owners to manage governance posture without code deploys.

### Layer 7: Simulation / Replay Plane

**Purpose:** Enable policy impact analysis before deployment and forensic
replay of past governance decisions.

| Capability | Description |
|------------|-------------|
| **Policy replay** | Replay historical audit events against a new policy bundle to see how decisions would change |
| **What-if analysis** | Simulate a proposed action under current or hypothetical policy to predict the governance outcome |
| **Diff reporting** | Compare governance outcomes between two policy versions across a corpus of historical events |
| **Regression detection** | Flag policy changes that would have changed past DENY → ALLOW (safety regression) |

**Why it matters:** The current `GovernanceAuditStore` and
`LedgerReplayVerifier` provide the data foundation for replay. The simulation
plane adds the interpretation layer that transforms audit data into actionable
policy intelligence.

### Layer 8: Approval Workflow Plane

**Purpose:** Provide durable, structured human-in-the-loop decision
lifecycle for DEFER outcomes.

| Capability | Description |
|------------|-------------|
| **Durable approval requests** | DEFER outcomes persisted as structured approval requests with full context |
| **Human decision lifecycle** | PENDING → APPROVED / DENIED / EXPIRED with who/when/why audit |
| **Delegation & escalation** | Approval routing based on domain, risk level, or asset type |
| **TTL & auto-expiry** | Unanswered approvals expire to DENY (fail-closed) |
| **Approval audit trail** | Full lifecycle captured in GovernanceAuditStore |

**Why it matters:** Currently, DEFER outcomes signal that human confirmation
is needed, but the actual approval workflow (how a human responds, tracks,
and records their decision) is not implemented beyond the `ApprovalManager`
in `governance_patterns/`, which is a standalone in-memory prototype.

### Dependency Order

```
  Layer 6 (Policy Control Plane)
    ↓  enables
  Layer 7 (Simulation / Replay)
    ↓  enables
  Layer 8 (Approval Workflow)
```

Layer 6 is the prerequisite: externalized policy is required before policy
replay or structured approval workflows become meaningful.
