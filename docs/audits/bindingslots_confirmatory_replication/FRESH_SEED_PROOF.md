# Fresh-seed proof

Machine-readable: [`FRESH_SEED_PROOF.json`](./FRESH_SEED_PROOF.json) (canonical copy of
`experiments/bindingslots_confirmatory/fresh_seeds.json`).

## Selection rule (outcome-independent, deterministic)

The five confirmatory seeds are the **next five consecutive integers after the highest BindingSlots
model-training seed ever used** in the program. That highest seed is **12** (Stage B fresh seeds
8–12). Therefore:

> **Confirmatory seeds = 13, 14, 15, 16, 17.**

The rule inspects no outcome and predates all training.

## Previously-used BindingSlots training seeds

`{0,1,2}` (frozen) ∪ `{3,4,5,6,7}` (PR #1300 holdout) ∪ `{3,6,7}` (Stage A) ∪ `{8,9,10,11,12}`
(Stage B) = **0…12**. Highest = 12.

## Independence

A repo-wide search confirms seeds 13–17 **never** appear as a BindingSlots model-init/training seed,
nor in any five-seed / stabilization result artifact, log, or manifest.

Two literal appearances exist in **disjoint research lines** and never touch BindingSlots model
state:

- `seed=13` — `experiments/branch_d/…` and `experiments/phase_guidance_diagnostics/score_decomposition.py`
  (permutation / decomposition RNG for an unrelated phoneme/varna line).
- `seed=17` — `experiments/phase_guidance_diagnostics/slot_chain_trace.py` (default arg of an
  unrelated tracer).

Seeds 14, 15, 16 appear nowhere. The constants `123`, `777`, `4321` are evaluation-RNG seeds
(needle fixtures, routing/grad probes), not model-training seeds.

**Conclusion:** 13–17 are uncontaminated for the BindingSlots formation experiment.

## Replacement policy

Outcome-based replacement is forbidden. A seed is replaced **only** for a documented
infrastructure-only failure that produced no valid result, using the next unused integer (18, 19, …)
chosen without inspecting model quality. Restarts retain the same seed and configuration.
