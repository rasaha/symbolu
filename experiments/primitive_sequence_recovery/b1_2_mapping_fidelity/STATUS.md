# B1.2 Mapping-Fidelity — STATUS

```
status:            DESIGN_OR_PREREG_ONLY
implementation:    NOT_STARTED
generation:        NOT_APPLICABLE / NOT_RUN
judging:           NOT_RUN
scoring:           NOT_RUN
freeze:            NOT_FROZEN
B1.1 verdict:      RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:           BLOCKED
Track G negative:  RANDOM_POLARITY_EXPLAINS (1fe5562) — preserved
Track F negative:  CORRECTNESS_DEGRADED — preserved
only allowed positive: MAPPING_FIDELITY_SIGNAL
ontology validation:   NONE
Sanskrit privilege:    NONE
semantic-truth claim:  NONE
```

## Design state

- Proposal, R_deranged control-validity review, go/no-go decision, and preregistration are written.
- Prereg carries Amendment A1 (G = dictionary answer key vs V = varṇa prediction) and Amendment A2
  (two-axis controls: Axis 1 answer-key distractors / word-specificity; Axis 2 prediction ablations /
  mechanism). Both axes required for support.
- The design is **conditional**: it presupposes a **frozen, mechanical, word-agnostic** function that derives
  `V(word)` (and its scramble/derange ablations) from the varṇa skeleton. If no such function exists without
  hand-tuning, the prereg's default rule is `STOP_NOW`.

## Next gate

- **`B1_2_LAYER3_DERIVATION_FUNCTION_FEASIBILITY`** — determine whether Symbol-U actually provides a
  mechanical rule to produce `V(word)` and its ablations from the varṇa skeleton (the load-bearing
  precondition), **then**
- **`B1_2_PREREG_REVIEW_OR_STOP_NOW`** — adversarial review of the prereg; if any of G / V / tiers / Axis-2
  ablations require hand-tuning to favor the target, default to `STOP_NOW` and close the line.

No build, generation, judging, or scoring may occur before both gates and a new freeze.

**Structure, not validated meaning.**
