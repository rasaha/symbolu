# Tier-A replay — TOOLING SELF-TEST (synthetic fixture)

> **Label: `real-trace-replay (estimate pending live adjudication)`.** Detector + cost model are frozen in `Project_documentation/governance/docs/cloud_scaling_real_validation/TIER_A_DETECTOR_SPEC.md`. The replay surfaces Tier-A **candidates**; an SRE confirms true/false + cost before anything counts. **Tier-B is never market evidence.**

> ⚠️ **This is a synthetic schema fixture — a tooling self-test, NOT a market number.** The coverage trip-wire below refuses it as evidence by design. Real numbers require real partner data + SRE adjudication.

## Per-cluster Tier-A counts

| org | cluster | cluster-months | cycles H/N/NH | Tier-A candidates | Tier-B (diagnostic) |
|---|---|--:|--:|--:|--:|
| fixture-org | `fixture-cluster` | 0.001 | 10/16/29 | 1 | 0 |

## APCY (fleet roll-up) — with the pre-registered honesty gate

- orgs: **1** · clusters: **1** · coverage: **0.00 cluster-months**
- Tier-A candidates: **1** · Tier-B events: 0
- **APCY:** **WITHHELD** — not reportable as market evidence (see reason)
- **reportable as market evidence: False** · market-red: False
- reason: NOT reportable as market evidence — insufficient coverage (0.0 < 150 cluster-months); too few orgs (1 < 6; single-workload bias risk); too few Tier-A (1 < 5)

## SRE-adjudication worksheets

_One per Tier-A candidate. Full template: `Project_documentation/governance/docs/cloud_scaling_real_validation/track_c_design_partner/04_SRE_ADJUDICATION_WORKSHEET.md`._

### SRE Adjudication — `fixture-cluster-ep1`
*Source: replay (Track B) · label: `real-trace-replay (estimate pending live adjudication)`*

| field | replay-filled value |
|---|---|
| Org / cluster | fixture-org / fixture-cluster |
| Window (cycles) | 26 → 46 (21 cycles × 60s) |
| Verdict / pattern | futile-runaway (21 consecutive NOT_HELPING ≥ 20 replicas) |
| Replicas (floor → peak) | 24 → 34 |
| Peak p99 latency (norm) | 0.960 |
| Peak error rate | 0.220 |
| Mean CPU (norm) | 0.439 |
| SLO-breach cycles in window | 19 |
| Incident overlap | yes: INC-101 (17.0 min) |
| Excess replica-hours | 2.77 |
| Estimated episode cost | $85.28 |
| Classification (replay) | tier_a_candidate |

**SRE to complete:**
- [ ] TRUE positive (scaling genuinely not helping) / [ ] FALSE positive / [ ] ⛔ HARMFUL FP (it actually relieved a constraint → STOP-AND-REVIEW)
- [ ] Confirm **Tier-A** (materially over-provisioned / amplified a non-capacity incident) — or downgrade to **Tier-B**
- Root cause: ____  · Confirmed episode cost: $____  · Counts toward APCY: yes / no

> Full template + definitions: `track_c_design_partner/04_SRE_ADJUDICATION_WORKSHEET.md`.
