# ACP V2 — Cross-Domain Preregistration

**Committed BEFORE the final V2 cloud shadow benchmark runs.** Frozen below: the
hypothesis, the reusable-core vs domain-logic split, the selected cloud path, the
canonical envelopes, the hard constraints and their sources, the outcome mapping,
the ActionGate boundary, the corpus and its provenance, the metrics, the safety
invariants, the verdict rules, and the exclusions. Deviations are appended
post-hoc, never edited in place.

**Standing constraints (V2):** ACP stays shadow-only; the current runtime is
authoritative; ACP never actuates a cloud change; ActionGate is not rebranded or
reimplemented; the VC brief is untouched; no enterprise telemetry is fabricated;
no financial/healthcare/other-domain support is claimed from one cloud adapter;
the frozen ACP V1 core is not modified (hash-verified at completion). Do not
recommend production deployment.

---

## 1. Hypothesis (frozen)

**H1 (core reusability).** The ACP V1 *decision core* — canonical identity,
non-compensatory hard-constraint filtering, deterministic total-order selection,
explicit closed-set outcomes, structured decision traces, state/action binding,
commit-time revalidation, and shadow-only operation — is **domain-neutral** and
can be reused **unchanged** to govern a non-robotics domain (Kubernetes/cloud
operations).

**H2 (boundary distinctness).** ACP and ActionGate answer **different
questions** and compose cleanly: ActionGate = *"is this operation authorized?"*;
ACP = *"is this operation operationally safe against live cluster state now?"* A
correct composition must exhibit at least one case where **ActionGate allows but
ACP holds**, and one where **ActionGate denies but ACP would have found it
safe** — proving neither layer subsumes the other.

**Predicted-reusable (core):** identity/serialization, `ConstraintResult` /
`ConstraintKind`, `filter_admissible`, `LexicographicActionSelector`,
`ActionDecision`, `DecisionTrace`, `ControlAuthorization` /
`ReferenceCommitRevalidator`, the error hierarchy, and the fail-closed +
hard-before-soft philosophy.

**Predicted domain-specific (must be re-authored per domain):** the world/action/
evidence envelope *fields*, the concrete hard constraints and their thresholds,
the evidence source, the outcome→domain-action interpretation, and the
authorization-layer composition.

**Non-goal (frozen):** we do **not** claim robotics thresholds or trajectory
equations transfer; we do **not** claim support for any domain other than the one
cloud adapter built here.

## 2. Selected cloud path (frozen)

**Kubernetes deployment operations** (scale / rollout / config-update / delete /
rollback), grounded in the repository's real `cloud_controller` package and
`deploy/gke/*.yaml` manifests. Evidence is produced by the **real**
`cloud_controller` modules:

- `cloud_controller.action.readiness.ReadinessChecker` (min_plasticity 0.3,
  min_time_since_action 120 s, block-during-rollback-watch);
- `cloud_controller.action.policy.PolicyEngine` + `DeploymentPolicy`
  (min/max replicas, blackout windows, rate limit);
- `cloud_controller.recommend.safety.SafetyBounds` + `SafetyConfig`
  (+50 % / −25 % per-action fractions, min_replicas floor, cooldown).

## 3. Canonical envelopes (frozen, additive)

`CloudWorldState` (`.version` identity, domain `cloud_world_state`),
`CloudActionCandidate` (`.identity`, domain `cloud_action_candidate`,
`blast_radius` / `is_destructive`), `CloudOperationalEvidence` (`.identity`,
domain `cloud_operational_evidence`, `validity ∈ {VALID,STALE,EVALUATOR_FAILED,
MISSING}`). All three reuse the frozen `identity.identity` + `normalize_float`
unchanged, with domain separation.

## 4. Hard constraints + sources (frozen)

All HARD (non-compensatory). Missing/stale/evaluator-failure ⇒ single failing
HARD result ⇒ inadmissible (fail closed).

| id | source | rule | reason on fail |
|---|---|---|---|
| `STATE_FRESH` | AUTHORED | `freshness_s ≤ 30 s` | `STATE_STALE` |
| `TARGET_BOUND` | AUTHORED | candidate names this ns/deployment | `TARGET_MISMATCH` |
| `READINESS_OK` | **REAL** `ReadinessChecker` | `.ready` | `NOT_READY` |
| `REPLICA_WITHIN_LIMIT` | **REAL** `PolicyEngine` | absolute min/max | `REPLICA_LIMIT_VIOLATION` |
| `BLAST_RADIUS_WITHIN_BOUND` | **REAL** `SafetyBounds` fractions | `|Δ|` (scale) / surge ≤ bound | `BLAST_RADIUS_EXCEEDED` |
| `MIN_AVAILABILITY_PRESERVED` | **REAL** `SafetyConfig.min_replicas` | `target ≥ min` | `BELOW_MIN_REPLICAS` |
| `NO_ACTIVE_FREEZE` | **REAL** `BlackoutWindow` (flag) | `¬freeze_active` | `FREEZE_WINDOW_ACTIVE` |
| `DEPENDENCY_HEALTHY` | AUTHORED | `dependency_healthy` | `DEPENDENCY_UNHEALTHY` |
| `CAPACITY_SUFFICIENT` | AUTHORED | `available ≥ min_replicas` | `INSUFFICIENT_CAPACITY` |
| `ROLLBACK_AVAILABLE` (rollout/delete) | AUTHORED | `rollback_ref ≠ ""` | `NO_ROLLBACK_REF` |

No soft (weighted) score may compensate for any HARD failure (enforced by the
frozen `filter_admissible`).

## 5. Outcome mapping (frozen)

`EXECUTE → PROCEED`, `EXECUTE_WITH_CONSTRAINTS → PROCEED_WITH_CONSTRAINTS`,
`REQUEST_MORE_OBSERVATION → REOBSERVE`, and `{REPLAN, DEGRADE_MODE, SAFE_STOP,
NO_SAFE_ACTION} → HOLD`. No new decision states are added to the frozen enum.

## 6. ActionGate boundary + composition (frozen)

ActionGate's verdict (one of `DENY / REQUEST_MORE_EVIDENCE / SIMULATE_AND_RETRY /
ESCALATE_TO_HUMAN / ALLOW_WITH_CONSTRAINTS / ALLOW`) is passed to `compose()` as
an **input token**; ACP never recomputes it. Precedence (non-compensatory):

1. `DENY` ⇒ `BLOCKED_BY_AUTHORIZATION` (ACP can never override);
2. pending gate states ⇒ `PENDING_AUTHORIZATION` (ACP cannot authorize);
3. authorized **and** ACP permissive ⇒ `PROCEED`;
4. authorized **and** ACP not permissive ⇒ `HELD_BY_ACP`.

## 7. Corpus (frozen, 19 scenarios)

Provenance-labelled `REPOSITORY_MANIFEST` / `REPOSITORY_SCENARIO` /
`SYNTHETIC_UNIT` / `AUTHORED_DETERMINISTIC`. Required members: healthy rollout,
insufficient capacity, stale state, invalid manifest, excessive replica increase,
excessive blast radius, missing rollback, dependency unhealthy, active freeze
window, safe constrained rollout, destructive delete, modified-manifest-after-eval,
state drift, all-strategies-unsafe, and the two decisive boundary cases
**`ag_allows_acp_holds`** and **`ag_denies_acp_safe`**. (Full listing in
`robotics_reliability_bench/acp_cloud/corpus.py`; description in
`ACP_CLOUD_SHADOW_METHOD.md`.)

## 8. Metrics (frozen)

Cloud-shadow: decision + recommendation distribution, fail-closed count and
"all fail-closed ⇒ HOLD". Composition: combined-outcome distribution, ACP-decisive
count (`HELD_BY_ACP`), authorization-blocked count. Determinism: rerun-identity,
sink seen/dropped. Latency: mean/p95/max. Correctness: match vs the expectations
frozen here (0 mismatches required).

## 9. Safety invariants (frozen — must all hold)

I1 an `DENY` is never composed to `PROCEED`; I2 an ACP hold never proceeds
regardless of authorization; I3 `PROCEED` requires **both** an authorizing verdict
and a permissive ACP; I4 every record is `shadow_only`; I5 no uncontained shadow
error; I6 the two decisive boundary scenarios resolve as designed; I7 commit
revalidation rejects both drift scenarios.

## 10. Verdict rules (frozen)

- **Cross-domain architecture** → `ACP_GENERALIZES` iff H1 holds (core hash
  unchanged AND the frozen selector/filter/trace/revalidator run unchanged on
  cloud envelopes) AND all §9 invariants pass; `…_WITH_LIMITATIONS` if it works
  but required an adapter-only concession worth flagging; `ACP_ROBOTICS_SPECIFIC`
  if any core change was required.
- **Cloud adapter** → `CLOUD_ADAPTER_SUPPORTED` iff every corpus expectation is
  met and evidence comes from the real `cloud_controller`; `…_WITH_LIMITATIONS`
  if coverage is thin or partly authored; `…_NOT_SUPPORTED` otherwise.
- **ActionGate composition** → `BOUNDARY_CLEAN` iff H2 holds (both decisive cases
  present and correct, no reimplementation of ActionGate); `…_OVERLAP_NEEDS_
  REDESIGN` if the layers duplicate; `…_NOT_VIABLE` if they conflict.
- **Product direction** → `PROCEED_HORIZONTAL_PLATFORM` /
  `REMAIN_ROBOTICS_FOCUSED` / `INSUFFICIENT_EVIDENCE`, argued from the evidence
  (one adapter is one data point).

## 11. Exclusions (frozen)

No real cluster is contacted; no Kubernetes client is imported by the adapter; no
ActionGate token is minted by ACP; `BlackoutWindow` day/hour evaluation is
represented as a deterministic carried flag to keep identity timezone-independent
(the real logic is exercised in `cloud_controller`'s own tests); the corpus is
19 scenarios (decision-grade, not certification); one domain adapter cannot prove
horizontal-platform generality.
