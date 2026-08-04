# Functional routing & retention — Stage-1 results

**Primary verdict: `ROUTING_PURITY_NOT_RESOLVED`** · `KDA_READINESS = KDA_VALIDATION_BLOCKED`.
No candidate selected. Source of truth:
`experiments/bindingslots_functional_routing/results/stage1_aggregate.json`.

All 25 runs (A+/R0/O1/O2/H3 × seeds 18–22) completed at the frozen 1200-step budget.

## Raw needle@d96 formation (chance ≈ 0.02)

| seed | A+ | R0 (CR1) | O1 | O2 | H3 |
|---|---|---|---|---|---|
| 18 | 0.00 | 0.00 | 0.94 | 0.98 | 0.00 |
| 19 | 0.00 | 1.00 | 1.00 | 0.99 | 0.58 |
| 20 | 0.00 | 0.00 | 1.00 | 1.00 | 0.98 |
| 21 | 0.00 | 1.00 | 1.00 | 1.00 | 0.00 |
| 22 | 0.00 | 0.91 | 1.00 | 0.89 | 1.00 |
| **raw forms** | 0/5 | 3/5 | **5/5** | **5/5** | 3/5 |

**O1/O2 raise raw needle formation to 5/5** — including seeds 18 and 20 where R0 (frozen CR1) fails.
But raw needle is not the objective; **causally clean, retained** routing is.

## The gate that matters — clean stable formers

| arm | clean-stable | routing-unclean formers | collapse (formed→collapsed) | causal-clean formers | full gate |
|---|---|---|---|---|---|
| R0 | **1/5** | 1 (s19) | 2 (s18, s20) | 3/3 | ✗ |
| O1 | **0/5** | 5 (all) | 0 | **1/5** | ✗ |
| O2 | **0/5** | 4 | 0 | 0/5 | ✗ |
| H3 | **0/5** | 1 | 2 (s18, s21) | 1/3 | ✗ |

No arm clears the Stage-1 gate; **no intervention exceeds R0's clean-stable count (1)**.

## Why O1/O2 fail despite 5/5 needle — the address-independent shortcut

For O1's five formers, **slots-off collapses retrieval (≈0) but randomized-addressing does not**
(0.96–1.00 on 4/5). Retrieval uses the slot memory but **not** through correct addressing:

| O1 seed | needle | slots-off | randomized-address | correct-slot prob@1200 | rank | margin |
|---|---|---|---|---|---|---|
| 18 | 0.94 | 0.00 | **0.96** | 0.14 | 8.9 | 1.0 |
| 19 | 1.00 | 0.00 | **1.00** | 0.23 | 4.7 | 1.0 |
| 20 | 1.00 | 0.03 | **1.00** | 0.27 | 7.5 | 2.2 |
| 21 | 1.00 | 0.00 | 0.04 | 0.28 | 5.6 | 1.4 |
| 22 | 1.00 | 0.02 | **1.00** | 0.15 | 8.4 | 1.2 |

Only seed 21 collapses under randomized-addressing. The others are the **seed-16 impurity mode**,
now on 4/5 seeds. O2 is similar (address-margin higher early, but still survives randomized-address on
4/5). See `ROUTING_PURITY_ANALYSIS.md`.

## The mechanism — routing forms then decays after withdrawal

O1/O2 **do** build correct-slot routing during the scaffold, but it is **not retained** after λ→0:

| O1 correct-slot prob | step 300 | step 600 | step 900 | step 1200 |
|---|---|---|---|---|
| seed 18 | 0.81 | 0.54 | 0.18 | 0.14 |
| seed 21 | 0.74 | **0.97** | 0.29 | 0.28 |
| seed 22 | 0.49 | 0.54 | 0.21 | 0.15 |

Correct-slot probability peaks around the end of the scaffold window (step 600) then **decays** while
needle **stays at 1.0** — the routing circuit suffers the **same post-scaffold retention failure** as
retrieval, and needle survives via the address-independent shortcut. See
`SCAFFOLD_WITHDRAWAL_ANALYSIS.md`.

## H3 and R0

- **H3** (gradual handoff) forms 3/5, still collapses on 2/5 (seeds 18, 21), and does not improve
  purity — it neither prevents collapse nor grounds addressing.
- **R0** reproduces ~3/5 formation with the familiar retention collapses (seeds 18, 20) and one
  clean-stable seed (21).

## Verdict

Interventions form but stay routing-unclean, and none exceeds R0's clean-stable count →
`ROUTING_PURITY_NOT_RESOLVED`. Integrity clean (23/0); frozen `abc.json` unchanged. No protocol
deviation, no best-checkpoint selection, no outcome-based seed replacement.
