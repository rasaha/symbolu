# Ugence Risk Authority Runtime Assurance (RA-7)

**RA-7 OBSERVES AND ASSESSES. RA-6 OWNS AUTHORITY CONSEQUENCES.**

RA-7 is the **missing producer** of the neutral `AuthorityReassessmentSignal`
that the fully-built RA-6 seam already consumes. It observes the Agent Runtime
through the existing neutral event seam, risk-types the per-workflow-instance
*trajectory*, and — on a *material* deviation — emits a neutral signal into the
RA-6 intake. RA-6 decides and enacts the authority consequence.

`RiskAuthorizationEnvelope` (Ed25519) remains the **sole** signed machine-authority
artifact. RA-7 mints nothing, mutates no lifecycle state, and cannot trigger
emergency stop — it is **not** a second authority layer.

Ratified spec: [`docs/architecture/RISK_AUTHORITY_RA7_SPEC.md`](../../../docs/architecture/RISK_AUTHORITY_RA7_SPEC.md)
(ADR ratification commit `4d2776e7`). As-built:
[`docs/architecture/RA7_RUNTIME_ASSURANCE_AS_BUILT.md`](../../../docs/architecture/RA7_RUNTIME_ASSURANCE_AS_BUILT.md).

## Flow

```
runtime event / external telemetry
    → TrustedTelemetryIngress            trust boundary; reject wrong tenant/workflow/envelope (§10/D7)
    → RuntimeAssuranceObserver           bounded per-(tenant, workflow) trajectory; dedupe/re-sequence (§11,§13)
    → SafeEvaluator(ReferenceTrajectoryEvaluator)  deterministic sequence-risk rules (§6,§12)
    → TrajectoryAssessment   NORMAL / ESCALATED / UNKNOWN     (evidence, not authority)
    → if material ESCALATED →
    → AuthorityReassessmentSignal(RUNTIME_RISK_ESCALATED, target=ENVELOPE)
    → AuthorityReassessmentSignalPort.submit   (RA-6 intake — reused as-is; §15,§18)
    → RA-6 reassessor → sole authenticated writer → targeted revoke / no-op
    → StatusAwareActionGate / pre-effect recheck enforce at the next consequential commit
```

## Dependency direction (one-way)

```
risk_authority (stdlib-only leaf)             neutral signal + intake port
      ▲
ugence-risk-authority-status-runtime (RA-6)   reassessor + sole writer
      ▲
ugence-risk-authority-runtime-assurance (RA-7, this package)
      │  observes ▼ (neutral duck-typed event contract only)
agent-runtime                                 never imports Risk Authority
```

RA-7 depends **only** on the RA leaf and the RA-6 status runtime. It never imports
the Agent Runtime; it observes it through a neutral `.seq`/`.type`/`.detail` event
contract (`RuntimeEventAdapter`). No database / framework / event-bus dependency.

## Sequence-level risk (D3)

RA-7 does not duplicate the Agent Runtime portfolio ledger — it **reads** cumulative
exposure carried on observations and **risk-types** it. Deterministic, explainable
rules (no weighted score that converts to authority):
`CUMULATIVE_EXPOSURE`, `NEAR_BOUNDARY_REPEAT`, `RETRY_LOOP`,
`DATA_CLASS_PROGRESSION`, `CONTEXT_EXPANSION`, `MODEL_BEHAVIOR_CHANGED`.

## Assurance-required (D4, opt-in)

By default RA-7 is **additive and event-driven** — an observer/ingress being
unavailable never blocks the runtime hot path. The opt-in `assurance_required`
pre-effect gate (`RuntimeAssuranceService.pre_effect_assurance_decision`) fails
closed (`ERROR_NON_EXECUTABLE` / `DENY_IF_ASSURANCE_REQUIRED`) when current
assurance is absent / stale / not-`NORMAL`. Read-only; grants no authority.

## Reference vs production

The reference ingress authenticator, policy reader, and evaluator are clearly
marked `is_reference_*`. Production composition (`production_mode=True`) **refuses**
them (RA-5/RA-6 F-1) so a permissive stand-in can never silently produce unsafe
assurance. Persistence is a bounded in-memory window only — no second execution
ledger.

## Build & verify

```
python -m build packages/integration/risk-authority-runtime-assurance
python packages/integration/risk-authority-runtime-assurance/scripts/verify_isolated_install.py
```

## Maturity (no overclaim)

Event-driven, reference-grade runtime assurance. **Not** continuous real-time
authorization, zero-window revocation, cryptographically-attested telemetry, ACP
physical-control safety, or RA-8 post-effect reconciliation. Revocation bites at
the next pre-effect recheck — bounded-latency, not instantaneous.
