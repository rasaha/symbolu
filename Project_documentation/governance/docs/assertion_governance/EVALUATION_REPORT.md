# Evaluation Report (v1)

*Phase 9. All baselines + the AGE engine on the frozen `age_corpus_v1` eval split (229 items).
Deterministic; no live calls. Baselines dev-tuned; AGE un-tuned on eval. Raw:
`assertion_governance/eval_results/evaluation_v1.json`
(regenerate: `python3 -m assertion_governance.evaluation`).*

## Primary results (eval, n=229)

| Method | Agreement | Unsupported-escape | Qual recall | Qual prec | Esc recall | Esc prec | Agree hi-risk | Agree lo-risk |
|---|---|---|---|---|---|---|---|---|
| A none | 0.24 | **1.00** | 0 | 0 | 0 | 0 | 0.24 | 0.24 |
| B confidence | 0.31 | 0.00 | 0 | 0 | 0 | 0 | 0.14 | 0.43 |
| C grounding | 0.38 | 0.44 | 0 | 0 | 0 | 0 | 0.31 | 0.43 |
| D entailment | 0.69 | 0.24 | 0 | 0 | 0 | 0 | 0.53 | 0.82 |
| E rule-qualify | 0.31 | 0.82 | 0.47 | 0.44 | 0 | 0 | 0.31 | 0.31 |
| F authority | 0.37 | 0.49 | 0 | 0 | 0.35 | 0.42 | 0.43 | 0.33 |
| G grounding+entailment | 0.83 | **0.00** | 1.00 | 0.71 | 0 | 0 | 0.59 | **1.00** |
| **G_risk** (G + risk rule) | **1.00** | **0.00** | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| **AGE** (engine) | **0.97** | **0.00** | 0.80 | 1.00 | 1.00 | 0.87 | 0.94 | 1.00 |

## Paired comparisons (McNemar-style discordance)

| Comparison | AGE-only correct | Other-only correct | χ² | Reading |
|---|---|---|---|---|
| AGE vs D (entailment) | 64 | 0 | 64.0 | AGE dominates the strongest single signal |
| AGE vs G (grounding+entailment) | 40 | 6 | 25.1 | **AGE significantly beats G** (risk overlay) |
| AGE vs G_risk (G + risk rule) | **0** | 6 | 6.0 | **G_risk strictly dominates AGE** — AGE beats it on *zero* items |

Adversarial-to-AGE subset (n=12): AGE error rate **0.0** — it does **not** over-escalate
well-supported high-risk claims.

## Findings

1. **The delivery decision needs more than any single existing signal.** Confidence (0.31),
   grounding (0.38), entailment (0.69), authority (0.37) all fall well short, and most carry
   dangerous unsupported-escape rates (grounding 0.44, entailment 0.24, authority 0.49, none 1.0).
   The safety-critical metric alone rules out single signals.

2. **AGE beats every *existing-technique* baseline by the preregistered margin.** Agreement 0.97
   vs the best combined baseline G at 0.83 (+0.14 > 0.05; χ²=25.1), and unsupported-escape 0.00.
   By the Phase-3 rule, AGE is **SUPPORTED against existing techniques.**

3. **But the anti-circularity decisive test fails.** A trivial composition — grounding+entailment
   **plus a risk rule** (G_risk) — reproduces the ground truth **exactly (1.00)** and **strictly
   dominates the AGE engine** (G_risk beats AGE on 6 items; AGE beats G_risk on **0**). The
   dedicated engine is, if anything, slightly *worse* than the trivial rule, because its continuous
   thresholds misclassify a few boundary items (escalation precision 0.87 vs 1.00; qualification
   recall 0.80 vs 1.00).

4. **AGE's entire advantage over existing techniques is the RISK overlay, concentrated in
   high-risk domains.** G (risk-blind) already scores **1.00 on low-risk** items — there is no room
   for AGE to add value there. AGE's gain over G is on high-risk items (0.94 vs 0.59). Remove the
   risk dimension and AGE ≈ G.

5. **QUALIFY transform is a genuine distinct capability** (a scoped rewrite), but it is a
   *presentation/transform* feature, not a *decision* advantage — and it can be attached to G_risk.

## What this means for the primary question

> Can an Assertion Governance layer provide measurable value beyond existing techniques?

- **Beyond single techniques (confidence/grounding/entailment/authority): YES**, clearly and
  safely (agreement +0.14 to +0.66; escape 0.00 vs 0.24–1.00).
- **Beyond a trivial composition of existing signals (grounding+entailment + a risk rule): NO.**
  The G_risk composition reproduces ground truth exactly and dominates the dedicated engine. The
  "assertion governance function" is real, but it **decomposes into existing signals + a risk
  overlay** — it does not require a novel engine.
- **The measurable value is risk-concentrated:** it appears only where risk changes the disposition
  (high-risk escalation), i.e. in high-risk domains.

## Statistical honesty

The dataset is synthetic and the ground-truth rubric is, by construction, expressible as
grounding+entailment+risk — which is *itself the finding* (the decision decomposes into existing
signals). The engine was given the same inputs a deployed AGE would receive and still did not beat
the trivial composition. n=229 with clear, large discordance margins (χ² 6–64), so the direction is
not a small-sample artifact — though external validity (real model outputs, real NLI noise, human
disposition labels) is untested (see limitations).
