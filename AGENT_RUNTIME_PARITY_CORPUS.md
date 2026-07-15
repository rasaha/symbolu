# Agent Runtime — Legacy-vs-New Parity Corpus (Deliverable 3)

16 labeled scenarios comparing the legacy runtime and the new runtime, driven by the SAME
deterministic model so the comparison isolates the runtimes, not the model. Grounded in
`agent_runtime_migration/parity/`.

Labels: `FACT`.

## Method
`FACT`. Each scenario carries a shared model plan (both legacy `type`/`parameters` and new
`tool`/`arguments` fields set identically). The runner drives the legacy `decompose_goal` and the
new `ModelPlanner` with the same `ReplayModel`, and compares decomposition length, tool sequence, and
arguments. Governed scenarios additionally run the NEW side through the AI Control Plane; the legacy
in-runtime governance is an **intentional difference** and is not executed (it violates the new
ownership boundary — §4 "do not require parity where the legacy behavior violates the boundary").

## Scenarios & labels
| # | Scenario | Label | New-side governance |
|---|---|---|---|
| 1 | read_only_research | PARITY | — |
| 2 | multi_step_info_gathering | PARITY | — |
| 3 | structured_extraction | PARITY | — |
| 4 | file_analysis | PARITY | — |
| 5 | local_deterministic_transformation | PARITY | — |
| 6 | kubernetes_scale_proposal | INTENTIONAL_DIFFERENCE | PROCEED |
| 7 | kubernetes_rollout_proposal | INTENTIONAL_DIFFERENCE | PROCEED |
| 8 | database_mutation_proposal | INTENTIONAL_DIFFERENCE | PROCEED |
| 9 | authorization_denial | INTENTIONAL_DIFFERENCE | BLOCKED_BY_AUTHORIZATION |
| 10 | acp_operational_hold | INTENTIONAL_DIFFERENCE | HELD_BY_ACP |
| 11 | more_evidence_request | INTENTIONAL_DIFFERENCE | PENDING_AUTHORIZATION |
| 12 | human_escalation | INTENTIONAL_DIFFERENCE | HELD_BY_ACP |
| 13 | execution_failure | INTENTIONAL_DIFFERENCE | — (local failure) |
| 14 | retry | INTENTIONAL_DIFFERENCE | — |
| 15 | cancellation | PARITY | — |
| 16 | observation_reflection_replan | INTENTIONAL_DIFFERENCE | BLOCKED_BY_AUTHORIZATION |

**Intentional differences** (not regressions): legacy governs in-runtime (SafeMCPGateway/SafetyGate);
the new runtime delegates authorization + operational safety to the AI Control Plane. Legacy has no
governed CER-profile concept; the new runtime routes governed actions through CER.

## Result (`parity/results.json`)
`FACT`. Decomposition agreement: **16/16** plan, **16/16** tool sequence, **16/16** arguments (both
runtimes decompose the shared model identically). Parity scenarios met: **6/6**. Governed new-side
outcomes correct vs preregistered: **8/8**. Intentional differences: **10**. **Unexplained
regressions: 0.**

## Interpretation
`INTERPRETATION`. Where the model output is shared, the new runtime reproduces the legacy runtime's
decomposition, tool selection, and arguments exactly; the only differences are the intended
governance-ownership differences. This supports `LEGACY_PARITY_SUPPORTED` at the
decomposition/tool/argument level, with governance execution intentionally different by design.
