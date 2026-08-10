# E1 capability probe — limitations

1. **Bundle test, no attribution.** E1 changes several things at once (explicit keys, separate encoders,
   contrastive supervision, in-episode hard negatives, hard top-1 read, learned null key). A pass shows
   the **bundle** beats B0; it does **not** isolate which component is responsible. Component ablations
   were **not** run (out of scope).

2. **Not a repair of anonymous BindingSlots.** E1 is a **successor** architecture. B0 (the frozen
   anonymous-slot recipe) remains unrepaired; `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` stands.

3. **B0 is the recipe re-instantiated on the shared task, not the original 2M-param checkpoint.** The
   original needle task cannot express paraphrase or compositional identity, so the literal checkpoint
   is not evaluable here. B0 keeps the anonymous-slot mechanism and its own objective, unchanged, with
   no explicit-key supervision (documented in `DESIGN_DECISIONS.md`).

4. **Synthetic compositional task, not natural language.** "Semantic" identity is a composition of
   primitive tokens with synonym surface forms — enough to force learned matching over surface hashing
   (mechanically verified), but it is **not** free-form NL, real entities, or enterprise data.

5. **Scoped to the frozen ~32-key density.** The claim holds at the preregistered density; larger
   capacity, capacity scaling, and long-context were **not** tested.

6. **No-match is the weakest gate.** Learned-null-key abstention leaves a residual false-accept
   (~0.07–0.13); open-set rejection remains the hardest part and would need dedicated work before any
   reliance. It clears the frozen gate but is not solved.

7. **Value path is a lookup.** E1's value read is exact given the selected key (oracle-key value
   accuracy ≈ 1.0), so all difficulty is in **addressing**; this is not a test of value decoding.

8. **Reliability unaffected either way.** The external table already provides exact factual reliability;
   a positive E1 result does **not** authorize removing the external verifier, and a negative one would
   not have harmed the operational path.

9. **KDA stays blocked.** Nothing here bears on KDA; `KDA_VALIDATION_BLOCKED` is preserved and a pass
   additionally requires `INDEPENDENT_NEURAL_MEMORY_CONFIRMATION_REQUIRED` before any further claim.

10. **Determinism scope.** Model-state hashes, metrics, and artifact hashes are deterministic and
    committed; per-seed E1 hashes differ across seeds by construction (fresh seeds), identical on replay
    of the same seed.
