# ACP Maturity Assessment

## Overall classification: **SHADOW_ONLY** (with a PARTIAL_PROTOTYPE governance reading)

Machine-readable companion: `acp_maturity_matrix.json`.

The frozen robotics core is *code-quality* production-shaped, but the **capability** — as an operational,
production, cross-domain governance product — is **shadow-only**. Passing synthetic tests does not establish
production readiness.

## Evidence-weighted scoring

| Evidence axis | Finding | Weight |
|---|---|---|
| Consumers | 3 product subsystems (`cer_v0_*`) deep-import; console reimplements separately | Real but narrow |
| Tests | 112 ACP tests pass; **synthetic/authored fixtures**; real safety/cloud modules exercised offline | Medium |
| Real integrations | real `TrajectoryValidator`, real `TaskPlanner`, real `cloud_controller` — but **no live cluster, no live sensors** | Medium-low |
| Persistence | in-memory/bounded only; no durable clearance store, no consumption ledger | Low |
| External signals | trusted-signal evaluation only; no incident/identity/credential wiring | Low |
| Operational use | **none in production**; "no production enforcement recommended" | None |
| Failure handling | **fail-closed pervasive** (missing input → HARD fail / raise) | High |
| Replay evidence | 100% deterministic rerun; frozen replays | High |
| Packaging discipline | not a package; consumers deep-import the unfrozen `.cloud.*` surface | Low |

## Explicit maturity ceilings in the docs

- `Project_documentation/control_plane/acp/ACP_EXECUTIVE_SUMMARY.md:3-4` — "Design-first; documentation only; no production code modified."
- `Project_documentation/control_plane/acp/ACP_PHASE1_RESULTS.md:7` — "Shadow-only. Production BCVF remained authoritative. Zero production
  edits." (later phases walked the gated-canary aspiration back to `SHADOW_CONTINUE`.)
- `Project_documentation/control_plane/acp/ACP_LIVE_PATH_AUDIT.md:41-44` — the single live robotics path runs on a **stub** planner emitting a
  fixed velocity; verdict `LIVE_TRAJECTORY_INTEGRATION_LIMITED`.
- `Project_documentation/control_plane/acp/ACP_V2_1_RESULTS.md:117-118` — "PLATFORM_CLAIM_PREMATURE remains the honest ceiling… no production
  enforcement is recommended."
- Console: `capabilities/registry.py:65` labels the Clear stage "Implemented (shadow-mode) · Internally
  Validated"; the governed loop defaults to `DeploymentMode.SHADOW`.

## Scale position

```
PRODUCTION_SHAPED   : NO  (code-shape yes; capability no)
IMPLEMENTED         : NO
PARTIAL_PROTOTYPE   : YES
SHADOW_ONLY         : YES  <= overall
SIMULATED           : YES  (authored fixtures / no live cluster)
DOCUMENTED_ONLY     : NO   (real code exists)
PLANNED             : NO
MISSING             : NO
```

## Control-implementation summary (detail in `acp_maturity_matrix.json`)

- **IMPLEMENTED:** authorization freshness / temporal expiry, action-fingerprint consistency, policy/state
  version validity, environment readiness, target availability, blast-radius/rate limits, required
  checks/rollback, operational-risk hard filter.
- **PARTIAL:** change-freeze/maintenance windows (flag only; robotics `MAINTENANCE` mode ungated).
- **SHADOW_ONLY:** predictor-reliability (BCVF advisory, never authoritative).
- **MISSING:** actor identity, credential validity, incidents, replay/prior-consumption, duplicate dispatch.

## Bottom line

A genuinely well-engineered, frozen, deterministic robotics clearance core exists, but the capability is
**shadow-only, robotics/cloud-domain-shaped, and missing the identity/credential/incident/replay controls a
production governance clearance product requires.** It is not production-mature and must not be presented as
such.
