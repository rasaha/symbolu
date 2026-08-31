# PRIORITIZATION_ABLATIONS — Edge Prioritization Experiment v0.1

Preregistered ablations P0–P4 on the hidden pilot. P0 reproduces v0.2 bit-for-bit.

| ablation | disc P | disc R | class | govG | packP | select | unsafe |
|---|---|---|---|---|---|---|---|
| P0_none | 0.8974 | 0.4167 | 0.9143 | 0.6000 | 0.5167 | 0.2982 | 2 |
| P1_authority | 0.8974 | 0.4167 | 0.9143 | 0.6000 | 0.5167 | 0.2982 | 2 |
| P2_authority_temporal | 0.8974 | 0.4167 | 0.9143 | 0.6000 | 0.5167 | 0.2982 | 2 |
| P3_auth_temporal_specificity | 0.8974 | 0.4167 | 0.9143 | 0.6000 | 0.5167 | 0.2982 | 2 |
| P4_full | 0.8974 | 0.4167 | 0.9143 | 0.6000 | 0.5167 | 0.2982 | 2 |

**Every ablation is identical on every metric.** In all three competing cases the
**authority** component alone is decisive, so P1 (authority only) already realizes
the full reordering and P2–P4 add nothing. The protected metrics (discovery
precision/recall, classification, governance Mode G, packet Mode P, unsafe) are
unchanged across the ladder — as guaranteed structurally, and confirmed here.
Selective accuracy is flat at 0.2982 throughout.
