# ACP Determinism & Before/After Equivalence

## Determinism findings

The ACP discipline is **strongly deterministic** in its core:

- **No nondeterminism in the frozen core.** No `time.time()`, `datetime.now()`, `random`, `uuid`, or network
  anywhere in the 10 core modules. All times are **injected floats** (`issued_time_s`, `now_s`,
  `observation_time_s`, `freshness_s`).
- The only clock use is `time.perf_counter()` in `safety_adapters/shadow_planner_hook.py` — **latency
  telemetry only**, explicitly excluded from every deterministic content dict (`:59-76`).
- Determinism is asserted by tests and benches: `deterministic_rerun_identity_pct == 100.0` across
  `test_acp_phase1/2/3`, `test_acp_cloud`, and the `robotics_reliability_bench/acp_*` harnesses.
- Domain adapters (`cloud`, `safety_adapters`, `acp_db`) run on **authored fixtures** with fixed clocks
  (`NOW_S`, `NOW="2026-07-12…"`); no live cluster, no live sensors, no `np.random` (phase-3 uses a seeded
  RNG only).

Determinism inputs and dependencies:

| Kind | Present? | Where |
|---|---|---|
| Fixed test fixtures | Yes | `tests/*`, bench corpora |
| Scenario harnesses | Yes | `robotics_reliability_bench/acp_*`, `acp/` phase corpora |
| Replay data | Yes | `acp/` results are frozen replays; benches self-check rerun identity |
| Expected results / fingerprints | Yes | SHA-256 content identities; frozen digests |
| Policy fixtures | Yes | `ThresholdConstraint` sets, `CloudConstraintConfig` |
| Clock dependency | Injected only | `*_time_s` floats; `perf_counter` (telemetry, excluded) |
| Random dependency | Seeded only | phase-3 `np.random.seed(sc.seed)` |
| Network dependency | **None** | no sockets/HTTP |
| External-system dependency | Read-only adapters | real `cloud_controller` / trajectory validator, deterministic |

## Console clearance (concept #3)

`operational_safety.clear()` is a pure function of `OperationalSignals` with fixed thresholds — fully
deterministic, no clock/random/network.

## Proposed before/after equivalence harness (schema only — not built here)

If the project ever migrates, a semantic-equivalence harness (mirroring `scripts/
model_selection_equivalence_capture.py` and `scripts/gpf_equivalence_capture.py`) should record, per
scenario, a JSON row:

```json
{
  "scenario_id": "…",
  "input_request": { "world_state": "…", "candidates": ["…"], "constraints": {"…": ["…"]} },
  "trusted_current_state_signals": { "readiness": "…", "freeze_active": false, "resource_version": "…" },
  "status": "EXECUTE | NO_SAFE_ACTION | HOLD | PROCEED | BLOCKED_BY_AUTHORIZATION | …",
  "reason_codes": ["…"],
  "obligations": ["…"],
  "escalation": "SAFE_STOP | ESCALATE_TO_HUMAN | null",
  "expiration_behavior": { "expiry_time_s": 0.0, "stale_at": 0.0 },
  "exception": "StaleAuthorizationError | AuthorizationBindingError | null",
  "serialized_result": "…",
  "fingerprint": "sha256…"
}
```

Captured across **all current implementations** (robotics core, cloud adapter, acp_db, console clearance) to
prove a consolidated core reproduces each. This document defines the schema only; the harness is **not**
created in this audit.

## Byte-identical vs semantic equivalence

**Byte-identical migration is NOT feasible** for a *governance* ACP, for two reasons:

1. Converting internal absolute imports to relative imports changes module content and breaks the ACP V1
   per-module SHA-256 freeze digest (`FREEZE_IMPLICATIONS.md`).
2. A governance ACP requires **neutralizing** the robotics-domain envelopes (`CanonicalWorldState`,
   `CanonicalActionCandidate` are robotics-shaped) and **curating** a public surface (consumers currently
   deep-import `.cloud.*`), which is a semantic reshaping, not a verbatim move.

Therefore **semantic equivalence** (identical status + reason codes + obligations + escalation + expiry +
exception behavior + fingerprints, per the schema above) is the appropriate standard — as it was for the
GPF and Decision-Authority migrations. Byte-identical replay can still be preserved *within* a single
domain adapter (e.g. `cloud/`) if that adapter is moved verbatim, but not for the neutral kernel.
