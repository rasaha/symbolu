# COMPETING_AUTHORITY_ANALYSIS — Governance Semantics Experiment v0.1

3 hidden cases contain two or more competing
governance sources — the scenario the v0.3 diagnostic flagged as the bottleneck.
Opaque case identifiers are used; hidden contents are not reproduced.

## Table 8 — competing-authority cases (G4)

| case | governance sources | operative | abstained | G0 → G4 | gold abstain |
|---|---|---|---|---|---|
| HX59d7a3eb1c | Order Form §2 (effective 2020) p.1; Policy P-8 (effective 2024) p.1 | Policy P-8 (effective 2024) p.1 | False | changed | False |
| HXb3def36e76 | Corporate Policy G-2 p.2; Regulatory Directive R-9 p.1 | Corporate Policy G-2 p.2 | False | same | False |
| HPb167985bd5 | MSA §2 p.2; Order Form §1 p.1 |  | True | changed | True |

In these cases the operative-source layer separates the authority-establishing node
from the answer-bearing node. Under **G3** (operative selection, no abstention) all
five decisions that change are **fixes** (COMPETING fixes span `policy_migration`,
`parallel_overrides`, `hierarchical_governance`, `multiple_authorities`,
`scoped_exceptions`) — including the exact `parallel_overrides` case that Edge
Prioritization v0.3 broke. Reading the operative term from the prohibition-bearing
clause rather than the highest-authority clause is what fixes them.

Under **G4** the abstention rule additionally abstains whenever a prohibition and a
permission co-occur in the governing set, which over-fires and is the source of the
coverage collapse.
