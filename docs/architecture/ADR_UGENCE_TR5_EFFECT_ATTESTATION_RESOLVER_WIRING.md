# ADR — TR-5 effect-attestation resolver wiring (TW-1 to TW-5)

**Status:** rulings ratified by the owner, 2026-09-06; implemented in
`ugence-risk-authority-effect-attestation` 0.2.0 and surfaced by
`ugence-risk-authority-execution-assurance` 0.3.0.
**Maturity:** REFERENCE-GRADE. The signed-snapshot resolver it can now be
wired to remains a **production-shaped candidate only** — not independently
reviewed, not externally cryptographically audited, not production-ready.
D-38 and D-32(4) remain applicable. Nothing here wires a deployment.
**Predecessors:** `ADR_UGENCE_TEA_PRODUCTION_TRUST_ANCHOR_RESOLVER.md`
(TR-1 to TR-5, TR-3-PROTOCOL), `ADR_UGENCE_SIGNED_EFFECT_ATTESTATION_SCOPING.md`
(SE-1 to SE-5), `ADR_UGENCE_RA8_EFFECT_ATTESTATION_INTEGRATION.md` (RI-1 to RI-5).

## 1 — The question

TR-5 names effect attestation the first consumer of the signed-snapshot
resolver. What must change before it is wired? Answer: the plumbing already
works, but the consumer collapsed three distinct trust-state refusals into one,
and a resolver whose snapshot failed to load crashed composition instead of
refusing. Both are fixed here; no deployment is wired.

## 2 — Audit findings

| Finding | Evidence |
| --- | --- |
| The verifier already forwards its instant to the resolver, so nothing else was needed to reach the new resolver `[V]` | `verification.py:315` (`resolve(coordinate, as_of=instant)`), the TR-3-PROTOCOL migration |
| `require_production_resolver` admits the snapshot resolver when its snapshot loaded, and a fresh snapshot returns `VERIFIED` under `production_mode=True` `[V]` | measured before this change: `trust.py:137-169`; probe over `SignedSnapshotTrustAnchorResolver` |
| **All three new TEA reasons collapsed to `ANCHOR_UNAVAILABLE`.** Measured: a stale snapshot and a not-yet-in-force set returned one reason where D-28 requires two; only free text distinguished them `[G]` | `verification.py:325-331` before this change |
| A resolver whose snapshot failed to load reported `is_production_authoritative = False`, so `require_production_resolver` **raised** at construction rather than refusing `[G]` | `trust.py:160-166` before this change |
| RA-8 inherited the collapse: `admit_attested` copies the verifier's reason into its rejection text, so an operator saw one reason for "republish the snapshot" and "the resolver is broken" `[I]` | `ingress.py` attested path |
| The composition boundary must supply five values: complete document bytes, pinned publication root, maximum snapshot age, last accepted set version, and a trusted `as_of` per verification; RA-8 adds `verification_instant` `[V]` | `SignedSnapshotTrustAnchorResolver.from_document`, `verify(as_of=)`, `assess(verification_instant=)` |
| Nothing wired the resolver anywhere, as TR-5 requires `[V]` | repository-wide search for `SignedSnapshotTrustAnchorResolver` outside its own package |
| Adding refusal members moves the vocabulary off 24; existing `ANCHOR_UNAVAILABLE` pins cover resolver faults, wrong types and lookalike resolutions, which all remain `[R]` | `tests/test_refusals.py:326-332` |

## 3 — Rulings

| Ruling | Consequence in code |
| --- | --- |
| **TW-1 VOCABULARY = DISTINCT_MEMBERS** | Two appended members, `ANCHOR_SET_UNAVAILABLE` and `ANCHOR_SET_STALE`. TEA's `TRUST_ANCHOR_SET_UNAVAILABLE` and `TRUST_ANCHOR_SET_STALE` map one-to-one onto them; `TRUST_ANCHOR_MISSING` and `TRUST_ANCHOR_NOT_CONFIGURED` still map to `ANCHOR_UNKNOWN`; every other TEA reason still falls to `ANCHOR_UNAVAILABLE`. The vocabulary moves 24 → 26. D-28's distinction survives into the consumer. |
| **TW-2 INSTANT_REQUIRED = CALLER_CONTRACT_ERROR** | No member is minted. A bad `as_of` handed to `verify` already raises `EffectAttestationContractError` at the caller seam (D-42(a)), which is the real occurrence. A resolver that returns `TRUST_ANCHOR_SET_INSTANT_REQUIRED` **despite being handed a valid instant** is non-conforming, and is treated as a resolver fault: `ANCHOR_UNAVAILABLE`, pinned by test. |
| **TW-3 FAILED_LOAD = ADMIT_AND_REFUSE_EACH_VERIFICATION** | `require_production_resolver` now admits a resolver that **declares** `is_production_authoritative` as an exact `bool`, whether `True` or `False`: declaring the contract is what is checked at construction, being able to serve is checked per verification. Absent, non-`bool` and reference-grade resolvers are refused exactly as before. A new production-mode gate then refuses **before consulting** any declaring resolver whose posture is not `True`, with `ANCHOR_SET_UNAVAILABLE`. `DenyAllTrustAnchorDirectory`, which declares no posture and is admitted by exact type under E-8, is exempt from the gate and keeps its ratified `ANCHOR_UNKNOWN`. |
| **TW-4 COMPOSITION_ROOT = DEPLOYMENT_ONLY_NO_CODE** | No module reads a snapshot file. The package's structural ban on `open`, `os` and `pathlib` is unchanged, and the five composition inputs are documented rather than coded. |
| **TW-5 RA8_PROPAGATION = SURFACE_NEW_REASONS** | RA-8 exports `TRUST_STATE_REFUSALS`, the two reason values an operator must act on differently, and pins end to end that a stale snapshot and a broken resolver reach `admit_attested` as distinguishable rejections. No RA-8 admission rule changes. |

## 4 — What did not move

`EffectSourceAuthenticator.authenticate`, the D-41 pair and its point check, role
separation, the observer-gated production `MATCHED`, `effect_digest` as a content
digest, the no-clock, no-network, no-signer, no-credential posture, TEA itself,
Decision Authority, and `ExecutionObservation`.

## 5 — Stated explicitly

- A verified attestation still proves provenance and integrity only.
- Distinguishing stale from unavailable is an operator-legibility and D-28
  conformance fix. It admits nothing new: both still refuse.
- Admitting a failed-load resolver at construction never admits an anchor: the
  production gate refuses every verification before the resolver is consulted.
- No deployment is wired, no snapshot file is read, and the resolver remains a
  production-shaped candidate.

## 6 — Next step

Operational: the TR-4 custody roles and the anchor-publication process remain
specified and unimplemented. Engineering: RA-8 production wiring stays blocked
until a deployment supplies a genuine production resolver.
