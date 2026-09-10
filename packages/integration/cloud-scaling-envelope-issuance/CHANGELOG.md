# Changelog — ugence-cloud-scaling-envelope-issuance

## [Unreleased] — public_api.json no longer records the interpreter it was generated on

No API change: every exported symbol, kind, field list and version is identical. The
manifest's `class` entries for exception types listed `add_note` and `with_traceback`,
which are inherited from `BaseException` rather than declared by this package — and
`add_note` exists only from Python 3.11, so a 3.10 run could never reproduce a file
generated on 3.11 whatever the package declared. `scripts/generate_public_api.py` now
excludes inherited exception methods, and the manifest is regenerated accordingly. This
is what unblocked the suite's 3.10 leg, which the package's own
`requires-python >= 3.10` had always claimed and no workflow had ever run.

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
