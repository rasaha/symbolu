# Changelog — ugence-cloud-scaling-envelope-issuance

## 0.1.0 — Phase 5B-4, initial release

Composition root for Risk Authority's Phase 5 envelope issuance seam.

- `CloudScalingEnvelopeIssuance` with fail-closed `production` and `reference` factories;
  `issue(request)` builds one verification port and one seam per act.
- `CloudScalingArtifactVerification` implements `risk_authority.api.ArtifactVerificationPort`:
  runs the 5B-0A and 5B-0B verifiers at the seam's instant, revalidates their artifacts,
  reconciles them to the candidate and the instant, re-derives the candidate's digests, and
  reports the five ratified bindings.
- Ratified binding kinds and `ArtifactBindingStatus` / `CloudScalingVerificationReport`.
- Neighbours unmodified: Risk Authority 0.6.0, Phase 5A 0.2.0, 5B-0A 0.2.0, 5B-0B 0.9.0.
