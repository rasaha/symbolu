# Query-Update Repair — Verdict (structured pointer → capacity probe → beam)

**Gate:** grounded_D1 (oracle route + autonomous learned next-hop query) ≥ 0.85, leak-free, on
held-out compositions, before any Phase / Phase-free 3Q comparison.

**Result: gate NOT passed. grounded_D1 = 0.797 (beam) < 0.85.** The query-update *mechanism* is
validated; the residual, precisely localized, is next-hop **pointer discrimination** — not query
evolution and not embedding capacity.

## 1. Parity anomaly — RESOLVED

`tests/test_parity.py` (2/2 pass): forcing the oracle (D1) and learned (D2) arms onto **identical
routed indices** yields **bit-identical answer logits**. So every non-routing code path is shared;
the earlier D2(0.49) > D1(0.19) gap was a routing-selection effect, not a shortcut. With a working
query update the ordering also flips to the expected direction (D1 0.74 > D2 0.48).

## 2. Structured soft pointer — the decisive repair

Replaced the query update with a structured soft pointer over the **candidate evidence keys**
(not the global identity vocab):
`scores_i = (W_ptr · o) · ev_i ; pointer = softmax(scores) ; q_next = Σ_i pointer_i · ev_i`.
Train-only supervision on the next required event; autonomous eval uses only the predicted pointer.

| arm | before | after (pointer) |
|---|---:|---:|
| grounded_D1 (oracle route + learned query) | 0.170 | **0.740** |
| D0 (oracle route + GT query) | 1.000 | 1.000 |
| acc \| correct pointer | — | **0.934** |

`acc|correct-pointer = 0.934 ≈ D0` ⇒ **composition + decode are correct given the right next
event**; the query-evolution failure the audit flagged is fixed. The bottleneck moved to pointer
precision: **top-1 = 0.60, top-3 = 0.91**.

## 3. Capacity probe (dim 64→128) — width is NOT the cause

Identical data / seed / N=32 / eval; only model width differs.

| metric | dim=64, h=4 | dim=128, h=8 |
|---|---:|---:|
| params | 86,785 | 320,961 (3.7×) |
| train time | 271.9 s | 297.5 s |
| latency / 64 | 13 ms | 20 ms (1.53×) |
| peak mem | 1.0 MB | 1.0 MB |
| **D0** | 1.000 | 1.000 |
| **grounded_D1** | **0.740** | **0.693** |
| pointer top-1 | 0.607 | 0.543 |
| pointer top-3 | 0.910 | 0.900 |
| pointer entropy | 0.894 | 0.679 |
| acc \| correct pointer | 0.912 | 0.883 |

Doubling width **degraded every metric** (gain −0.047 for 3.7× params). Not an embedding-capacity
limit (item-1 caution confirmed) — consistent with an optimization / discrimination ceiling. Per
item 5, width/head scaling stops here; no open-ended sweep.

## 4. Bounded top-3 pointer beam (item 5's permitted next test)

Expand the top-3 predicted next keys, traverse each through the next bounded Q block, score
completed paths (log pointer prob + answer confidence), select the best. Bounded (3 hypotheses),
autonomous (labels only in the oracle upper-bound).

| decoder | grounded_D1 |
|---|---:|
| soft (mixture) | 0.740 |
| hard top-1 | 0.740 |
| **beam-3** | **0.797** |
| oracle pointer (upper bound) | 0.933 |

Beam closes **29%** of the gap to oracle (+0.057) but stays below 0.85. The correct answer is
reachable within the top-3 (coverage 0.91), yet path scoring — which leans on the same weak
matching signal — cannot reliably pick it.

## 5. Diagnosis (localized, cross-experiment)

The sole residual bottleneck is the **next-hop pointer / matcher**: matching hop-0's readout
(value-content = next entity B) to the correct event keyed on B among 32 candidates seeded with
same-entity-wrong-relation and same-relation-wrong-entity hard negatives. This is the **same
discrimination ceiling** already characterized elsewhere in this line of work — one-hop oracle
0.853 at N=32, and the earlier focus↔event matcher study (bilinear+hard AUROC ≈ 0.80). It is
**not** query evolution (D0 = 1.000, oracle_ptr = 0.933, acc|cp = 0.91) and **not** capacity
(width hurt).

## 6. Gate status & sequencing

- grounded_D1 = **0.797 < 0.85** after the full permitted sequence (pointer → width probe → beam).
- Autonomous eval **leak-free** (18/18 audit+parity+softmax tests; learned arm bit-identical under
  randomized labels).
- Held-out compositional controls (unseen entity-pair / relation-composition / identity-renaming /
  shuffled order / hard negatives) are **built** (`heldout_splits.py`, `run_generalization.py`) but
  **gated behind ≥0.85** (item 4) — **not run**.
- **Phase and Phase-free 3Q comparisons remain BLOCKED** (item 7).

**Frozen Phase:** unchanged — FREEZE OK, 98/98.

## 7. What the permitted ladder has and hasn't shown

Validated: the iterative evidence-navigation *mechanism* (route → bounded exact softmax →
structured pointer → q_next → route) is correct and, given a correct next-hop selection, solves the
2-hop task at ≈0.93. Not validated: an **autonomous** next-hop selector accurate enough to clear
0.85 at N=32 under hard negatives. The next move is a decision for the operator — the permitted
capacity/beam avenues are exhausted; further progress needs either an explicit high-precision
matcher for the next-hop pointer (the one lever not yet permitted here) or a lower-difficulty
operating point — neither of which may be taken until authorized.
