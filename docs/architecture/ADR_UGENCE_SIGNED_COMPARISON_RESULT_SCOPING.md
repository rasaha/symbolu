# ADR — Signed comparison results: scoping

**Status:** scoping, 2026-09-06. Documentation only; no package, key or seam exists.
Closes requirement A3 of `docs/REASONING_METHOD_FIRST_ADMISSION_STUDY_PLAN.md` on the
precedent of `ADR_UGENCE_SIGNED_EFFECT_ATTESTATION_SCOPING.md` (SE-1 to SE-5). Labels:
`[V]` verified, `[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

`admit()` now refuses anything but a `ReadinessComparisonResult` naming the comparison
engine `[V]` (`admission.py:204-222`), but the engine identity is a string in a
dataclass anyone can construct. What would let `admit()` require a **verified
signature over `result_digest`** before admitting? **A wrapper, a lent capability, a
signer at the study's composition root, and a typed verification record the advisor
consumes without importing the engine or the authority.** Every piece has a precedent
in the repository; none of it is built, and the key does not exist.

## 2 — What the repository already fixes `[V]`

- **The digest to sign.** `ReadinessComparisonResult.result_digest` is a function of
  the request alone: it excludes `produced_at` and takes each assessment's time-free
  payload `[V]` (`governance/contracts/ports.py:182-191`). Signing it binds content,
  not the instant.
- **The anchor lookup.** TEA resolves an anchor only at an exact
  `TrustAnchorCoordinate(authority_id, key_id, capability)` — no wildcard, no
  normalization `[V]` (`trusted-evidence-authority/.../authority/trust.py:216-240`) —
  through `TrustAnchorResolverPort.resolve(coordinate, as_of=...)`, which a deployment
  backs with configuration, a managed key service or an HSM directory without caller
  change `[V]` (`trust.py:518-545`). With no anchor configured the answer is deny
  (`DenyAllTrustAnchorDirectory`, `trust.py:704`).
- **The capability vocabulary is built to be extended.** `TrustAnchorCapability` is
  single-valued per anchor, so a new member is a disjoint entitlement that grants
  nothing to any existing member `[V]` (`trust.py:142-160`). Five members exist today:
  `EVIDENCE_PRODUCTION`, `RECEIPT_ISSUANCE`, `CLOUD_SCALING_RECOMMENDATION_ATTESTATION`,
  and the effect-attestation pair `[V]` (`trust.py:165-197`).
- **The signing pattern.** A signer sits behind a port that advertises the authority
  and key it speaks for, so the issuer binds those coordinates into the frame before
  signing `[V]` (`authority/signing.py:160-190`); the key object exposes only
  `verification_key` and `sign(bytes)` and cannot be copied or printed `[V]`
  (`authority/backend.py:237-272`); an HSM- or KMS-backed signer drops in behind the
  same port `[V]` (TEA README, DD-10). Signed input is a domain-separated, fixed-order
  frame reconstructed independently of the signer `[V]` (`authority/envelope.py:121, 179`).
- **The role-typed verifier pattern.** `risk-authority-effect-attestation` wraps an
  unmodified `ExecutionObservation`, puts the attester role inside the signed bytes,
  maps each role to its own lent capability so an anchor for one role can never
  satisfy the other `[V]` (`roles.py:34-61`), and its `Ed25519EffectAttestationVerifier`
  refuses a reference-grade resolver when `production_mode=True` `[V]`
  (`verification.py:167-196`). Its reference signer is seed-derived and refused in
  production `[V]` (`signing.py:71-`).
- **Independent re-verification.** `SignedReceiptVerifier.verify_signature` answers
  "authentic under a currently trusted key" at an explicit instant, revocation checked
  first `[V]` (`authority/reverification.py:508-584, 758`).

## 3 — The design `[I]`

**Wrapper, not modification.** `SignedComparisonResult` binds one complete, unmodified
`ReadinessComparisonResult` with `signer_identity`, `signer_key_id`, the role, the
algorithm and profile, the schema and domain version, and the signature.
`governance-contracts` and `readiness-comparison` are not touched; the engine stays a
pure function with no I/O and no cryptography.

**Home.** A new integration package, `reasoning-method-result-attestation`, on SE-1's
exact grounds: it owns the wrapper contract and the verifier only. It imports TEA and
`reasoning-method-governance`; it imports neither the engine nor the advisor.

**Role and capability.** One role for this slice, `COMPARISON_ENGINE`, establishing
"which engine produced this result under which key; not that the comparison is
correct." It resolves under one new lent capability,
`TrustAnchorCapability.COMPARISON_RESULT_ATTESTATION`, added beside the four
existing members and covered by TEA's disjointness tests. The coordinate the engine
identity resolves to is therefore
`TrustAnchorCoordinate("ugence-readiness-comparison", <deployment key id>,
COMPARISON_RESULT_ATTESTATION)`. An independent-verifier role is deliberately **not**
scoped here: a second signature by a party that re-ran the comparison is A2/A3 of the
study plan for the *records*, and would be a later slice with its own role.

**Who holds the key.** The party that runs the engine — the study harness's
composition root under `experiments/workflow_fit_study/` — behind a
`ComparisonResultSignerPort` shaped like `ReceiptSignerPort`. The engine package never
sees the key. The reference signer is seed-derived, test-only, and refused in
production; a production signer is HSM- or KMS-backed and outside this slice.

**Who verifies.** `Ed25519ComparisonResultVerifier` in the new package, handed TEA's
resolver, the caller's expected engine identity and an aware instant; `production_mode`
refuses a reference resolver. It returns a pure `ComparisonResultVerificationResult`
carrying outcome, one typed refusal reason, identity, key, result digest, coordinate
digest, anchor revision and instant.

**How a signed result reaches `admit` without new imports.** The advisor is handed a
**typed fact**, not a signature: a `VerifiedResultSignature` dataclass the advisor
itself defines — `result_digest`, `signer_identity`, `signer_key_id`,
`verification_receipt_digest`, `verifier_identity`, `verified_at`. The composition root
runs the verifier and constructs it; the advisor checks it against the result it was
given. This is the repository's existing posture: the comparison engine treats
`resolved_authorities` as requester-asserted `[V]` (`engine.py:218`), and the effect
verifier is handed its anchors. The trade-off is stated, not hidden: the advisor trusts
the composition root's verification, and an auditor re-verifies from the cited receipt
digest with TEA's `verify_signature`, outside the advisor.

**What changes in `evidence_from_result`.** One keyword parameter,
`verified: Optional[VerifiedResultSignature] = None`, and one flag on `admit`,
`require_signature: bool = False`. With the flag set and no record: refuse
`COMPARISON_RESULT_UNSIGNED` (new code). With a record whose `result_digest` differs
from `result.result_digest`: refuse `COMPARISON_RESULT_SIGNATURE_MISMATCH` (new code).
With a record whose `signer_identity` is not `COMPARISON_ENGINE_IDENTITY`: the existing
`COMPARISON_EVIDENCE_UNBOUND`. The admission gains
`result_signature_receipt_digest: Optional[str]`, `None` in the research posture,
required when the flag is set, and the schema moves to `advisory_admission.v3`. The
bridge carries the receipt digest with the C6 prefix; `ReasoningMethodAdvisoryInput`
gains one optional field (13 → 14). `validate_admission` replays the same checks.

## 4 — What needs a key that does not exist `[G]`

- **No signing key for the engine identity exists anywhere in the repository.** TEA
  ships key derivation for reference signers only; production custody is a port with
  no implementation `[V]` (TEA README, DD-10 rows).
- **No trust-anchor set names `ugence-readiness-comparison`** under any capability;
  the reference directory holds only what a test constructs, and the deny-all default
  applies to a deployment that configures nothing.
- **The revocation process is specified and implemented nowhere** `[V]`
  (`authority/trust_snapshot.py:28`), so a compromised engine key cannot yet be retired.
- **The study harness has no composition root** that signs: today it calls the engine
  and stores an unsigned result.
- Until all four exist, `require_signature=True` refuses every result, which is the
  correct behaviour and also means the first admission study runs unsigned `[R]`.

## 5 — Ruling `[R]`

**SCR-1 — SIGNED_RESULT = WRAP_AND_LEND.** Adopt §3 as scoped: a new
`reasoning-method-result-attestation` package wrapping an unmodified
`ReadinessComparisonResult`; one `COMPARISON_ENGINE` role under one new lent capability
`COMPARISON_RESULT_ATTESTATION`; signing at the study harness's composition root behind
a signer port with a production signer outside the slice; verification by a role-typed
verifier through TEA's resolver; `admit()` consuming a typed `VerifiedResultSignature`
and citing its receipt digest, refusing an unsigned result only when
`require_signature` is set. The first admission study may run unsigned under this ADR's
§4, and its admission is research evidence only until a signed result exists.
