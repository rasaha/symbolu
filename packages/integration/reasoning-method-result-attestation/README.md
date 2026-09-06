# ugence-reasoning-method-result-attestation — 0.1.0

**Signed comparison results, contracts first.** The structural closure of
requirement A3 in
[`REASONING_METHOD_FIRST_ADMISSION_STUDY_PLAN.md`](../../../docs/REASONING_METHOD_FIRST_ADMISSION_STUDY_PLAN.md),
scoped and ratified by
[`ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING.md`](../../../docs/architecture/ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING.md)
(SCR-1).

> **A verified signature proves provenance and integrity, not factual
> correctness.** It establishes which engine produced a `ReadinessComparisonResult`
> under which key, and that the bytes are the bytes it signed. It never
> establishes that the comparison is correct, that its inputs were genuine, or
> that any method is fit for any task. Every result says so on its face.

Maturity: **REFERENCE-GRADE / NOT PRODUCTION-READY.** No key for any comparison engine exists
anywhere in the repository; the first admission study runs unsigned under the ADR's §4.

## What this package is

| Piece | What it does |
| --- | --- |
| `SignedComparisonResult` | An immutable wrapper binding one complete, **unmodified** `ReadinessComparisonResult` with the signer's identity, role, key reference, algorithm, schema/domain version and signature. The governance contract is wrapped, never changed; the result's own `result_digest` is **recomputed through the contract** at every read and a result whose self-digest disagrees with its fields is refused |
| `ComparisonResultAttesterRole` | One member, `COMPARISON_ENGINE`: the engine the result names signs it under its own identity. The role is inside the signed bytes and selects the trust-anchor capability. An independent-verifier role is deliberately absent — a later slice |
| `Ed25519ComparisonResultVerifier` | The one verifier. Resolves the engine's anchor through the Trusted Evidence Authority's `TrustAnchorResolverPort` at the exact `(engine identity, key_id, COMPARISON_RESULT_ATTESTATION)` coordinate and verifies through TEA's strictly validated Ed25519 key. Returns a typed result; never raises for an invalid input |
| `ComparisonResultVerificationResult` | Pure and evidence-bound: outcome, one typed refusal reason, the role, signer identity and key, the expected engine identity, the governance `result_digest` of the caller's own result, payload digest, coordinate digest, anchor revision and instant. `establishes` is always `PROVENANCE_AND_INTEGRITY_ONLY`; `factual_correctness_established` is permanently `False` |
| `ReferenceEd25519ComparisonResultSigner` | Deterministic, seed-derived, **for tests and local composition only**; `sign_comparison_result(..., production_mode=True)` refuses it and every subclass. A production signer is HSM- or KMS-backed, implements `ComparisonResultSignerPort` at the study harness's composition root, and is outside this slice |

## What it establishes

A verified `COMPARISON_ENGINE` signature establishes **which engine produced this
comparison result under which key; not that the comparison is correct, and not
that any method is fit for any task.** The advisor's admission consumes this as a
typed fact it is handed, cites the receipt digest, and re-verifies nothing.

## What it does not do

- It **does not run a comparison**, admit an advisory, or judge a method fit.
  It **imports neither the engine nor the advisor**: the dependency runs one
  way, from this package to the governance contracts and to TEA, and the
  advisor consumes a typed `VerifiedResultSignature` it defines itself.
- It does **not** alter `ReadinessComparisonResult`; `reasoning-method-governance`
  is unchanged and the engine stays a pure function with no cryptography.
- It holds **no second trust store**: anchors are TEA's, reused as the identical
  objects, under one capability TEA lends for this purpose
  (`COMPARISON_RESULT_ATTESTATION`). Evidence, receipt, Cloud Scaling, effect and
  set-publication anchors are non-transferable to it.
- It ships **no production signer**, no key loading, no key generation, no
  network, filesystem, environment-variable, credential or discovery code, and
  imports no cryptographic library of its own. **No key for any comparison
  engine exists**; no trust-anchor set names `ugence-readiness-comparison`.

## Verification pipeline, in order

1. exact-type admission of the signed result, the caller's role, expected engine
   identity, result and aware instant; the caller's own `result_digest` is
   recomputed through the governance contract;
2. contract admission: schema version, signing domain, algorithm, profile,
   encoding — all pinned, none negotiated;
3. reconciliation against the **caller's** facts: role, engine identity, and
   the complete canonical projection of the result (identity fields, the
   instant it was produced, and its recomputed `result_digest`);
4. anchor resolution at the exact coordinate; the resolution and the record
   are both re-checked against the coordinate asked;
5. lifecycle at the caller's instant, in TEA's order: revoked, disabled, not
   yet valid, expired; then the optional expected anchor revision;
6. key admission through TEA's point check, payload recomputed from the
   caller's result and compared byte for byte, signature decoded and verified.

A resolver that raises, returns the wrong type or answers another coordinate
refuses closed. Nothing is memoized. Trust-state refusals stay distinguishable
(`ANCHOR_SET_STALE`, `ANCHOR_SET_UNAVAILABLE`, `ANCHOR_UNKNOWN`,
`ANCHOR_UNAVAILABLE`), exactly as in the effect-attestation package this one
mirrors.

## Two digest spellings

The governance contract spells `result_digest` as bare 64-hex, and that value is
what the advisor's admission cites, so this package carries it **verbatim**. Its
own digests — the projection digest, the signing-payload digest, the coordinate
digest and TEA's anchor revision — are spelled `sha256:<hex>`.

## Dependencies

```
ugence-reasoning-method-governance (>=0.2.0)   ReadinessComparisonResult, wrapped unchanged
ugence-trusted-evidence-authority (>=0.6.0)    trust-anchor contracts, resolver port,
                                               Ed25519 key/codec types — exact grant
        ▲
ugence-reasoning-method-result-attestation (this package)
```

## Verify

```bash
python -m pytest packages/integration/reasoning-method-result-attestation/tests -q
python packages/integration/reasoning-method-result-attestation/scripts/verify_isolated_install.py
python packages/integration/reasoning-method-result-attestation/scripts/mutation_sweep.py
```

Measured figures live in `CHANGELOG.md` and are re-run, never edited.
