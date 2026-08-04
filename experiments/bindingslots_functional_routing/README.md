# BindingSlots Functional Routing & Retention Development (focused Stage-1 screen)

Follow-up to the confirmatory failure (PR #1324, `CONFIRMATORY_REPLICATION_FAILED`). Tests whether an
**address-specific functional objective** and/or a **gradual scaffold withdrawal** produce **causally
clean, retained** slot routing — attacking the two diagnosed failures:

- **Retention** — seeds 13/14 formed then collapsed (aggregate overlap ~0.70 retained, needle → 0).
- **Purity** — seed 16 solved the task without depending on correct addressing (randomized-address 0.45).

## Interventions (training-only)

Each arm runs the **frozen `stabilize.run_arm` loop** with **at most one** in-memory function swap
(the `interventions.py`/`stabilize.py` files on disk are never edited; their sha256 are verified):

| arm | idea | swap |
|---|---|---|
| A+ | window-only control | none |
| R0 | frozen CR1 (comparator) | none |
| O1 | `−log r[q, s*]` — read prob on the *written* slot | `alignment_loss` |
| O2 | read-logit margin ≥ 3.0 for the written slot | `alignment_loss` |
| H3 | gradual curriculum handoff (600→900) | `curriculum_batch` |

`s* = argmax_j stop_gradient(w[f,j])`. O1/O2 keep R0's λ schedule. No answer-label / evaluator /
frozen-randomized-address signal is used in training (verified by `verify_fr_prereg.py`).

## Reproduce

```bash
python experiments/bindingslots_functional_routing/verify_fr_prereg.py            # torch-free integrity
python experiments/bindingslots_functional_routing/fr_runner.py                    # A+/R0/O1/O2/H3 x 18-22 (resumable)
python experiments/bindingslots_functional_routing/fr_classifier.py \
    --results-dir experiments/bindingslots_functional_routing/results/seeds \
    --out experiments/bindingslots_functional_routing/results/stage1_aggregate.json
python experiments/bindingslots_functional_routing/validate_known_signatures.py    # metric reproduction on committed seeds
```

## Scope

Stage-1 screen only. Stage-2 development holdout, the O3/H1/H2/O1R/C1 arms, and independent
confirmation are **deferred** to a follow-up phase. Readiness never exceeds
`KDA_VALIDATION_BLOCKED_PENDING_INDEPENDENT_CONFIRMATION`.
