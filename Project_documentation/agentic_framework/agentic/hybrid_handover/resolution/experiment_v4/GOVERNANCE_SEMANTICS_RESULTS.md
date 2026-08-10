# GOVERNANCE_SEMANTICS_RESULTS — Governance Semantics Experiment v0.1

**Resolver under test:** HybridRelationshipResolver Experimental v0.4
**Corpus:** Hidden Relationship Corpus Pilot v0.2 (22 seed + 38 pilot = 60)
**Lock:** `a14c3ba00b819278ee5b295a80662e4c998b6ebe73e1f22d487770607a582273`

---

## Verdict: **NO CLEAR SIGNAL** (full layer G4) — with a clean, causally isolated sub-signal from operative-source selection (G3)

The full Governance Semantics Layer (G4) raises selective accuracy 0.2982 → 0.5294, but
that headline is **coverage-driven**: G4's abstention rule over-fires, collapsing answer
coverage 0.95 → 0.2833 and driving false-abstention 0 → 0.5, which violates three
non-inferiority constraints. Per the preregistration, a gain that "depends mainly on
abstention or coverage reduction" is **NO CLEAR SIGNAL**.

But the experiment is **not** a null result. The ablation ladder cleanly isolates one
mechanism that works: **operative-source selection (G3)** lifts selective accuracy
0.2982 → 0.3860 (**+0.0878**) with coverage, Mode G, false-abstention, and unsafe **all
unchanged** — 5 fixes, 0 breaks, on exactly the competing-authority cases. Separating the
authority source from the operative source is a real, non-inferior improvement; the
governance-abstention rule as specified is what spoils the full layer.

## Table 1 — Protected-stage identity (G0–G4)
| stage | identical across G0–G4 |
|---|---|
| discovery precision / recall / F1 | **yes** |
| classification | **yes** |
| proposal-validation records | **yes** |
| packet Mode P | **yes** |

## Table 2 — G0–G4 aggregate (hidden)
| condition | select | cover | govG | false-ab | miss-ab | unsafe |
|---|---|---|---|---|---|---|
| G0_frozen | 0.2982 | 0.9500 | 0.6000 | 0.0000 | 0.2167 | 2 |
| G1_supersession_amendment | 0.2982 | 0.9500 | 0.6000 | 0.0000 | 0.2167 | 2 |
| G2_parallel | 0.2982 | 0.9500 | 0.6000 | 0.0000 | 0.2167 | 2 |
| **G3_operative** | **0.3860** | 0.9500 | 0.6000 | 0.0000 | 0.2167 | 2 |
| G4_full | 0.5294 | 0.2833 | 0.4333 | 0.5000 | 0.0500 | 2 |

## Table 3 — Primary endpoint (G4 vs G0)
| quantity | value |
|---|---|
| G0 selective | 0.2982 |
| G4 selective | 0.5294 |
| absolute gain | +0.2312 |
| practical threshold | 0.03 |
| bootstrap 95% CI (G4−G0) | [−0.0119, 0.4702] (includes 0) |
| **coverage-driven?** | **yes — coverage 0.95 → 0.2833** |

## Table 4 — Non-inferiority (G4 vs G0)
| constraint | G0 | G4 | verdict |
|---|---|---|---|
| discovery precision/recall/F1 | — | — | identical ✅ |
| classification | 0.9143 | 0.9143 | identical ✅ |
| packet Mode P | 0.5167 | 0.5167 | identical ✅ |
| governance Mode G (≤0.03 dec) | 0.6000 | 0.4333 | **violated** ❌ |
| answer coverage (≤0.05 dec) | 0.9500 | 0.2833 | **violated** ❌ |
| false-abstention (≤0.05 inc) | 0.0000 | 0.5000 | **violated** ❌ |
| missed-abstention (≤0.05 inc) | 0.2167 | 0.0500 | ok ✅ |
| unsafe answers | 2 | 2 | ok ✅ |

**G4 fails non-inferiority.** For the clean G3 comparison every constraint above is
satisfied (G3 differs from G0 only in selective accuracy).

## Table 5 — Fix/break transitions
| comparison | fixes | breaks | unchanged-correct | unchanged-incorrect |
|---|---|---|---|---|
| G3 vs G0 (coverage held) | 5 | 0 | 17 | 35 |
| G4 vs G0 (answered set) | 5 | 0 | 4 | 8 |

Both show 5 fixes / 0 breaks; G4's smaller unchanged counts reflect its shrunken answered
set. The five G3 fixes are all competing-authority cases (policy_migration,
parallel_overrides, hierarchical_governance, multiple_authorities, scoped_exceptions),
including the exact `parallel_overrides` case Edge Prioritization v0.3 broke.

## The mechanism, precisely
For each fixed case, the frozen packet was reading the answer from the highest-authority
governance source, which did not carry the operative termination-for-convenience term.
The operative-source rule instead selects the governing clause that actually carries the
prohibition/permission, and the adapter steers the frozen packet onto it. Discovery,
classification, validation, and Mode P are untouched (Table 1), so the improvement is
attributable purely to governance-semantic operative selection — confirming the v0.3
diagnostic.

## Why G4's abstention rule fails
G4 abstains whenever a prohibition and a permission co-occur in the governing set. On the
hidden pilot this fires far too often (coverage 0.95 → 0.28): many such co-occurrences
have a legitimate dominant outcome that operative selection already resolves correctly in
G3. The abstention rule as preregistered is too aggressive; it converts answerable cases
into abstentions and inflates selective accuracy through coverage reduction.

## Status
HybridRelationshipResolver **Experimental v0.4** / **Governance Semantics Experiment
v0.1** — NO CLEAR SIGNAL for the full layer; operative-source selection (G3) is a clean,
non-inferior mechanism worth further research. Frozen architecture unchanged. Not
promoted, not production-ready, not RRB v1.0.
