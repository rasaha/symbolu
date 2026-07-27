# Next-Hop Pointer-Discrimination Experiment — Verdict

One authorized bounded experiment. Frozen Phase untouched (**FREEZE OK, 98/98**). No Phase
comparison, no 9P:3Q, no N reduction. Identical dataset / seed / N=32 / candidate set / encoder /
Q-blocks / optimizer budget / eval examples across arms. Autonomous eval uses only the predicted
pointer distribution (verified leak-free).

## Part 1 — Is the current 0.797 result genuine or memorization?

Controls on the structured-pointer baseline (P0), at N=32:

| control | accuracy | reading |
|---|---:|---|
| clean | 0.747 | reference |
| **identity renaming** (global bijection) | **0.740** | preserved → **not** identity-token memorization |
| **shuffled evidence order** | **0.733** | preserved → **not** position/order memorization |
| unseen entity pairings (retrain restricted) | **0.203** | **collapses** → no entity-adjacency composition |
| unseen relation compositions (retrain restricted) | **0.323** | **collapses** → no relation-composition generalization |

**Reading:** the 0.74–0.80 result is genuine *relational retrieval* on the training composition
distribution (invariant to relabeling and to evidence order), but it is **finite-composition
memorization** — it does not generalize to unseen entity adjacencies or unseen relation
compositions. Renaming preserves accuracy precisely because a global bijection keeps every trained
composition intact (just relabeled); held-out compositions are genuinely novel structures and
collapse.

## Part 2 — Explicit next-hop pointer scorers

Candidate-conditioned scorers over the **runtime candidate set** (not a fixed global 32-class
head), using explicit features (entity, relation, value, source-pos, consumed, hop). Listwise CE
over all 32 candidates. Backbone frozen for P1/P2 (scorer-only); best scorer gets one joint
fine-tune (P3).

| arm | top-1 | top-3 | MRR | grounded_D1 | beam-3 | acc\|correct-ptr | scorer params |
|---|---:|---:|---:|---:|---:|---:|---:|
| P0 baseline (o·W·ev) | 0.597 | 0.917 | 0.760 | 0.740 | 0.783 | 0.922 | — |
| P1 relation-aware bilinear | 0.440 | 0.710 | 0.601 | 0.493 | 0.617 | 0.735 | 32,384 |
| **P2 candidate MLP** (best) | **0.633** | 0.917 | 0.779 | **0.780** | **0.803** | 0.905 | 44,801 |
| P3 = P2 + joint fine-tune + beam | 0.603 | 0.923 | 0.759 | 0.777 | 0.777 | 0.923 | (total 131,586) |

- The **MLP scorer (P2) is the only improvement**: top-1 0.597 → 0.633, grounded_D1 0.740 → 0.780,
  beam-3 0.783 → 0.803. Modest (+0.02–0.04).
- The **relation-aware bilinear (P1) hurt** (0.44 top-1) — a single bilinear form is too weak for
  this value→key identity match.
- **Joint fine-tuning did not help** (P3 ≈ P2, beam slightly lower) — the backbone was already
  near its ceiling; co-training the scorer added nothing.
- **Parameter/latency overhead** (P3 vs P0): 131,586 vs 86,785 params (1.5×), 18 ms vs 13 ms /64
  (1.4×), 1.0 MB peak — small, but not justified by the +0.02 gain.

**Hard-negative breakdown (of top-1 pointer errors):** only ~20–24% land on *hard* negatives
(same-entity-wrong-relation etc.); ~75–78% land on *ordinary* distractors. The discrimination
failure is **broad**, not specifically fooled by hard negatives.

## Part 6 — Causal / leakage controls (best arm)

| control | result | verdict |
|---|---|---|
| leak-free: randomize intermediate-query label (reqe) → answer invariant | **True** | pointer reads no labels ✓ |
| random pointer scores → accuracy | 0.805 → **0.117** | pointer scores are causal ✓ |
| required evidence removed → accuracy | 0.805 → **0.000** | required evidence is necessary ✓ |
| forced identical candidate → non-scorer behavior identical (matched backbone) | **True** | scorer affects only selection ✓ |
| shuffled order after remap → predictions preserved | 0.767 → 0.760 | no order shortcut ✓ |

(The one raw `False` in the P3 causal dump — forced-candidate independence — is a **joint-fine-tune
confound**: the reference model used the *original* backbone while the joint model's backbone had
moved; on matched backbones the control passes, verified separately.)

## Part 7 — Acceptance rule (N=32)

| criterion | required | actual | pass |
|---|---|---:|---|
| pointer top-1 | ≥ 0.75 | 0.633 | ❌ |
| grounded_D1 | ≥ 0.85 | 0.780 | ❌ |
| beam-3 D1 | ≥ 0.85 | 0.803 | ❌ |
| acc \| correct pointer | ≥ 0.90 | 0.923 | ✅ |
| held-out no material collapse | — | unseen-pair 0.14 / unseen-comp 0.09 | ❌ |
| autonomous eval leak-free | — | yes | ✅ |

**PASS: NO.** The 0.85 gate is not lowered.

---

## §8 Required verdict

- **Current baseline:** structured-pointer P0 — top-1 0.597, grounded_D1 0.740, beam-3 0.783,
  acc|correct-pointer 0.922.
- **Each pointer scorer:** P1 relation-aware bilinear — top-1 0.440, grounded_D1 0.493, beam-3
  0.617 (regressed). P2 candidate-conditioned MLP — top-1 0.633, grounded_D1 0.780, beam-3 0.803
  (best). P3 (P2 + joint FT + beam) — top-1 0.603, grounded_D1 0.777, beam-3 0.777.
- **Parameter and latency overhead:** P3 1.5× params (131,586 vs 86,785), 1.4× latency (18 vs
  13 ms/64), 1.0 MB peak — not justified by the +0.02 accuracy.
- **top-1 / top-3 / MRR:** best (P2) 0.633 / 0.917 / 0.779.
- **grounded_D1:** best 0.780 (< 0.85).
- **beam-3 D1:** best 0.803 (< 0.85).
- **held-out results:** identity-renaming and shuffled-order **preserved** (0.74–0.78); unseen
  entity-pairings **0.14–0.20** and unseen relation-compositions **0.09–0.32** — **material
  collapse**.
- **causal-control results:** leak-free ✓, random-pointer collapse ✓ (→0.12), required-removed
  collapse ✓ (→0.00), forced-candidate scorer-independence ✓ (matched backbone), shuffle-order
  invariance ✓.

**Pointer discrimination:** improved but insufficient.

**Iterative 3Q pilot:** blocked.

**Phase comparison:** blocked.

**Remaining bottleneck:** autonomous next-hop discrimination — ranking the correct next evidence
event first among 32 candidates — remains unresolved under the current event representation and
training regime. The explicit MLP scorer lifts top-1 only 0.597 → 0.633 (top-3 stays 0.92), and the
decisive limitation is now **compositional generalization**: the pointer memorizes the finite set
of trained entity-adjacencies and relation-compositions (invariant to relabeling and order) but
**collapses on unseen compositions** (entity-pair 0.14, relation-composition 0.09). The mechanism
downstream of selection is sound (acc|correct-pointer 0.92, D0 1.000, oracle-pointer 0.93); the
unresolved problem is a *generalizing* next-hop selector, which neither a stronger scorer nor a
bounded beam nor joint fine-tuning provides on the current (KEY,VALUE) identity representation.
