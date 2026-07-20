# Primary Endpoint Report — Table 2

**Primary endpoint (singular):** hidden owner-clean macro =
mean(discovery_F1, classification_accuracy, governance_accuracy_modeG,
packet_realization_accuracy_modeP, selective_accuracy).

| quantity | value |
|---|---|
| GraphTraversal macro | 0.4973 |
| Hybrid macro | 0.5761 |
| absolute macro gain | 0.0788 |
| practical threshold | 0.0300 |
| practically significant | yes |
| paired bootstrap 95% CI (hybrid − graph) | [0.0350, 0.1311] |
| CI excludes zero | yes |
| n (paired cases) | 60 |
| bootstrap iters / seed | 10000 / 20240601 |

The macro gain (+0.0788) exceeds the preregistered practical-significance
threshold (0.03) and the 95% paired-bootstrap CI excludes zero. The primary
endpoint therefore shows a statistically and practically significant improvement.
Whether this counts as *success* is gated by the non-inferiority constraints
(see NON_INFERIORITY_REPORT.md).
