# NEGATIVE_CONTROL_ANALYSIS

Negative controls measure **proper uncertainty** — whether a resolver abstains
when it should, rather than guessing. The correct outcome for every case here is
abstention.

## The five controls
| Control | Case shape | Why abstention is correct |
|---|---|---|
| no_relationship | an NDA term + an invoice; the question asks about termination | no document addresses the queried relationship — nothing to govern |
| unresolvable_conflict | two amendments, identical effective dates, contradictory notice | no precedence rule and no tie-break -> genuinely unresolvable |
| insufficient_evidence | a clause deferring the value to "the Master Pricing Terms", which is absent | the decisive document is not present — a dangling reference |
| circular_reference | A defines the fee via B; B defines it via A | reference cycle; no ground term exists |
| multiple_valid_interpretations | "Affiliate" defined via "control"; "control" left undefined | more than one defensible reading; none is entailed |

## What they test
- **Abstention precision** (from the repaired measurement): a resolver that answers
  any of these confidently is penalised, because these should be refused.
- **Discrimination from answerable cases**: 17 of 22 cases are answerable, so a
  resolver cannot pass by always abstaining (that collapses answer-coverage and
  selective accuracy — see the measurement repair).
- **Distinct failure modes**: the five controls exercise five different reasons to
  abstain (absence, contradiction, missing document, circularity, interpretive
  ambiguity), so "abstain" is not a single trick.

## Ambiguity handling
Answerable cases also carry honest ambiguity where it exists (16 of 22 have
ambiguity notes). Several answerable cases are *conditionally* correct (e.g.
"allowed unless the engagement is government-facing"); the annotation records the
condition and the author confidence rather than overstating certainty. This keeps
the negative controls (must-abstain) distinct from merely-conditional answers
(answer, with a stated caveat).

## Limitation
Each negative control currently has a SINGLE example. Five single cases can be
matched by five bespoke abstention triggers. Robust measurement of proper
uncertainty needs several varied instances per control type (see the coverage
matrix and generalisation protocol).
