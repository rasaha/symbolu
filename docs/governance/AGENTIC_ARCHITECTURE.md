# Agentic Governance Architecture

## Package Map

```
agentic/
├── agentic_framework/    CORE   Governance orchestration hub
│   ├── governance_service.py      9-step authorization engine
│   ├── confidence_gate.py         Confidence evaluation & gating
│   ├── mcp_gateway.py             Safe MCP tool execution gateway
│   ├── safety_contract.py         7-precondition safety contract
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
│   9-Step Authorization Engine                                    │
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
│  │ Step 5: DECISION MERGE                                   │    │
│  │                                                           │    │
│  │   forbidden_cap ──────────────────────────────▶ DENY      │    │
│  │   not eligible ───────────────────────────────▶ DENY      │    │
│  │   BLOCKED execution mode ─────────────────────▶ DENY      │    │
│  │   requires_human (CONFIRM/HALT) ──────────────▶ DEFER     │    │
│  │   all passed ─────────────────────────────────▶ ALLOW     │    │
│  │                                                           │    │
│  └────────────────────┬─────────────────────────────────────┘    │
│                       ▼                                          │
│  Steps 6-9: Build rationale → confidence summary →               │
│             audit event → assemble AuthorizationResponse         │
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
  ┌─ Step 4: Min confidence ────▶ BLOCKED ───────┐
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 5: Escalation ───────▶ CONFIRM/HALT ──┐
  │  NOTIFY: inform human (non-blocking)          │
  │  CONFIRM: request approval → deny/timeout     │
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 6: Execute tool ──────────────────────┐
  │  mcp_client.call_tool() with timeout         │
  │  → ALLOWED / TIMEOUT / ERROR                 │
  └──────────┬───────────────────────────────────┘
             ▼
  ┌─ Step 7: Audit ────────────────────────────┐
  │  Append AuditEntry to audit_log             │
  └─────────────────────────────────────────────┘
```

---

## Decision Points Summary

### Core Governance Pipeline (13 decision points)

| # | Decision Point | Outcomes | Module |
|---|---------------|----------|--------|
| 1 | P51 Readiness | READY / CONDITIONAL / NOT_READY | posture/ |
| 2 | Forbidden capability | DENY (hard block) | agentic_framework/ |
| 3 | Confidence gate mode | FULL / CAUTIOUS / CONFIRM / BLOCKED | agentic_framework/ |
| 4 | Confidence escalation | NONE / NOTIFY / CONFIRM / HALT | agentic_framework/ |
| 5 | Safety contract (7 checks) | eligible=True/False | agentic_framework/ |
| 6 | Governance merge | **ALLOW / DENY / DEFER** | agentic_framework/ |
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
| GovernanceService._audit_log | Per-decision structured events | In-memory |
| SafeMCPGateway.audit_log | Per-tool-call entries | In-memory |
| LedgerEntryStore | Hash-chained append-only | Persistent |
| P54 ComplianceAuditRecord | Determinism-hashed records | Per-pipeline-run |
| Posture audit | Posture application records | Per-modulation |
| ApprovalManager.history | Governance decision lifecycle (who/when/why) | In-memory |
| RollbackMonitor.history | Post-action watch verdicts | In-memory |
| PolicyEngine._action_log | Rate-limit action history | In-memory |

---

## Inter-Module Dependency Graph

```
                    governance_api.py
                         │
                         ▼
                 governance_service.py
                    │           │
                    ▼           ▼
            confidence_gate  mcp_gateway
                    ▲           │
                    │           ▼
                    └── confidence_gate
                    
            safety_contract  (standalone)
            
            sovereign_bridge → confidence_gate
                 ▲
                 │
            sovereign/  (128D cognitive state tensor)

            olm_bridge → confidence_gate
                 ▲
                 │
            symbolu_core.mechanical.olm/  (12-layer OLM engine)


  POLICY PATH:
    policy_engine.py → domain_profiles, interaction_modes
    governance_binding.py → symbolu_core.mechanical.p53
    licensing/            → symbolu_core.licensing
    preferences.py        → symbolu_core.service.preferences

  POSTURE PATH:
    posture/ → modulation, audit, governance_readiness
    governance_readiness.py → symbolu_core.mechanical.p51

  LEDGER PATH:
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
