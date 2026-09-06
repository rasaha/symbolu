# Changelog — ugence-risk-authority-effect-attestation

All measured figures below are re-run, never edited. Maturity is stated on
every entry and never rises by wording.

## 0.1.0 — 2026-09-06 — first slice, contracts and verification only

Scoped by `docs/architecture/ADR_UGENCE_SIGNED_EFFECT_ATTESTATION_SCOPING.md`
(SE-1 to SE-5). **REFERENCE-GRADE / NOT PRODUCTION-READY. Not wired into RA-8.**

### Added

- `EffectAttestation`: an immutable wrapper binding one complete, unmodified
  governance-contracts `ExecutionObservation` with attester identity, role,
  key reference, algorithm, schema/domain version and signature (SE-3).
- `EffectAttesterRole` with `EXECUTING_PROVIDER` and `INDEPENDENT_OBSERVER`,
  each mapped to its own Trusted Evidence Authority capability; the role is
  inside the signed bytes and an anchor for one role refuses the other (SE-2).
- Deterministic canonical payload (sorted keys, compact separators, NFC-only
  text, exact types, UTC microsecond instants) and the domain-separated frame
  `uint32_be(len(domain)) || domain || canonical_json`.
- `EffectAttestationVerifierPort` and `Ed25519EffectAttestationVerifier`:
  resolves through TEA's `TrustAnchorResolverPort` at the exact
  `(identity, key_id, role capability)` coordinate (SE-4) and verifies through
  TEA's strictly validated Ed25519 key, the D-41 pair with the libsodium point
  check (SE-5). Returns a typed, pure result; never raises for invalid input.
- `EffectAttestationVerificationResult` with twenty-four typed refusal reasons;
  `establishes` is always `PROVENANCE_AND_INTEGRITY_ONLY` and
  `factual_correctness_established` is permanently `False`.
- `ReferenceEd25519EffectAttestationSigner` and `mint_effect_attestation`, for
  tests and local composition only; refused under `production_mode=True`.
- `require_production_resolver`: the reference `StaticTrustAnchorDirectory`
  and every subclass are refused in production.
- `scripts/verify_isolated_install.py` (isolated, offline install proof),
  `scripts/mutation_sweep.py` (measured gate-deletion sweep, ledger in
  `mutation_ledger.json`) and `scripts/generate_public_api.py`.

### Not in this slice

No RA-8 integration, no Third-Party Gateway (FUTURE), no production signer,
no KMS/HSM, no key loading or generation, no network, filesystem,
environment-variable, credential or discovery code, no LIVE execution.
`ExecutionObservation` is unchanged. This slice cannot make RA-8
production-ready.

### Measured (2026-09-06, this machine; CI re-runs every figure)

- package suite: 133 passed (`tests/`, from the package directory)
- mutation sweep: 30 gates inventoried, 27 killed, 3 survived, all 3 classified
  `EQUIVALENT_DEFENSE_IN_DEPTH` (G-12, G-15, G-19) in `mutation_ledger.json`
- isolated install: 11 steps passed; phase B installed `--no-index` from a local
  wheelhouse with no monorepo path; the pinned digests and the reference
  signature reproduce inside the installed wheel
- wheel: the twelve package modules and `py.typed` only; declares exactly
  `ugence-governance-contracts>=0.8.0` and `ugence-trusted-evidence-authority>=0.4.0`
- neighbouring baselines: Trusted Evidence Authority 1215 passed;
  5B-0A producer attestation 458 passed, 3 skipped; RA-8 execution assurance
  177 passed, untouched
- repository: import-boundary and package-CI-coverage suites 38 passed;
  terminology validator PASS; doc-link checker PASS
