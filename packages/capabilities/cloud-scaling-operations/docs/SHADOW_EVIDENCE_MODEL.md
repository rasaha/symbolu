# Shadow Evidence Model

Every artifact is stamped `evidence_class: FAKE_LOCAL_FIXTURE`,
`real_environment_observed: false`, `real_cluster_accessed: false` and written to
`artifacts/shadow_harness_fixture/`. The path `artifacts/shadow_validation/` is
**reserved** for a future genuine real-environment run and is not used in this phase.

JSON Schemas live in `shadow_validation/schemas/` (11 schemas). Fixture artifacts:

| Artifact | Content |
|----------|---------|
| `fixture_environment_manifest.json` | config summary (no credentials) |
| `fixture_target_allowlist.json` | approved + rejected targets with reasons |
| `fixture_session_manifest.json` | session + package versions + hashes |
| `fixture_observation_records.jsonl` | scaling-relevant observed fields only |
| `fixture_shadow_decisions.jsonl` | proposed-only decisions |
| `fixture_authorization_validation.json` | 20 synthetic scenarios |
| `fixture_stale_state_results.json` | all staleness classifications |
| `fixture_hpa_interaction_results.json` | all HPA classifications |
| `fixture_request_method_ledger.jsonl` | every attempted method (redacted) |
| `fixture_mutation_canary_results.json` | per-entrypoint canary results |
| `fixture_network_failure_results.json` | contained read-only failures |
| `fixture_secret_redaction_report.json` | redaction checks |
| `fixture_shadow_harness_integrity_report.json` | embedded integrity checks |
| `fixture_aggregate_shadow_report.json` | verdict + per-artifact hashes |

Generation is deterministic (fixed clock, sorted keys). The verifier regenerates the
deterministic subset and compares hashes byte-for-byte. Secrets are never recorded; a
scan asserts no committed artifact contains secret material.
