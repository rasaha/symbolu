# Consistency Review of the v1.2.0 Normative Additions

Each new document was checked against the Formal Specification, the BASE Profile, the Companion
Release, the v1.1.1 package bytes, Implementation A, Implementation B, and the independent review.
**No contradiction was found.**

## Checks performed
| New document | Checked against | Result |
| --- | --- | --- |
| CANONICALIZATION.md | every published root/fingerprint/Π hash | consistent — the four roots + fingerprint recompute from the stated procedure |
| CONFIG_FINGERPRINT_SPEC.md | resource-manifest `outcome_affecting` set; release-manifest roots | consistent — recomputes `d01e466e…` from the manifests alone (verified) |
| PROJECTION_PI_SPEC.md + projection-pi.schema.json | `expected.projection_pi` across sampled fixtures | consistent — recipe reproduces `projection_pi_sha256`; shape `{outcome, findings[category,polarity], 5 counts}` matches; excludes the x-tap histogram |
| INTEROPERABILITY_PROFILE.md | A-vs-B agreement (86/86); v1.1.1 stage-precedence audit | consistent — the normative-agreement set is exactly what A and B matched, incl. the correspondence-stage histogram |
| EXTERNAL_IMPLEMENTER_GUIDE.md | BASE Profile scope; informative INF handling | consistent — informative-only categories remain non-gate; no out-of-scope behavior required |
| VERSIONING_RATIONALE.md | SemVer intent; unchanged roots | consistent — MINOR (adds normative surface, no behavior change) |

## Cross-artifact agreement
- Both independently authored implementations (A: Python; B: JavaScript) and the independent
  reviewer reconstructed the fingerprint and Π and matched — the new documents describe exactly
  that reconstructed behavior, so they cannot contradict a conforming implementation.
- The documents add no requirement that any of the three existing analyses would fail.

## Outcome
No contradiction. No behavior is altered. The additions are safe to publish as v1.2.0.
