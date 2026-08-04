# Arm definitions

Machine-readable: `experiments/bindingslots_persistence/arm_definitions.json` (+ `o1r_definition.json`,
`h1_parameter_group_manifest.json`, `h2_teacher_definition.json`). Each arm runs the **frozen**
`stabilize.run_arm` loop with at most one in-memory function swap (files on disk unchanged, hashes
verified); H1/H2 add a training-only optimizer/loss augmentation that touches no inference path.

| arm | change | key freeze |
|---|---|---|
| A+ | window-only control (required by same-seed causal threshold) | none |
| R0 | frozen CR1 reference / clean-stable baseline | none |
| O1 | `−log r[q,s*]`, R0 λ schedule (reproduction anchor) | Stage-1 `objectives.py` sha256 pinned |
| O1R | O1 + standing λ_addr = 0.01 for steps 601–1200 | coefficient 0.01, no sweep |
| H1 | 0.1× LR on the addressing param group during 600–900 | 12-tensor group, name-list sha256 `4f245f46…` |
| H2 | distill step-600 address-conditioned slot-read distribution | teacher target frozen, no answer label |

`s* = argmax_j stop_gradient(w[f,j])` (lowest index on ties). O1R/H1/H2 pass only if they retain
**causal** address-dependence at step 1200, not merely the proxy. **No O2/O3/H3/C1** in this screen.
