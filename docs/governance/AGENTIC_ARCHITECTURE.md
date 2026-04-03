# Agentic Governance Architecture

## Package Map

```
agentic/
├── agentic_framework/    CORE   Governance orchestration hub
├── safety/               CORE   Hard safety constraints & guards
├── policy/               CORE   Policy evaluation & domain profiles
├── posture/              CORE   Behavioral modulation & readiness
├── ledger/               CORE   Immutable audit trail
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

---

## Audit Logging Locations

| Location | Type | Persistence |
|----------|------|-------------|
| GovernanceService._audit_log | Per-decision structured events | In-memory |
| SafeMCPGateway.audit_log | Per-tool-call entries | In-memory |
| LedgerEntryStore | Hash-chained append-only | Persistent |
| P54 ComplianceAuditRecord | Determinism-hashed records | Per-pipeline-run |
| Posture audit | Posture application records | Per-modulation |

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


  POLICY PATH:
    policy_engine.py → domain_profiles, interaction_modes
    governance_binding.py → symbolu_core.mechanical.p53

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
```
