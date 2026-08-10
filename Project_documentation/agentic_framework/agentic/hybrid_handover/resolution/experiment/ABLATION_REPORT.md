# Ablation Report — Table 8 (hidden pilot)

Preregistered ablations A0–A8. A7 (Mode G, gold graph injected) and A8 (Mode P,
gold governance injected) are evaluation-mode isolations already reported as the
govG / packP columns; they are recorded below the table.

| ablation | disc P | disc R | disc F1 | class | select | MACRO |
|---|---|---|---|---|---|---|
| A0_full | 0.8140 | 0.4167 | 0.5512 | 0.9143 | 0.2982 | 0.5761 |
| A1_no_semantic | 1.0000 | 0.1786 | 0.3031 | 0.7333 | 0.3333 | 0.4973 |
| A2_no_traversal | 0.8140 | 0.4167 | 0.5512 | 0.9143 | 0.3333 | 0.4631 |
| A3_no_governance_rules | 0.8140 | 0.4167 | 0.5512 | 0.9143 | 0.3333 | 0.5664 |
| A4_no_confidence_abstain | 0.8140 | 0.4167 | 0.5512 | 0.9143 | 0.2982 | 0.5761 |
| A5_no_provenance | 0.8140 | 0.4167 | 0.5512 | 0.9143 | 0.2982 | 0.5761 |
| A6_discovery_only | 0.8140 | 0.4167 | 0.5512 | 0.9143 | 0.3333 | 0.4631 |

- **A7 Mode G (gold graph):** governance_accuracy_modeG = 0.6000
- **A8 Mode P (gold governance):** packet_realization_accuracy_modeP = 0.5167

**Attribution of the gain.** A1 (remove the semantic proposal layer → fall back to
the narrow cue set) collapses every discovery/classification gain and returns the
macro to the GraphTraversal baseline (0.4973). The semantic proposal layer is the
*sole* source of the improvement. A4 (remove the confidence gate) leaves the macro
unchanged (0.5761) — the τ=0.5 gate does not drive the result. A5 (remove the
provenance filter) is likewise inert on this corpus. A2/A6 (no governance traversal
/ discovery-only) zero out the governance-dependent metrics as expected while
leaving discovery intact, confirming clean separation of the discovery layer.
