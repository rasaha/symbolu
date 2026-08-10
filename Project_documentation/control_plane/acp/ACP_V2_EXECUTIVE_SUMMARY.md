# ACP V2 — Executive Summary & Migration Recommendation

## The question

Is the Autonomous Control Plane (ACP) a genuinely reusable **cross-domain**
control architecture, or is it robotics-specific? We tested this by freezing ACP
V1 and building **one** non-robotics adapter — Kubernetes/cloud operations —
reusing the frozen core and driving it from the repository's **real**
`cloud_controller` logic, entirely in shadow mode.

## The answer (evidence-grounded)

**The ACP decision core generalizes cleanly; a horizontal-platform product claim
does not yet follow from one adapter.**

- The frozen ACP core ran **byte-for-byte unchanged** on cloud envelopes — the
  10-module core SHA-256 is identical before and after V2
  (`8f8660e293308cf94c983a26a2ae69c9`). **Zero core lines were edited.**
- The frozen `filter_admissible`, `LexicographicActionSelector`, `DecisionTrace`,
  and `ReferenceCommitRevalidator` all operate on cloud state/candidates through
  the same duck-typed contract (`.version` / `.identity` / `.candidate_id`).
- Cloud hard constraints are driven by the **real**
  `ReadinessChecker` / `PolicyEngine` / `SafetyBounds` — not reimplemented.
- The 19-scenario shadow benchmark met **19/19** preregistered expectations, with
  all 7 safety invariants passing, 100 % rerun-determinism, 0 dropped records, and
  sub-millisecond latency.

## The four verdicts

| dimension | verdict |
|---|---|
| Cross-domain architecture | **`ACP_GENERALIZES`** |
| Cloud adapter | **`CLOUD_ADAPTER_SUPPORTED_WITH_LIMITATIONS`** |
| ActionGate composition | **`BOUNDARY_CLEAN`** |
| Product direction | **`INSUFFICIENT_EVIDENCE`** (for a platform claim; core-reuse signal is positive) |

## Why ACP and ActionGate are both needed

They answer **different questions**, proven by two decisive cases:

- **ActionGate allows, ACP holds** — a scale ActionGate fully authorizes, but the
  real readiness checker blocks (a scaling action happened 30 s ago < the 120 s
  cooldown). Only ACP caught it. → `HELD_BY_ACP`.
- **ActionGate denies, ACP would allow** — an operationally-safe scale the gate
  denies. ACP's "safe" verdict did **not** override the denial. →
  `BLOCKED_BY_AUTHORIZATION`.

ActionGate asks *"is this authorized?"*; ACP asks *"is this operationally safe
against live cluster state now?"* An action must pass **both**.

## Migration recommendation

**Do not migrate anything to production, and do not declare a horizontal
platform, on this evidence.** ACP remains shadow-only and the current runtime
stays authoritative — in both robotics (V1) and cloud (V2).

Concretely:

1. **Keep the cloud adapter in shadow.** It is OFF by default, imports no
   Kubernetes client, mints no ActionGate token, and is not wired into any
   production path. Deletion is a clean rollback (nothing imports it).
2. **Before a platform claim, add a second structurally-different domain** (e.g.
   database migrations or CI/CD promotion gating) with **real** evidence — not
   authored fixtures. Two clean generalizations with real evidence would justify
   `PROCEED_HORIZONTAL_PLATFORM`; the first forced core change would bound the
   claim honestly.
3. **Integrate the real ActionGate end-to-end.** V2 composes against a *supplied*
   authorization verdict; a real gate→ACP integration test would harden the
   boundary result from `BOUNDARY_CLEAN` (design-proven) to operationally proven.
4. **Close the authored-evidence gap.** 6 of 10 cloud constraints are authored
   operational rules; back them with real cluster signals (or a real config
   source) before treating cloud numbers as anything beyond decision-grade.

## What this milestone did and did not change

- **Changed:** added an additive `cloud/` domain adapter (+ tests + benchmark +
  8 docs). Nothing else.
- **Unchanged:** the frozen ACP V1 core (hash-verified), every production path,
  the robotics baseline (112 ACP tests pass), the VC brief, and the shadow-only
  posture. No actuation, no fabricated telemetry, no production deployment.

## Artifacts

Docs: `ACP_V1_FREEZE`, `ACP_V2_CROSS_DOMAIN_PREREGISTRATION`,
`ACP_ACTIONGATE_BOUNDARY`, `ACP_CLOUD_DOMAIN_MODEL`, `ACP_CLOUD_CONSTRAINTS`,
`ACP_CLOUD_ADAPTER_DESIGN`, `ACP_CLOUD_SHADOW_METHOD`,
`ACP_CROSS_DOMAIN_REUSE_ANALYSIS`, `ACP_V2_RESULTS`, this summary. Code:
`symbolu_robotics/autonomous_control_plane/cloud/`. Corpus + harness:
`robotics_reliability_bench/acp_cloud/`. Machine-readable results:
`robotics_reliability_bench/results/acp_cloud_results.json`. Tests:
`tests/test_acp_cloud.py`.
