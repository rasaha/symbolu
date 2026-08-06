# Hybrid LLM V1.1 — capability evidence-status matrix

Companion to `HYBRID_LLM_ENTERPRISE_RELATIONAL_REASONING_V1_1.md`. Status is grounded in merged repository
evidence (PRs #1344–#1361). "Authorized now" is **Yes** only for the operational foundation already
implemented/tested; **every future research item is No** and requires its own preregistration + explicit
authorization.

| Capability | Current status | Strongest supporting evidence | Interpretation boundary | Next research required | Authorized now |
|---|---|---|---|---|---|
| Deterministic authorized retrieval | Operational foundation | External-table reliability program (#1346/#1349); database is authoritative | Tested reference conditions, not production infra | Enterprise-schema robustness (unauth.) | Yes |
| External-table exact-fact reliability | Supported (tested reference) | Table-only exact; always-verify exact (#1346/#1349) | No production-reliability claim; latency not generalized | Real-infra measurement (unauth.) | Yes |
| Anonymous BindingSlots routing | **Unresolved** | `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`; A1/G1 not selected (#1344/#1345) | Values storable; read-routing unreliable | New mechanism only (unauth.) | No |
| Explicit-key semantic addressing | Controlled-task confirmed | `EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED`, `E1_INDEPENDENTLY_CONFIRMED` (#1351/#1352) | Synthetic tasks, ~32 memories; not enterprise transfer | Enterprise/real-model transfer (unauth.) | No |
| No-match behavior | Partially supported | Bounded no-match on controlled tasks (#1352/#1354) | Controlled synthetic only | Enterprise no-match stress (unauth.) | No |
| Temporal position-specific retrieval | Supported (controlled synthetic) | `E1_TEMPORAL_TRANSFER_PARTIAL` supported splits (#1354) | Synthetic; not natural-language temporal | NL temporal transfer (unauth.) | No |
| Latest-state inference | **Not supported** (below gate) | `E1_TEMPORAL_TRANSFER_PARTIAL`, `T4_SHORTFALL_MIXED`, `T4_FACTORIAL_NO_INTERVENTION_SELECTED`, `FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND` (#1354–#1360) | C1 & bounded-readout tracks closed; not all architectures ruled out | New temporal architecture (unauth.) | No |
| Predecessor/successor reasoning | **Not supported** | T5 weak / diagnostic-only (#1354) | Unresolved, outside closures | New architecture (unauth.) | No |
| Multi-hop enterprise reasoning | **Not supported** | Not established by E1 experiments | No enterprise relational evidence | Relational benchmark (unauth.) | No |
| Evidence grounding | **Not established** (design hypothesis) | Architectural requirement only | No empirical claim yet | Claim-to-record alignment study (unauth.) | No |
| Tenant isolation | **Not established** (design control) | Authorization-before-model design | No adversarial evidence yet | Cross-tenant stress testing (unauth.) | No |
| Bounded quadratic reader | **Not established** (optional) | None; treated as optional | Must prove incremental value or be omitted | Reader ablation (unauth.) | No |
| Real-model quality preservation | **Not established** | All work synthetic probes; H5 open | No real-pretrained-model evidence | Quality-retention study (unauth.) | No |
| Efficiency advantage | **Not established** | Reference: neural+table slower than table-only (#1349) | Neural must justify via reasoning, not lookup | Real-model cost/latency study (unauth.) | No |
| Production readiness | **Not supported** | — | Research hypothesis under validation | Full validation ladder (unauth.) | No |
| KDA validation | **Blocked** | `KDA_VALIDATION_BLOCKED` (persistent invariant) | Remains blocked; nothing here unblocks it | N/A while blocked | No |

**Invariants preserved:** `E1_TEMPORAL_TRANSFER_PARTIAL` · `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`
· `KDA_VALIDATION_BLOCKED`. No `E1_TEMPORAL_TRANSFER_VALIDATED`, `E1_STRUCTURAL_TRANSFER_CONFIRMED`,
`E1_FOLLOW_ON_RESEARCH_ELIGIBLE`, or `KDA_VALIDATION_ELIGIBLE` is emitted; no production-readiness claim.
