# ACP Phase 1 — Call-Site Audit

The three real production call sites where the direct action BCVF scorer affects
behavior, and exactly what constraint data each provides. Nothing absent is
inferred; unavailable constraints are marked **UNAVAILABLE**.

---

## Call site 1 — Deliberative action selection

`tiers/deliberative.py :: TaskPlanner.plan` (`:109`).

| aspect | finding |
|---|---|
| candidate representation | `List[Tuple[str, dict]]` — `(action_name, params)`; actions ∈ {move_to, grasp, release, wait} (`:165`) |
| feasibility source (sf) | `_compute_forward_score` (`:188`): base 0.7 + O3 motor − O12 safety; `*0.5` if any obstacle `distance < 0.5` for move_to (`:212`); `*0.5+O5` for grasp |
| goal source (sb) | `_compute_backward_score` (`:221`): keyword/goal match |
| existing pre-filters | **none hard**; safety enters only as a soft subtraction on sf |
| BCVF output use | pure argmax of `normalized_weight` (`:154`) |
| downstream behavior | `best_action → plan_fn → ActuatorCommand` (velocity/gripper) — direct actuation |
| **available hard constraints** | `OBSTACLE_CLEARANCE` (move_to, from `world.get_obstacles()[i]["distance"]`, PROD floor 0.5); `SAFE_FALLBACK` (wait) |
| **UNAVAILABLE** | stopping distance, actuator limits, stability, trajectory validity — no candidate/world data; grasp/release carry **no** hard-constraint data at this site |
| gap preventing ACP eval | manipulation (grasp/release) is **unevaluable** here — ACP marks it `NO_HARD_EVIDENCE` (fail closed) |

## Call site 2 — Conflict resolution

`coordination/conflict_resolution.py :: ConflictResolver.resolve` (`:370`).

| aspect | finding |
|---|---|
| candidate representation | `StrategyCandidate{strategy, forward_score, backward_score, priority_score, safety_score, details}` (`:139`), scores hardcoded per strategy (`:444`) |
| feasibility source (sf) | `forward_score` (hardcoded per strategy) |
| goal source (sb) | `backward_score` (efficiency, hardcoded) |
| existing pre-filters | **none hard**; safety enters as a post-normalization multiplier `*(1+0.4*safety_score)` (`:402`) |
| BCVF output use | `score → *(1+0.3*priority)*(1+0.4*safety) → renorm → argmax` (`:392–412`) |
| downstream behavior | per-robot `stop/yield/proceed/avoid` actions |
| **available hard constraints** | `SAFETY_SCORE_FLOOR` (per-candidate `safety_score`, POLICY 0.5); `FEASIBILITY_FLOOR` (`forward_score`, POLICY 0.3); `SAFE_FALLBACK` (MUTUAL_STOP) |
| **UNAVAILABLE** | physical collision margin (metres), stopping, actuator — strategy scores are abstract, not physical |
| gap preventing ACP eval | scores are the resolver's own abstract signals; ACP's floor on `safety_score` is a policy threshold, not a measured margin |

**Known BCVF pathology reproduced:** `MUTUAL_STOP` (sf=1.0, sb=0.3, safety=1.0)
is the resolver's safest strategy but its BCVF consistency term makes it a weak
pick; ACP's `safety_score ↓` order ranks it first among admissible.

## Call site 3 — Task allocation

`coordination/task_allocation.py :: TaskAllocator.close_auction` (`:329`).

| aspect | finding |
|---|---|
| candidate representation | `TaskBid{robot_id, distance_to_task, capability_match, current_load, coherence, ...}` (`:72`) |
| feasibility source (sf) | `_score_bid` (`:264`): capability/load/coherence composite |
| goal source (sb) | `_score_bid`: distance/capability/coherence composite |
| existing pre-filters | **HARD, at bid intake**: `capability_match < 0.5 → reject` (`:239`), `current_load > 0.9 → reject` (`:243`), `coherence < 0.4 → reject` (`:323`), `min_bid_score` on BCVF weight (`:320`) |
| BCVF output use | `score → *(1+0.1*priority) → renorm → argmax` (`:358–376`) |
| downstream behavior | `assigned_robot` |
| **available hard constraints** | `CAPABILITY_MATCH` (PROD 0.5), `LOAD_LIMIT` (PROD 0.9), `COHERENCE_FLOOR` (PROD 0.4) — all mirror the existing intake pre-filters |
| **UNAVAILABLE** | collision, stopping, actuator, stability |
| gap preventing ACP eval | ACP's task hard filter **duplicates** the existing intake pre-filters, so by `close_auction` all bids are already admissible; ACP's only distinct effect is the deterministic SELECTION rule (distance/load) vs BCVF |

## Cross-site summary

- **Only deliberative** carries a genuine *physical* hard constraint (obstacle
  distance). Conflict provides an *abstract* safety score; task provides
  *operational* gates that duplicate existing pre-filters.
- **No call site** provides collision-margin-in-metres, stopping distance,
  actuator limits, or stability — the architecture's core physical constraints.
  Those live in `safety/{collision_guard,trajectory_validator,constraint_monitor,
  energy_bounds,human_proximity}.py`, which are **not wired into these three
  decision points**. Wiring them is Phase 2+ work, not fabricatable in Phase 1.
- This is the central reason the hard-admissibility verdict is
  *SUPPORTED_WITH_LIMITATIONS*, not unconditionally supported.
