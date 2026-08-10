# ACP Action Selection Implementation (Phase 1)

The deterministic selection actually used in shadow: hard filter → refuse if
empty → lexicographic order among survivors → total id tie-break. Code:
`autonomous_control_plane/action_selection.py`.

---

## 1. Two selectors, one admissibility filter

`filter_admissible(candidates, candidate_constraints)` is shared by both
selectors. A candidate is admissible iff it has ≥1 HARD result and no failed
HARD result. No hard evidence ⇒ not admissible (fail closed). The first failed
HARD result is the dispositive rejection reason.

- `DeterministicActionSelector` (Phase 0) — scalar soft cost → margin → id.
- `LexicographicActionSelector` (Phase 1) — a caller-supplied frozen total key →
  id. Used for all three call-site adapters.

Both refuse identically: empty admissible → `NO_SAFE_ACTION`; no evidence →
`REQUEST_MORE_OBSERVATION`. Neither ever ranks an inadmissible candidate (shared
filter), and neither reads a BCVF score, softmax, or temperature.

## 2. Ordering (frozen per call site)

Encoded in `adapters.py` as the `sort_key`. Candidate id is appended by the
selector as the always-unique final tie-break, so the order is total and the
winner is unique and replayable.

| call site | key (ascending sort; smaller = better) | meaning |
|---|---|---|
| deliberative | `(-goal_progress, -feasibility)` | most goal progress, then most feasible |
| conflict | `(-safety_score, -efficiency)` | safest, then most efficient |
| task_alloc | `(distance, load, -capability)` | closest, least-loaded, most-capable |

Justification is from existing system semantics (`ACP_PHASE1_CALLSITE_AUDIT.md`):
conflict resolution should prefer the safest viable strategy (fixing the BCVF
demotion of `MUTUAL_STOP`); task allocation should prefer the closest capable
available robot; deliberative should make goal progress among feasible actions.

## 3. Decision outcomes

- `EXECUTE` — a survivor selected, no failed soft constraint on it.
- `EXECUTE_WITH_CONSTRAINTS` — a survivor selected but with a failed SOFT
  constraint (execution caps would attach). Not exercised by the Phase-1 corpus
  (no soft constraints defined yet).
- `NO_SAFE_ACTION` — admissible set empty after the hard filter.
- `REQUEST_MORE_OBSERVATION` — no candidate had any hard evidence.

## 4. Determinism properties (verified)

- Total order (site key then id) ⇒ unique winner; no unresolved ties.
- No randomness, no temperature, no softmax on the path.
- Injected identity/versioning only; wall-clock excluded from decision content.
- Deterministic-rerun identity = 100% on the corpus (decision content).

## 5. What selection deliberately does NOT do

- Does not read `bcvf_advisory` (cannot resurrect an inadmissible candidate).
- Does not consult the physical margin fields (`collision_margin_m`,
  `stability_margin`, …) at these call sites — they are inert `0.0` placeholders
  flagged `unavailable` by the adapter, never read by the site sort keys.
- Does not authorize actuation — selection produces a `SelectionOutcome` +
  trace; authorization is a separate shadow-only object never used to actuate in
  Phase 1.
