# ACP V2 — Cross-Domain Results & Verdicts

**Run:** deterministic cloud-operations shadow benchmark (19 scenarios).
Machine-readable: `robotics_reliability_bench/results/acp_cloud_results.json`.
Preregistration: `ACP_V2_CROSS_DOMAIN_PREREGISTRATION.md` (committed `7dadf7c`,
**before** this run). **Shadow-only. Current runtime unchanged. Zero production
edits. No actuation. No fabricated telemetry. No cluster contacted.** Frequencies
are reported only within this 19-scenario corpus.

The frozen ACP V1 core is **hash-identical** after V2 (combined SHA-256
`8f8660e293308cf94c983a26a2ae69c9`; `ACP_V1_FREEZE.md` §4).

---

## 1. Headline

| metric | value |
|---|---|
| scenarios | 19 (REPOSITORY_MANIFEST 3 · REPOSITORY_SCENARIO 4 · AUTHORED 7 · SYNTHETIC_UNIT 5) |
| ACP decisions | EXECUTE 6 · NO_SAFE_ACTION 13 |
| combined outcomes | PROCEED 5 · HELD_BY_ACP 12 · PENDING_AUTHORIZATION 1 · BLOCKED_BY_AUTHORIZATION 1 |
| **ACP-decisive holds** (authorized but ACP held) | **1** (`ag_allows_acp_holds`) + 11 no-auth-token holds |
| **authorization-blocked** (ACP safe, gate denied) | **1** (`ag_denies_acp_safe`) |
| corpus expectations met | **19 / 19** (0 permissive mismatches, 0 combined mismatches) |
| safety invariants I1–I7 | **all pass** |
| rerun identity | **100 %** · sink dropped **0** |
| frozen V1 core hash | **unchanged** |
| shadow latency | mean **0.23 ms** · p95 **0.45 ms** · max **0.56 ms** |

## 2. The two decisive boundary cases (H2)

- **`ag_allows_acp_holds`** — ActionGate `ALLOW`, but the **real**
  `cloud_controller` `ReadinessChecker` reports NOT_READY (a scaling action 30 s
  ago < the 120 s cooldown). ACP → `NO_SAFE_ACTION`/`HOLD`. Composition →
  **`HELD_BY_ACP`**. ActionGate had no way to catch this; ACP did.
- **`ag_denies_acp_safe`** — an operationally-perfect scale (ready, within real
  SafetyBounds, rollback present) that ActionGate `DENY`s. ACP → `EXECUTE`/
  `PROCEED`, but composition → **`BLOCKED_BY_AUTHORIZATION`**. ACP's safe verdict
  did **not** mint authorization.

Both present, both correct → the layers are orthogonal; neither subsumes the
other.

## 3. Safety invariants (all proven — §13)

I1 gate `DENY` never composes to `PROCEED`; I2 an ACP hold never proceeds
regardless of authorization; I3 `PROCEED` requires **both** an authorizing verdict
and a permissive ACP; I4 every record `shadow_only`; I5 no uncontained shadow
error; I6 the two decisive boundary scenarios resolve as designed; I7 commit
revalidation rejects both drift scenarios (state drift + manifest mutation).
`test_acp_cloud.py` (28 tests) proves these plus fail-closed on every degraded
path, frozen-selector reuse, OFF-by-default, bounded-sink drop counting, and
no-k8s-client. **112 ACP tests pass** overall; robotics baseline unchanged.

## 4. Limitations (binding)

- **One adapter is one data point.** Cloud generalization does **not** by itself
  establish finance/healthcare/other-domain support (explicit V2 non-goal).
- **Evidence is partly authored.** 4 of 10 hard constraints (`READINESS_OK`,
  `REPLICA_WITHIN_LIMIT`, `BLAST_RADIUS_WITHIN_BOUND`, `MIN_AVAILABILITY_
  PRESERVED`) are driven by **real** `cloud_controller` logic; the other
  6 (`STATE_FRESH`, `TARGET_BOUND`, `NO_ACTIVE_FREEZE`, `DEPENDENCY_HEALTHY`,
  `CAPACITY_SUFFICIENT`, `ROLLBACK_AVAILABLE`) are authored operational rules with
  no repository equivalent. That gap is honest, not fabricated.
- **`NO_ACTIVE_FREEZE` uses a carried flag** rather than calling
  `BlackoutWindow.is_active` inside the evaluator, to keep canonical identity
  timezone-independent. The real blackout logic is exercised by
  `cloud_controller`'s own tests, not re-run here.
- **No live cluster / no real cluster telemetry.** Latency, capacity margins, and
  readiness signals come from authored/real-config fixtures, not a running
  cluster. Corpus is 19 scenarios — decision-grade, not certification.
- **ActionGate verdicts are inputs, not co-executed.** The composition consumes a
  supplied `AuthorizationVerdict`; a full end-to-end ActionGate→ACP integration
  test against the real gate is future work.

## 5. Verdicts (§14)

### Cross-domain architecture → **`ACP_GENERALIZES`**
H1 holds. The frozen ACP decision core — identity, `filter_admissible`,
`LexicographicActionSelector`, `ActionDecision`, `DecisionTrace`,
`ReferenceCommitRevalidator`, the error hierarchy, fail-closed + hard-before-soft
— ran **byte-for-byte unchanged** on cloud envelopes (core hash unchanged; 0 core
lines edited), and every §13 invariant passed. The decision machinery is
domain-neutral; only domain knowledge (fields, thresholds, evidence source,
authorization boundary) was re-authored. No `CORE_CHANGE_REQUIRED` property
appeared.

### Cloud adapter → **`CLOUD_ADAPTER_SUPPORTED_WITH_LIMITATIONS`**
Every one of the 19 corpus expectations was met, with the four numeric gates
driven by the **real** `cloud_controller` readiness/policy/safety modules, and
fail-closed on all degraded-evidence paths. The `_WITH_LIMITATIONS` qualifier is
honest: 6 of 10 constraints are authored (no repository source), the freeze check
is a carried flag, and no live cluster or real telemetry was involved. Sufficient
as decision-grade shadow evidence; not a certified production controller.

### ActionGate composition → **`BOUNDARY_CLEAN`**
H2 holds. `composition.py` imports nothing from ActionGate and never recomputes
its verdict; both decisive cases are present and correct; a gate `DENY` is never
overridden and an ACP hold never mints authorization. The layers answer different
questions and compose without overlap or conflict.

### Product direction → **`INSUFFICIENT_EVIDENCE`** (leaning toward a *deliberate*
horizontal step)
The architecture demonstrably generalizes (strong), but a **single** cloud
adapter — with partly-authored evidence and no live-cluster validation — is not
enough to justify `PROCEED_HORIZONTAL_PLATFORM` as a product commitment. The
honest call is `INSUFFICIENT_EVIDENCE` **for a platform claim**, while noting the
core-reuse result is a genuine, positive signal: the next data point (a second,
structurally-different domain with real evidence, e.g. database migrations or CI/CD
gating) would move this to `PROCEED_HORIZONTAL_PLATFORM` or expose the first real
`CORE_CHANGE_REQUIRED`. Do **not** deploy to production on this evidence.

## 6. Rollback & kill-switch

- **Kill switch:** `CloudShadowAdapter(enabled=False)` (default) — no shadow work,
  returns `None`. Not wired into any production path.
- **Rollback:** delete `symbolu_robotics/autonomous_control_plane/cloud/` and
  `robotics_reliability_bench/acp_cloud/`; nothing in production imports them; the
  frozen ACP core and `cloud_controller` are untouched.
- **Tested:** OFF ⇒ `None` + no record; exception contained; bounded sink caps
  length and counts drops; commit revalidation rejects drift.

## 7. Next step (if pursued)

Add a **second, structurally-different** domain adapter with **real** evidence
(not authored), and an **end-to-end integration test against the real ActionGate**
(not a supplied verdict token). Two clean generalizations with real evidence would
justify the horizontal-platform direction; the first forced core change would
bound it.
