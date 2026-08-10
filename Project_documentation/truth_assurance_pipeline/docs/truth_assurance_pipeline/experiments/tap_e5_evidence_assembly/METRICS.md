# TAP-E5 — Metrics

Every metric is reported **separately**, and the twelve critical-failure classes are counted
**independently** of the pass/fail metrics — a high average can never hide a packet defect.

## Metrics

| Metric | Definition |
|---|---|
| `packet_completeness` | fraction of required (evidence+relationship+governance+conflict+gap) objects present vs independent gold |
| `packet_minimality` | 1.0 iff no unreferenced evidence, no duplicate ids, no duplicate edges, no downstream-unused raw metadata |
| `dependency_preservation` | fraction of required dependency edges reconstructible in the packet |
| `provenance_preservation` | fraction of packet objects (incl. intent) present in the provenance index |
| `reference_integrity` | 1.0 iff no dangling edge / relationship→evidence / governance→relationship / conflict-member reference |
| `conflict_preservation` | fraction of upstream conflicts carried |
| `gap_preservation` | fraction of upstream gaps carried |
| `duplicate_elimination` | 1.0 iff no duplicate object ids |
| `unsupported_reference_rate` | fraction of relationships/governance lacking in-packet support |
| `orphan_rate` | fraction of packet objects touching no dependency edge (intent excepted) |
| `validation_success` | 1.0 iff the layer validated the packet and `packet_validator` passed |
| `packet_size_reduction` | 1 − mean object count / naive-union (A) mean object count |
| `determinism` | 1.0 iff re-assembly is byte-identical |
| `severe_critical_failure_count` | sum of the 12 independent critical-failure classes |

## Independent critical failures (all severe)

`ORPHAN_EVIDENCE`, `ORPHAN_RELATIONSHIP`, `ORPHAN_GOVERNANCE_DECISION`, `LOST_CONFLICT`,
`LOST_GAP`, `LOST_PROVENANCE`, `BROKEN_DEPENDENCY`, `DUPLICATE_IDENTIFIERS`,
`PACKET_SMALLER_BUT_INCOMPLETE`, `PACKET_LARGER_WITHOUT_JUSTIFICATION`, `SCHEMA_CORRUPTION`,
`NON_DETERMINISTIC_PACKET`.

## Preregistered gates (14) — locked eval, selected baseline F

All pass: `packet_completeness` = 1.00, `packet_minimality` = 1.00,
`dependency_preservation` = 1.00, `provenance_preservation` = 1.00, `reference_integrity` =
1.00, `conflict_preservation` = 1.00, `gap_preservation` = 1.00, `duplicate_elimination` =
1.00, `unsupported_reference_rate` = 0.00, `orphan_rate` = 0.00, `validation_success` = 1.00,
`packet_size_reduction` = 0.32 (≥ 0.05), `determinism` = 1.00,
`severe_critical_failure_count` = 0.

## Ablation ladder (DEV) — why F is required

| Metric | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| packet_completeness | 1.00 | 1.00 | 0.79 | 1.00 | 1.00 | **1.00** |
| packet_minimality | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | **1.00** |
| provenance_preservation | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | **1.00** |
| reference_integrity | 1.00 | 1.00 | 0.81 | 1.00 | 1.00 | **1.00** |
| duplicate_elimination | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** |
| orphan_rate | 0.05 | 0.06 | 0.00 | 0.00 | 0.00 | **0.00** |
| validation_success | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | **1.00** |
| packet_size_reduction | 0.00 | 0.27 | 0.50 | 0.32 | 0.32 | **0.32** |
| severe_critical_failure_count | 52 | 36 | 43 | 32 | 16 | **0** |

Each rung fixes exactly what it adds: B eliminates duplicates but still ships unused
evidence; C prunes but — closing only from the winner — drops rejected/minority evidence,
producing a packet that is **smaller (reduction 0.50) yet incomplete (0.79)**, the exact
`PACKET_SMALLER_BUT_INCOMPLETE` trap; D restores full closure but has no provenance index; E
adds provenance but leaves downstream-unused raw metadata and never validates; only F
minimizes, validates, and freezes with zero severe failures. **F is the simplest baseline
passing all gates.**
