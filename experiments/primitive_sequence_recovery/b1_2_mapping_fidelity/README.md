# B1.2 Mapping-Fidelity — design / prereg materials

This folder holds **B1.2 mapping-fidelity proposal, review, decision, and preregistration materials only**.
Nothing here is implemented, run, judged, or scored.

## What B1.2 is (and is not)

1. This folder contains **B1.2 mapping-fidelity** proposal/review/prereg materials **only**.
2. **B1.2 is separate from B1.1 and does not rescue B1.1.** A B1.2 result — positive or negative — cannot
   reach back and change B1.1.
3. **B1.1 verdict remains `RANDOM_OR_SCRAMBLED_MATCHES`** (locked; see the B1.1 files in the parent folder).
4. **B1.2 is NOT authorized for implementation** until the prereg/freeze gates are complete (feasibility →
   prereg review → new freeze). No generation, judging, or scoring may run before then.
5. **B1.2 tests G/V alignment**, not generation utility:
   - **G(word)** = dictionary-derived differential **answer key** (built from the target definition + ≥10
     synonym/neighbor definitions → shared-feature subtraction → target-specific residual; dictionary-only
     pipeline, never varṇa-derived).
   - **V(word)** = varṇa-derived **prediction** (Layer-1 skeleton + frozen gloss table + frozen composition
     rule; varṇa-only pipeline, never dictionary-derived).
   - The test: does **V(target)** align with **G(target)** better than with wrong keys / under ablation?
6. **B1.2 requires two-axis controls** (both must pass):
   - **Axis 1 — answer-key distractors / word-specificity** (hold V = V(target), vary G): G(near)/G(mid)/
     G(far) distance gradient + R_same / R_domain / generic_symbolic.
   - **Axis 2 — prediction ablations / mechanism** (hold G = G(target), vary V): V_scrambled, V_deranged,
     V_removed(dictionary-only ceiling+probe), optional V_random.
7. The **only** positive label B1.2 may ever earn is **`MAPPING_FIDELITY_SIGNAL`** (with a distance-gradient
   qualifier).
8. **No** ontology validation, Sanskrit privilege, semantic-truth claim, or Track-B unblock — at any outcome.

**Structure, not validated meaning.**

## Where B1.1 lives

B1.1 artifacts (raw outputs, judge packets/outputs, scoring, final reports, freeze manifests, configs,
generation/judge scripts, audits) remain in the **parent** directory
`experiments/primitive_sequence_recovery/` and were **not** moved. The decision memo in this folder cites
several of them as inputs (e.g. `B1_1_POST_RESULT_FORENSIC_REPORT.md`,
`B1_1_THEORY_APPLICATION_MISMATCH_REVIEW.md`, `B1_1_FINAL_SCORING_AND_VERDICT.md`) — those files are one
level up.

## Index of B1.2 materials

| file | purpose | kind | authorizes implementation? |
|---|---|---|---|
| `B1_2_MAPPING_FIDELITY_PROPOSAL.md` | first proposal of a mapping-fidelity study after the B1.1 null | proposal | NO |
| `B1_2_R_DERANGED_CONTROL_VALIDITY_REVIEW.md` | critique of the flat R_deranged control; proposes near/mid/far stratification | review | NO |
| `B1_2_MAPPING_FIDELITY_PREREG_DECISION.md` | go/no-go memo → AUTHORIZE_ONE_B1_2_PREREG (conditional) else STOP_NOW | decision | NO |
| `B1_2_MAPPING_FIDELITY_PREREG.md` | the preregistration (G/V design, two-axis controls, endpoints, kills) | prereg | NO |
| `README.md` | this file — scope and index | index | NO |
| `STATUS.md` | current state of the B1.2 line | status | NO |
| `MIGRATION_NOTE.md` | record of the folder reorganization | note | NO |

No file in this folder authorizes generation, judging, or scoring. Implementation remains gated behind a
Layer-3 derivation-feasibility check, a prereg review, and a new freeze.
