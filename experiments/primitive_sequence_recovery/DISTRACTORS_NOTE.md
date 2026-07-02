# Distractors Note — Primitive-Sequence Recovery (Step C.4)

**Status:** Documentation only. Records `frozen/distractors.json`. **No** manifest,
realizer, or run_params were created; readiness remains **NOT_READY**. No embeddings,
no similarity, no scoring, no retrieval, no network/LLM, no runtime sampling, no Stage A
change. Design basis: `SCHEMA_SPECIFICATION.md` §5, `PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md`.

## What was produced

For **every** active word (107) a frozen candidate set of exactly **K = 8** `word_id`s:
the **true target** (exactly once) plus **7 distractors**. Stored in
`assignments["<word_id>"]`, seed-recorded, fully reproducible.

- **Candidate-set representation.** The stored list is the *complete* ranking pool of
  K = 8 including the true target (target position is shuffled to remove positional
  leakage). This differs from the earlier `SCHEMA_SPECIFICATION.md` §5 phrasing
  ("K−1 distractors in the list, true added at run"); the spec has been updated in the
  same commit to match this K-including-target representation. The JSON schema
  (`schemas/distractors.schema.json`) is unchanged — it only requires an array of
  strings — so both representations are schema-valid; this one is unambiguous.

## Construction rule (deterministic balanced sampling)

No semantic-class metadata exists in the corpus (`family_id` is etymological/unique, not a
broad semantic class), so **class-matched hard negatives are not available**. Distractors
are drawn by a deterministic, balance-enforcing rule instead:

1. Candidate pool for target *t* = all **active** words except *t* (excluded words are never
   in the pool).
2. Seed a single RNG with the frozen seed, iterate targets in sorted `word_id` order.
3. For each target: shuffle the pool (seeded), then **stable-sort by current usage count**
   and take the 7 **least-used** words. This makes every active word appear as a distractor
   an equal number of times; the seeded shuffle breaks usage ties and decorrelates the
   choice from insertion order.
4. Prepend the target, then shuffle the 8-list (seeded) so the target's position carries no
   information.

**Result:** every active word is used as a distractor **exactly 7 times** (min = max = 7;
749 slots / 107 words); no duplicates within a set; target present exactly once; no excluded
or inactive/unknown IDs anywhere.

Because all 107 active words have **distinct** canonical meanings (enforced at the ontology
freeze), distinct candidate `word_id`s automatically imply distinct canonical meanings — the
"no duplicate canonical meaning among candidates" rule holds by construction.

## Seed

- `sampling_seed = 20260702` (recorded in `distractors.json`). Re-running the builder with
  this seed reproduces the file **bit-for-bit** (verified: identical sha256 on re-run).

## Why frozen distractors are necessary

If candidate sets were sampled at run time, the ranking difficulty — and therefore the score
— would depend on an unfrozen random draw, and re-sampling after seeing results would be a
researcher degree of freedom that inflates false positives. Freezing the per-word candidate
IDs with a fixed seed makes the ranking task **fully reproducible** and forbids post-hoc
reshuffling. The candidate sets are fixed **before** any realizer or score exists (there is
none yet), so they cannot be tuned to a result.

## Limitations

- **No semantic-class matching (material).** Distractors are class-agnostic random-balanced,
  not matched hard negatives. Consequences: (a) task difficulty is **uncontrolled** and
  generally *easier* than a hard-negative design — some distractors will be semantically far
  from the target, so a positive result is weaker evidence than it would be against matched
  negatives; (b) difficulty is not equalized across targets. This is a limitation of the
  available metadata, not of the sampler. If a broad semantic-class field is later added to
  `word_list.json`, distractors should be re-frozen as class-matched (new file + new seed).
- **`match_keys = []`** records that no matching key was applied (honest empty, not omitted).
- **Small pool.** 107 active words; 7 distractors per target draw ~6.5% of the pool, so
  distractor sets overlap heavily across targets (unavoidable at this N).
- **Shared corpus.** Distractors are other corpus words; they inherit the corpus's own
  coverage biases (heavier on emotions/abstractions early, concrete nouns late).

> structure, not validated meaning.
