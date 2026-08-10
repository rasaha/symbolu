# ACP Hard Constraints (Phase 1)

The deterministic hard constraints implemented in
`autonomous_control_plane/constraint_library.py`, and — equally important — the
constraints deliberately **NOT** implemented because no call site provides their
data. Nothing is fabricated.

---

## 1. Implemented constraints

Every constraint defines: id, hard/soft, input field(s), units, pass rule,
reason code, evidence reference (the world-state version), and missing-data
behavior (fail closed).

| id | kind | input field | units | pass rule | reason code | provenance |
|---|---|---|---|---|---|---|
| `SAFE_FALLBACK` | HARD | action_type / `safe_fallback` | — | STOP/HOLD/wait ⇒ pass | `SAFE_FALLBACK` | POLICY (a stop cannot collide) |
| `OBSTACLE_CLEARANCE` | HARD | `min_obstacle_distance_m` | m | `>= 0.5` | `OBSTACLE_CLEARANCE` / `MISSING_min_obstacle_distance_m` | PROD |
| `SAFETY_SCORE_FLOOR` | HARD | `safety_score` | [0,1] | `>= 0.5` | `SAFETY_SCORE_BELOW_FLOOR` | POLICY |
| `FEASIBILITY_FLOOR` | HARD | `feasibility` | [0,1] | `>= 0.3` | `FEASIBILITY_BELOW_FLOOR` | POLICY |
| `CAPABILITY_MATCH` | HARD | `capability_match` | [0,1] | `>= 0.5` | `CAPABILITY_BELOW_FLOOR` | PROD |
| `LOAD_LIMIT` | HARD | `current_load` | [0,1] | `<= 0.9` | `OVERLOADED` | PROD |
| `COHERENCE_FLOOR` | HARD | `coherence` | [0,1] | `>= 0.4` | `COHERENCE_BELOW_FLOOR` | PROD |

Evidence reference for every result = the `CanonicalWorldState.version` the
candidate was bound to. Missing required input ⇒ HARD **fail** `MISSING_<field>`
(never a silent pass).

## 2. Availability matrix (implemented vs UNAVAILABLE)

| constraint class | deliberative | conflict | task_alloc |
|---|---|---|---|
| physical feasibility | partial (obstacle) | abstract (feasibility floor) | operational (capability) |
| collision margin (m) | **UNAVAILABLE** | **UNAVAILABLE** | **UNAVAILABLE** |
| trajectory validity | **UNAVAILABLE** | **UNAVAILABLE** | **UNAVAILABLE** |
| actuator / velocity / accel limits | **UNAVAILABLE** | **UNAVAILABLE** | **UNAVAILABLE** |
| stopping / escape margin | **UNAVAILABLE** | **UNAVAILABLE** | **UNAVAILABLE** |
| stability / ZMP | **UNAVAILABLE** | **UNAVAILABLE** | **UNAVAILABLE** |
| obstacle clearance | **implemented** (move_to) | — | — |
| per-candidate safety floor | — | **implemented** | — |
| capability / load / coherence | — | — | **implemented** (mirror pre-filters) |
| safe fallback (stop/hold) | **implemented** | **implemented** | — |
| stale world-state | **implemented** (identity binding) | implemented | implemented |
| missing evidence | **implemented** (fail closed) | implemented | implemented |

**The UNAVAILABLE rows are the load-bearing limitation of Phase 1.** They are not
implemented because the call sites do not carry the data; the data exists in the
`safety/` modules but is not wired into these decision points. Implementing them
requires Phase-2 integration, not fabrication.

## 3. Non-compensatory guarantee

Admissibility reads HARD `ConstraintResult`s only. A soft objective, a BCVF
score, or the optional BCVF advisory can never flip a failed HARD result to
admissible — proven by `filter_admissible` (which ignores soft results and never
sees advisories) and the invariant tests
(`test_bcvf_attractive_but_unsafe_is_rejected`,
`test_advisory_never_read_by_selector`).

## 4. Threshold provenance & freezing

- **PROD** thresholds (`0.5` obstacle, `0.5` capability, `0.9` load, `0.4`
  coherence) are lifted verbatim from production code — ACP re-expresses existing
  behavior, it does not invent limits.
- **POLICY** thresholds (`0.5` safety floor, `0.3` feasibility floor) are ACP
  choices, justified from semantics (a strategy with `safety_score < 0.5` is
  majority-unsafe; `forward_score < 0.3` is unlikely to work) and **frozen in
  `ACP_PHASE1_PREREGISTRATION.md`** before the final benchmark. They are not
  tuned on the corpus.
