# ActionGate Consumer Map

Every occurrence of `import actiongate_provider` / `from actiongate_provider …`
and every consumer of the public `ActionGateProvider` /
`ActionGovernance*` / control-plane surface. Full data:
`actiongate_consumer_map.json`.

**Migration policy:** the initial migration **preserves all consumers unchanged
through the logic-free `actiongate_provider` compatibility facade.** No consumer is
mass-edited in this phase (this mirrors the merged TAP migration, PR #1297).

| Classification | Count | Consumers |
|---|---|---|
| `MONOREPO_COMPOSITION` | 5 | enterprise_validation_pilot (engines/root/manifest), comparative_governance_benchmark, provider_heterogeneity_validation |
| `KEEP_LEGACY_IMPORT` | 4 | ugence_console_api, products/code-governance adapter, **ai-hiring legacy adapter**, platform_freeze/invariants |
| `COMPATIBILITY_TEST` | 7 | enterprise pilot test, code-governance tests, platform_freeze test, TAP verifier, framework verifier, tap_provider boundary+e2e tests |
| `MIGRATE_TO_CANONICAL_NOW` | 0 | — |
| `EXTERNAL_CONSUMER_UNKNOWN` | 0 | — |
| `DEAD_CODE` | 0 | — |

**Total consumers: 16.** All continue to import `actiongate_provider…` and resolve —
through the facade — to the identical canonical objects (object identity preserved).

Notable:

- **AI Hiring** (`actiongate_legacy_adapter.py`) is `KEEP_LEGACY_IMPORT` and is
  explicitly **out of scope for modification** in this phase; it is only verified to
  still load against the compatibility distribution (Scenario G).
- The TAP verifier and `tap_provider` boundary tests import ActionGate solely to
  assert **peer independence** (ActionGate ↔ TAP never invoke each other). They are
  compatibility tests, not couplings.
