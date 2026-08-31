# Robotics Action-Selection Baselines (Part 3)

**Milestone:** Robotics reliability redesign — Part 3, action-selection track.
**Code:** `robotics_reliability_bench/action_baselines.py`,
`run_action_scenarios.py`. **Data:** `results/action_scenarios.json`.
**Status:** evaluation-only. No production selector is modified.

---

## 1. The canonical action envelope

Every selector consumes one shape (`ActionCandidate`) that separates
**hard, non-compensatory invariants** from **soft scores**:

* Hard: `hard_safe`, `feasible`, `collision_margin ≥ 0.20 m`,
  `stability_margin ≥ 0.10`.
* Soft: `goal_progress`, `exec_cost` (and the BCVF port's `sf`/`sb`).

`_hard_admissible` (`action_baselines.py`) is the non-compensatory gate: a
candidate that fails any hard invariant is removed **before** any soft score is
consulted. No soft score can buy it back. Every selector can return
`NO_SAFE_ACTION`; the deterministic ones never normalize an inadmissible
candidate into a winner.

## 2. Selectors compared

| selector | rule |
|---|---|
| `Lexicographic` | filter → order by (min margin) ▷ goal ▷ cost ▷ index |
| `WeightedUtility` | filter → `1.0·margin + 1.0·goal − 0.5·cost` |
| `ConstrainedOpt` | filter → max goal s.t. margin ≥ 0.30 (else lexicographic) |
| `BCVF` | the **real** `formulas/bcvf.py` scorer; `pre_filter=False` mirrors the unguarded deliberative/conflict path |

## 3. Head-to-head result (`action_scenarios.json`)

| scenario | admissible set | Lexicographic | WeightedUtility | ConstrainedOpt | **BCVF (unguarded)** |
|---|---|---|---|---|---|
| unsafe_but_consistent_wins | detour, stop | stop ✅ | stop ✅ | detour ✅ | **charge_through ❌ (margin 0.05)** |
| all_candidates_unsafe | ∅ | **NO_SAFE_ACTION** ✅ | **NO_SAFE_ACTION** ✅ | **NO_SAFE_ACTION** ✅ | **ram_ahead ❌ (unsafe + infeasible)** |
| only_stop_is_safe | stop | stop ✅ | stop ✅ | stop ✅ | **weave ❌ (margin 0.10)** |
| safe_tradeoff | fast, slow | slow | slow | fast | fast (all admissible ✅) |

**Invariant checked and passed:** `deterministic_never_selects_unsafe = True`.
**BCVF selected a hard-inadmissible candidate in 3 of 4 scenarios**, including a
candidate that is *both* unsafe and infeasible, and it has no way to abstain
when every candidate is unsafe.

## 4. Why BCVF loses here (mechanism, not luck)

* **No hard gate.** `score_action_candidates` ranks over whatever it is given;
  the two coordination/deliberative call sites pass unfiltered candidates
  (audit §1.2). Normalization always yields a winner (CE4).
* **Consistency term is safety-adverse.** `(sf−sb)²` penalizes exactly the
  emergency-stop profile (`sf=1.0, sb≈0.2`), so the safest action is the
  worst-scored (audit CE2/CE6).
* **Temperature/scale sensitivity.** Where a post-multiplier exists (conflict,
  allocation) the winner depends on β and on sf/sb scaling (CE1/CE3/CE5/CE6),
  so the "decision" moves without new evidence.

## 5. Does the action BCVF add value over the four references?

| reference | does BCVF beat it? | why |
|---|---|---|
| hard feasibility filtering | **no** | BCVF has none; it ranks unsafe candidates into winners |
| deterministic lexicographic | **no** | lexicographic is safer (hard gate), temperature-free, scale-free, auditable |
| weighted utility | **no** | same expressiveness without the safety-adverse consistency term |
| constrained optimization | **no** | BCVF cannot express a hard constraint at all |

## 6. Recommendation (action track)

Replace the direct action BCVF with a deterministic constrained selector
(hard-invariant filter → constrained/lexicographic ranking → `NO_SAFE_ACTION`
when empty). This is the `REPLACE_ACTION_BCVF` verdict; the migration is in
`ROBOTICS_V2_MIGRATION_PLAN.md`. The selector should adopt the ActionGate
architectural properties mapped in
`ROBOTICS_ACTIONGATE_ARCHITECTURE_MAPPING.md` (non-compensatory invariants, an
explicit non-binary outcome set with `NO_SAFE_ACTION`, and a decision trace).

### Caveats

Synthetic hand-built scenarios chosen to probe the failure modes the audit
predicted; they demonstrate the *mechanism*, they are not a field trial. The
`safe_tradeoff` row shows the selectors legitimately differ when no safety
issue is present — that divergence is a tuning choice, not a correctness claim.
