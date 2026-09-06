# Ugence signed external-effect verification — scoping record and ratification

**Status:** ratified 2026-09-06 by the repository owner (rulings SE-1 to SE-5
below). Sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md`
(wave 5, row "Signed external-effect verification": "RA-8 successor milestone;
Trusted Evidence Authority DD-10b custody"). The rulings authorize one new
contracts-first package, `packages/integration/risk-authority-effect-attestation`,
two lent capabilities in the Trusted Evidence Authority, and nothing beyond them.

Evidence labels: `[V]` verified against this repository at commit `5d602fdb`,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

RA-8 shipped post-effect reconciliation with effect-source trust that is
explicitly **not** cryptographic. What does the ratified successor add, and where
does it live? **A signed attestation over an observation, verified against the
Trusted Evidence Authority's anchors under purpose-specific roles, in a new
package that neither reconciles nor observes.** Everything else in the row —
the connector layer, receipt acquisition, RA-8 wiring — stays where the
repository already put it: FUTURE or later.

## 2 — What the repository fixed before these rulings

| Finding | Where |
|---|---|
| RA-8 exists at 0.1.0 as reference-grade post-effect reconciliation, emitting `EXECUTION_EFFECT_MISMATCH` into RA-6 `[V]` | `packages/integration/risk-authority-execution-assurance/README.md:1-32` |
| Its effect-source trust is "authenticated / delegated ingress + content-hash integrity (integrity ≠ authenticity; a hash is not a signature)"; per-receipt signing is ruled FUTURE, not a reference precondition `[V]` | `docs/architecture/RISK_AUTHORITY_RA8_SPEC.md:160-171,505`; RA-8 ADR D-A |
| The seam a successor replaces is `EffectSourceAuthenticator.authenticate(obs) -> (bool, reasons)`, whose reference implementation trusts any observation carrying a `source` and is refused in production `[V]` | `…/execution_assurance/ingress.py:75-110` |
| What it authenticates is the neutral `ExecutionObservation` — outcome, parameters, `final`, `reason`, `provider_trace_id`, `fingerprint` — which carries no signature, signer or key field `[V]` `[G]` | `governance-contracts/contracts/execution.py:48-56` |
| The "Third-Party Gateway" connector layer is FUTURE and its noun is reserved by two READMEs `[V]` | `risk_authority/README.md:32`; `vendor-dependency/README.md:32` |
| DD-10b custody is structural: production signers sit behind a Protocol and an HSM/KMS signer drops in without caller change; `os`, `pathlib`, `socket`, `secrets` are banned package-wide `[V]` | ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY line 1210; TEA `authority/signing.py:47-55` |
| The Trusted Evidence Authority resolves anchors by an exact `(authority_id, key_id, capability)` coordinate; `TrustAnchorCapability` is a closed enum it owns, and the 0.3.0 precedent lent one member to a named consumer under an exact symbol grant `[V]` | TEA `authority/trust.py:142-200,492-511`; TEA `CHANGELOG.md` 0.3.0; `tests/packaging/test_dependency_boundary.py` |
| A complete precedent for signing an artifact outside TEA and verifying it against TEA's anchors ships: `cloud-scaling-producer-attestation` reuses TEA's anchors unchanged, recomputes the signed payload before verifying, refuses its reference signer and reference resolver in production, and rules that a key provisioned for one purpose is not thereby entitled to another `[V]` | its `pyproject.toml:41-45`, `README.md:42,93,112,233-239`, `verification.py:246-470` |
| The BR-2C candidate measured that the signature backend alone accepts key-less forgeries under five malformed anchors and that libsodium's point check refuses all twelve `[V]` | `packages/benchmark-registry-authority/tests/contract/test_verifier.py`; ADR §35.2 D-41 |

## 3 — Rulings `[R]`, ratified 2026-09-06

| # | Ruling | Consequence in this slice |
|---|---|---|
| **SE-1** | HOME = NEW_PACKAGE `risk-authority-effect-attestation`. It owns effect-attestation contracts and verification only; it does not absorb RA-8 reconciliation, the Third-Party Gateway, receipt acquisition, execution, credential custody or effect observation. RA-8 integration is a later, separately validated step. | One new integration package. No import of RA-8, Decision Authority, Agent Runtime or any Risk Authority runtime. |
| **SE-2** | ATTESTER = EITHER_UNDER_DISTINCT_ROLES. A provider attestation proves which provider reported the effect, not that the effect occurred. An independent-observer attestation proves the identity and authorized role of the observer, not the truth of its observation. The role is in the signed binding; an anchor authorized for one role refuses use in the other. | `EffectAttesterRole` with two members, each mapped to its own TEA capability; the role is a signed field and part of the resolved coordinate. |
| **SE-3** | SHAPE = WRAP_EXECUTION_OBSERVATION. `governance-contracts.ExecutionObservation` is not modified. An immutable `EffectAttestation` wrapper binds the complete canonical observation with attester identity, role, key reference, algorithm, schema/domain version and signature, and adds, repairs or reinterprets no observation fact. | The wrapper holds the observation by exact type; canonicalization refuses rather than coerces; governance-contracts is unchanged. |
| **SE-4** | ANCHORS = TEA_RESOLVER_WITH_EFFECT_ATTESTER_ROLE. Reuse TEA's `TrustAnchorResolverPort` and anchor representation; add purpose-specific roles under it, one for executing-provider and one for independent-observer effect attesters. No second trust store or package-owned directory. Evidence-verifier, producer-attester and effect-attester anchors are non-transferable across purposes. | TEA 0.4.0 lends `EFFECT_ATTESTATION_EXECUTING_PROVIDER` and `EFFECT_ATTESTATION_INDEPENDENT_OBSERVER` and names this package as a second consumer under the same exact symbol grant. TEA verifies nothing under either. |
| **SE-5** | BACKEND = D41_PAIR_WITH_POINT_CHECK. Verification uses the D-41 pair with strict Ed25519 point validation; malformed, small-order, non-canonical, identity and otherwise invalid points refuse before trust is granted. The ratified cryptographic behaviour is neither weakened nor forked. | The package verifies through TEA's `TrustAnchorRecord.verification_key()` and `TrustedEvidenceVerificationKey`, which already are that pair with that check; it imports no cryptographic library of its own. |

## 4 — Stated explicitly

- **A valid signature proves provenance and integrity, not factual correctness.** A `VERIFIED` result binds who signed and what bytes; it carries a permanently `False` `factual_correctness_established` and no field that could be read as "the effect occurred".
- **Provider self-attestation is not independent effect verification.** The executing-provider role proves which provider reported. Only a signature under the independent-observer role establishes that a distinct authorized party observed, and even that establishes the observer's identity and role, not the truth of its observation.
- **Unsigned observations remain admissible only under the existing reference-grade posture.** RA-8's `ReferenceEffectSourceAuthenticator` is unchanged and still refused in production; nothing here relaxes that.
- **The Third-Party Gateway remains FUTURE.** Attestation is a property of a receipt; this package produces no connector.
- **The new package does not alter `ExecutionObservation`.** governance-contracts is not modified by this slice `[V]`.
- **It does not produce, fetch, reconcile or admit an observation.** It verifies an attestation it is handed, against an anchor it is handed, at an instant it is handed.
- **No trust role or key authority transfers between evidence, capacity and effect attestation.** Five disjoint capabilities in one store; each consumer resolves only its own; TEA's disjointness tests cover all three lent members.
- **The contracts-only slice cannot make RA-8 production-ready.** RA-8's production posture is unchanged until a separately validated integration step wires a production authenticator, and that step is not this one.
- **Maturity after this slice is REFERENCE-GRADE / NOT PRODUCTION-READY.** Reference signer and reference resolver are refused in production; no production signer, key loading, key generation, network, filesystem, environment-variable, credential or discovery implementation exists.

## 5 — What this slice moves, and what it does not

**Moves** `[V]`: TEA `0.3.0 → 0.4.0` (two enum members, a second named consumer, no export change); a new package at `0.1.0`; a CI workflow for it.

**Does not move**: RA-8 code, ports, tests or maturity; `ExecutionObservation`; any BR-2 artifact; the Third-Party Gateway noun; any refusal vocabulary outside the new package's own.

## 6 — Next step

Implement and verify the slice under these rulings, then, as a separate and
separately validated step, rule on how RA-8's production `EffectSourceAuthenticator`
consumes an `EffectAttestationVerificationResult`.
