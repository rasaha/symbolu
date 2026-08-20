# Changelog — ugence-cloud-scaling-policy-authenticity

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
