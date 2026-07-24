# Limitations (Assertion Governance)

*Phase 10. Failure modes, overlaps, and the boundaries of what the evaluation licenses. Stated
before the recommendation so the recommendation is read against them.*

## Failure modes observed

- **The dedicated engine underperforms a trivial rule.** AGE (0.97) < G_risk (1.00). Its
  continuous thresholds (0.12/0.38) misclassify boundary items the categorical rubric gets right:
  escalation precision 0.87 (a few false escalations), qualification recall 0.80 (some high-risk
  QUALIFYs pushed to ESCALATE). A dedicated engine buys nothing here and costs a little.
- **False escalations.** AGE escalates some items a human need not review (precision 0.87) — this
  is *human burden*, the main operational cost of an over-eager assertion layer.
- **Risk-blindness is fatal to the cheap baselines.** Grounding+entailment (G) collapses to 0.59
  agreement on high-risk items precisely because it ignores risk — the exact place a governance
  layer is supposed to help.

## Where confidence alone is enough

- Never, for the delivery decision: confidence scored 0.31 and is orthogonal to evidence support
  (confident-but-unsupported items are its blind spot). Confidence is useful *inside* the support
  estimate, not as the decision.

## Where grounding alone is enough

- **Low-risk domains.** Grounding+entailment (G) already reaches **1.00 on low-risk** items. In
  casual/coding contexts, an assertion-governance layer adds nothing measurable over grounding+
  entailment.

## Where Assertion Governance clearly helps

- **High-risk domains** (medical/legal/financial): the risk-sensitive escalation lifts high-risk
  agreement from 0.59 (G) toward 1.00, and drives unsupported-escape to 0.00 (vs 0.24–1.00 for
  single signals). This is the one region with a clear, safety-relevant win.
- **The QUALIFY transform**: no baseline produces a scoped rewrite of an overclaim; AGE does. This
  is a genuine capability, though a *presentation* one, not a *decision* one.

## Overlap with existing work

- The decision function **decomposes** into grounding + entailment + a risk rule (G_risk = 1.00).
  So Assertion Governance is not a new *capability* so much as a *composition* of existing signals
  with a risk overlay and a rewrite step. Its novelty is organizational (a named layer), not
  algorithmic.

## False positives / false negatives

- False positives (over-governance): false escalation (AGE precision 0.87) and, for the evidence-
  blind rule baseline E, rampant false qualification. Cost = human burden + latency.
- False negatives (under-governance): the safety-critical case is unsupported-escape; AGE and the
  two composition baselines (G, G_risk) achieve 0.00, single signals do not.

## Latency / cost / human burden

- Compute is trivial (deterministic rules). The real cost is **human burden from escalation** —
  minimized only by good escalation precision, where the dedicated engine is *worse* than the rule.

## External-validity limitations (the big ones)

- **Synthetic corpus.** The ground-truth rubric is, by construction, expressible as grounding+
  entailment+risk — which is *why* G_risk hits 1.00. On **real** model outputs with **noisy** NLI/
  grounding signals and **human** disposition labels, the clean decomposition may not hold, and a
  richer/learned engine might recover value a hand rule cannot. **This is untested.**
- **No real NLI/grounding noise.** AGE and the baselines received clean relation labels + support
  scalars. Real upstream noise would degrade all methods, possibly unevenly.
- **Single annotator model (the rubric).** No inter-annotator agreement; "human agreement" is
  proxied by the rubric itself.
- **n=229 eval.** Margins are large (χ² 6–64) so the *direction* is robust, but domain-level and
  rare-disposition estimates are thin.

## Net

The evaluation robustly establishes the *decomposition* (delivery = grounding+entailment+risk) and
the *risk-concentration* of value. It does **not** establish that a dedicated engine is needed
(evidence says the opposite here), and it does **not** settle the real-world case, where noisy
signals could change the answer.
