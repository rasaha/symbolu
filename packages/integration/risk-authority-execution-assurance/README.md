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

## Attested ingress (RI-1 to RI-5) — 0.2.0

Ratified by `docs/architecture/ADR_UGENCE_RA8_EFFECT_ATTESTATION_INTEGRATION.md`,
built on `ugence-risk-authority-effect-attestation`.

```
EffectAttestation (signed wrapper over an unmodified ExecutionObservation)
    → TrustedEffectIngress.admit_attested(attestation, correlation=, as_of=, observation_id=)
        1. as_of must be an aware datetime, injected — else reject, resolver never asked (RI-5)
        2. exact types: EffectAttestation, ExecutionCorrelation; a verifier must be configured
        3. verifier: exact wrapped observation, tenant from the governed correlation,
           attester's declared role and anchor → VERIFIED, and only VERIFIED, passes (RI-1)
        4. normalize from the governed correlation; stamp typed EffectAttestationProvenance
        5. the unchanged checks: binding, domain, producer authentication
    → assess(..., attested=[AttestedEffectInput(...)], verification_instant=as_of)
        production: MATCHED requires verified INDEPENDENT_OBSERVER provenance on an admitted,
        favorable, final observation; otherwise UNVERIFIABLE / INDEPENDENT_OBSERVER_REQUIRED (RI-3)
```

- **RI-2** In production the unsigned path `admit` rejects every observation.
  Unsigned evidence is admissible only under the labelled reference-grade posture.
- **RI-3** An executing-provider attestation is provider provenance only. It can
  surface `MISMATCH` and every other adverse verdict; it can never make a
  production `MATCHED` reachable. Roles and anchors are non-interchangeable.
- **RI-4** Production wiring is **blocked**: a production ingress requires a
  verifier in production posture, which refuses TEA's `StaticTrustAnchorDirectory`;
  the only admissible resolver in this repository, `DenyAllTrustAnchorDirectory`,
  refuses every anchor. No production resolver, anchor publication, signer, key
  custody or KMS/HSM is provided here. No production `MATCHED` flow exists.
- **RI-5** `produced_at` is the assessment timestamp and an attestation's
  `attested_at` is the attester's claim; neither is the verification instant.
- A verified attestation proves provenance and integrity, never that the effect
  occurred. `effect_digest` remains a content digest; the role travels only in the
  typed provenance, never in `source`, `source_version` or reason text.

## Maturity (no overclaim)

Reference-grade post-effect reconciliation. **NOT PRODUCTION-READY.** Effect-source
trust is **authenticated / delegated ingress + content-hash integrity** on the
unsigned reference path (integrity ≠ authenticity; a hash is not a signature), and
**signed effect attestation** on the attested path, which establishes provenance
and integrity only. Persistence is **delegated to Decision Authority**. The
reference effect authenticator, the reference DA reconciler and the reference
trust-anchor directory are **refused in production** (the RA-5/6/7 F-1 pattern).
Production effect-attestation wiring is blocked on the Trusted Evidence Authority's
production resolver milestone (RI-4). This is **NOT** a production Third-Party
Gateway, globally-distributed effect observation, cryptographically-attested
physical-world truth, zero-window correction, ACP, or GRC.

## Develop / test / verify

```bash
# Source tests (needs pydantic for the reused Decision Authority kernel, and the
# Trusted Evidence Authority's Ed25519 backends for the attested path):
pip install pytest pydantic "cryptography>=41.0.7,<47.0.0" "PyNaCl>=1.5.0,<2.0.0"
python -m pytest packages/integration/risk-authority-execution-assurance/tests -q

# Build + isolated-install proof (first-party wheels; index only for pydantic):
python packages/integration/risk-authority-execution-assurance/scripts/verify_isolated_install.py
```
