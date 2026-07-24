# Ground-Truth Protocol & Corpus (M2)

*`scope_integrity/dataset.py`; corpus `sc_corpus_v1` at `scope_integrity/data/v1/corpus.json`. 520
scope-spanning conjunctions, built in the shape the FROZEN ClaimIntegrity downstream adapter consumes,
so unsafe delivery is scored by the exact prior machinery.*

## Corpus shape

- **520 examples**, 13 template families × 8 domains × 5 lexicalizations, 1080 gold claims, 880
  unsafe-allow claims.
- **Families:** postposed/preposed/nested exception, shared negation, shared modality, numeric/temporal
  qualifier, attribution-spanning, one-supported-one-unsupported, mixed assertion+recommendation,
  multiple-subjects, cross-sentence antecedent, adversarial punctuation (40 each).
- **Domains:** legal, medical, finance, safety, software, policy, scientific, operational.
- **120 ambiguous** examples (nested exception, multiple subjects, adversarial punctuation) where scope
  attachment is genuinely uncertain; **400 provable**; **168 held-out**.

Each example carries: original text, gold atomic claims (with propagated governing material), a
**governing-scope graph** (element → the conjunct indices it governs), acceptable decompositions,
unacceptable (drift) decompositions, an **ambiguity flag**, a **`provable`** flag (can attachment be
resolved deterministically — used by the hybrid), a **held-out** flag, two-annotator counts, and a
rationale.

## The governing-scope graph is the ground truth

For each governing element (subject, negation, modality, uncertainty, exception, condition, temporal,
numeric, attribution, evidentiary), the graph records **exactly which conjuncts it governs**. A
decomposition is scope-faithful iff every element is propagated to precisely those conjuncts — no
detachment (omission) and no spurious attachment. Subject-carry, qualifier-attachment, and
exception-attachment accuracy (secondary endpoints) are measured against this graph, not against a
single gold string.

## Two annotation procedures

- **Annotator A — proposition/scope segmentation:** counts the governing propositions and their scope.
- **Annotator B — downstream evaluability:** on **ambiguous** families, B may keep the span whole
  rather than commit to a contested attachment (returning 1 unit).

They agree on the number of governing propositions and diverge only on the ambiguous families
(nested/multi-subject/adversarial). Recorded disagreement rate **0.052**, concentrated there. Both the
gold split and, for ambiguous examples, the whole-span preservation are recorded as **acceptable** — so
preserve-and-flag is never wrongly scored as an error on a genuinely ambiguous case.

## Held-out discipline (anti-overfit)

Two mechanisms guard against the study "constructing the corpus around the mechanism":

1. **Held-out lexicalization** — the 5th subject noun per domain (index 4) is never used to design the
   variant rules (M3); it only appears at evaluation.
2. **Held-out families** — `multiple_subjects` and `adversarial_punctuation` are held out entirely from
   rule design. They are also the ambiguous families where a scope-carrying splitter is *expected* to
   struggle and preserve-and-flag is *expected* to win.

**168 examples are held-out.** The falsification plan requires the primary result to hold on the
held-out slice; a win that appears only on the rule-design slice is reported as overfit, not success.

## Frozen-adapter compatibility (validated)

The corpus is scored by `claim_integrity.downstream.score_method` unchanged. Smoke test: preserve-whole
→ **0.4815** unsafe delivery (keeping conjunctions whole omits the governing conjunct); oracle → **0.000**.
That 0.48 → 0.00 gap is the space every variant is measured in, using the prior study's scorer.

## Honesty note

The corpus is deterministic and self-built. The scorer being frozen and the held-out slice being
evaluated separately are the two guards that make a positive result meaningful. Rates are construction
properties; what transfers is whether a *small* scope-propagation rule set generalizes to held-out
structure without introducing spurious attachment.
