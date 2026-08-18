# Changelog — ugence-cloud-scaling-authorization-contracts

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

### Versioning judgement

`0.1.0` — a new, never-released distribution, matching the Phase 4C and TEV-1 convention
for a first contract package. No `CONTRACT_VERSION` is minted: that is the *provider*
convention in this repository, not the contract-shape convention. No other package's
version changes, and no existing package's source is modified.
