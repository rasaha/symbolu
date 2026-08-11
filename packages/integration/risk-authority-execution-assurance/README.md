# Ugence Risk Authority Execution Assurance (RA-8)

**Post-execution effect / reconciliation assurance.** RA-8 answers one question:

> *After an authorized action executes, did the actual execution and resulting
> effect match what was authorized and expected — and if not, should that
> discrepancy cause future machine authority to be reassessed?*

**RA-8 OBSERVES, CORRELATES, AGGREGATES, AND ASSESSES POST-EFFECT. RA-6 OWNS
AUTHORITY CONSEQUENCES.** RA-8 emits *evidence and a neutral reassessment signal* —
never authority. `RiskAuthorizationEnvelope` remains the sole signed machine
authority; Decision Authority remains the sole owner of execution/reconciliation
records. RA-8 introduces **no second authority artifact** and **no third execution
ledger**.

See the ratified specification: `docs/architecture/RISK_AUTHORITY_RA8_SPEC.md`,
the ADR `docs/architecture/ADR_RISK_AUTHORITY_RA8_EXECUTION_EFFECT_RECONCILIATION.md`,
and the as-built record `docs/architecture/RA8_EXECUTION_ASSURANCE_AS_BUILT.md`.

## Flow

```
governed authority context + Agent Runtime attempt
    → ExecutionCorrelation            bind (tenant, workflow, envelope, action digest, attempt)
    → TrustedEffectIngress            trust boundary (reference authenticator refused in prod)
    → DecisionAuthorityReconciler     reuse DA ExecutionIntent/Attempt/Record/Reconcile
    → safe_aggregate (non-compensatory)   close M-1: favorable cannot mask unfavorable
    → EffectAssuranceAssessment       neutral verdict: MATCHED / MISMATCH / PARTIAL /
                                      UNKNOWN / MANUAL_REVIEW / CONFLICTED / UNVERIFIABLE
    → EffectAssuranceSignalEmitter    material only → AuthorityReassessmentSignal(EXECUTION_EFFECT_MISMATCH)
    → AuthorityReassessmentSignalPort.submit   (RA-6 intake, reused as-is)
    → RA-6 reassessor → sole authenticated writer → targeted revoke / epoch / no-op
```

## Dependency direction (one-way)

```
risk_authority (stdlib-only leaf)            neutral signal + intake port
    ▲
ugence-risk-authority-status-runtime (RA-6)  reassessor + sole writer
    ▲
ugence-risk-authority-execution-assurance (RA-8, this package)
    ├─► ugence-decision-authority            reconciliation kernel (reused)
    └─► ugence-governance-contracts          neutral effect-observation seam
    ··· observes agent-runtime via a neutral, duck-typed event contract (no AR dependency)
```

`pydantic` enters only as a transitive dependency of Decision Authority; RA-8
defines no pydantic models of its own. The Agent Runtime never imports Risk
Authority or Decision Authority; Decision Authority imports neither; the RA leaf
stays stdlib-only.

## The M-1 closure (the security kernel)

Decision Authority's internal `_compare` keys the primary-outcome verdict off
`records[-1]` (latest-wins), so a later favorable record can mask an earlier
material unfavorable one. DA stays reusable by non-RA products; **RA-8 owns the
safe aggregation** (`aggregation.safe_aggregate`) over the *full* record set,
applied before trusting any single-record verdict:

- a material unfavorable **final** effect can never be masked by a later favorable
  record of a *different* effect identity;
- supersession is explicit and narrow — a later record supersedes an earlier one
  **only** when they share the same effect identity and it is a `PARTIAL → FINAL`
  update (no last-writer-wins);
- conflicting trusted observers → `CONFLICTED`; duplicate distinct real effects →
  `MANUAL_REVIEW`; not-yet-final → `PARTIAL`/`UNKNOWN`, never a premature `MATCHED`
  or a fabricated failure.

No failure, malformed input, wrong binding, replay, or conflict ever becomes
`MATCHED`. A false RA-8 mismatch can cost availability but can never widen
authority (RA-6's worst consequence is restriction, never a grant).

## Maturity (no overclaim)

Reference-grade post-effect reconciliation. Effect-source trust is
**authenticated / delegated ingress + content-hash integrity** (integrity ≠
authenticity; a hash is not a signature). Persistence is **delegated to Decision
Authority**. The reference effect authenticator and the reference DA reconciler are
**refused in production** (the RA-5/6/7 F-1 pattern). This is **NOT** a production
Third-Party Gateway, signed external receipts / attestations, globally-distributed
effect observation, cryptographically-attested physical-world truth, zero-window
correction, ACP, or GRC.

## Develop / test / verify

```bash
# Source tests (needs pydantic for the reused Decision Authority kernel):
pip install pytest pydantic
python -m pytest packages/integration/risk-authority-execution-assurance/tests -q

# Build + isolated-install proof (first-party wheels; index only for pydantic):
python packages/integration/risk-authority-execution-assurance/scripts/verify_isolated_install.py
```
