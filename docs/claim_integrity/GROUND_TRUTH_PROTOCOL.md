# Ground-Truth Protocol (Phase 7)

*Ground truth is **not** generated from the ClaimIntegrity implementation. Two independent annotation
procedures produce claim segmentations; adjudication handles alternate valid decompositions and
irreducible ambiguity without coercing them to one gold sequence. Implemented in
`claim_integrity/dataset.py`; corpus `ci_corpus_v1` at `claim_integrity/data/v1/corpus.json`.*

## Anti-circularity

Each example carries a **TRUE latent decomposition** — the gold claim units with every semantic
dimension (polarity, modality, uncertainty, conditions, exceptions, temporal/jurisdiction/population,
numerics, attribution, evidence-status, references) and, per claim, the **fragile dimension** whose loss
changes downstream governance and the **downstream consequence** (unsafe-allow vs conservative-block).
A decomposition *method* sees only OBSERVED text (`original_text` + `context`) and must recover the
units. No ClaimIntegrity rule is used to define gold, so a method that matches gold is genuinely
recovering the intended meaning, not replaying the scorer.

## Two annotation procedures

- **Annotator A — semantic proposition & scope.** Segments by independently-meaningful proposition and
  checks that every qualifier/quantifier/condition/exception is attached to the right proposition.
- **Annotator B — downstream evaluability & governance.** Segments by what is *independently evaluable
  downstream*: a conjunction of two separately-checkable claims may be split one finer; a dependent
  fragment (a pronoun-bearing follow-up) may be merged into its antecedent so the unit is evaluable.

The two share the **hard structure** — the count of core propositions, negation, numerics, attribution,
evidence-status — and diverge only on the **soft atomicity** of borderline conjunctions
(`MULTI_CLAIM`) and cross-sentence dependencies (`CROSS_SENTENCE`). This is a realistic, bounded
disagreement: annotators rarely dispute *what* is claimed, often dispute *how finely* to cut it.

## Adjudication

- **A == B →** gold decomposition and count.
- **A ≠ B →** both counts are recorded as **acceptable alternate decompositions**;
  `annotator_disagreement = True`. The disagreement is *not* resolved to a single number — a method
  matching *either* valid decomposition is scored correct on atomicity (Phase 12). This directly
  addresses H0-15 (does human disagreement make gold too unstable?): disagreement is confined to
  atomicity granularity, never to the semantic dimensions that drive the safety endpoint.
- **Irreducible ambiguity** (`ADVERSARIAL_SCOPE`) is kept as ambiguity: the example records the
  unacceptable drift variants explicitly, so the test is "did the method avoid the known-wrong
  decompositions", not "did it hit one canonical string".

## Recorded agreement (ci_corpus_v1, 832 examples)

- **Claim-count exact agreement: 0.934.** Disagreement is 0 on `SIMPLE_ATOMIC`, `QUALIFIED_COMPLEX`,
  and `ADVERSARIAL_SCOPE`; it is concentrated on `MULTI_CLAIM` (0.262) and `CROSS_SENTENCE` (0.202) —
  exactly the soft-atomicity strata, by construction.
- **Overall disagreement rate: 0.066**, all of it on atomicity granularity, **none** on a semantic
  dimension (polarity, modality, uncertainty, numerics, attribution, evidence-status). The safety
  endpoint never rides on a disputed label.

## Corpus shape

- **832 examples**, 13 domains × 5 partitions, 1144 gold claims, two lexical variants per case.
- **Partitions:** SIMPLE_ATOMIC 338, QUALIFIED_COMPLEX 182, MULTI_CLAIM 130, CROSS_SENTENCE 104,
  ADVERSARIAL_SCOPE 78.
- **806 examples carry an `unsafe_allow` downstream consequence** — losing the fragile dimension would
  flip the thin gate to deliver-as-supported. This is the population the primary safety endpoint scores.
- Each example records: original text, paragraph context, gold claim units (with all dimensions and
  source-relevant fields), expected claim count, **acceptable** alternate decompositions,
  **unacceptable** drift decompositions (with the failure type each exhibits), downstream evidence
  consequence, downstream delivery consequence, both annotator counts, disagreement flag, and rationale.

## What the corpus deliberately includes

- **Cases where "preserve whole sentence" is genuinely safest** (SIMPLE_ATOMIC with a single
  qualified claim) — so the trivial baseline is not strawmanned.
- **Cases engineered to make decomposition lose** (ADVERSARIAL_SCOPE: an exception attaching to only
  the second clause of a conjunction) — so the component is not flattered.
- **True paraphrase pairs** (the two lexical variants) — so the semantic-equivalence machinery is
  tested against wrongly rejecting valid paraphrase (failure type 50), not only against missing drift.

## Honesty note

This corpus is **deterministic and constructed by us**, from templated skeletons. Its *rates* (drift
frequencies, downstream flip rates) are properties of the construction and will not transfer to live
model outputs. What the study puts weight on is the *mechanism and ordering*: which dimensions are
fragile, whether downstream layers absorb the drift, and whether simple methods match the component.
An external, independently-annotated corpus of real model outputs is the necessary follow-up (stated
in the falsification plan, revisited in Phase 27).
