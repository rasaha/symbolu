# CORPUS_DESIGN_RATIONALE

Why this corpus is built the way it is.

## 1. Development vs evaluation are physically separated
Debugging on evaluation data silently tunes a resolver to the test. The hidden
corpus lives in its own package, behind opaque ids, with gold metadata in a
separate module a resolver never imports. This makes "train on the test" a
structural impossibility, not a policy.

## 2. Preserve capability, vary expression (no paraphrase)
The audit showed the deterministic resolvers pass by matching a fixed cue
vocabulary. Simple paraphrase would still share structure. So each hidden case
expresses the SAME capability with genuinely different language and structure:
- supersession via "rescinded and substituted" (not "deleted and replaced");
- precedence via an ordered charter list, an appendix "prevails over the body",
  or an effective-date comparison — not a single pairwise "governs over";
- override via "notwithstanding", "regardless of", policy migration chains;
- references that are implicit ("the applicable pricing appendix"), multi-hop, or
  circular.
This targets the exact weakness the audit found: cue dependence.

## 3. Structural variation, not just wording
Cases vary document order, numbering, entity names, date formats, policy naming,
table-vs-prose, number formatting, and document granularity — so a resolver that
generalises on structure but not wording (or vice versa) is distinguishable.

## 4. Negative controls measure proper uncertainty
A benchmark that only rewards correct answers rewards confident guessing. Five
negative controls require abstention: no relationship, unresolvable conflict,
insufficient evidence, circular reference, and multiple valid interpretations.
These measure whether a resolver knows when NOT to answer.

## 5. Difficulty by reasoning depth only
Cases are labelled Level 1–5 by how many interacting relationships must be
composed (DIFFICULTY_CALIBRATION.md) — never by surface length. Difficulty labels
are analysis-only and are withheld from resolvers.

## 6. Human-validated ground truth with recorded uncertainty
Every case records an author justification, a confidence value, and explicit
ambiguity notes. Where the correct answer is conditional (e.g. "if the engagement
is government-facing"), that is stated rather than hidden — so a low-confidence
gold does not masquerade as certainty.

## 7. Seed, not final
The corpus is deliberately a seed: broad coverage first (every capability present)
to expose blind spots, then depth. Its own statistics name the thin capabilities
so expansion is evidence-driven, not guessed.
