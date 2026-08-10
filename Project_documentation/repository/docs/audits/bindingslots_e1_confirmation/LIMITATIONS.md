# E1 independent confirmation — limitations

1. **Confirms the bundle, not a component.** Like PR #1351, this replicates the E1 **bundle**; it does
   not isolate which part (explicit keys, separate encoders, contrastive loss, hard negatives, hard
   top-1, learned null key) drives the effect. No ablations were run.

2. **Still a successor, not a repair.** B0 (anonymous slots) remains at chance;
   `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` stands.

3. **Independent but comparable synthetic task.** The vocabulary, templates, evaluator, and seeds are
   new and disjoint, but the task family is the same compositional-matching construction at comparable
   difficulty — it is not natural language, real entities, or enterprise data. Confirmation shows
   robustness to fresh content, not transfer to a different task family.

4. **Scoped to the frozen density and recipe.** ~32 keys/episode, C1 recipe, no retuning. Capacity
   scaling, versioning, and long-context were not tested.

5. **No-match remains the weakest gate.** Learned-null-key abstention leaves a residual false-accept
   (~0.15, one seed 0.22) — within the frozen 0.30 gate but not solved; open-set rejection needs
   dedicated work before any reliance.

6. **Value path is a lookup.** E1's value read is exact given the selected key (oracle value ≈1.0); the
   confirmation tests addressing, not value decoding.

7. **Reliability unaffected.** The external table still provides operational reliability; this result
   neither requires nor replaces it.

8. **KDA stays blocked.** `E1_FOLLOW_ON_RESEARCH_ELIGIBLE` denotes eligibility for further *research*
   only; it does **not** unblock KDA, MLA, Phase, or any downstream validation, and no follow-on
   experiment is started here.
