# ADR — Signed comparison results: scoping

**Status:** ratified and implemented as a contracts-only slice, 2026-09-06 (owner ruling
SCR-1 = YES, §5; implementation record in §6). No key exists: see §4.
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
  nothing to any existing member `[V]` (`trust.py:142-160`). Six members existed before
  this ADR: `EVIDENCE_PRODUCTION`, `RECEIPT_ISSUANCE`,
  `CLOUD_SCALING_RECOMMENDATION_ATTESTATION`, the effect-attestation pair, and
  `TRUST_ANCHOR_SET_PUBLICATION` `[V]` (`trust.py:165-211`). (Corrected: an earlier
  revision of this ADR counted five.)
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
`TrustAnchorCapability.COMPARISON_RESULT_ATTESTATION`, appended after the six
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

## 5 — Ruling — ratified 2026-09-06 (SCR-1 = YES)

**SCR-1 — SIGNED_RESULT = WRAP_AND_LEND.** Adopt §3 as scoped: a new
`reasoning-method-result-attestation` package wrapping an unmodified
`ReadinessComparisonResult`; one `COMPARISON_ENGINE` role under one new lent capability
`COMPARISON_RESULT_ATTESTATION`; signing at the study harness's composition root behind
a signer port with a production signer outside the slice; verification by a role-typed
verifier through TEA's resolver; `admit()` consuming a typed `VerifiedResultSignature`
and citing its receipt digest, refusing an unsigned result only when
`require_signature` is set. The first admission study may run unsigned under this ADR's
§4, and its admission is research evidence only until a signed result exists.

## 6 — Implementation record `[V]`

The contracts-only slice of §3 is built; nothing in §4 has changed.

- **TEA 0.6.0.** `TrustAnchorCapability.COMPARISON_RESULT_ATTESTATION` appended as
  the seventh member; the disjointness, lifecycle and roster tests extended; a third
  named consumer, `packages/integration/reasoning-method-result-attestation`, in the
  closed allowlist under the same exact symbol grant
  (`tests/packaging/test_dependency_boundary.py`). TEA verifies nothing under it.
- **`ugence-reasoning-method-result-attestation` 0.1.0**, mirroring
  `risk-authority-effect-attestation` file for file: `SignedComparisonResult` over an
  unmodified `ReadinessComparisonResult`, whose `result_digest` is recomputed through
  the governance contract at every read; `ComparisonResultAttesterRole.COMPARISON_ENGINE`
  → `COMPARISON_RESULT_ATTESTATION`, with the signer identity bound to the result's
  `engine_identity`; `ComparisonResultSignerPort`; a seed-derived reference signer
  refused in production; `Ed25519ComparisonResultVerifier` over TEA's resolver with
  TW-1..3 posture; `verification_result_digest` as the citation. Suite, measured
  mutation sweep (38 gates, four classified survivors) and offline isolated install
  all pass; CI workflow `reasoning-method-result-attestation-ci.yml`.
- **Advisor 0.3.0.** `VerifiedResultSignature`; `admit`/`validate_admission`/
  `evidence_from_result` take `verified=` and `require_signature=`; codes
  `COMPARISON_RESULT_UNSIGNED` and `COMPARISON_RESULT_SIGNATURE_MISMATCH`; admission
  schema `advisory_admission.v3` with `result_signature_receipt_digest`; the bridge
  carries it with the C6 prefix.
- **Proposer 0.6.0.** `ReasoningMethodAdvisoryInput.result_signature_receipt_digest`,
  optional (13 → 14 fields); no public name added; `P_unsigned` untouched.
- **Shipped nothing of §4**: no key, no key loading, no production signer, no
  trust-anchor set naming the engine, no harness composition root. The first
  admission study still runs unsigned, and `require_signature=True` refuses every
  result today.

## 7 — The first signed study: rulings SR-0 to SR-5, ratified and implemented `[V]`

Given 2026-09-06 after the composition-root design; enacted in
`experiments/workflow_fit_study/signed_admission.py`.

| # | Ruling | Enacted by |
|---|---|---|
| SR-0 | **ENGINE_KEY_CUSTODY = RESEARCH_REFERENCE_ONLY.** The experiment operator controls both keys; they are two distinct seeds; no production key, KMS, HSM, vault, cloud signer, Credential Broker or network signer. | `RESEARCH_ENGINE_SEED` in `signed_admission.py`; `RESEARCH_PUBLICATION_SEED` only in `publish_research_trust_anchor_set.py`; a test asserts the seeds, public keys, coordinates and capabilities differ |
| SR-1 | **COMPOSITION_ROOT = HARNESS_MODULE.** | `experiments/workflow_fit_study/signed_admission.py`; no signer or attestation composition in the pilot package, no new package. Step 1 runs the pilot through `run_phase_4c_pilot`, not the bare `run_pilot` the ruling named: the pilot's ratified tripwire (revision 20/26, `test_the_phase_4c_study_never_calls_the_ungated_runner`) forbids the ungated runner from this harness, and the gate delegates to `run_pilot` after F3 and F4. A signed study therefore needs a v2 manifest with a committed role `[V]` |
| SR-2 | **SIGNER_BACKEND = REFERENCE_SIGNER_ONLY.** | `research_engine_signer()` is `ReferenceEd25519ComparisonResultSigner`; signing never sets `production_mode`; the verifier does, so the reference *resolver* is refused |
| SR-3 | **SNAPSHOT_CUSTODY = COMMITTED_RESEARCH_SNAPSHOT.** | `research_trust_anchor_set_v1.json`, rendered deterministically by the publisher script and checked equal by a test; `research_resolver()` takes the document bytes, the pinned root (public key by literal), `max_snapshot_age=30 days` and `last_accepted_set_version=0` explicitly |
| SR-4 | **ENGINE_KEY_ID = VERSIONED_RESEARCH_KEY.** | `workflow-fit-research-engine/1`; anchor window 2026-09-01 to 2026-09-26 (25 days), inside the set's 30-day window; a later generation issues new seeds under `/2` |
| SR-5 | **EVIDENCE_STATUS = RESEARCH_ONLY.** | `SignedAdmissionEnvelope.evidence_classification` is fixed at `RESEARCH_EVIDENCE / CRYPTOGRAPHICALLY_VERIFIABLE_SELF_ATTESTATION` and unconstructible otherwise; `render_envelope` opens and closes with it and carries the same-party note |

**What the run proves `[V]`** (`tests/experiments/workflow_fit_study/test_signed_admission.py`,
one genuine pilot run through the boundary process): a valid signed admission citing
the verification record; refusals for a mutated result, a different key under the
engine's identity, an unpublished key id, a snapshot without the engine anchor, a
forged or engine-signed publication signature, a stale set, a rollback, an expired
engine key, a signer for another identity, and an unsigned result under
`require_signature=True`; the two keys are distinct; and the classification survives
success. The receipt digest is the attestation package's `verification_result_digest`
with the repository's one `sha256:` prefix translation; no second representation.

**What it does not change `[V]`.** §4 stands except that a research trust chain now
exists: no production key, no production trust anchor, no revocation, no
independent-verifier role. The study's admission is research evidence.

