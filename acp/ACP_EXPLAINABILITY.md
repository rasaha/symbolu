# ACP Explainability (Task 8)

Every ACP decision produces a **structured, human-legible explanation** bound to
the evidence it used. No opaque scalar decides anything alone (axiom A3). This is
enforced by construction: the pipeline is deterministic threshold/predicate
logic, so every accept/reject/abstain *has* a nameable dispositive reason — there
is nothing to reverse-engineer.

---

## 1. The `Explanation` record

Every stage emits one `Explanation` per decision onto the Explanation Bus; the
Decision Ledger persists them hash-chained per tick.

```
Explanation := {
  tick, stage, decision,                     # e.g. "REJECT" / "SELECT" / "ABSTAIN"
  subject_id,                                # candidate id / predictor index / mission id
  dispositive_reason : {                     # the ONE rule that decided it
      code,                                  # enum, e.g. COLLISION_MARGIN_VIOLATION
      signal,                                # e.g. "collision_margin"
      value, threshold, units,               # 0.05 m  <  0.20 m
      comparator,                            # "<"
  },
  contributing : [ {signal, value, state} ], # other signals, for context (not decisive)
  evidence_ref : { snapshot_hash, constraint_set_hash },  # what world it judged
  confidence : { margin_m, margin_s, predictor_state, evidence_complete, admissible_count },
}
```

The **dispositive reason is singular and deterministic**: because stage 7
evaluates hard constraints in a fixed order, the *first* violated constraint is
the reason — reproducible every run.

## 2. Worked example (a full tick)

```
tick 4821  stage=ACTION_SELECTION  decision=SELECT

Candidate A "charge_through"   REJECTED
  reason: COLLISION_MARGIN_VIOLATION
          collision_margin = 0.05 m  <  0.20 m floor
  evidence: snapshot 0x9f3a…, constraints 0x1120…

Candidate B "fast_detour"      REJECTED
  reason: ENERGY_LIMIT_EXCEEDED
          energy = 142 J  >  120 J budget

Candidate C "safe_detour"      SELECTED
  reason: ONLY_ADMISSIBLE (1 of 3 candidates passed all hard constraints)
          soft_cost = 0.63  (energy 0.4·? + distance 0.55 + time 0.30 …)
          margin: collision 0.60 m, stability 0.6
  confidence: margin_m=0.60, predictor_state=TRUSTED,
              evidence_complete=1.00, admissible_count=1
```

Contrast with the system being replaced: BCVF emitted `normalized_weight=0.42`
with no reason a reviewer could act on. ACP emits *why*.

## 3. Explanation per stage

| stage | typical decision | dispositive reason codes (examples) |
|---|---|---|
| 1 Mission | REJECT_MISSION | ODD_UNSUPPORTED, GOAL_CONFLICT, MALFORMED |
| 2 Task Planner | FAIL_PLAN | GOAL_UNREACHABLE, EXPANSION_CAP |
| 4 World Validation | STALE_WORLD | STALE(sensor,age), NAN_FIELD, OBSTACLE_CAP |
| 5 Predictor Reliability | state per predictor / ABSTAIN | PERSISTENT_BIAS, HARD_HEALTH_FAULT, STALE, NO_QUORUM |
| 7 Admissibility | REJECT(candidate) | COLLISION_MARGIN, INFEASIBLE_MOTION, SPEED_LIMIT, GEOFENCE, STABILITY |
| 8 Selection | SELECT / NO_SAFE_ACTION | ONLY_ADMISSIBLE, MIN_SOFT_COST, TIE_BREAK_MARGIN, EMPTY_ADMISSIBLE_SET |
| 9 Authorization | DENY_COMMIT | STATE_MOVED, DEADLINE_MISSED, CLOCK_ANOMALY |
| 11 Monitoring | TRIP | INTENT_DIVERGENCE, MARGIN_COLLAPSE, WATCHDOG_TIMEOUT |
| 12 Recovery | posture transition | (refusal code → posture, per failure SM) |

## 4. Properties the format guarantees

- **Actionable.** Every reason names a signal, its value, the threshold, and the
  comparator — an operator or auditor can check it by hand.
- **Bound to evidence.** `snapshot_hash` + `constraint_set_hash` tie the reason to
  the exact world and rule set it was judged against; a replay reproduces it
  bit-for-bit.
- **Singular & deterministic.** One dispositive reason, chosen by fixed
  evaluation order — no "the model felt it."
- **Confidence is physical.** The `confidence` block is the §2.1 tuple from the
  architecture doc: metres, seconds, an enum, a fraction, a count — never a bare
  probability.
- **Complete.** Rejections are explained too, not just the selection — so "why
  not A?" always has an answer.

## 5. Consumers

- **Decision Ledger:** hash-chained persistence for incident recall + safety
  case (the ISO-26262/SOTIF evidence artifact).
- **Operator surface:** live "why did it do that / why did it stop" panel.
- **Offline replay:** feed a recorded tick's evidence back through the pipeline;
  the explanation must match bit-for-bit (a determinism regression test).
- **Certification:** the reason catalogue is the enumerable behaviour set a
  reviewer signs off against.

## 6. Non-negotiable rule

**No decision without an explanation.** A stage that cannot produce a dispositive
reason for its output is a bug, not a black box — the pipeline is designed so
that state never arises. If an optional feature (e.g. the BCVF S9 signal) can
only offer a scalar, it may **influence latency** but may never be the
*dispositive* reason for a state change; the dispositive reason must always be a
nameable deterministic signal.
