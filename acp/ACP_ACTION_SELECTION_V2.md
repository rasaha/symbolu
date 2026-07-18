# ACP Action Selection V2 (Task 5)

Action Selection V2 (AS-V2) is **stages 6–8** of the Autonomous Control Plane:
candidate generation → non-compensatory admissibility filter → deterministic
selection with an explicit `NO_SAFE_ACTION` outcome.

**Design stance:** there is **no BCVF here.** The `REPLACE_ACTION_BCVF` verdict
is honored by construction. The reference implementation is the validated
deterministic selector in `robotics_reliability_bench/action_baselines.py`
(which, in the prior benchmark, never selected a hard-inadmissible candidate,
while unguarded BCVF selected an unsafe action in 3/4 scenarios).

---

## 1. The core rule

> **Hard constraints filter. Soft objectives rank. Never rank an unsafe action.
> If the admissible set is empty, return `NO_SAFE_ACTION`.**

Safety is non-compensatory (axiom A1): no soft optimum can buy back a violated
hard constraint, because unsafe candidates are removed *before* any objective is
computed. This is the single most important structural difference from the
BCVF action scorer, whose additive/consistency terms let an unsafe-but-
"consistent" action win (prior `ROBOTICS_ACTION_SELECTION_BASELINES.md`).

## 2. Canonical candidate

```
CandidateAction := {
  id, primitive, params, predicted_traj,
  hard   : { collision_ok, feasible, speed_ok, geofence_ok,
             regulatory_ok, mission_ok, stability_ok },   # all boolean
  soft   : { energy, distance, time, comfort },            # all real, bounded
  margins: { collision_m, stability, speed_headroom },     # for confidence + tie-break
}
```

`hard.*` are booleans derived from stage-3 `ConstraintSet` predicates evaluated
on `predicted_traj` against the trusted consensus world. `soft.*` are computed
only to rank *already-admissible* actions.

## 3. Stage 6 — Candidate generation (bounded, deterministic)

- Fixed motion-primitive library or fixed lattice; **fixed count** `K ≤ 64`.
- Trajectories rolled out against the PR-V2 trusted consensus.
- No RNG. If sampling is used it is a fixed low-discrepancy sequence, seeded and
  identical every run. `O(K·H)`.
- Emits `Candidates[K]`; may be empty (fully blocked) — that is a valid input to
  stage 7, not an error.

## 4. Stage 7 — Admissibility filter (the hard gate)

```
Admissible = [ c for c in Candidates
               if c.hard.collision_ok and c.hard.feasible
                  and c.hard.speed_ok and c.hard.geofence_ok
                  and c.hard.regulatory_ok and c.hard.mission_ok
                  and c.hard.stability_ok ]
```

- **Non-compensatory:** a single false hard flag removes the candidate. No
  weighting, no score.
- **Fixed evaluation order** so the *first* violated constraint is the
  deterministic rejection reason (drives explainability — Task 8).
- Malformed/NaN feature → treated as a violation (fail-closed).
- `O(K·C)`, bounded.

### Hard constraint catalogue (from stage-3 `ConstraintSet`)

| class | examples | source |
|---|---|---|
| collision | swept-volume clearance ≥ floor vs obstacles | `safety/collision_guard.py`, `trajectory_validator.py` |
| feasible motion | joint/velocity/accel limits, kinematic envelope | `safety/constraint_monitor.py` |
| unsafe speed | speed-and-separation (ISO/TS 15066), zone speed law | `safety/human_proximity.py` |
| regulatory limits | geofence, road-class speed, keep-outs | stage-3 resolver |
| mission constraints | mission keep-outs, ordering, no-go goals | mission + stage-3 |
| stability | ZMP / tip-over / energy bounds | `safety/energy_bounds.py` |

## 5. Stage 8 — Deterministic selection

```
if not Admissible:
    return NO_SAFE_ACTION                       # explicit, routed to recovery

def soft_cost(c):
    return (w_energy*c.soft.energy + w_dist*c.soft.distance
            + w_time*c.soft.time + w_comfort*c.soft.comfort)   # fixed weights

# total order: soft cost, then larger safety margin, then lowest id
selected = min(Admissible,
               key=lambda c: (round(soft_cost(c), 6),
                              -round(min(c.margins.collision_m,
                                         c.margins.stability), 6),
                              c.id))
return selected
```

- The soft objective is a **fixed weighted sum** over admissible actions only.
  Weights are config, not learned; changing them cannot admit an unsafe action.
- **Total tie-break** (cost → margin → id) guarantees a unique, replayable
  winner. No probabilistic scoring; ties cannot be left unresolved.
- Optional profile: a **lexicographic** variant (max margin ▷ goal ▷ cost) or a
  **constrained-optimum** variant (max goal s.t. margin ≥ comfortable floor) —
  both already prototyped; a deployment picks one profile, frozen.
- `O(|Admissible|)`.

## 6. Why this beats the four alternatives (recap of measured result)

| alternative | AS-V2 vs it |
|---|---|
| BCVF action scorer | AS-V2 never ranks an unsafe action; BCVF did in 3/4 scenarios; AS-V2 has `NO_SAFE_ACTION`, BCVF has none |
| pure hard filter | AS-V2 = hard filter **plus** a principled soft objective and total tie-break |
| weighted utility (only) | AS-V2 applies the utility **only after** the hard gate, so utility can't override safety |
| constrained optimization | AS-V2 *is* a constrained optimizer with an explicit infeasible outcome (`NO_SAFE_ACTION`) |

## 7. Runtime, determinism, failure modes

- **Complexity:** `O(K·H + K·C + |Admissible|)`, every factor a fixed bound.
- **Determinism:** fixed candidate count, fixed constraint order, total tie-break,
  fixed weights — bit-for-bit replayable.
- **Failure modes:**
  - empty admissible set → `NO_SAFE_ACTION` → recovery selects a safe posture
    (SAFE_HOLD / minimum-risk maneuver). This is a *correct outcome*, not a crash.
  - PR-V2 returned `ABSTAIN` (no trusted consensus) → stage 6 has no reliable
    world to roll out against → AS-V2 is skipped and control routes straight to
    recovery (never plan on an untrusted consensus).
  - all candidates tie exactly → resolved by id (total order) — deterministic.

## 8. Interaction with Execution Authorization (stage 9)

Selection is *decision-time* admissibility; stage 9 re-checks admissibility of
the single selected action against freshly re-read state at commit (TOCTOU). A
selected action can still be denied at commit if the world moved — that is by
design, and it is the second, independent safety check.
