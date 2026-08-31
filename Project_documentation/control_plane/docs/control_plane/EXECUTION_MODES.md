# Execution Modes

*Phase 11. Five explicit modes. Default is **MOCK**. ENFORCEMENT is the only mode with
real external calls and real action execution and requires explicit configuration; it is
**disabled in this environment** (task constraint: no live provider calls, no real actions).
Source of truth: `control_plane/modes.py` (`MODE_TABLE`).*

| Property | REPLAY | MOCK (default) | SHADOW | ADVISORY | ENFORCEMENT |
|---|---|---|---|---|---|
| Authoritative decision maker | historical record | mock components | existing production path | human consumer | control plane |
| External provider calls | no | no | no | no | **yes** |
| Real customer data | no | no | no | no | **yes** |
| Actions execute | no | no | no | no | **yes** |
| Audit required | yes | yes | yes | yes | yes |
| Fallback behavior | as-recorded | mock re-evaluation | defer to production | human decision | re-enter eligibility+policy (inv 19) |
| Override behavior | none (read-only) | simulated | none | human | explicit, attributable, audited (inv 8) |
| Spend controls | zero | zero | zero incremental | zero action spend | hard cost/latency budgets |
| Allowed component substitutes | recorded values | deterministic mocks | mocks + real reads | mocks | real adapters |
| Promotion criteria | n/a | scenarios pass | recommendation quality vs prod | human trust established | explicit config + green shadow/advisory |

## Semantics

- **REPLAY** — re-runs a recorded trace under its *pinned historical* policy + registry
  versions (invariant 13); emits nothing. Used to prove determinism and to investigate a
  past decision. `control_plane/replay.py`.
- **MOCK** — default. Provider/TAP/ActionGate/ActionAdapter/Telemetry are deterministic
  provider-neutral mocks. The scenario suite (Phase 9) and the integration evaluation
  (Phase 15) run here. Zero spend, zero external effect.
- **SHADOW** — computes a recommendation next to the real authoritative route and records
  agreement/divergence, without taking control or acting. `control_plane/shadow.py`.
- **ADVISORY** — emits decisions/recommendations for a human to act on; the plane executes
  nothing. Human is authoritative.
- **ENFORCEMENT** — the sole mode where `ProviderAdapter` may make a real call and
  `ActionAdapter` may execute a real action. Requires explicit configuration. Audit-write
  success **gates** execution (invariant 15). Fallback re-enters eligibility+policy
  (invariant 19). **Not enabled here.**

## Guarantees that hold across all modes

- Fail-closed governance: unknown critical state never becomes approval (invariant 9).
- Version pins immutable per trace (invariant 10).
- Append-only audit; telemetry never rewrites a prior decision (invariants 11, 12).
- The default can never silently escalate to ENFORCEMENT: `DEFAULT_MODE = "MOCK"` and
  `may_execute_actions()` / `may_call_provider()` return False for every non-ENFORCEMENT
  mode, so an action adapter invoked outside ENFORCEMENT returns `SIMULATED`, never `EXECUTED`.
