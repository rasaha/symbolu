# BindingSlots address-generalization / gradient-isolation — execution report

**Primary verdict: `NO_BINDINGSLOTS_INTERVENTION_SELECTED` · `KDA_VALIDATION_BLOCKED`.**

Intervention-development phase. Neither preregistered lever passed its frozen mechanism gate; both
were stopped by second-failure futility; AG was correctly never run. No candidate selected, so
`INDEPENDENT_CONFIRMATION_REQUIRED` is **not** emitted. KDA cannot be unblocked by this phase.

## Reproduction integrity

B0 (levers off) is byte-identical in training to the frozen `persistence_arms.run_h2`
(`test_b0_equivalence_short`). G1 modifies gradients only in `write_addr_proj` and leaves the LM
gradient and all other groups untouched (`test_ag_impl.py`). A1 draws its batch from a dedicated rng
so the main data stream matches B0. Seeds 28–32, no replacement. See `results/integrity_report.json`.

## Base rate (B0 = frozen H2 on the fresh seeds)

| seed | B0 needle@96 | B0 ppl₂₅₆ | A+ ppl₂₅₆ | quality |
|---|---|---|---|---|
| 28 | **0.99** | 123.9 | 129.1 | pass |
| 29 | 0.00 | 139.4 | 136.3 | pass |
| 30 | 0.00 | 148.2 | 134.9 | pass |
| 31 | 0.02 | 204.2 | 98.3 | fail |
| 32 | 0.03 | 143.6 | 109.2 | fail |

B0 is clean-stable on **1/5** fresh seeds (s28) — the ~1/5 historical H2 rate. The interventions were
therefore tested against a base that mostly fails on fresh seeds.

## A1 — read-address generalization: `ARM_FUTILITY_REACHED` (2 seeds)

| seed | quality | clean-stable | eval prob (Δ vs B0) | top-1 Δ | ordinary→oracle | wak cos (B0 wak) |
|---|---|---|---|---|---|---|
| 28 | pass | **fail** | 0.262 (**−0.56**) | −0.25 | 0.025 → 0.98 | **−0.27** (+0.05) |
| 29 | pass | fail | 0.173 (−0.19) | +0.00 | 0.00 → 1.00 | +0.02 (+0.25) |

A1 did not generalize address routing to the held-out eval queries; on **s28 — the one seed B0 had
working — it collapsed retrieval** (needle 0.99 → 0.025, eval correct-slot prob −0.56) and **induced a
`write_addr_proj` gradient conflict** (+0.05 → −0.27). Two non-clean seeds → futile after two. The
contrastive routing objective at real task-query positions, at the prior objective's coefficient,
destabilized rather than improved routing.

## G1 — routing-gradient isolation: `ARM_FUTILITY_REACHED` (3 seeds)

| seed | quality | clean-stable | eval prob (Δ vs B0) | ordinary→oracle | wak cos (B0 wak) |
|---|---|---|---|---|---|
| 28 | pass | **pass** | 0.730 (−0.09) | 0.98 → 0.98 | −0.00 (+0.05) |
| 29 | pass | fail | 0.500 (+0.14) | 0.00 → 1.00 | +0.03 (+0.25) |
| 30 | pass | fail | 0.012 (−0.50) | 0.00 → 0.79 | +0.10 (+0.04) |

G1 was benign on the already-clean seed (s28 stayed clean-stable) but **did not rescue the collapsed
seeds** (s29, s30 remained at needle 0). Two non-clean seeds among the first three → futile after
three. On these fresh seeds B0's `write_addr_proj` conflict was not consistently negative to begin
with (e.g. s28 +0.05, s29 +0.25), so there was often no conflict for G1 to remove — the quality
regression the diagnostic phase localized on seeds 24/25 did not reproduce as a negative wak cosine on
28–32, and G1's projection therefore had little to act on.

## AG — not run

A1 and G1 did not both pass, so AG was correctly skipped.

## Interpretation (conservative)

- The interventions were **falsified on these seeds under the frozen gates**: A1's contrastive routing
  objective degraded a working seed and induced conflict; G1 preserved quality but did not restore
  retrieval where B0 failed.
- This does **not** prove the hypotheses are impossible — only that these specific operationalizations,
  at the preregistered coefficients/schedules, did not pass on seeds 28–32.
- The gradient-conflict that G1 targets was localized on the *diagnostic* seeds (24/25); it did not
  present as a consistent negative wak cosine on the *fresh* seeds, so G1 had limited leverage here.

## Next phase (named, not started — §19)

Neither component passed → **controlled intervention redesign based on the failed mechanism gates**
(its own preregistered phase). In particular: A1 needs a routing objective that does not destabilize
already-formed seeds (the current form induced conflict); G1 needs seeds that actually exhibit the
negative wak conflict, or a reformulated target. **Nothing is redesigned or implemented here.** KDA
remains blocked.
