# Specification Ambiguities & Package Defects found by Implementation A

## Package defects (fixture expected result unreachable from the CandidateArtifact bytes)
1. **DT03** — artifact `Systém` (a bare word) cannot correspond to VR `acme owns system b`;
   expected ASSURED is wrong. Correction target: **fixture** (use a full faithful proposition as
   the artifact, keep the NFC pair in `alt_representation`). Not runtime-semantic.
2. **UC08 / UC09** — artifact `systém` ≠ VR `system` (diacritic); expected ASSURED is wrong under
   the published normalization (no diacritic fold). Correction target: **fixture** (either make the
   VR entity `systém` too, so it is a genuine clean match, or change the expected result to
   CORRESPONDENCE_UNRESOLVED). Not runtime-semantic.

## Specification ambiguities (outcome-preserving)
3. **exact vs structured stage for free-text S-V-O** — a plain text proposition that equals the
   entry's canonical `subject predicate object` string is classified `exact` (stage 2) by a
   staged matcher, but several v1.1.0 fixtures (SEC05, UC07, and the UC clean cases) record it as
   `structured` (stage 3). CR02 records the identical string as `exact`. The published resources do
   not state whether the exact stage reconstructs a proposition string from S/P/O. Correction target:
   **specification clarification** (define the exact-stage input) and align the affected fixtures'
   method sub-counts. Not outcome-affecting (projection Π excludes the method histogram).

## Under-documentation (recomputable, but not from a normative doc)
4. **config-fingerprint serialization** — the exact JSON object hashed to produce the runtime
   fingerprint is defined only in the corpus builder, not in a normative document. Implementation A
   reconstructed it from the release-manifest (target ids, canonicalization, corpus-exclusion note) +
   frozen thresholds + resource-manifest `outcome_affecting` flags, and it MATCHED. Recommendation:
   publish the fingerprint construction recipe normatively so a second implementer need not reverse it.
5. **projection Π shape** — Π's exact field set (outcome, findings[category,polarity], the 5
   evaluation-summary counts) is discoverable from `expected.projection_pi` but not schema-pinned.
   Recommendation: publish a projection schema so Π hashes are cross-implementation stable by
   construction rather than by inference.

None of items 1–5 require altering a frozen TAP-E7-BASE semantic (thresholds, precedence, taxonomy,
polarity, band order, scope semantics, verify-only). Items 1–2 are fixture corrections; 3–5 are
clarifications/documentation.
