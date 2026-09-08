# Changelog — ugence-risk-authority-effect-attestation

## [Unreleased] — the suite runs on Python 3.10, which this package already declared

No source change and no API change: `src/` is untouched and nothing about the package's
behaviour moves. The packaging/boundary test read `pyproject.toml` with a bare
`import tomllib`, stdlib only from 3.11 — so the whole module failed to import on 3.10
and, with every CI job pinned to 3.11, nothing ever noticed that
`requires-python >= 3.10` was a claim no job checked. The import now falls back to the
`tomli` backport, and the workflow's suite job runs the full matrix 3.10, 3.11, 3.12.
The fallback is a hard import rather than `pytest.importorskip`: a missing backport must
fail the run loudly, not quietly drop the packaging assertions from the 3.10 leg.

## 0.2.0 — 2026-09-06 — distinguishable trust state (TW-1 to TW-3)

Ratified by `docs/architecture/ADR_UGENCE_TR5_EFFECT_ATTESTATION_RESOLVER_WIRING.md`.
Additive over 0.1.0: every existing symbol, refusal, digest and pinned vector is
unchanged, and the wrapper, roles, canonical form and D-41 pair are untouched.
**REFERENCE-GRADE.** The signed-snapshot resolver this can now be wired to
remains a production-shaped candidate only; no deployment is wired here.

### Added

- Two appended refusal reasons (TW-1), taking the vocabulary from 24 to 26:
  `ANCHOR_SET_UNAVAILABLE` (the trust-anchor set could not be consulted at the
  caller's instant) and `ANCHOR_SET_STALE` (it was admitted but is no longer
  fresh). TEA's `TRUST_ANCHOR_SET_UNAVAILABLE` and `TRUST_ANCHOR_SET_STALE` map
  one-to-one onto them through the exported `TRUST_ANCHOR_SET_REASONS`, so
  D-28's ratified distinction survives instead of collapsing into
  `ANCHOR_UNAVAILABLE`. `TRUST_ANCHOR_MISSING` and `TRUST_ANCHOR_NOT_CONFIGURED`
  still map to `ANCHOR_UNKNOWN`; every other TEA reason still falls to
  `ANCHOR_UNAVAILABLE`.
- `resolver_serves_production` and `declares_production_posture` (TW-3): a
  resolver **declares** the production contract by carrying
  `is_production_authoritative` as an exact `bool`, and separately **is able to
  serve** when that value is `True`.

### Changed

- `require_production_resolver` admits a resolver that declares the contract
  either way, so a snapshot that failed to load is a typed refusal rather than a
  crashed composition root (TW-3). Absent, non-`bool` and reference-grade
  resolvers are refused exactly as before, and `DenyAllTrustAnchorDirectory` is
  still admitted by exact type under E-8.
- The verifier refuses `ANCHOR_SET_UNAVAILABLE` **before consulting** any
  declaring resolver whose posture is not `True`, so admitting one can never
  yield an anchor. The deny-all directory declares no posture and keeps its
  ratified `ANCHOR_UNKNOWN`.
- Dependency floor: `ugence-trusted-evidence-authority>=0.5.0`, the release that
  first defines the two trust-anchor-set reasons.

### Not changed

`TRUST_ANCHOR_SET_INSTANT_REQUIRED` mints no member (TW-2): a bad `as_of` raises
at the caller seam, and a resolver returning it despite being handed a valid
instant is a resolver fault. No composition-root module reads a snapshot file
(TW-4); the ban on `open`, `os` and `pathlib` stands.

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
