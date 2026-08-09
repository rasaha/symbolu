# BTRR Gate Rationale

Every numeric gate below is derived from (1) chance level, (2) structure-blind baselines, (3) a
meaningful minimum competence / effect size, and (4) prior base-capability performance where applicable.
**No gate is set at observed reserved performance.** This document is frozen with the protocol lock.

## Generator parameters that fix chance
- Entities per episode: 6–12 → entity-selection chance ≤ 1/6 ≈ 0.17.
- Outcome vocabulary: 8 outcome tokens + NULL → categorical answer chance ≈ 1/9 ≈ 0.11.
- Events per relevant entity: 2–4 → naive latest chance ≈ 0.33; the meaningful floor is the
  **global-most-recent** structure-blind baseline (pick the highest `sequence` anywhere), which the
  generator deliberately makes wrong on a controlled fraction of episodes.
- Relation types ≈ 6; exact ordered multi-hop path chance ≪ 0.05.

## Structure-blind baselines (computed, not learned)
shuffled-context, query-only, majority-class, most-recent-token, global-most-recent, policy-id→outcome.
Each model gate must exceed its relevant blind baseline by ≥ 0.10. Any blind baseline within 0.10 of the
model on a gated metric → `SHORTCUT_OR_LEAKAGE_DETECTED` (fail-closed).

## Gate derivations
| Gate | Value | Derivation |
|---|---|---|
| Structured-output validity | ≥ 0.98 | near-mechanical once P0 established; below this indicates a protocol/format failure, not reasoning |
| R1 direct attribute | ≥ 0.95 | competence floor; chance ≤ 0.17; trivial single lookup |
| R2 PATH_GIVEN 1-hop | ≥ 0.90 | competence; plan supplied, one hop |
| R3 PATH_GIVEN multi-hop | ≥ 0.85 | competence; plan supplied, 2–3 hops |
| R4 PATH_DISCOVERY multi-hop | ≥ 0.75 | chance ≪ 0.05; strictly harder than R3; set below R3 to reflect discovery difficulty while remaining well above chance and blind baselines |
| Entity-selection accuracy | ≥ 0.90 | chance ≤ 0.17; selection must be near-reliable to trust downstream reasoning |
| Relation-path accuracy (exact ordered) | ≥ 0.80 | chance ≪ 0.05; exact ordered match is unforgiving |
| Latest-event accuracy | ≥ 0.85 AND ≥ global-most-recent + 0.20 | absolute competence + effect size over the strongest temporal shortcut |
| Policy-condition accuracy | ≥ 0.85 | competence; conditions are explicit and typed |
| Evidence precision | ≥ 0.90 | citations must be trustworthy; low precision = hallucinated support |
| Evidence recall | ≥ 0.85 | must cite the actually-supporting evidence |
| Abstention accuracy (R10+R11) | ≥ 0.85 AND false-abstain on answerable ≤ 0.10 | chance 0.5; abstention must not be bought by over-abstaining |
| Hallucinated-entity rate | ≤ 0.02 | near-zero fabrication tolerance |
| Hallucinated-relation rate | ≤ 0.02 | near-zero fabrication tolerance |
| Hallucinated-evidence rate | ≤ 0.02 | near-zero fabrication tolerance |
| R7 PATH_DISCOVERY + temporal | ≥ 0.72 | composed discovery+temporal; below R4 to reflect added temporal step |
| R9 composite final-answer | ≥ 0.70 | chance 0.11; full compose is the hardest answerable task |
| R9 full-chain-correct | ≥ 0.60 | strictest: answer ∧ path ∧ temporal ∧ policy all correct |
| R12 confusable | ≥ R9 − 0.10 | must not collapse under near-duplicate distractors |
| Final seeds required | ≥ 4 of 5 | matches E1-lineage fresh-seed convention (5 seeds, ≥4 pass) |

## Non-compensation rule
`RELATIONAL_REASONING_VALIDATED` requires **every** critical gate to pass on ≥ 4/5 final seeds. Strong
R1/R2/R3 (PATH_GIVEN execution) cannot offset any failure of temporal, PATH_DISCOVERY (R4/R7/R9), policy,
evidence, or abstention gates. This is enforced structurally by the precedence order (temporal, policy,
evidence, and abstention failures short-circuit to their own verdicts before a VALIDATED can be reached).

## Representation-comparison exclusion (justification)
No prose-vs-typed factorial is included. (1) The settled V1.1 architecture already commits to a *typed*
entity/relation/event working set as the deterministic-retrieval output, so representation is settled by
architecture, not open here. (2) The prose-vs-typed comparison is already owned by
`single_hop_typed_vs_prose` (roadmap #11.A). (3) A representation × reasoning-depth factorial would
confound representation with depth/temporal/policy effects and risk averaging away failure. A prose
control is reserved as a separate follow-up at R9 only, never part of these primary gates.
