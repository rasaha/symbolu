# Changelog — ugence-cloud-scaling-authorization-contracts

## [0.3.0] — Cloud Scaling Phase 5B-2 part 1: R-9

Ratified in `docs/architecture/ADR_CLOUD_SCALING_DECISION_SCOPE_PHASE5B1_RATIFICATION.md`,
owner ruling on the three residual decisions. **Breaking**, pre-1.0: a candidate that was
constructible at `0.2.0` may be refused at `0.3.0`. No schema identifier moves and **no digest
moves** — a refusal changes what is constructible, not what is hashed.

### Added

- `POLICY_SCOPE_TENANT` — the one `policy_scope` value that constrains which tenant a policy
  may bound. A literal rather than an import: this package depends on neither the Policy
  Authority nor the UVI contracts, which is why the coordinate travels as strings at all.
- Rejection reason `CROSS_TENANT_POLICY_BINDING`. Its own member, deliberately not folded into
  `POLICY_COORDINATE_CONTENT_MISMATCH`: the two references agree perfectly and the coordinate
  is bound to this very scope. What is wrong is whose action the policy may bound, which is a
  scope violation rather than a content disagreement.
- A third builder guard in that family (inventory 51 → 52), closing **R-9**: a `TENANT`-scoped
  policy may bound only its own tenant's action. Keyed on the scope, never on a bare tenant
  equality — a `GLOBAL` policy carries the empty tenant, so `!=` alone would refuse every
  global policy in the platform. Mirrors the ratified shape at
  `uvi-policy-contracts/.../contracts/context.py:118` and `:223`.

### Changed

- The commentary at the two-reference cross-check said the coordinate's tenant was not
  compared at all, reasoning from the empty global tenant. That is a correct reason not to
  compare *unconditionally* and not a reason not to compare; it is corrected in place rather
  than deleted, because the reasoning it records is what shaped the guard.

### Tests

- **R-11 closed.** The completeness test enumerated `__dataclass_fields__`, and a property is
  not a field, so a binding could arrive outside the digest while appearing to bind. Measured:
  one per-instance property outside `digest_payload()` left the suite green with zero test
  edits.

  R-11 is now stated precisely: *every public attribute declared on
  `CapacityAuthorizationCandidate` or inherited through its MRO is either a dataclass field
  covered by `digest_payload()` or an explicitly named non-field surface member, and the
  allowlist cannot grow without a disclosed, reviewed change.* It does not claim coverage of
  every attribute an instance could ever expose: the class is a frozen dataclass without
  `__slots__`, so `object.__setattr__` can still staple an attribute onto a live instance, and
  no static check sees that.

  Enumeration is static — `inspect.getmembers_static`, falling back to `dir()` plus
  `inspect.getattr_static` — so it never executes a descriptor, and total over *names*, so it
  asks nothing about how a member is implemented. A first attempt classified instead, reading
  an exempt property's source for the name `self`; that is source classification, and every
  syntactic approximation of "derives from instance state" has a bypass class. The five that
  defeated it — renamed receiver, helper delegate, `getattr`, custom descriptor, inherited or
  class-attached — are now parametrised acceptance tests over the enumerator.

  The allowlist is ratcheted against the merge base (`tests/_surface_ratchet.py`), so it
  cannot grow silently. That closes accidental drift; it does not close a contributor editing
  the class and the allowlist together, which no test in one trust domain can. What it buys is
  that widening becomes disclosed rather than silent — the same residual D-5B1-3's third rule
  carries, recorded rather than repaired.

- The public non-field surface, disclosed in full because nothing was exempt before it existed:
  - surface: digest — a method, computes the canonical digest and stores nothing.
  - surface: digest_payload — a method, returns the payload the digest is taken over.
  - surface: to_canonical_dict — a method, the canonical serialisation.
  - surface: trust_state — constant `PRESENT_BUT_NOT_TRUST_VERIFIED`; a read-only property
    rather than a field so `object.__setattr__` cannot forge it on a frozen dataclass.
  - surface: grants_authority — constant `False`, and no branch in this package returns `True`.
- Suite 277 → 283, 0 failed, 0 skipped.

## [0.2.0] — Cloud Scaling Phase 5B-1: decision-scope repair

Ratified in `docs/architecture/ADR_CLOUD_SCALING_DECISION_SCOPE_PHASE5B1_RATIFICATION.md`.
**Breaking**, pre-1.0: the candidate gains a required field, its digest moves, and its schema
identifier moves with it.

### Added

- `PolicyTargetBindingReferenceV2` — the complete six-component Policy Authority coordinate
  the bounding policy lives at, plus the framed body digest its issuance signature covers and
  the issuing key, bound to one exact execution target scope. Carried **beside**
  `PolicyTargetBindingReference`, which is unchanged. All six components are required; a
  reference carrying five of them cannot address a policy version (D-5B1-5).
- `CapacityAuthorizationCandidate.policy_coordinate_binding` and
  `policy_coordinate_binding_digest` — **required**, because an optional coordinate would
  leave the residual it closes open by default (D-5B1-1).
- `is_policy_authority_digest` / `require_policy_authority_digest` — the Policy Authority's
  bare 64-hex digest shape, validated separately from Phase 5A's `sha256:`-prefixed one. The
  two namespaces are never interchanged and **no converter exists in either direction**: a
  re-prefixed digest is a digest nobody signed, over a frame nobody hashed (D-5B1-4).
- `POLICY_COORDINATE_COMPONENTS`, `POLICY_TARGET_BINDING_V2_SCHEMA_VERSION`, and three
  rejection reasons — `MISSING_POLICY_COORDINATE_BINDING`,
  `MALFORMED_POLICY_COORDINATE_BINDING`, `POLICY_COORDINATE_CONTENT_MISMATCH`.
- Two builder guards: the candidate's two policy references must agree on `policy_id` and
  `policy_version`, and the coordinate must bind this scope. A candidate could otherwise carry
  a V1 binding for policy A beside a coordinate for policy B — two well-formed halves stating
  a contradiction.

### Changed — digests that moved, and who pins each

- `FROZEN_CANDIDATE_DIGEST`: `sha256:db72ffff…` → `sha256:be06c653…`. Every field of a
  candidate enters its digest payload, so this is the floor: no in-candidate binding moves
  none, and widening the existing binding in place would have moved
  `FROZEN_POLICY_BINDING_DIGEST` as well. Pinned in `tests/test_frozen_digests.py`, in
  `cloud-scaling-producer-attestation` (`tests/test_frozen_digests.py`,
  `tests/test_phase5a_invariants.py`, `tests/data/phase5a_candidate.json`), and re-run by
  `cloud-scaling-policy-authenticity` (`tests/test_phase5a_untouched.py`).
- `FROZEN_VERIFIED_ARTIFACT_DIGEST` in `cloud-scaling-producer-attestation`:
  `sha256:519983d8…` → `sha256:5a2a6648…`. That artifact binds the candidate digest, so it
  moved with it. No source in that distribution changed and its version does not move.
- **New pin** `FROZEN_POLICY_COORDINATE_BINDING_DIGEST`:
  `sha256:ad1d1ad9…`. Eleven frozen digests where there were ten.
- Nothing else moved. The nine other Phase 5A constants, the v2 signing payload and the v2
  attestation are asserted unchanged from both sides of the boundary.
- `AUTHORIZATION_CANDIDATE_SCHEMA_VERSION` → `cloud-scaling-capacity-authorization-candidate-2`.
  A new **field set** is a new schema identifier; the F-2 remediation moved the candidate
  digest without moving this identifier, and correctly so — it changed what the payload
  covered, not which fields the artifact carries.

### Superseded, pinned as negative anchors

- `SUPERSEDED_PRE_5B1_CANDIDATE_DIGEST` — the candidate digest while nothing in a candidate
  could name a policy version. Reproducing it would mean the coordinate had left the payload.

### Still not added

No resolution, no signature verification, no clock, no envelope, no authority. Carrying a
complete coordinate is not resolving it: both policy references still report
`PRESENT_BUT_NOT_TRUST_VERIFIED`, and reconciling the coordinate against a verified policy
proof is `ugence-cloud-scaling-policy-authenticity`'s work, not this package's.

## [0.1.0] — Cloud Scaling Phase 5A

Initial release. Never previously released.

### Added

- `CapacityAuthorizationCandidate` — an immutable, exact-typed, explicitly
  **non-authoritative** reconciled request for future authorization, with a canonical
  schema identifier and a deterministic `sha256:`-prefixed digest binding the whole Phase
  4 chain, the D-4 identifiers, the exact action parameters, the execution target, the
  policy binding and the producer attestation's signing identity.
- `build_capacity_authorization_candidate` — the production entry point. Admits only exact
  types, reconciles Phase 4 in full before constructing anything, and consumes the
  validated values returned by the reconciler rather than re-reading its sources.
- `reconcile_phase4` / `ReconciledPhase4Facts` — independent Phase 4 reconciliation,
  recomputing every digest including `decision_digest` over `decision_snapshot`.
- `ProducerAttestationEvidence` — a required, immutable, non-authoritative evidence
  artifact carrying a producer signature over the recommendation digest, under a dedicated
  producer-signing purpose.
- `ExecutionTargetScope` — new Phase 5 vocabulary carrying the **required** `account_id`
  the frozen Phase 4 subject has no field for, plus the magnitude and delta ceilings.
- `PolicyTargetBindingReference` — a structural reference to the bounding policy, tied to
  one exact target scope by digest.
- `EvidenceTrustState` — a **single-member** vocabulary,
  `PRESENT_BUT_NOT_TRUST_VERIFIED`. There is no verified state to reach.
- `AuthorizationCandidateRejectionReason` and eleven typed errors. Every reason is a
  refusal; there is no success member.

### Deliberately not added

No signature verification, no policy resolution, no decision minting, no envelope, no
ActionGate, no credential, no executor, no clock, no effect verification and no learning.
Phase 5B, 5C, 5X, 5D and Phase 6 are all excluded, and no capability toward any of them is
introduced. No placeholder trust verifier and no reserved field for one.

### Audit remediation (pre-merge, same unreleased 0.1.0)

Findings F-1 – F-5 from the independent adversarial audit, fixed before merge. The
distribution has never been released, so the version does not move.

- **F-1 (test-suite defect, TEV-1).** TEV-1's consumer-boundary test scanned raw file text
  for its own package name, so it flagged this package's *forbidden-import denylist* — a
  statement that TEV-1 is **not** imported — as if it were an import. Replaced with AST
  semantic import detection covering plain, dotted, aliased, multiline, `from`-form and
  string-literal dynamic imports, and proven both directions: it fires on a genuine
  injected import and ignores denylists, prose, error messages and negative controls.
- **F-2 (production defect, this package).** `_digest_payload()` accepted 37 parameters and
  read 35: `policy_binding` and `producer_attestation` were passed in and ignored. A rogue
  policy issuer or forged producer signature could be carried under an unchanged,
  self-validating candidate digest. Both artifacts are now bound in full. **The candidate
  digest moved** as a result; the superseded value is pinned as a negative anchor.
- **F-3 (test-suite defect).** Gates that no test exercised, plus mutation kills previously
  attributed to the wrong gate. Focused behavioural tests added that isolate each gate.
- **F-4 (production defect, this package).** `_ALLOWED_KEYS` / `_REQUIRED_KEYS` were
  annotated `Final` inside dataclass bodies, which makes them real **fields** — constructor
  keywords a caller could override. Four occurrences across three classes, now `ClassVar`.
- **F-5 (documentation defect).** The claim that Phase 4C "carries no recommendation id"
  was wrong. The ID *is* transitively bound by the Phase 4C digest chain; it is simply not
  recoverable from the digest and not an independently cross-checkable field.

### Versioning judgement

`0.1.0` — a new, never-released distribution, matching the Phase 4C and TEV-1 convention
for a first contract package. No `CONTRACT_VERSION` is minted: that is the *provider*
convention in this repository, not the contract-shape convention. No other package's
version changes, and no existing package's source is modified.
