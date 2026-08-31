# COMPETING_OPERATIVE_RESULTS — Competing Operative Resolution Experiment v0.1

**Resolver under test:** HybridRelationshipResolver Experimental v0.5
**Corpus:** Hidden Relationship Corpus Pilot v0.2 (22 seed + 38 pilot = 60)
**Lock:** `6b5eec75e2be1054946abe8039616751ece69f3f2ef4d46bf8389ac2dd9be763`

---

## Verdict: **NO CLEAR SIGNAL**

The precise Competing Operative Resolution Layer does what G4 failed to do — it does **not**
over-abstain — and it **retains all five G3 fixes** while passing every non-inferiority
constraint. But on the hidden pilot it finds **zero genuine unresolved conflicts** to act
on, so it adds no material improvement over G3. Per the preregistration, "C4 preserves G3
but adds no material improvement" and "the corpus contains too few activating cases for a
defensible conclusion" are both NO CLEAR SIGNAL conditions. It is decidedly **not**
FALSIFIED (no G3 fix lost, no over-abstention, no unsafe increase, protected stages
identical) and **not** PROMISING (no selective gain; abstention-recall gain +0.0625 is below
the +0.10 bar; and no genuine-conflict mechanism activated).

## The two headline facts
1. **G4's over-abstention is fixed.** Where historical G4 collapsed coverage 0.95 → 0.2833
   and drove false-abstention 0 → 0.5, C4 keeps coverage at 0.9333 and false-abstention at
   0. The precise conflict model never abstains on mere permission/prohibition co-occurrence
   (verified by the C8 synthetic gate).
2. **The corpus lacks the target phenomenon.** Every operative competition on the hidden
   pilot classified as `COMPATIBLE_OPERATIVES` (same polarity) or was resolved by
   supersession/domain/temporal separation. **Genuine unresolved conflicts: 0.**

## Table 3 — C0–C4 aggregate (hidden)
| condition | select | cover | govG | packP | false-ab | miss-ab | unsafe |
|---|---|---|---|---|---|---|---|
| C0 = G3 | 0.3860 | 0.9500 | 0.60 | 0.5167 | 0.0000 | 0.2167 | 2 |
| C1 extract | 0.3860 | 0.9500 | 0.60 | 0.5167 | 0.0000 | 0.2167 | 2 |
| C2 scope | 0.3860 | 0.9500 | 0.60 | 0.5167 | 0.0000 | 0.2167 | 2 |
| C3 classify | 0.3860 | 0.9500 | 0.60 | 0.5167 | 0.0000 | 0.2167 | 2 |
| C4 full | 0.3750 | 0.9333 | 0.60 | 0.5167 | 0.0000 | 0.2000 | 2 |

## Table 4 — primary endpoint (C4 vs C0)
| quantity | value |
|---|---|
| selective gain | −0.0110 (threshold +0.03) — not met |
| abstention-recall gain | +0.0625 (threshold +0.10) — not met |
| coverage | 0.95 → 0.9333 (within 0.05 margin) |
| primary met | **no** |

## Table 5 — non-inferiority (C4 vs C0): **passes**
| constraint | result |
|---|---|
| discovery P/R/F1, classification, validation records, governing set, Mode P | identical ✅ |
| coverage decrease ≤ 0.05 | 0.0167 ✅ |
| false-abstention increase ≤ 0.03 | 0.0 ✅ |
| missed-abstention increase ≤ 0.03 | decreased ✅ |
| unsafe answers | 2 = 2 ✅ |

## Table 6 — G3-fix retention: **all five retained**
`HX59d7a3eb1c`, `HP059f01c294`, `HP7d8d12efac`, `HPb3463204c9`, `HPebe6e8abf0` — all correct
under C4, none abstained.

## Table 7 — transitions
0 fixes, 0 breaks, 1 new (correct) abstention, 0 new answers. The single changed case is a
`no_relationship` gold-abstain case that C4 correctly abstains on (`OPERATIVE_TERM_NOT_LOCATED`)
where G3 had answered `unknown`.

## Table 10 — conflict categories (hidden)
| category | count |
|---|---|
| COMPATIBLE_OPERATIVES | 5 |
| GENUINE_UNRESOLVED_CONFLICT | 0 |
| (all others) | 0 |

## What this establishes and what it does not
- **Establishes:** the precise operative model is safe (retains G3, no over-abstention, no
  unsafe regression) and the machinery provably works on synthetic genuine conflicts (C9).
- **Does not establish:** any positive selective gain, because the 60-case pilot contains no
  genuine unresolved operative conflict. The packet single-primary contract was never the
  binding constraint here (0 cardinality-forced abstentions), so it is **not yet
  demonstrated** as the active bottleneck.

## Status
HybridRelationshipResolver **Experimental v0.5** / **Competing Operative Resolution
Experiment v0.1** — NO CLEAR SIGNAL (too few activating cases). Frozen architecture
unchanged. Not promoted, not production-ready, not RRB v1.0.
