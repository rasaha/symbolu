# BTRR smoke-tier calibration log (seed 8100)

**Status:** calibration only. Seed 8100 is the smoke seed; nothing here is admissible evidence. No
development (8101–8103) or final (81600–81604) seed has been consumed. All numbers below were produced on
the operator's RunPod pod (RTX 6000 Ada, torch 2.4.1+cu121) and pasted into the session; they are
operator-reported `[V]` against the pasted output, not re-executed here.

Effective authority remains Amendment 002 (`config_digest`
`ba73d7bc6df4699dd0ddbd1e6dae79341fccd74b474f231e8857a20a22ffcfe3`, unchanged by every commit below).

## Load-bearing question
Can the frozen recipe (394,752 params, batch 8, **≤ 2000 updates**) establish the P0 base-capability
gate (≥ 0.98 on each of B1–B7)? **No.** No explored configuration up to 15× the frozen budget does, and
the two runs above the budget disagree with each other on B1, so the P0 gate is not established and a
budget amendment is not supported by this evidence.

## Runs (chronological; `n_train` = examples per split/subtask; `n_eval` = 8 per cohort)
| # | code | n_train | updates | validity | B1 | B2 | B3 | B4 | B5 | B6 | B7 | note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `32658677` | 50 | 15000 | 0.573 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | role-digit pools (F14 artifact), B7 unflagged (F12) |
| 2 | `4b2d5311` | 400 | 2000 | 0.198 | 0 | 0 | 0 | 0 | 0 | .12 | .25 | frozen budget: format not learned |
| 3 | `4b2d5311` | 1500 | 2000 | 0.490 | 0 | 0 | 0 | 0 | 0 | .25 | 0 | frozen budget: format not learned |
| 4 | `4b2d5311` | 400 | 15000 | 0.990 | 0 | 0 | 0 | 0 | 0 | 0 | 1.0 | letters copied, training-pool digit emitted (`DTWXX7`→`DTWXX1`) |
| 5 | `11e1d1d7` | 400 | 15000 | 0.875 | .88 | .88 | 0 | 0 | .75 | .62 | 1.0 | first fair copy measurement (F14 fixed); loss 0.66, flattening |
| 6 | `11e1d1d7` | 1500 | 30000 | 1.000 | .12 | 0 | .12 | .12 | .12 | .62 | 1.0 | loss 0.49 still falling; B1 collapsed vs run 5 |

Fixture-only learnability diagnostic (`overfit_diagnostic`, seed 883003, eval-on-train, 15 examples):
validity / answer / P0 = 1.0 / 1.0 / 1.0 at both 2000 and 4000 updates (CPU). The train→generate
machinery is sound.

## Findings (see CONFORMANCE_MATRIX.md for the closed items)
- `[V]` F11 (`b16e4e4c`): generator RNG was seeded from the salted builtin `hash()`; not reproducible across
  processes. Fixed.
- `[V]` F12 (`06e8f9e6`): B7 carried no visible "absent" flag; B7 inputs were shaped identically to B1/B5.
  Fixed. B7 reaches 1.0 in every run since.
- `[R]` F13 (open): R1–R4 gold is always `EU`, R8/R9/R12 always `VP_APPROVAL_REQUIRED`; the
  `query_only`/`shuffled_context`/`majority_class` baselines emit `NO_ACTION` and are 0.0 by construction.
  A per-operation constant emitter passes the R1–R4, R9-composite and R12 answer gates with
  `shortcut_detected=False` (verified torch-free on fixture 883004). Non-compensation still blocks
  VALIDATED. Requires owner ratification because it changes 7 splits' answer distributions.
- `[V]` F14 (`11e1d1d7`): held-out ids carried a visible marker (trailing digit 6/7/8 never seen in
  training). Run 4's predictions showed letter-exact copies with a training-pool digit. Pools are now
  partitioned by an invisible hash of the id string with identical token/position distributions. Fixed.
- `[V]` F15 (`11e1d1d7`): `is_valid_output` raised on schema-cap violations. Fixed.
- `[V]` Failure shape (runs 5–6): where copying works it is position-anchored (the B1/B2/B5 answer sits at a
  fixed absolute token offset ≈ 11 in the query line; B6 is the last value before the output marker).
  B3/B4 answers sit at a variable offset ≈ 190–200 and are never retrieved: predictions are id-shaped
  babble (`WSSSY9`, `MSSSS0`) with the correct field layout. `[I]` Learned absolute positional embeddings
  (249,856 of 394,752 params) are the plausible mechanism; not verified.
- `[V]` Run 5 vs run 6: same seed, more data and 2× the updates, lower training loss, and B1 fell from
  0.88 to 0.12. One run per configuration is a sample of size one; copy-circuit formation in a 2-layer
  model is trajectory-dependent. Calibration numbers above must not be read as monotone in budget.
- `[G]` `config_digest` binds vocab, limits, params, caps, gates and seeds but **not** the training recipe
  (`max_updates`, lr, batch). A budget amendment would not change the protocol-lock digest.

## Owner decisions
1. Accept `RELATIONAL_REASONING_BLOCKED_BY_BASE_CAPABILITY` as the frozen-recipe result and proceed to
   the final tier at the frozen recipe (the preregistration names an unlearnable split at this recipe a
   reported result), **or** open Amendment 003. The calibration evidence does not support a budget-only
   amendment; the capacity rule forbids the architectural change (relative/rotary positions, copy head)
   that the failure shape points to.
2. Ratify and implement the F13 correction before any R-split number is reported, even under decision 1.
3. Extend `config_digest` to the training recipe (protocol-lock change; invalidates and requires
   re-signing the current record).
4. Optional: additional smoke runs at fixed configuration to bound run-to-run variance before decision 1.

## Not done / not claimed
No development or final seed consumed. No gate, cap, verdict precedence, or architecture value changed.
The always-preserved verdicts (`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
`E1_TEMPORAL_TRANSFER_PARTIAL`, `KDA_VALIDATION_BLOCKED`) are unaffected.
