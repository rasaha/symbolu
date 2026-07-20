# VALIDATION_ABLATIONS — Proposal Validation Experiment v0.1

Preregistered ablations V0–V4 on the hidden pilot. V0 reproduces Hybrid v0.1
bit-for-bit (verified). Governance Mode G (0.60), packet Mode P (0.5167),
coverage (0.95), and unsafe answers (2) are identical across all five and are
omitted from the table.

| ablation | disc P | disc R | disc F1 | class | select | macro |
|---|---|---|---|---|---|---|
| V0_none | 0.8140 | 0.4167 | 0.5512 | 0.9143 | 0.2982 | 0.5761 |
| V1_dedupe_only | 0.8140 | 0.4167 | 0.5512 | 0.9143 | 0.2982 | 0.5761 |
| V2_evidence_only | 0.8140 | 0.4167 | 0.5512 | 0.9143 | 0.2982 | 0.5761 |
| V3_authority_temporal | 0.8974 | 0.4167 | 0.5691 | 0.9143 | 0.2982 | 0.5797 |
| V4_full | 0.8974 | 0.4167 | 0.5691 | 0.9143 | 0.2982 | 0.5797 |

**Reading.** V1 (duplicate suppression) and V2 (evidence consistency + minimum
confidence) reject nothing on the hidden set — the v0.1 proposals already carry
provenance, resolvable destinations, and lexical confidence ≥ 0.6. The entire
precision gain appears at **V3**, from the type-specific `same_as` alias-validity
constraint (a `same_as` needs a shared version lineage or a matching normalized
section number). **V4 equals V3**: the remaining gates (dedupe, evidence,
exclusivity, min-confidence) add no further rejection on this corpus. Discovery
recall is unchanged at 0.4167 throughout — precision is recovered at zero recall
cost.
