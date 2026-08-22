# Changelog — ugence-cloud-scaling-policy-authenticity

## 0.2.0 — Cloud Scaling Phase 5B-1: decision-scope repair

Ratified in `docs/architecture/ADR_CLOUD_SCALING_DECISION_SCOPE_PHASE5B1_RATIFICATION.md`.

### Added — gate 11, candidate reconciliation (D-5B1-1, closing ADR residual R-4)

- A supplied candidate's `PolicyTargetBindingReferenceV2` is reconciled against the resolved
  policy: all six coordinate components, `policy_body_digest`, and the issuing identity
  (`issuing_authority_id`, `key_id`, `signature_alg`). A disagreement is the new
  `CANDIDATE_COORDINATE_MISMATCH` — a refusal, because the proof and the candidate are handed
  to a consumer together and a proof about policy A beside a candidate about policy B is a
  misstatement however genuine each half is.
- The verification routine now runs **eleven** ordered gates, not ten. The candidate stays
  optional; omitting one is not a refusal.
- Before Phase 5A `0.2.0` this comparison could not be made at all: a Phase 5A binding carried
  three of the coordinate's six components and its fourth was in the wrong digest namespace,
  so one genuine policy proof verified alongside any candidate whatsoever. That was R-4.

### Changed — the promotion, and what it cost

- promoted: `candidate_digest_fact` — gate 11 reconciles a supplied candidate's policy
  coordinate against the resolved policy, so the fact this artifact carries about which
  candidate it accompanied is now checked rather than merely recorded. This line's shape is
  load-bearing: the ratchet requires every fact that changes halves to be disclosed as
  `promoted: <fact>` or `demoted: <fact>` on its own line, so that a version bump earned by
  one promotion cannot carry a second, undisclosed one along with it.
- `candidate_digest_fact` moved from the **recorded** half to the **verified** half.
  `VERIFICATION_PROFILE_VERSION` moves to `v2` in the same commit, as the ratchet requires,
  and the reference artifact digest moved with it:
  `8b0ea25f…` → `f245511d…`. The partition fingerprint moved `86d39d25…` → `242ac003…`.
  Both superseded values are pinned as negative anchors.
- `RECORDED_FACT_NAMES` is now three members: `resolved_as_of_fact` (R-2, still open),
  `policy_type` and `trust_configuration_digest`. The recorded half's domain tag does not
  move — the frame is unchanged, only its membership.
- `None` on `candidate_digest_fact` means **no candidate accompanied the determination**. It
  never means one was carried unchecked: a candidate that does not reconcile mints no artifact.
- The distribution moves to `0.2.0`. Phase 5A moves to `0.2.0` independently, and one of its
  frozen digests moved; `tests/test_phase5a_untouched.py` is amended rather than deleted,
  because its purpose — a change to Phase 5A surfaces in a package that depends on it —
  survives the superseded premise it was written for.
- `tests/test_candidate_not_bound.py` is replaced by `tests/test_candidate_reconciliation.py`.
  The old module measured the residual and asserted `VERIFIED` for a candidate naming another
  policy; the new one asserts the refusal.

### Still open

- **R-2** — `resolved_as_of_fact` stays in the recorded half. Whose clock supplies `as_of` is
  5B-2's work, and a determination reached at an attacker-chosen instant can still resolve a
  policy that is revoked, expired or not yet effective *now*.
- **A-59 (5B-0A)** — the producer attestation binds the recommendation, not the candidate.
  Reconciling the policy does not reconcile the producer's signature to this candidate.
- Bound extraction — that the candidate's `max_permitted_*` are the bounds the verified policy
  body states — remains 5B-2's.

### Added — the partition ratchet (D-5B1-3)

- `tests/test_partition_ratchet.py` and `tests/_partition_ratchet.py`. The partition
  fingerprint pinned in `tests/test_frozen_digests.py` was a **pin, not a ratchet**: the 5B-1
  audit measured that promoting `candidate_digest_fact`, updating the two pinned constants and
  leaving `VERIFICATION_PROFILE_VERSION` at `"v1"` passes that file at 5 passed. Updating a pin
  is exactly as cheap as the change it gates, because both land in the same commit.
- The ratchet takes its "before" from **repository history** — the membership recorded at the
  merge base, parsed out of the historical source rather than imported — and fails when the
  verified/recorded partition moved without a `VERIFICATION_PROFILE_VERSION` bump, or when the
  version moved with no changelog line naming it.
- It lands **before** the promotion it exists to catch, with negative controls that drive a
  promotion-without-a-bump and a bump-with-a-silent-changelog through the gate and observe it
  fail. A guard built after the first promotion would have missed the one event it is for.
- CI resolves the baseline from the event's own default branch and sets
  `UGENCE_RATCHET_REQUIRED=1`, so a baseline that cannot be resolved fails the workflow
  instead of skipping quietly. Outside a checkout the gate skips, as the suite's other
  repository-dependent properties do.

## 0.1.0 — Cloud Scaling Phase 5B-0B: policy authenticity

First release. Adds a distribution; changes none.

### Added

- `PolicyAuthenticityVerifier` — the authoritative routine. Ten ordered gates, stopping at the
  first failure, deterministic, fail-closed. An unexpected exception becomes
  `VERIFICATION_UNAVAILABLE`, which is a refusal.
- `PolicyResolutionPort` with `PolicyAuthorityResolutionPort` (the one production-grade seam
  to the Policy Authority's trusted-resolution path, pinning the fail-closed historical rule
  and reporting its trust-configuration identity) and `DenyAllPolicyResolutionPort` (the
  production-admissible "trust not configured" posture).
- `VerifiedPolicyAuthenticity` — the exact-typed, immutable, non-authoritative result. Minted
  only by the routine, guarded by a construction token, a self-digest, a provenance registry
  and `require_verified_policy_authenticity` revalidation at every consumption boundary.
- `PolicyAuthenticityOutcome` — a closed vocabulary with exactly one success. Every Policy
  Authority refusal reason maps across one-for-one and injectively; an unrecognised reason
  becomes `INDETERMINATE`, which is a refusal.
- `policy_trust_configuration_digest` — the identity of one policy trust configuration,
  computed from the anchors' governing attributes and never from key material.

### Ratified decisions implemented

- **D-5B0B-1** — the verified artifact is a `RESOLVED`, non-historical `PolicyResolution`.
- **D-5B0B-2** — `policy_body_digest` is the content binding. The two digest namespaces (bare
  64-hex for the Policy Authority, `sha256:`-prefixed for Phase 5A) are validated separately
  and never converted.
- **D-5B0B-3** — all six coordinate components are carried; a Phase 5A binding cannot name a
  coordinate, so none is derived from one.
- **D-5B0B-4, option (a)** — policy signatures are verified through the Policy Authority's own
  `PolicyKeyRing`. No Trusted Evidence Authority dependency exists, and an import-boundary test
  makes that unreachable rather than merely unused.
- **D-5B0B-5** — "is valid now", at an injected `as_of`. No clock is read anywhere.
- **D-5B0B-6** — the proof travels alongside the candidate. Phase 5A stays at `0.1.0`; this
  suite re-runs its frozen-digest tests to prove all ten are unmoved.

### Audit remediation (pre-merge, same version)

Three findings from the independent audit of this package, addressed without adding or
removing a verification gate and without touching Phase 5A.

- **The result pair is bound.** `PolicyAuthenticityResult` now cross-checks the verified
  artifact against the `PolicyResolution` it carries, on the coordinate and on
  `policy_body_digest`. Two individually genuine halves about different policies are a
  misstatement — a consumer reading the body out of the resolution would read a body the
  proof does not cover — and the pair is refused as one.
- **The trust identity is snapshotted at verifier construction** and every determination is
  minted from the snapshot, so a port cannot report one identity when it is admitted and
  another when the artifact is stamped.
- **Typed outcomes survive the terminal handler.** An escaping error of this package's own
  types keeps the member it carries (`COORDINATE_MALFORMED`, `INVARIANT_VIOLATION`, …);
  anything else is `VERIFICATION_UNAVAILABLE`. "The check could not run" and "the check ran
  and the artifact is bad" are different facts. An exception claiming `VERIFIED` never
  becomes one.

### D-5B0B-7 — the digest payload partitions (ratified, implemented at the same version)

`VerifiedPolicyAuthenticity.digest_payload()` is now two separately framed maps, each carrying
its own domain tag as a canonical field:

- **`verified`** — the facts a gate checked;
- **`recorded`** — carried and digest-covered but never attested. Exactly
  `resolved_as_of_fact` (R-2: injected, unvalidated) and `candidate_digest_fact` (R-4:
  recorded, never reconciled).

Both halves remain inside the artifact digest, so neither can be rewritten; what the partition
adds is that the frame a fact sits in is part of what the digest commits to. Promoting a fact
into the verified half — what 5B-1 and 5B-2 do when they close R-4 and R-2 — therefore moves
the artifact digest instead of silently relabelling it.

`verified_fact(name)` and `recorded_fact(name)` each refuse the other's half, so an unattested
value cannot be read through a call that reads as attested. `VERIFIED_FACT_NAMES` and
`RECORDED_FACT_NAMES` are exported, and an import-time guard refuses a field in neither set.

No gate was added or removed (still ten), the distribution stays at `0.1.0`, and no Phase 5A
frozen digest moved.

### Second audit round (pre-merge, same version)

Three further findings. **No verification gate was added or removed — the routine still runs
ten — so `VERIFICATION_PROFILE_VERSION` stays `v1`.** Two facts moved from the verified half
to the recorded half, which does move every artifact digest; that is safe only because nothing
downstream pins one yet and no verification artifact crosses a process boundary.

- **`policy_type` moves to `recorded`.** It is absent from the 21 keys of
  `IssuedPolicyRecord.signing_payload()` (`adapter_id` is present; this is not), and
  `resolve_policy` recomputes the body digest from the *descriptor's* `policy_type`, never the
  record's — so a record differing only in that field resolves `RESOLVED` and minted a
  `VERIFIED` artifact carrying the substituted value. No gate is available: the fact is
  transitively committed inside `policy_body_digest`, whose frame includes it, but a hash is
  one-way and this package holds no adapter registry with which to re-derive the descriptor.
- **`trust_configuration_digest` moves to `recorded`.** It was port-self-reported and checked
  only for shape, so a wrapper delegating to a genuine `PolicyAuthorityResolutionPort` while
  reporting an arbitrary well-formed digest minted an artifact carrying that value. No gate is
  available either: the port *is* the seam to the authority, so any check would be the port
  vouching for itself. The construction-time snapshot is kept — it stops drift between
  admission and minting — but it does not make the value true, and the docstrings now say so.
- **The result pair binds which answer, not only which policy.**
  `PolicyAuthenticityResult` now also requires the carried resolution to be non-historical and
  to have been reached at the instant the artifact reports. A genuine artifact previously
  paired cleanly with a genuine `historical=True` resolution of the same policy — same
  coordinate, same body digest, `implies_current_validity=False` — and with one reached at a
  different `as_of`.

### Residual closed at this boundary

- **R-3** — `resolve_policy` does not re-enforce `coordinate.content_digest ==
  policy_body_digest`. Reproduced with a synthetic decoupling adapter and refused here as
  `COORDINATE_DIGEST_UNBOUND`. `tests/test_coordinate_gap.py` also pins the residual itself, so
  a future Policy Authority fix surfaces as a failing test rather than as a silently redundant
  gate.

### Residuals carried, not closed

- **R-2** — whose clock supplies `as_of`, and what makes it trustworthy. Open by ruling; this
  implementation proceeds with `as_of` injected and unvalidated. 5B-2's work.
- **R-4** — binding the verified policy proof to the recommendation and target scope. 5B-1's
  decision-scope repair. `candidate_digest_fact` records scope, never a binding.
