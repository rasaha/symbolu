# Clearance Chain Reconstruction

The governance-chain record is extended with the Action Clearance stage:

- clearance stage state, `ClearanceRequest` fingerprint, `ClearanceResult` id/fingerprint,
  `ClearanceStatus`, reason codes, signal refs, clearance policy ref/version, `evaluated_at`,
  `valid_until`, effective constraints/obligations;
- intervention-assessment ref/fingerprint, `human_intervention_required`, required authorities;
- `execution_status = DISABLED`.

## Verification

Reconstruction verifies tenant consistency, workflow-revision consistency,
prepared-action consistency, ActionGate authorization consistency, Action Clearance
request/result linkage, exact-action fingerprint consistency, signal bindings and
fingerprints, policy references, validity fields, intervention-assessment linkage, and
that execution remains disabled. Clearance-specific failures surface as issues:
`CLEARANCE_REFERENCE_MISSING`, `CLEARANCE_FINGERPRINT_MISMATCH`,
`SIGNAL_REFERENCE_MISMATCH`, `INTERVENTION_ASSESSMENT_MISMATCH`, `CLEARANCE_STALE`.

## Semantics

A current shadow workflow reconstructs **COMPLETE** when either:

- ActionGate authorized **and** Action Clearance was evaluated correctly; or
- ActionGate did **not** authorize **and** the chain records Action Clearance as
  `NOT_EVALUATED_UPSTREAM_NOT_AUTHORIZED` (no fabricated result).

A chain is **INCOMPLETE** when ActionGate authorized, clearance evaluation was required,
but the request/result record is absent. A superseded head SHA reconstructs **STALE**
(historical but fully linked). Historical records are never mutated.
