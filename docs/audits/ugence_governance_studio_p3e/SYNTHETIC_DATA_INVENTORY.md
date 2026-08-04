# Synthetic Data Inventory (P3E)

`data_classification = SYNTHETIC_DEMONSTRATION_ONLY` · `source_contract = governance_studio.api.v1`

| Scenario | Fixture hash (prefix) |
|----------|----------------------|
| customer_support | `sha256:9cfb966615d0c244b97…` |
| cybersecurity_no_feasible_team | `sha256:3eebff71ccc6aaaaeee…` |
| cybersecurity_success | `sha256:36852b764e2c8bc513d…` |
| procurement | `sha256:1df40604557e980aeb3…` |

Aggregate bundle hash: `sha256:c0e5ac73048824f07543f38f67a445cd289ff481f26505c3446bc7609e4dfcdc`

## Enforcement (fail closed → `SYNTHETIC_DATA_BOUNDARY_FAILED`)

Startup verifies: every packaged scenario is in the manifest and vice-versa; each
fixture hash matches; the aggregate bundle hash matches; the classification equals
`SYNTHETIC_DEMONSTRATION_ONLY`; and no `UGS_API_SCENARIO_ROOT` override points away
from the pinned root. There is no filesystem-path, URL, upload, environment-variable,
or remote-fetch vector to add or redirect scenarios. Covered by
`tests/test_synthetic_boundary.py` and `tests/test_startup_integrity.py`.
