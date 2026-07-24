# Semantic Preservation Protocol (Phase 11)

*`claim_integrity/equivalence.py` + `claim_integrity/metrics.py`. Preservation is evaluated **per
dimension** and never as one aggregate similarity score — because similarity is HIGHEST exactly on the
pairs where meaning has been inverted.*

## Why not one similarity score

Lexical overlap and embedding cosine both rate these pairs as near-identical, yet each is a meaning
inversion:

| Gold | Produced | Dimension changed |
|---|---|---|
| the drug **may** cause harm. | the drug causes harm. | modality |
| **no evidence that** the drug harms patients. | the drug is false for patients. | evidence-status |
| the drug **does not** prevent infection. | the drug prevents infection. | polarity |
| the drug is **associated with** better outcomes. | the drug **causes** better outcomes. | causal direction |
| **according to one review,** the drug improves outcomes. | the drug improves outcomes. | attribution |
| lowers risk by **10 to 20** percent. | lowers risk by 15 percent. | range |
| the drug **should** be considered. | the drug is used. | normative status |

A single similarity threshold would accept every one of these (`SIMILARITY_TRAPS` in `equivalence.py`).
The per-dimension check flags all seven on the correct dimension — verified in the test suite.

## The dimensions scored (each separately)

`polarity · modality · uncertainty · numeric · ranges · causal_direction · attribution ·
evidence_status_language · conditions · exceptions · temporal_scope · jurisdiction · population ·
normative_status · propositional`.

`preservation(gold_claim, produced_text)` returns `per_dimension` (a bool per dimension),
`material_preserved` (True only if **every** MATERIAL dimension is preserved **and** the propositional
core survives), and `changed_dimensions`. `MATERIAL_DIMENSIONS` are the ones whose change alters what
would be governed; a mismatch on any is material drift regardless of surface similarity.

## Endpoints (metrics.py)

- **material_drift_rate** — fraction of gold claims whose aligned produced claim is not
  materially preserved (an unaligned/omitted gold claim counts as maximal drift).
- **omitted_claim_rate / invented_claim_rate** — completeness in both directions.
- **mean_count_error, over_split / under_split** — atomicity, in both directions (not "more splitting
  is better").
- **per_dimension_preservation** — the vector, reported in full in the evaluation; the headline number
  never hides which dimension failed.

## An early, honest result (before the downstream phase)

Scoring the methods on **material drift** already surfaces a finding that the coarse fragile-dimension
proxy (Phase 8) hid:

| Method | material_drift | omitted | under_split | over_split |
|---|--:|--:|--:|--:|
| Q_oracle | 0.000 | 0.000 | 0 | 0 |
| **B_sentence_split** | **0.136** | 0.068 | 78 | 0 |
| **P_claim_integrity** | **0.136** | 0.068 | 78 | 0 |
| A_preserve_whole | 0.545 | 0.273 | 312 | 0 |
| F_openie | 0.705 | 0.000 | 0 | 312 (invented 0.295) |

**On material text drift, the reference component ties sentence splitting.** The component's only
substantive difference from sentence-splitting on this corpus — resolving a dangling cross-sentence
pronoun — does not change text-level drift, because the referent noun usually survives in the span
anyway. Both under-split the 78 ADVERSARIAL_SCOPE conjunctions (counted here as an omitted second
claim).

This is exactly the H0-1 question, and at the text-drift layer **H0-1 is not yet rejected.** The
component's distinctive value, if it has one, must appear **downstream** (Phase 18): a dangling "it"
sent to evidence retrieval builds a query about an ambiguous entity, and an under-split conjunction is
evaluated conservatively rather than unsafely. The text-drift metric cannot see either effect; the
downstream-impact experiment is built to. We record the tie now, before running that experiment, so the
downstream result is interpreted against a preregistered null, not a moving target.

## Traps the protocol also guards against

- **False rejection (failure type 50):** the two lexical variants of each corpus example are true
  paraphrases; `material_preserved` must return True across a variant pair. A protocol that only
  punished missed drift, without this guard, could score well by rejecting everything.
- **Structural-only preservation:** `population` and reference are checked by span/substring, not
  lexical class, so "recoverable somewhere" is not mistaken for "attached to the right claim" — the
  finer scope-attachment check is what separates preserve-whole (0.545 drift) from the splitters.
