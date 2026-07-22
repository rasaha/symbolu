# Specification Ambiguities observed by Implementation B

Implementation B reached 86/86 mandatory exact with no outcome-affecting ambiguity. Two
documentation gaps (recomputable, non-blocking) match those Implementation A reported:

1. **Config-fingerprint serialization** — the exact JSON object hashed for the runtime fingerprint
   is not published normatively; B reconstructed it from the release + resource manifests and the
   corpus-exclusion note, and it MATCHED. Recommend publishing the recipe.
2. **Projection Π shape** — Π's field set is inferable from `expected.projection_pi` but not
   schema-pinned. B implemented `{outcome, findings[category,polarity], 5 summary counts}` and all Π
   hashes matched. Recommend publishing a Π schema.

Bounded implementation notes (not package defects): imperative/instruction detection uses a small
closed lead-word set (the resources do not fully pin imperative detection); BASE-MD is implemented
as the conformance subset the mandatory corpus exercises. Neither affected any mandatory result.
