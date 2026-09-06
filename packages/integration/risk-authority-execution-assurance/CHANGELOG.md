# Changelog — ugence-risk-authority-execution-assurance

## 0.3.0 — 2026-09-06 — trust-state refusals surfaced (TW-5)

Ratified by `docs/architecture/ADR_UGENCE_TR5_EFFECT_ATTESTATION_RESOLVER_WIRING.md`.
Additive over 0.2.0. **No admission rule changes**, and RA-8 remains
REFERENCE-GRADE / NOT PRODUCTION-READY and unwired to any production resolver.

### Added

- `TRUST_STATE_REFUSALS`: the two attestation refusal values that describe trust
  state rather than the attestation — `ANCHOR_SET_STALE` (publish a newer
  trust-anchor snapshot) and `ANCHOR_SET_UNAVAILABLE` (the trust state could not
  be consulted). `admit_attested` already carried the verifier's typed reason
  through; these now arrive distinguishable from each other and from a
  misbehaving resolver, instead of all three reading as one reason.

### Changed

- Dependency floor: `ugence-risk-authority-effect-attestation>=0.2.0`, the
  release that first defines the two reasons.

### Unchanged

Every RI-1 to RI-5 rule: the attested entry point and its order, the production
refusal of unattested observations, the observer-gated production `MATCHED`,
typed provenance outside `effect_digest`, the injected instant, and every
existing binding, domain, exact-`True` and F-1 refusal. A trust-state refusal
rejects exactly as every other refusal does; the distinction is for the
operator, never for the admission decision.

Measured figures are re-run, never edited. Maturity is stated on every entry.

## 0.2.0 — 2026-09-06 — attested ingress (RI-1 to RI-5)

Ratified by `docs/architecture/ADR_UGENCE_RA8_EFFECT_ATTESTATION_INTEGRATION.md`.
**REFERENCE-GRADE / NOT PRODUCTION-READY.** Production wiring is blocked until
the Trusted Evidence Authority ships a production `TrustAnchorResolverPort`
(RI-4); no production resolver, signer, key custody, anchor publication, KMS/HSM,
connector, gateway, LIVE execution or credential is added here.

### Added

- `TrustedEffectIngress.admit_attested(attestation, correlation=, as_of=, observation_id=, ...)`
  (RI-1): verifies the exact wrapped `ExecutionObservation` under the attester's
  declared role and anchor through the injected
  `EffectAttestationVerifierPort`, binds the tenant from the governed
  correlation, normalizes only after `VERIFIED`, stamps typed provenance, then
  runs the unchanged binding, domain and authentication checks. Every
  non-`VERIFIED` disposition rejects with the verifier's typed reason.
- `TrustedEffectIngress(..., attestation_verifier=)`; in production the verifier
  must itself state `production_mode is True` (RI-4), else
  `AttestationVerifierRejectedError`.
- `EffectAttestationProvenance` and `EffectObservation.provenance` (RI-3): role,
  identity, key id, observation digest, signing-payload digest, anchor revision
  and the injected verification instant, as a typed value outside
  `effect_digest`.
- `production_matched_gate` / `independent_observer_supports` and reason code
  `INDEPENDENT_OBSERVER_REQUIRED` (RI-3): in production a `MATCHED` aggregate is
  withheld to `UNVERIFIABLE` unless an admitted observation carries verified
  independent-observer provenance with a favorable final outcome. All other
  verdicts pass through.
- `EffectAssuranceService.assess(..., attested=, verification_instant=)` and
  `AttestedEffectInput` (RI-5): the instant is injected explicitly; `produced_at`
  and the attestation's own `attested_at` are never used as it.
- Typed ingress reason constants: `UNATTESTED_REFUSED_IN_PRODUCTION`,
  `INVALID_VERIFICATION_INSTANT`, `ATTESTATION_REFUSED`,
  `ATTESTATION_VERIFIER_FAULT`, `NO_ATTESTATION_VERIFIER`.

### Changed

- `TrustedEffectIngress.admit` (the unsigned path) under `production_mode=True`
  still runs the unchanged checks and rejects for their reasons, and rejects an
  observation they would have admitted with `UNATTESTED_REFUSED_IN_PRODUCTION`
  (RI-2). Reference grade is unchanged.
- Dependencies: `ugence-governance-contracts>=0.8.0` (the floor the attestation
  package requires) and `ugence-risk-authority-effect-attestation>=0.1.0`.

### Unchanged

`EffectSourceAuthenticator.authenticate`, exact-`True` admission, authenticator
fault fails closed, reference authenticator refused in production (F-1),
production service requires a production ingress (F-2), `effect_digest` as a
content digest, Decision Authority records, `ExecutionObservation`.

### Measured

See the pull request that introduced this version for the exact figures of the
RA-8, effect-attestation and Trusted Evidence Authority suites, the mutation
sweep and the distribution verifier.

## 0.1.0 — RA-8 reference milestone

Post-effect execution/effect reconciliation over the Decision Authority kernel,
non-compensatory aggregation (M-1), `EXECUTION_EFFECT_MISMATCH` handoff into RA-6.
Effect-source trust is authenticated ingress plus content integrity; per-receipt
signing was FUTURE.
