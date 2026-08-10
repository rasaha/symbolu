# Scenario Inventory (P3B)

Four frozen v1 demo scenarios (P3A `demo_data` + `expected_outputs`) and four v2
conformance bundles (AWC P2.1 `governance_studio_v2`). All bundled read-only into
the API distribution as package data; a drift test asserts byte-identity with the
P3A/AWC sources so no fixture is duplicated-and-mutated.

| Scenario | Domain | Expected plan state | v1/v2 equivalence |
|----------|--------|---------------------|-------------------|
| procurement | procurement | COMPLETE | SEMANTICALLY_EQUIVALENT |
| customer_support | customer_support | COMPLETE | SEMANTICALLY_EQUIVALENT |
| cybersecurity_success | cybersecurity | COMPLETE | SEMANTICALLY_EQUIVALENT |
| cybersecurity_no_feasible_team | cybersecurity | NO_FEASIBLE_TEAM | SEMANTICALLY_EQUIVALENT |

Logical time (pinned input): `1_000_000.0`. AWC 0.2.1 reproduces every frozen
fingerprint (verified on every scenario execution endpoint).
