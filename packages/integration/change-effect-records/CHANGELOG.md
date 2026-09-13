# Changelog

All notable changes to `ugence-change-effect-records`.

## 0.1.0 — 2026-09-13

First release. Stage 1 item 3.3, with the admission succession data of item 3.6,
authorized as tracked work by the owner on 2026-09-13 (ADR §8) and scoped against GERL
target classification version 4.2.10 and its recorded erratum.

### Added

- The thirteen record types of the classification chain, frozen and digest-bound:
  `ClassificationRecord`, `ConfirmationAmendment`, `InvestigationRecord`,
  `InvestigationExtensionRecord`, `InvestigationClosureRecord`, `FinalResolutionRecord`,
  `AuthorizationBinding`, `ResolutionRevocationRecord`, `RevocationImpactRecord`,
  `AdmissionReservationRecord`, `AdmissionClaimRecord`, `AdmissionCompletionRecord`,
  `AdmissionResolutionRecord`; with the parts they carry — `RegistryEffectResult`,
  `BlockingObligation`, `PrimitiveEffect`, `ClosureEffectBundle`, `SampleBinding`.
- The canonical-bytes profile of rule section 6a over the repository's `_canon.py`
  envelope, and the `chain_id` and `obligation_id` derivations, reproducing all eight of
  the rule's published test vectors.
- Closed vocabularies, the admission succession and control-register transition tables as
  data, and the refusal-code register of rule section 10a.
- Owner decision 6b, taken 2026-09-13, is enforced in `RevocationImpactRecord`: a revoked
  applied delta always requires a state-repair candidate, and downstream-exposure
  remediation is a separate obligation carried alongside it.

### Deliberately absent

No classifier, replay harness, projection, routing, policy resolution, sampler, admission
boundary, memory reader or writer, or runtime registration. Boundary tests assert the
absence rather than documenting it.
