# ADR — Comparison-result signing: authority, profile and key custody

**Status:** ratified 2026-09-09 by the repository owner. Rulings CRSC-1 to CRSC-4.
**Scope:** who owns the trusted issuer identity and signing profile for a
`ReadinessComparisonResult`, who holds the private key, and what a verified signature
does and does not establish.
**Relation to SCR-1:** this ADR answers the production-custody question that
`ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING.md` §4 left open as a `[G]`. It does not
reopen SCR-1, SR-0 to SR-5, or the research trust chain those rulings ratified.

## The question

The Reasoning Method Advisor's slice 3 admits a comparison result into the product only
when the result is signed and that signature has been verified. The mechanism shipped;
the trust arrangement behind it did not. The open question was who establishes the
trusted identity a comparison engine signs under, and who holds the key.

The dangerous answer — the one this ADR exists to foreclose — is that the advisor issues
or self-custodies its own trust key. An advisory component that mints the credential
attesting to its own inputs has closed a loop it should not be able to close.

## What the repository already fixes `[V]`

Recording the state before the ruling, because three of the four pieces already exist
and the ruling must not be read as commissioning them:

- **The capability exists.** `TrustAnchorCapability.COMPARISON_RESULT_ATTESTATION`
  (`packages/trusted-evidence-authority/.../authority/trust.py:222`). The enum's own
  docstring states it is "safely extensible for a *different* signing domain" and that
  a member "is a vocabulary this package owns and lends; it is **not** a claim that
  this package verifies, admits or authorizes whatever the new domain signs."
- **The profile is fixed and unnegotiable.** One Ed25519 profile, lowercase base16,
  length-prefixed framing, per-domain tags, no `none` algorithm and no downgrade path
  (`authority/profile.py`).
- **The custody seam exists.** `ComparisonResultSignerPort` and
  `TrustAnchorResolverPort`; `ReferenceEd25519ComparisonResultSigner` is seed-derived
  and test-only, and `production_mode=True` refuses it and every subclass
  (`packages/integration/reasoning-method-result-attestation`).
- **A research trust chain exists and runs.** SR-0 to SR-5 ratified it; the study signs
  under a reference signer (`production_mode=False`) and verifies under
  `production_mode=True`, so `require_signature=True` succeeds there. `[V]` 17 tests in
  `tests/experiments/workflow_fit_study/test_signed_admission.py`.

So what is missing is not a mechanism. It is a production custodian and the review that
would let a signature mean something outside a research harness.

## CRSC-1 — Trusted Evidence Authority owns the identity, profile and verification contract

**Ruled.** The trusted issuer identity, the signing profile and the verification contract
for comparison results belong to `trusted-evidence-authority`. Anchors are resolved at
the exact `(engine identity, key_id, COMPARISON_RESULT_ATTESTATION)` coordinate through
TEA's resolver port, against TEA's anchors, under TEA's lifecycle order.

No second trust store is created. `reasoning-method-result-attestation` holds none today
and may not acquire one; evidence, receipt, Cloud Scaling, effect and set-publication
anchors remain non-transferable to the comparison capability, and it to them, because an
anchor carries exactly one capability.

**The advisor does not issue or self-custody a trust key.** It defines
`VerifiedResultSignature` as a typed fact it is *handed*, cites the receipt digest, and
re-verifies nothing. It imports neither the engine, nor the attestation package, nor the
authority. That boundary is the point of the ruling, not an implementation detail of it.

## CRSC-2 — the private key lives in an external KMS or HSM

**Ruled.** Production key generation and custody belong to an organizational KMS or HSM
operated under the Trusted Evidence Authority's governance. Neither the advisor, nor the
attestation package, nor this repository may generate, embed, persist or transit a
production private key. A production signer implements `ComparisonResultSignerPort` at
the operator's composition root and is not committed here.

The reference signer stays what it is: seed-derived, deterministic, for tests and local
composition, and structurally refused wherever `production_mode=True`. The research seeds
ratified under SR-0 remain research seeds and are not a precedent for a production key.

## CRSC-3 — a verified signature is provenance, never authority

**Ruled.** The signed object is an authenticity and provenance attestation. A verified
signature establishes which engine produced which result under which key, and that the
bytes are the bytes it signed. It establishes **none** of: that the comparison is
correct, that its inputs were genuine, that any method is fit for any task, that policy
sufficiency is met, or that anything may be executed.

Consequential authorization stays with Decision Authority and Risk Authority. The advisor
remains advisory. `establishes` stays permanently `PROVENANCE_AND_INTEGRITY_ONLY` and
`factual_correctness_established` stays permanently `False`.

## CRSC-4 — slice 3 stays research until custody is implemented **and reviewed**

**Ruled.** Slice 3 remains `RESEARCH_ONLY` until all of the following exist: the TEA
signing profile extension in production form, the KMS/HSM custody arrangement, the
production verification path, and an independent review of the three together.
Implementation alone does not lift the label — the review is a named condition, not a
formality.

**The fail-closed posture is preserved and is not to be relaxed to make progress.**
`require_signature=True` continues to refuse an unsigned result
(`COMPARISON_RESULT_UNSIGNED`), a record whose digest is not this result's
(`COMPARISON_RESULT_SIGNATURE_MISMATCH`) and a record naming another signer
(`COMPARISON_EVIDENCE_UNBOUND`).

## What remains open after this ADR `[G]`

- No production key, and no trust-anchor set naming `ugence-readiness-comparison`
  outside the committed research snapshot.
- **Revocation is specified and implemented nowhere** (`authority/trust_snapshot.py:28`),
  so a compromised engine key cannot yet be retired. This is a precondition of any
  production custody arrangement, not a follow-up to one.
- No independent-verifier role: `ComparisonResultAttesterRole` has one member, and the
  engine signing its own result is a self-attestation by construction.
- No real comparison evidence. The fit assessments in the advisor's tests are synthetic
  fixtures proving the mechanism; a forged result remains possible to the extent that
  the signer is the same party as the producer.
