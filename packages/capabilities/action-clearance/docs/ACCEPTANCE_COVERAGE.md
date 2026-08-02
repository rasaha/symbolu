# Acceptance Coverage

> Machine-readable: `acceptance_coverage.json`. Harness:
> `tests/test_scenario_harness.py`.

The merged 25-row core scenario matrix
(`docs/design/action_clearance/acceptance_scenarios.json`) is classified and
executed:

| Classification | Scenarios | Count |
|---|---|---|
| `CORE_IMPLEMENTED` | 1–20 | 20 |
| `FUTURE_ADAPTER` | 21, 22 (GitHub profile) | 2 |
| `FUTURE_WORKFLOW` | 23, 25 (receipt lifecycle) | 2 |
| `FUTURE_EXECUTION_LEDGER` | 24 (concurrent-dispatch reservation) | 1 |

Every `CORE_IMPLEMENTED` scenario is executed and asserted. `FUTURE_*` scenarios
are skipped, never faked. Notes:

- **Scenario 2 (ActionGate denied):** the design labels it `no_evaluation` at the
  boundary; the neutral core fail-closes to `BLOCK` (`AUTHORIZATION_NOT_ELIGIBLE`).
- **Scenarios 21–22 (GitHub head-SHA / merge-group):** these are profile
  manifestations of action-identity change. The neutral core already `BLOCK`s on
  `ACTION_FINGERPRINT_MISMATCH`; the `GITHUB_*` reason codes are supplied by the
  (future) GitHub profile, not this package.

The prerequisites matrix
(`docs/design/action_clearance_prerequisites/acceptance_scenarios.json`) is
dominated by receipt-persistence, reservation, and dispatch scenarios classified
`FUTURE_WORKFLOW` / `FUTURE_EXECUTION_LEDGER`; its signal-provenance and freshness
rules are exercised by the core signal tests.
