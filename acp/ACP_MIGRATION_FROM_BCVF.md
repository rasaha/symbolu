# ACP — Reuse Audit & Migration from BCVF (Tasks 3 & 10)

Reuse audit of every `symbolu_robotics` control-plane component (Task 3), then
the migration roadmap and effort estimate (Task 10). Grounded in a full
component inventory (LOC, deps, determinism, actual BCVF imports). The
control-plane subpackages total **~18,800 LOC**; the standalone
`bcvf_autonomous/` (~200 files) and `bcvf_ros2/` are separate vendored packages.

**Ground-truth BCVF coupling.** Only **four** files actually import the action
BCVF: `formulas/bcvf.py` (def), `formulas/__init__.py` + `__init__.py`
(re-exports), `tiers/deliberative.py:27`, `coordination/task_allocation.py:20`,
`coordination/conflict_resolution.py:20`. `planning/htn_planner.py`,
`planning/mpc_planner.py`, and `safety/trajectory_validator.py` *mention*
BCVF/SCC in docstrings but **do not import it** — docstring aspiration, not a
dependency. **The BCVF blast radius is 3 call sites, not the tree.**

---

## 1. Classification legend

- **KEEP** — reusable as-is under ACP; deterministic, no BCVF coupling.
- **MODIFY** — reused but adapted (wrap behind an ACP stage, or remove a BCVF
  call, or replace a stochastic step).
- **OPTIONAL** — useful but not required for the deterministic core; gate behind
  a flag / deployment profile.
- **REMOVE** — not part of a deterministic control plane (learned/stochastic) or
  superseded.

## 2. Reuse audit (per component)

### core/ (2,207 LOC)
| module | class | why |
|---|---|---|
| `core/types.py` | **KEEP** | load-bearing dataclasses/enums (`RobotPose`, `ActuatorCommand`, `Plan`, `Goal`); ACP envelopes extend these |
| `core/exceptions.py` | **KEEP** | exception hierarchy; ACP adds typed refusals |
| `core/v27_state.py` | **KEEP** | deterministic EMA state; used by PR-V2 variance channel |
| `core/{chitta_vritti, mirror_pairs_12d, ontology_12d}` | **OPTIONAL** | proprietary 12D "ontological" semantic math; deterministic but not required by the ACP decision path — gate as a perception/encoding profile, do not put on the safety-critical path |

### tiers/ (996 LOC)
| module | class | why |
|---|---|---|
| `tiers/base.py`, `tiers/factory.py` | **KEEP** | tier abstraction ACP maps onto (R1 reflexive = fast safety, R2 reactive, R3 = ACP deliberative host) |
| `tiers/reflexive.py` (R1) | **KEEP** | sub-ms deterministic safety layer; becomes ESTOP/collision fast path in the failure SM |
| `tiers/reactive.py` (R2) | **KEEP** | deterministic behavioural control; the DEGRADED-envelope executor |
| `tiers/deliberative.py` (R3) | **MODIFY** | **imports BCVF (`:27`, select `:150`)**; replace the BCVF action scorer with AS-V2; keep the WorldModel/TaskPlanner/NL scaffolding |

### planning/ (2,125 LOC)
| module | class | why |
|---|---|---|
| `planning/htn_planner.py` | **KEEP** | deterministic HTN; wrap as ACP stage 2 (no BCVF import despite docstring) |
| `planning/path_planner.py` (A*) | **KEEP** | deterministic; candidate generation / route input |
| `planning/world_model.py` | **KEEP** | feeds stage 4 world validation |
| `planning/action_primitives.py` | **KEEP** | fixed primitive library for stage 6 |
| `planning/goal_stack.py` | **KEEP** | deterministic goal management for stage 2 |
| `planning/mpc_planner.py` | **MODIFY** | cost function deterministic, but the optimizer **samples `np.random.randn` (`:462`)**; replace with a deterministic solver (fixed lattice / low-discrepancy) for stage 6, or seed-freeze if used only as a candidate source |

### coordination/ (2,269 LOC)
| module | class | why |
|---|---|---|
| `coordination/conflict_resolution.py` | **MODIFY** | **imports BCVF (`:392`)** with hardcoded strategy scores + safety as a soft multiplier; replace with an AS-V2 admissibility+selection over conflict strategies (hard: safety/right-of-way; soft: delay/efficiency) |
| `coordination/task_allocation.py` | **MODIFY** | **imports BCVF (`:358`)**; keep the auction + hard bid pre-filters (capability/load/coherence — already the only guarded site), replace BCVF bid ranking with deterministic constrained ranking |
| `coordination/shared_world.py`, `formation.py` | **KEEP** | USE-fusion based, deterministic, no BCVF |

### safety/ (1,711 LOC) — all KEEP
`trajectory_validator.py` (963), `collision_guard.py`, `constraint_monitor.py`,
`human_proximity.py` (ISO/TS 15066), `energy_bounds.py`. **KEEP all** — these are
the deterministic threshold/geometry checks that *become* ACP's stage-3 constraint
catalogue, stage-7 hard predicates, and stage-11 monitors. Highest-value reuse in
the tree; no BCVF coupling.

### state/ (775 LOC) — KEEP
`robot_state.py`, `localization.py`, `world_state.py`, `ema_tracker.py` — feed
stage 4 world validation and PR-V2. Deterministic.

### recovery/ (1,280 LOC) — MODIFY (become mechanisms under the failure SM)
`fallback.py` (R3→R2→R1), `watchdog.py`, `sensor_recovery.py`. **MODIFY** — keep
the mechanisms; the *policy* (which posture, when, re-entry) moves to
`ACP_FAILURE_STATE_MACHINE.md`, which calls these as actuators.

### formulas/ (1,240 LOC)
| module | class | why |
|---|---|---|
| `formulas/bcvf.py` | **REMOVE** (from action path) / **OPTIONAL** (as PR-V2 S9 feature) | action use replaced by AS-V2; the disagreement math survives only as the optional latency feature, and only as the `bcvf_autonomous` kernel, not this action scorer |
| `formulas/scc.py` (coherence) | **OPTIONAL** | deterministic; useful as a perception/consistency signal, not on the decision path |
| `formulas/use.py` (sensor fusion) | **KEEP** | deterministic USE fusion; used by shared_world/formation and encoders |

### learning/ (1,816 LOC) — REMOVE from the deterministic core
`dynamics_model.py` (NN/ensemble/GP + `np.random`), `skill_learning.py` (RL),
`calibration.py`, `transfer.py`. **REMOVE** from the safety-critical decision
path (non-deterministic/learned). May live as an **OPTIONAL** offline/advisory
module that *proposes* candidates or parameters, but nothing learned may sit
inside stages 4–9. (This is the axiom-A2 line.)

### comms/ (1,803 LOC)
| module | class | why |
|---|---|---|
| `comms/swarm_protocol.py`, `ros_bridge.py` | **KEEP** | deterministic protocol/IO |
| `comms/human_interface.py` | **OPTIONAL / REVIEW** | claims LLM integration — a potential non-deterministic external dependency; keep off the decision path, gate as an advisory HRI surface |

### adapters/ (781 LOC) — KEEP (per target HW)
`base_adapter`, `mujoco`, `isaac`, `serial`, `ros2`. KEEP the ones matching target
hardware; others OPTIONAL. Clean HAL for stage 10 execution.

### decoders/ (492) & encoders/ (735) — KEEP
Deterministic 12D↔actuator/sensor mapping; feed stage 6 (decoders → actuator
commands) and stage 4/5 (encoders → world/predictor streams).

### vision/ (1,580 LOC) — REMOVE from core (OPTIONAL perception)
`su_vit.py` (torch ViT), `loss.py`, `config.py`. Learned/torch → **REMOVE** from
the deterministic plane; lives upstream as a perception producer whose output
enters ACP only as validated `WorldSnapshot` fields (stage 4 gates it).

### configs/ (YAML) — KEEP
Tier/robot/safety YAML; ACP adds its constraint-set and threshold configs here.

## 3. Reuse summary

| class | components (approx LOC) | share |
|---|---|---|
| **KEEP** | core/types+exceptions+v27, safety/* , state/*, planning/{htn,path,world,primitives,goal}, tiers/{base,reflexive,reactive,factory}, coordination/{shared_world,formation}, formulas/use, decoders/*, encoders/*, comms/{swarm,ros_bridge}, adapters/*, configs/* | **~10,900 LOC (~58%)** |
| **MODIFY** | tiers/deliberative, coordination/{conflict_resolution,task_allocation}, planning/mpc_planner, recovery/* | **~3,000 LOC (~16%)** |
| **OPTIONAL** | core/12D math, formulas/{bcvf,scc}, comms/human_interface | **~2,400 LOC (~13%)** |
| **REMOVE (from core)** | learning/*, vision/* | **~3,400 LOC (~18%)** |

**The deterministic safety-critical spine (safety/ + state/ + planning-det +
tiers-det) is ~58% KEEP-as-is.** BCVF removal touches **3 call sites** in 3
MODIFY files. The redesign is overwhelmingly *reuse + rewire*, not rebuild.

## 4. Special-attention components (Task 3 callout)

| concern | finding | action |
|---|---|---|
| **predictor trust** | the `bcvf_autonomous` kernel is the standalone package; PR-V2 replaces it as primary, keeps it as optional S9 | MODIFY (demote) |
| **arbitration** | no separate arbitration module — arbitration *was* the BCVF action scorer; replaced by AS-V2 | REMOVE→REPLACE |
| **conflict resolution** | `conflict_resolution.py` BCVF-scored with soft safety multiplier | MODIFY → AS-V2 over strategies |
| **task allocation** | `task_allocation.py` BCVF bid ranking; already has hard pre-filters | MODIFY → deterministic constrained ranking |
| **deliberative planning** | `deliberative.py` hosts the BCVF call | MODIFY → host AS-V2; keep planner scaffolding |
| **recovery** | solid deterministic mechanisms, ad-hoc policy | MODIFY → mechanisms under the failure SM |

## 5. Migration roadmap

Staged, each stage independently revertible, **no production edit until this
architecture is approved**. Shadow-first throughout (run ACP alongside, log
divergences, switch only on a clean log).

**Phase 0 — Scaffolding (design→code boundary).**
Stand up the ACP package skeleton (stages as interfaces + the canonical
envelopes) and port the prior milestone's validated
`robotics_reliability_bench` baselines into it as the reference AS-V2 and PR-V2
implementations. No call-site changes. *Deliverable: ACP runs in shadow on
recorded logs.*

**Phase 1 — Close the action-safety hole (highest value, lowest risk).**
Insert the hard-admissibility filter ahead of the BCVF call at the two unguarded
sites (`deliberative.py`, `conflict_resolution.py`; `task_allocation.py` already
pre-filters). This removes the "unsafe candidate can win" defect *before*
touching the ranker. *Reversible; ships independently.*

**Phase 2 — Replace action ranking with AS-V2**, one site at a time
(deliberative → conflict → allocation), each gated on shadow-divergence showing
no safe-action regression. Wire `NO_SAFE_ACTION` to the failure SM at each site.

**Phase 3 — PR-V2 as primary predictor trust.**
Land PR-V2 (deterministic state machine) as primary, `bcvf_autonomous` demoted to
the optional S9 latency feature (off by default). Shadow vs the current
`TrustWeightComputer` on real logs using the frozen metric set.

**Phase 4 — Failure SM + governance.**
Formalize stages 9/11/12 (execution authorization, monitoring, failure SM) over
the existing `recovery/` mechanisms; add the Decision Ledger + Explanation Bus.

**Phase 5 — Deprecate action BCVF.**
Remove `formulas/bcvf.py` from the action path once all three sites are migrated
and shadow-clean for one release. Keep the kernel + tests (demoted, not deleted).

**Gates before any production switch:** a real-sensor pilot reproducing the
synthetic verdicts on ≥1 real fault episode per class; HIL verification of
`NO_SAFE_ACTION`/`ABSTAIN` reachability and safe-state correctness; external
review of the hard-constraint set and ASIL assignment. (The synthetic corpus and
the 1,560-cell characterization do **not** discharge these.)

## 6. Estimated implementation effort

Rough, engineering-planning-grade (not a bid). Assumes the design is approved and
the prior harness is the AS-V2/PR-V2 reference.

| phase | scope | effort |
|---|---|---|
| 0 Scaffolding + port baselines | ACP skeleton, envelopes, reference AS-V2/PR-V2 | 2–3 wk |
| 1 Hard-admissibility filter | 2 call sites + tests | 1 wk |
| 2 AS-V2 rollout | 3 sites, shadow, tie-break profiles | 3–4 wk |
| 3 PR-V2 primary + S9 demote | state machine, quorum, shadow vs kernel | 3–4 wk |
| 4 Failure SM + governance | postures, ledger, monitors, authorization | 4–6 wk |
| 5 Deprecate action BCVF | removal + cleanup | 1 wk |
| — Real-sensor pilot (gating) | dataset adapter + per-class episodes | 3–4 wk (parallelizable) |
| **Total** | | **~14–19 wk** engineering, + pilot |

Largest risk/effort is Phase 4 (governance/failure SM) and the pilot; Phases 1–2
are quick, high-value, and independently shippable.
