# Interoperability Readiness

## What this trial demonstrated
An independently authored verifier, given only the published package, **recomputed the runtime
config fingerprint exactly**, ran **blind** (never reading expected/derivations), and reproduced
the mandatory expected results for **83 of 86** fixtures from the actual `(ValidationRecord,
CandidateArtifact)` bytes — with **0 implementation defects**. This is strong evidence that the
v1.1.0 package's mandatory corpus is a genuine input-driven oracle for the mechanical classes it
covers (strict JSON, Unicode, lexical Jaccard boundaries, explicit-map defects, descriptor
mismatch, structural violations, determinism, privacy, modality, zero-assertion).

## What blocks full interoperability today
1. **3 defective mandatory fixtures** (DT03, UC08, UC09) whose expected outcome cannot be produced
   by any faithful implementation. These must be corrected before a second implementation is scored.
2. **exact/structured method-label ambiguity** (SEC05, UC07) — outcome-preserving but should be
   pinned so method sub-counts are cross-implementation stable.
3. **Two under-documented contracts** — the config-fingerprint serialization and the projection Π
   field set are recomputable but not published normatively; publish both.
4. **4 informative categories** (MEANING_DISTORTION, CERTAINTY_OVERSTATEMENT, SCOPE_EXPANSION,
   QUALIFICATION_OMISSION) are not implementable from published resources alone; they remain
   non-gate until the engine-level rules are specified.

## Readiness statement
Interoperability is **substantially enabled** but **not yet demonstrated end-to-end**: a single
independent implementation reproduced 83/86, and the remaining 3 are package defects rather than
disagreements about semantics. After the point-release corrections above, the corpus is ready to
serve as the shared oracle for a genuinely separate Implementation B.
