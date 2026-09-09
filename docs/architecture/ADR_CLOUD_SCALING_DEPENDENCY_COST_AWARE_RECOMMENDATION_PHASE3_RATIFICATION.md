# Ratification record — Cloud Scaling Phase 3, dependency- and cost-aware capacity recommendations

**Status:** ratified, retrospectively. Closes the missing owner decision on
`ADR_CLOUD_SCALING_DEPENDENCY_COST_AWARE_RECOMMENDATION_PHASE3.md`, which is alongside this
file in the tree and which shipped before it was ratified.

**Ratified:** 2026-09-09 by the repository owner.
**Package:** `packages/capabilities/cloud-scaling-controller` (`ugence-cloud-scaling-controller`) at `0.4.0`.
**Merge commit:** `5d602fdb` (PR #1652) — the ADR and the `planning/` implementation it
describes entered the default branch together.

## Why this record exists

Phase 1 and Phase 2 each carry an `ACCEPTED` ADR. Phase 3 carried
`**PROPOSED** (draft PR; not merged)` while its code had been live at `0.4.0` for weeks and
`ugence-cloud-scaling-operations` had already moved its dependency range to `>=0.4.0,<0.5`.
The status was not merely stale — it recorded no owner decision at all, so a shipped,
consumer-visible capability had no ratified boundary to be audited against.

The owner's ruling was that shipping is not ratification: the status may not be promoted
merely because the code merged. This record ratifies the scope **as verified against the
implementation**, and ratifies no more than that.

## What was verified before ratifying

Ratification was conditioned on the implementation conforming to the Phase 3 boundary the
proposal states. Each claim below was checked against the source at `da3eb31b`, not accepted
from the ADR's own prose. Had any failed, the instruction was to stop and report the
mismatch rather than ratify.

| Boundary claim (proposal §Boundaries, §Consequences) | Verified | Evidence |
|---|---|---|
| Every recommendation carries `advisory_only = shadow_only = True`, `actuation_performed = authorization_performed = effect_verified = False`, `authority_class = ADVISORY`, `execution_capability = NONE` | ✅ | `planning/recommendation.py:171-177` declares them and `:182-193` **refuses construction** if any is overridden — enforced, not merely defaulted |
| Imports no Risk Authority, no ActionGate, no cloud/Kubernetes API, no credential or network code | ✅ | every non-relative import in `planning/*.py` is `math`; there is no other third-party or first-party import in the subpackage |
| Recommendations never feed the live controller | ✅ | `controller.py`, `contracts.py` and `api.py` contain no reference to `planning`; the dependency runs one way |
| Derived fields recomputed from embedded inputs at construction **and** at `from_dict` | ✅ | `__post_init__` + `from_dict` on `EvaluatedCandidate`, `CapacityActionRecommendation` and `RecommendationAbstention` (`planning/recommendation.py:86,124,180,501,670,720`) |
| Hard constraints filter **before** scoring (non-compensatory) | ✅ | `planning/pipeline.py` steps 5 and 7: feasibility precedes `score_candidate`; a cheaper unsafe plan is eliminated before it is scored |
| Planning target is `RUNNING_REPLICAS`; other targets abstain | ✅ | `planning/scoring.py:76,139`; `planning/pipeline.py:146` returns `UNSUPPORTED_FORECAST_TARGET` |
| No new runtime dependency | ✅ | `pyproject.toml` declares `numpy>=1.24.0` only, unchanged from Phase 1/2; `planning/` itself is pure stdlib |
| Phase 1 canonical layer and Phase 2 forecasting unchanged; live path unchanged | ✅ | `tests/behavior` 19 passed (frozen decision-baseline parity), `tests/canonical` 165 passed, `tests/forecasting` 243 passed |
| No import-time network/socket/process/thread activity | ✅ | `tests/side_effects` 6 passed |
| Consumer range moved to `>=0.4.0,<0.5` | ✅ | `packages/capabilities/cloud-scaling-operations/pyproject.toml:39` |

**Test evidence.** `tests/planning` 330 passed; full package suite 807 passed / 6 skipped;
`tests/boundaries` 9 passed / 1 skipped — the skip is `test_advisory_boundary.py:145`,
correctly conditional on the operations package being absent in a wheel-only environment.
The repository-root legacy regression `tests/cloud_controller` is 757 passed / 4 skipped
with the `prometheus` extra installed.

**CI evidence.** `.github/workflows/cloud-scaling-controller-phase3-ci.yml` runs the planning
suite, the Phase 1 + Phase 2 regression, the full package suite in isolation, the legacy
controller parity regression, and the advisory-boundary + side-effect gates.

## What is ratified

The Phase 3 scope exactly as the proposal states it: an additive, deterministic,
provider-neutral, shadow/advisory-only capacity-action recommendation layer built around the
Phase-2 forecast, producing a `CapacityActionRecommendation` or a typed
`RecommendationAbstention`, with hard constraints non-compensatory and cost an optimization
input.

**No code changed under this ratification.** The implementation was found conformant and is
ratified as it stands.

## What is not ratified, and stays not ratified

Ratifying the boundary ratifies nothing about quality. The proposal's own maturity labels
stand unchanged and are not weakened by this record:
`BASELINE_RECOMMENDATION_POLICY_IMPLEMENTED` · `PREDICTIVE_QUALITY_NOT_ESTABLISHED` ·
`ECONOMIC_OPTIMALITY_NOT_ESTABLISHED` · `PRODUCTION_EFFECTIVENESS_NOT_ESTABLISHED` ·
`NOT_AUTHORIZED_FOR_EXECUTION`.

A recommendation is descriptive capacity intelligence. It is not an authorization, a risk
evaluation, an ActionGate decision, or an execution instruction. Risk Authority (Phase 4),
ActionGate authorization and provider execution (Phase 5), and effect verification and
recommendation learning (Phase 6) remain out of scope and separately governed. Cost never
authorizes: a cheaper plan that violates a safety, quota or validity limit is eliminated
before scoring, and this record does not license any future change to that ordering.

Passing tests and CI prove implementation correctness, never recommendation quality. Nothing
here is a live-cluster validation or a production certification, and neither has been
performed.

## Process consequence

A capability that ships without a ratified ADR is a capability with no boundary to audit
against. The gap here was found by audit rather than by a gate, and this record closes the
instance, not the class.
