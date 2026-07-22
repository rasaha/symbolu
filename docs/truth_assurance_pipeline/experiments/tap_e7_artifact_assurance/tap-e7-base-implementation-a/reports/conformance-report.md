# TAP-E7-BASE Implementation A — Conformance Report

## Setup verified from the repository (not inferred)
- Package commit: `57c7106`; package path `docs/…/tap-e7-base-companion-1.1.0/`.
- Runtime config fingerprint recomputed independently from the resource-manifest + release-manifest:
  `sha-256:d01e466e5bb57d6a1a00d42b01fb9943d9208e6e39b6a90413a0b247b0416734` — **MATCH**. Execution gate passed.
- Package composite hash before and after execution: **`006ab443…` unchanged** — the implementation wrote nothing into the package.
- Blind boundary: verifier made **zero** reads of `expected/` or `derivations/` during evaluation (`results/blind-proof.json`).

## Mandatory corpus (86 authoritative fixtures)
| Class | Count |
| --- | --- |
| EXACT_PASS | **81** |
| SEMANTIC_PASS_WITH_ALLOWED_TRACE_DIFFERENCE (projection Π identical) | **2** (SEC05, UC07) |
| PACKAGE_DEFECT (Impl A byte-faithful result is correct; fixture expected is unreachable) | **3** (DT03, UC08, UC09) |
| IMPLEMENTATION_DEFECT | **0** |

**83 / 86 mandatory fixtures are semantically reproduced** (outcome + findings + projection Π match).
The 3 non-passes are defects in the *package*, surfaced by the independent implementation — not
implementation failures. Impl A does **not** reach 86/86 exact; per §29 it therefore does not
claim complete mandatory conformance.

### The 3 package defects (Impl A output is the correct one)
- **DT03** — CandidateArtifact is the bare demonstration word `Systém`, not a proposition; it
  cannot correspond to VR entry `acme owns system b`. Faithful result = FABRICATION (NOT_ASSURED);
  fixture expects ASSURED. Root: the determinism helper stored the demo token as the artifact.
- **UC08 / UC09** — artifact entity `systém` differs from VR entity `system` by a diacritic. BASE
  publishes no diacritic-folding rule; NFC keeps them distinct → Jaccard 3/5 → CORRESPONDENCE_UNRESOLVED
  (INDETERMINATE); fixture expects ASSURED. Root: fixture asserted a clean match without the tokens matching.

### The 2 allowed-trace differences (projection Π identical, minor)
- **SEC05, UC07** — outcome, findings, and projection Π (with its hash) all match. Only the
  non-projected `x-tap correspondence_method_counts` differs: Impl A records `exact` (a full-text
  normalized string match, stage 2), the fixture records `structured` (stage 3). This is a
  SPEC_AMBIGUITY on the exact/structured boundary for free-text S-V-O (see specification-ambiguities.md).
  Not outcome-affecting; Π excludes the method histogram.

## Informative corpus (4 non-gate fixtures)
INF01–INF04 (MEANING_DISTORTION, CERTAINTY_OVERSTATEMENT, SCOPE_EXPANSION, QUALIFICATION_OMISSION):
Impl A abstains (produces CORRESPONDENCE_UNRESOLVED or no finding). These require full engine-level
semantic comparison not derivable from published resources → **SPECIFICATION_UNDERSPECIFIED for a
resource-only verifier**. Correctly excluded from the mandatory gate; not counted as failures.

## Per-stage comparison
For every mandatory fixture the harness compared outcome, findings, finding polarity,
evaluation-summary counts, projection Π, and projection hash. Divergences are recorded per fixture
in `results/mandatory-results.json` and `results/defects/`.
