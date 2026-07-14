# ACP Phase 1 — Preregistration

**Committed BEFORE the final shadow benchmark runs.** Everything below
(constraints, thresholds, missing-data policy, lexicographic order, comparison
classes, success criteria, corpus split, verdict rules) is frozen at commit
time. Deviations are appended post-hoc, never edited silently.

**Milestone rule honored:** shadow-only; production BCVF remains authoritative;
no call-site migration; no actuation through ACP; no real-sensor claim.

---

## 1. Frozen hard-constraint definitions (per call site)

Only constraints backed by data the call site actually provides. Provenance:
`PROD` = threshold taken from existing production code; `POLICY` = ACP policy
threshold frozen here. Everything else is **UNAVAILABLE** and NOT implemented
(no fabrication).

| call site | constraint id | rule | provenance | applies to |
|---|---|---|---|---|
| deliberative | `SAFE_FALLBACK` | STOP/HOLD/wait ⇒ admissible | POLICY (safe posture) | wait |
| deliberative | `OBSTACLE_CLEARANCE` | `min_obstacle_distance_m >= 0.5` | PROD (`deliberative.py:212`) | move_to |
| conflict | `SAFE_FALLBACK` | STOP ⇒ admissible | POLICY | MUTUAL_STOP |
| conflict | `SAFETY_SCORE_FLOOR` | `safety_score >= 0.5` | POLICY | all strategies |
| conflict | `FEASIBILITY_FLOOR` | `feasibility(forward_score) >= 0.3` | POLICY | all strategies |
| task_alloc | `CAPABILITY_MATCH` | `capability_match >= 0.5` | PROD (`task_allocation.py:239`) | all bids |
| task_alloc | `LOAD_LIMIT` | `current_load <= 0.9` | PROD (`task_allocation.py:243`) | all bids |
| task_alloc | `COHERENCE_FLOOR` | `coherence >= 0.4` | PROD (`coherence_threshold`) | all bids |

**UNAVAILABLE at every call site (NOT implemented):** collision-margin-in-metres,
stopping distance, actuator limits, stability/ZMP, trajectory validity — the
call sites do not carry this data; it lives in the separate `safety/` modules
that are not wired into these decision points. See `ACP_HARD_CONSTRAINTS.md`.

## 2. Missing-data policy (frozen)

- A constraint that *applies* to a candidate but whose feature is *absent* emits
  a HARD **failing** result `MISSING_<feature>` → candidate inadmissible (fail
  closed). It never silently passes.
- A candidate with *no applicable hard constraint* is `NO_HARD_EVIDENCE` →
  inadmissible (fail closed).
- A candidate set where all rejections are `MISSING_*` (with no admissible
  survivor) classifies as `ACP_INSUFFICIENT_EVIDENCE` /
  `REQUEST_MORE_OBSERVATION` — never `EXECUTE`.

## 3. Frozen lexicographic soft order (per call site)

Applied only among ADMISSIBLE survivors; candidate id is the final total
tie-break. No BCVF score, softmax, or temperature is used.

| call site | order (best first) | justification |
|---|---|---|
| deliberative | goal_progress ↓ , feasibility ↓ , id ↑ | make progress; prefer more-feasible; stable |
| conflict | safety_score ↓ , efficiency(backward) ↓ , id ↑ | conflict resolution prioritizes safety, then efficiency |
| task_alloc | distance ↑ , load ↑ , capability ↓ , id ↑ | closest, least-loaded, most-capable robot |

## 4. Comparison classes (frozen)

`AGREE_ADMISSIBLE`, `DIFFERENT_BOTH_ADMISSIBLE`, `BCVF_SELECTED_INADMISSIBLE`
(sub-split `REAL_VIOLATION` vs `UNEVALUABLE`), `ACP_NO_SAFE_ACTION`,
`ACP_INSUFFICIENT_EVIDENCE`, `ADAPTER_UNSUPPORTED`, `SHADOW_ERROR`.
Precedence for the single categorical label: `BCVF_SELECTED_INADMISSIBLE` >
refusal classes > `AGREE` > `DIFFERENT`. Independent boolean fields
(`bcvf_selected_inadmissible`, `acp_no_safe_action`, `both_selected_same`,
`missing_evidence`) are recorded and drive the rate metrics so overlapping
conditions are all counted. A disagreement is classified, never scored as an ACP
"win".

## 5. Corpus split (frozen)

All scenarios are **synthetic** and labeled so. There is **no tuning split**:
every threshold is either PROD (fixed by production) or a POLICY value frozen in
§1 — none is fit to the corpus. The corpus is evaluation-only:
`robotics_reliability_bench/acp_shadow/corpus.py`, 14 classify scenarios +
2 authorization scenarios across the three call sites.

## 6. Success criteria (frozen)

Phase 1 succeeds iff, on the corpus:
1. deterministic-rerun identity = 100% (decision content, excluding wall-clock);
2. ACP never selects an inadmissible candidate (invariant test);
3. an advisory feature can never override a failed hard constraint (invariant);
4. missing required safety evidence never yields `EXECUTE` (invariant);
5. stale state / modified action invalidate authorization (invariants);
6. current-runtime behavior-change count = 0;
7. at least one real call site has adequate adapter coverage.

## 7. Verdict rules (frozen)

**Hard-admissibility logic** →
- `HARD_FILTER_SUPPORTED` if every call site has ≥1 non-fabricated hard
  constraint AND ACP never selects an inadmissible candidate AND determinism
  holds.
- `HARD_FILTER_SUPPORTED_WITH_LIMITATIONS` if the above holds but ≥1 call site
  can only be partially covered (key physical constraints UNAVAILABLE, or some
  candidate classes unevaluable).
- `HARD_FILTER_NOT_SUPPORTED` if a call site provides no usable hard-constraint
  data at all, or ACP can select an inadmissible candidate.

**Production migration readiness** →
- `SHADOW_CONTINUE` default.
- `READY_FOR_GATED_CANARY` only if ALL gating conditions hold (milestone §10):
  zero behavior change, 100% rerun identity, ACP never selects inadmissible,
  adequate adapter coverage for ≥1 real call site, unresolved missing-evidence
  fail-closed, no real-sensor claim.
- `NOT_READY_FOR_MIGRATION` otherwise.
Full replacement is out of scope for Phase 1 by rule.

## 8. Deviations (append-only)

*(none at preregistration commit)*
