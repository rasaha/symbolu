# Agent Runtime — Real-Model Corpus (Deliverable 3)

The frozen real-model evaluation subset (14 scenarios) drawn from the Phase-2 corpus. Grounded in
`agent_runtime_migration/benchmark/real_model_corpus.py`.

Labels: `FACT`.

## Classification (§5)
`FACT`. Each scenario is `EXACT_PARITY` / `SEMANTIC_PARITY` / `INTENTIONAL_DIFFERENCE` / `UNSUPPORTED`.
Exact wording is NOT required from a probabilistic model — tool/argument correctness uses semantic
parity.

| # | Scenario | Class | Governed | Expected outcome |
|---|---|---|---|---|
| 1 | read_only_research | SEMANTIC_PARITY | — | — |
| 2 | structured_extraction | SEMANTIC_PARITY | — | — |
| 3 | multi_step_retrieval | SEMANTIC_PARITY | — | — |
| 4 | local_deterministic_transformation | EXACT_PARITY | — | — |
| 5 | kubernetes_scale_proposal | INTENTIONAL_DIFFERENCE | yes | PROCEED |
| 6 | kubernetes_rollout_proposal | INTENTIONAL_DIFFERENCE | yes | PROCEED |
| 7 | database_mutation_proposal | INTENTIONAL_DIFFERENCE | yes | PROCEED |
| 8 | authorization_denial | INTENTIONAL_DIFFERENCE | yes | BLOCKED_BY_AUTHORIZATION |
| 9 | acp_operational_hold | INTENTIONAL_DIFFERENCE | yes | HELD_BY_ACP |
| 10 | request_more_evidence | INTENTIONAL_DIFFERENCE | yes | PENDING_AUTHORIZATION |
| 11 | execution_failure | INTENTIONAL_DIFFERENCE | — | — |
| 12 | observation_reflection_replan | INTENTIONAL_DIFFERENCE | yes | BLOCKED_BY_AUTHORIZATION |
| 13 | cancellation | SEMANTIC_PARITY | — | — |
| 14 | budget_exhaustion | SEMANTIC_PARITY | — | — |

## Use
`FACT`. The evaluation runner (`benchmark/real_model_eval.py`) drives the real model over this corpus
via the frozen planning template, parses fail-closed, builds CERs for governed scenarios, and runs the
AI Control Plane — recording proposal-quality and governance-containment metrics. With no model
configured it returns `BLOCKED_NO_REAL_MODEL` (it never fabricates model output).

## Status (this environment)
`FACT`. **Not executed** — no real model is available (`BLOCKED_NO_REAL_MODEL`). The corpus, runner,
and adapter are frozen and ready; the evaluation runs unchanged the moment a live/local model exists.
