# PRIORITIZATION_RESULTS — Edge Prioritization Experiment v0.1

**Resolver under test:** HybridRelationshipResolver Experimental v0.3
**Corpus:** Hidden Relationship Corpus Pilot v0.2 (22 seed + 38 pilot = 60)
**Lock:** `a36cadd8070d6880b6fe2b30a8a76370fb143f1d7eafbcb80049f3f713fc8db8`

---

## Verdict: **NO CLEAR SIGNAL**

Deterministic Edge Prioritization **can** re-rank competing governance sources and it
**did** change downstream governance decisions — but it did **not** improve selective
accuracy. It reshuffled edges without a net improvement in decisions. It is **not**
FALSIFIED: no protected metric degraded (discovery, classification, governance Mode G,
packet Mode P, and unsafe answers are all identical to v0.2, by construction and in
fact). And it is **not** PROMISING: selective accuracy is unchanged.

## Primary endpoint — selective accuracy (no improvement)
| | P0 (v0.2) | P4 (full) | Δ |
|---|---|---|---|
| selective accuracy | 0.2982 | 0.2982 | **0.0000** |

## Protected metrics — no degradation (all unchanged P0 → P4)
| metric | P0 | P4 |
|---|---|---|
| discovery precision | 0.8974 | 0.8974 |
| discovery recall | 0.4167 | 0.4167 |
| classification | 0.9143 | 0.9143 |
| governance Mode G | 0.6000 | 0.6000 |
| packet Mode P | 0.5167 | 0.5167 |
| unsafe answers | 2 | 2 |

## Success criteria (preregistered)
| criterion | result |
|---|---|
| selective accuracy improves | ❌ unchanged |
| discovery unchanged | ✅ |
| precision unchanged | ✅ |
| recall unchanged | ✅ |
| unsafe unchanged | ✅ |

Five criteria, one required outcome (selective improvement) not met → not PROMISING.

## What the layer did
- **3 cases** on the hidden pilot contain ≥2 competing governance sources; elsewhere the
  layer is a strict no-op.
- **3 competing edges reprioritized**, all decided by the **authority** component.
- **2 full-pipeline governance decisions changed** — and they cancel exactly:
  - `HX59d7a3eb1c` (policy migration): P0 `unknown` → P4 **`prohibited`** — **fix**.
  - `HXb3def36e76` (parallel overrides): P0 `prohibited` → P4 `unknown` — **break**.
- Paired McNemar on answered-case correctness (P4 vs P0): **1 fix, 1 break, n=2,
  p=1.0, net 0**.

## Why it is a wash
The authority heuristic ("later / higher instrument dominates") is correct for
**supersession and migration** — where the newer instrument genuinely replaces the
older — but wrong for **parallel authority**, where the correct outcome depends on
which instrument carries the operative term, not on which ranks higher. Making the
Regulatory Directive primary is "more authoritative" yet drops the Corporate Policy's
prohibition in the frozen packet. Edge ordering cannot separate these two situations;
that separation lives in the frozen governance / packet **semantics**, which are out of
scope for this experiment.

## Ablations
P0 = P1 = P2 = P3 = P4 on every metric (PRIORITIZATION_ABLATIONS.md): authority alone
is decisive in all three competitions, so the richer components never change a ranking
on this corpus.

## Status
HybridRelationshipResolver **Experimental v0.3** / **Edge Prioritization Experiment
v0.1** — no clear signal. Frozen architecture unchanged. Not promoted, not
production-ready, not RRB v1.0.
