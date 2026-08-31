# VALIDATION_RESULTS — Proposal Validation Experiment v0.1

**Resolver under test:** HybridRelationshipResolver Experimental v0.2
**Corpus:** Hidden Relationship Corpus Pilot v0.2 (22 seed + 38 pilot = 60)
**Lock:** `a15f4aa24a906602d300863efe1e5aac38d776a78c1e0ca2c27769a708cc07ce`

---

## Verdict: **PROMISING VALIDATION LAYER (partial — precision recovered, selective did not)**

A deterministic Proposal Validation Layer **can** reject unsupported relationship
proposals before graph construction **without reducing genuine discovery**: it
recovered discovery precision by **+0.083** (0.814 → 0.897) at **zero recall cost**
(0.4167 → 0.4167), removing **4 incorrect edges and 0 correct ones**. Five of the six
preregistered success criteria are met. The one miss: the precision gain did **not**
translate into higher selective accuracy (0.2982, unchanged). By the strict 6/6 bar
this is not a full "PROMISING VALIDATION LAYER," but it is decisively **not** NO CLEAR
SIGNAL (precision was not bought with recall) and **not** FALSIFIED (no genuine
discovery was removed).

## Primary endpoint — MET
| quantity | V0 (Hybrid v0.1) | V4 (full validator) | Δ |
|---|---|---|---|
| discovery precision | 0.8140 | 0.8974 | **+0.0834** |
| discovery recall | 0.4167 | 0.4167 | 0.0000 |
| discovery F1 | 0.5512 | 0.5691 | +0.0179 |

Precision recovery with recall loss 0.0 ≤ 0.03 → **endpoint met**. Paired bootstrap on
the precision difference: +0.0835, 95% CI **[0.0204, 0.1557]**, excludes zero.

## Success criteria (preregistered)
| criterion | result |
|---|---|
| discovery precision improves | ✅ +0.0834 |
| recall loss ≤ 0.03 | ✅ 0.0 |
| selective accuracy improves | ❌ unchanged (0.2982) |
| unsafe answers do not increase | ✅ 2 = 2 |
| governance unchanged | ✅ Mode G 0.60 |
| packet unchanged | ✅ Mode P 0.5167 |

## What the validator did (V4 over 60 hidden cases)
- 43 proposals evaluated → **39 accepted, 4 rejected**.
- All 4 rejections: spurious `same_as` alias edges between distinct policies
  (`relationship_ambiguity`). **4 incorrect removed, 0 correct rejected.**
- 4 spurious edges survived (`governs_over`×3, `overrides`×1) — structurally valid,
  not catchable by the frozen rulebook (honest limitation; see EDGE_REJECTION_ANALYSIS.md).
- The entire effect appears at **V3** and is unchanged at V4 (VALIDATION_ABLATIONS.md):
  the type-specific `same_as` alias-validity gate is the sole active mechanism on this
  corpus; the authority/temporal, duplicate, evidence, and confidence gates did not fire.

## Why selective accuracy did not move
Selective accuracy is governed by the **frozen** downstream, which is unchanged. The
removed edges were `same_as` alias proposals; alias edges do not alter which cases the
frozen governance answers or whether those answers are correct, so precision improved
while the answered-case outcomes — and thus selective accuracy — stayed exactly put.
This is consistent with governance Mode G, packet Mode P, coverage, and unsafe counts
all being identical between V0 and V4.

---

## The six final questions

**1. How many incorrect relationship proposals were removed?**
**4** — all spurious `same_as` alias edges between distinct policies. Precision rose
0.814 → 0.897 as a result.

**2. How many correct proposals were mistakenly rejected?**
**0.** Discovery recall is unchanged (0.4167); no gold edge was removed by any gate.

**3. Was the precision gain worth the recall loss?**
**Yes — there was no recall loss.** The gain (+0.083, CI excludes zero) came at zero
cost to recall, which is the strongest possible form of the trade-off. Whether +0.083
is *material* is a separate question: it recovers ~45% of v0.1's precision gap versus
GraphTraversal (which had precision 1.0), not all of it.

**4. Did selective accuracy recover?**
**No.** Selective accuracy is unchanged at 0.2982. The removed edges were aliases that
do not affect the frozen governance's answered-case decisions, so the precision gain
did not propagate downstream. This is the experiment's one clear negative.

**5. Is Proposal Validation now the preferred architecture?**
**Partially, and only for discovery precision.** As a discovery-precision filter it is
a strict improvement (free precision, no recall loss, fully explainable rejections). It
is *not* yet a general win, because it does not improve selective accuracy and leaves
4 structurally-valid spurious edges uncaught. Preferred for the precision sub-problem;
not yet a decisive upgrade to the whole resolver.

**6. Should Proposal Validation become part of the frozen resolver architecture?**
**No.** Per the experiment's own constraint, the frozen architecture is **not** changed
regardless of outcome. Independently of that rule, the evidence does not yet justify
promotion: the gain is confined to one edge type on a 60-case pilot, selective accuracy
did not move, and the residual `governs_over`/`overrides` false positives are untouched.
A follow-up should extend the type-specific gates (governance-aware validation) and
re-test on a larger corpus before any promotion is considered.

---

## Status
HybridRelationshipResolver **Experimental v0.2** / **Proposal Validation Experiment
v0.1** — promising for discovery precision, not promoted. Frozen architecture
unchanged. Not production-ready. Not RRB v1.0.
