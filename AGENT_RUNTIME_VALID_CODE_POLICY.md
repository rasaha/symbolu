# Agent Runtime — Valid-Code Policy (Deliverable 4)

The standard every module in `agent_runtime_migration/` meets. Code that fails any clause does not
enter the package (or is marked non-exported).

Labels: `FACT` (enforced/verified).

## Admission standard (all required)
| # | Requirement | How it is met / checked |
|---|---|---|
| 1 | Clear ownership | one responsibility per module (see `AGENT_RUNTIME_MIGRATION_ARCHITECTURE.md §3`) |
| 2 | No hidden governance authority | forbidden-import test + governed executor is the only execution seam; runtime returns no allow/deny |
| 3 | Deterministic where claimed | no wall clock / randomness in the loop; caller supplies `now`; benchmark reruns byte-stable |
| 4 | Explicit failure behavior | typed error taxonomy (`contracts/errors.py`); fail closed on invalid CER / unknown tool / risk mismatch |
| 5 | Typed inputs and outputs | dataclasses/enums for Goal/Plan/Action/Observation/ExecutionResult/GovernanceDecision |
| 6 | No silent fallback to unsafe execution | governed tool runs only on a control-plane execution reference; no placeholder execution branches |
| 7 | Tested | 39 migration tests (contracts, CER, boundary, loop, tools, workflow, compat, forbidden-import) |
| 8 | Documented | module docstrings + the deliverable docs |
| 9 | Imported only through intended boundaries | package `__init__` exports validated modules; `_paths` bootstrap is import-only for the frozen CER |
| 10 | No dependency on research-only modules | AST forbidden-import test (no CG/JEPA/vritti/sovereign/signal_adapters) |
| 11 | No circular dependency with ActionGate/ACP | the runtime imports the frozen control plane one-way; the control plane does not import the runtime |
| 12 | No direct tool-execution bypass in governed mode | the loop holds only the executor; governed tools are reachable only via `GovernedExecutor` on eligibility |

## Placeholder / non-production marking
`FACT`. There are no placeholders exported from the public API. Optional or future-facing hooks
(e.g. LLM-driven planning) are behind interfaces (`Planner` accepts a decomposer; the default is
deterministic) — not exported as finished features. Nothing in the package is marked
`EXPERIMENTAL`/`NOT_FOR_PRODUCTION` because nothing incomplete is exported; such items would be kept
out of `__init__.__all__`.

## What is explicitly excluded (per the inventory)
`FACT`. Authoritative governance (SafeMCPGateway, SafetyGate, ConfidenceGate, GovernanceService,
approvals, policy enforcement, replay) and research-only signal governance (CG/JEPA/vritti/
sovereign/entropy) are **not** in the package. The forbidden-import test fails the build if any of
them is imported.

## Determinism & side effects
`FACT`. The runtime performs no consequential actuation itself: governed tools run only through the
control plane; local tools are policy-permitted read-only. The control plane is shadow-only in this
environment (nothing actuates a real cluster/database).
