# Changelog — ugence-reasoning-method-result-attestation

## 0.1.0 — 2026-09-06 — the contracts-only slice (SCR-1)

Ratified by `docs/architecture/ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING.md`.
Mirrors `ugence-risk-authority-effect-attestation` 0.2.0 file for file, with the
wrapped object, the role and the reconciliation facts changed. **REFERENCE-GRADE /
NOT PRODUCTION-READY.** No key for any comparison engine exists.

### Added

- `SignedComparisonResult`: an immutable wrapper over one unmodified
  `ReadinessComparisonResult`. The signed projection carries the result's identity
  fields, the instant it was produced and its `result_digest` **recomputed through
  the governance contract**; a result whose self-digest was altered after
  construction is refused at wrap time and at every read.
- `ComparisonResultAttesterRole.COMPARISON_ENGINE`, resolved under the Trusted
  Evidence Authority's lent `TrustAnchorCapability.COMPARISON_RESULT_ATTESTATION`
  (TEA 0.6.0). Under it the signer identity must equal the result's own
  `engine_identity`; a signer speaking for another identity cannot sign a result
  as its engine.
- `Ed25519ComparisonResultVerifier` and its pure
  `ComparisonResultVerificationResult`; `production_mode=True` refuses the
  reference resolver and every subclass, admits a declaring resolver and refuses
  before consulting one whose posture is not `True` (TW-1 to TW-3, as in the effect
  package).
- `ComparisonResultSignerPort`, `ReferenceEd25519ComparisonResultSigner` (seed-derived,
  refused in production) and `sign_comparison_result`.
- Twenty-six refusal reasons: the effect package's vocabulary with
  `WRONG_ENGINE_IDENTITY` and `RESULT_MISMATCH` in place of the tenant and
  observation reasons.

### Measured

- Suite: 160 tests, all passing in a clean editable install.
- Mutation sweep: 38 gates inventoried, 34 killed, 4 survivors, every one classified
  (three equivalent defence-in-depth checks shared with the effect package, and the
  role-mismatch gate, unreachable while the role vocabulary has one member; see
  `mutation_ledger.json`).
- Isolated install: phases A–D pass; the installed API equals `public_api.json`
  symbol for symbol and the pinned vectors reproduce inside the wheel.
