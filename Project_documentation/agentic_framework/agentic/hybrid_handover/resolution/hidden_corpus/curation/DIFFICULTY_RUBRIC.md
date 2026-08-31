# DIFFICULTY_RUBRIC

Difficulty is scored by required OPERATIONS, not prose complexity. Authors never
assign the final difficulty; it is computed by `difficulty_rubric.py`.

## Score
```
score =  max(0, n_relationships - 1)      # each relationship beyond the first
       + hop_depth                         # reasoning hops
       + max(0, competing_authorities - 1) # each competing authority beyond one
       + exception_nesting                 # exception nesting depth
       + [temporal] + [cross_format] + [ambiguity]
       + distractor_paths
       + [must_abstain]
```
## Level
| score | 0 | 1 | 2–3 | 4–5 | ≥6 |
|---|---|---|---|---|---|
| Level | 1 | 2 | 3 | 4 | 5 |

Factors: number of relevant documents/relationships, reasoning-hop depth,
competing authorities, exception nesting, temporal reasoning, cross-format
reasoning, ambiguity, plausible distractor paths, requirement to abstain.

## Adjudicated pilot distribution
L1: 4 · L2: 9 · L3: 13 · L4: 7 · **L5: 5**. The five Level-5 cases genuinely
require ≥6 operations (e.g. a four-hop reference chain; a four-authority
hierarchy+migration+date+override stack; triple-nested exceptions).

## Retrospective calibration (reported, NOT applied)
The rubric is stricter than the seed's original hand labels: over the 22 seed
cases it recommends a different level in **16** cases (mostly rating the seed
one level LOWER, because several seed "high" labels rest on wording rather than
operation count). Over the 38 accepted pilot cases the rubric differs from the
author's PROPOSED difficulty in **27** cases — which is expected and is precisely
why authors do not set the final difficulty. Seed labels are NOT modified; these
are recommendations only.

Interpretation: the large author/seed-vs-rubric gap is a finding about the
subjectivity of hand-labelled difficulty, and a reason to trust the deterministic
rubric for the pilot rather than author intuition.
