# ACP Implementation Candidates

Every physical implementation that performs (or reuses) action-clearance logic, classified. Machine-readable
companion: `acp_candidate_matrix.json`. Classification vocabulary per the audit request.

| # | Candidate | Path | Class | Real product consumers | Frozen | Notes |
|---|---|---|---|---|---|---|
| 1 | Robotics ACP reusable core | `symbolu_robotics/autonomous_control_plane/` (10 modules) | **PRODUCT_CORE_CANDIDATE** | cer_v0_1/2/3 | **Yes** | Coherent, deterministic, stdlib-only, well-tested. Strongest candidate. |
| 2 | Cloud domain adapter | `…/autonomous_control_plane/cloud/` | **PRODUCTION_SHAPED** | cer_v0_1/2/3, acp_db | No | The surface consumers actually deep-import; K8s-domain-shaped. |
| 3 | Robotics safety adapters | `…/safety_adapters/` | **SHADOW_IMPLEMENTATION** | — | No | numpy + real trajectory validator; explicitly not core. |
| 4 | Console digital clearance | `ugence_console_api/…/operational_safety.py` + `ClearanceVerdict` | **PILOT_IMPLEMENTATION** | console governed loop | No | Live product code; clearest match to the audit definition; 63 lines, hard-coded k8s thresholds; separate reimpl. |
| 5 | ACP DB adapter | `cer_v0_3/acp_db/` | **PRODUCTION_SHAPED** | cer_v0_3 | No (reuses frozen `compose`) | Clean product-over-core reuse; adds duplicated freshness/freeze checks. |
| 6 | Reliability benches | `robotics_reliability_bench/acp_*` (6 dirs) | **SHADOW_IMPLEMENTATION** | — | No | Read-only shadow/benchmark harnesses. |
| 7 | Decision Authority control plane | `decision_governance/actions/control_plane.py` | **UNRELATED_ACP** (governance-chain seam) | governance chain | via DA package | Owns the `EXPIRED`/freshness check for the governance chain; Decision-Authority owned, not the robotics core. |
| 8 | GPF reference action provider | `packages/governance-provider-framework/.../reference/action.py` | **COMPATIBILITY_SURFACE** | conformance | via GPF | Honors `authorization_expired -> EXPIRED`; a reference impl, not a product core. |
| 9 | Governance-contracts seam | `packages/governance-contracts/.../contracts/action.py` | **DOCUMENTATION_ONLY** (vocabulary) | all action providers | frozen | Carries the vocabulary (`EXPIRED`, `authorization_expired`, `expiry`); no logic. |

Explicitly classified **UNRELATED_ACP** (recorded to prevent conflation): `execution_gate*` and
`control_plane*` (Model Selection / AI-governance eval), `bounded_shadow_pilot` (cyber ActionGate pilot).
There is no `EXPERIMENT`/`SIMULATOR`-only ACP-clearance candidate beyond the benches; no `STALE` or pure
`DEMO_ONLY` clearance implementation was found (the console clearance is wired into the live governed loop).

## Why not select on directory name or recency

- The most **recent** clearance-shaped code is `cer_v0_3/acp_db` — but it is a *domain adapter that reuses*
  the core, not the core.
- The most **obviously named** directory is `execution_gate/` — but "gate" there is *Model Selection
  eligibility*, entirely UNRELATED.
- The **console** clearance is the closest to the audit's definition and is live product code — but it
  shares no code with the robotics core and is target-specific.

Selection therefore proceeds on the ten criteria (consumers, production-shaped API, determinism, stable
contract, tests, dependency direction, freeze/replay evidence, identity/lifecycle, separation from
ActionGate/execution, cross-product compatibility) in `CANONICAL_SOURCE_DECISION.md`.
