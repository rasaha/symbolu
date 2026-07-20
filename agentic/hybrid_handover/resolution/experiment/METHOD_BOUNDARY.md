# METHOD_BOUNDARY — Exploratory Resolver Study v0.1

The mechanism of the resolver under test, and an explicit statement of what it does
NOT use.

## No LLM, no prompt, no training
The HybridRelationshipResolver is **fully deterministic symbolic code**. It contains:

- **no language model** of any kind (no API call, no local model, no embedding);
- **no prompt** and no natural-language instruction to any model;
- **no training, fine-tuning, or learned parameters** — every threshold and lexicon
  entry is a literal constant written into the source;
- **no randomness at inference** — identical inputs yield identical outputs, and two
  full experiment repetitions are byte-identical.

The only stochastic component anywhere in the study is the paired bootstrap in
`stats.py`, which is seeded with a fixed constant (20240601) recorded in the manifest,
so it too is reproducible bit-for-bit.

## How it works (composition, not replacement)
The resolver is a richer **relationship-proposal layer** that feeds the **frozen
GraphTraversalResolver governance + packet builder**, reused verbatim by composition
(`self._gt`). Concretely, beyond the narrow fixed cue set of the deterministic
baselines it adds:

- a broader *general-legal* cue lexicon (supersede / governs / override / exception /
  reference / rename synonyms) — authored from general legal English and the visible
  corpus, frozen before hidden evaluation;
- temporal precedence (`effective_after`) by comparing parsed effective years;
- rename / migration / alias resolution (`same_as`);
- nested-exception chaining;
- definition-conflict and version/table-conflict proposals;
- per-edge confidence and a confidence-gated abstention (τ = 0.5).

Because governance and packet construction are the frozen components unchanged, any
measured difference versus GraphTraversal is attributable to **relationship
discovery**, not to governance or packet realization. The ablation A1 (removing the
semantic proposal layer) confirms this: it returns the macro exactly to the
GraphTraversal baseline.

## Why deterministic-symbolic for an "exploratory" study
The question this study asks is narrow and architectural: *does a richer structured
relationship layer, holding governance and packet fixed, move the owner-clean
capability metrics on unseen wording?* A deterministic resolver answers that without
confounding the result with training data, prompt sensitivity, or sampling noise, and
keeps the whole pipeline auditable and exactly reproducible.
