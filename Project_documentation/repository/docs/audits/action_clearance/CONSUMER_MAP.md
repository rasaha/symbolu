# ACP Consumer Map

Machine-readable companion: `acp_consumer_map.json`. Two separate "clearance" capabilities exist and are
**not connected**: the robotics core (concept #1, with real cross-package consumers) and the console
digital clearance (concept #3, self-contained).

## Real product consumers of the robotics core — 3 subsystems / 13 files

| Consumer | Files | Import style | Relies on |
|---|---|---|---|
| `cer_v0_1` | `control_plane.py:28-29`, `spec.py:167,195,219`, `conformance/runner.py:182-183`, `_paths.py:6` | deep `…cloud.adapter`/`.composition`/`.envelopes` | `CloudShadowAdapter`, `AuthorizationVerdict`, `CloudWorldState` schema, enum `.value` |
| `cer_v0_2` | `control_plane.py:24-25`, `conformance/runner.py:188`, `profiles/{rollout,scale,_common}.py` | deep `…cloud.*` | same as above |
| `cer_v0_3` | `control_plane.py:30`, `acp_db/adapter.py:20,23`, `acp_db/safety.py:30`, `conformance/cross_domain.py:228` | deep `…cloud.composition`/`.outcomes` | `compose`, `CombinedOutcome`, `CompositionResult`, `CloudRecommendation` |

All product consumers **deep-import `.cloud.*`** (and `.safety_adapters.*`), i.e. they bypass the frozen
top-level `__init__` `__all__`, which does not re-export `cloud`. The de-facto contract is the cloud
subpackage's types and enum `.value` serialization — **not** the advertised frozen interface.

## Shadow / benchmark consumers — 8 files

`robotics_reliability_bench/acp_cloud`, `acp_k8s_integrated`, `acp_shadow`, `acp_shadow2`, `acp_shadow3` —
read-only shadow/benchmark harnesses; not runtime product. Behavior relied upon: `acp_evaluate`, `classify`,
`ReferenceControlAuthorizer/CommitRevalidator`, `CloudShadowAdapter`, `compose`.

## Test / boundary consumers — 6 files

Positive: `cer_v0_{1,2,3}/tests/*`, `acp_control_plane/test_control_plane.py`,
`acp_k8s_integrated/test_integrated.py`. Negative guard: `packages/capabilities/storygraph/tests/
compatibility/test_dependencies.py:25` asserts storygraph does **not** import `acp` /
`autonomous_control_plane` / `symbolu_robotics`.

## Console digital clearance (concept #3) — 0 imports of the robotics core

`ugence_console_api` references the string `"autonomous_control_plane"` only as a display label / registry
key (`registry.py:63`, `orchestrator.py:103`, `app.py:67`). `ClearanceVerdict` is defined and consumed only
inside `ugence_console_api`:

- `orchestrator.py:98-105` — the governed-loop **Clear** stage calls `operational_safety.clear(...)`.
- `app.py` — `POST /v1/actions/clear`.

## Governance-chain clearance seam — owned elsewhere

The `EXPIRED`/freshness seam for the governance chain is owned by Decision Authority + the provider
framework, **not** the robotics core:
`decision_governance/actions/control_plane.py`, `…/reference/action.py`, `…/adapters/
action_to_control_plane.py`.

## Consumers named in the request, mapped to reality

| Named consumer | Present? |
|---|---|
| ActionGate | Composes with ACP (opaque verdict); does not import it |
| Control plane | Console governed loop (concept #3) consumes clearance; `control_plane/` is Model Selection (UNRELATED) |
| Agent runtime | No ACP import found |
| Workflow engine | The console orchestrator + `compose()` play this role; no separate engine imports ACP |
| External execution providers | None import ACP (ACP never executes) |
| Shadow harnesses | `robotics_reliability_bench/acp_*` (8 files) |
| Code Governance designs/prototypes | No code import; CG is design-stage docs |
| Deployment governance | via cloud adapter (`cloud_controller`) — not a direct importer |
| Financial/trading governance | `trading/`, `trading2/` do not import ACP |
| Hiring/decision products | `ai_hiring/` does not import ACP |
| Tests & demos | 6 test/boundary files |

**Count:** real (non-test, non-shadow) product consumers of the robotics core = **3 subsystems / 13 files**;
shadow = 8; test = 6; console-clearance internal = its own loop; robotics core imports by console = **0**.
