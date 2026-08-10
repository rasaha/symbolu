# COMPRESSOR_PREREGISTRATION — ActionGate Context Minimization prototype

**Frozen before measurement.** Builds the first extractive compressor on the
existing corpus and frozen protected-span detector. No changes to ActionGate, the
corpus, the extractor, or the detector. No SCC/USE. Purely extractive (no rewrite,
paraphrase, or summarization).

## Objective (not maximum compression)

    maximize token reduction
    subject to:  protected-span recall = 100%
                 AND ActionGate decision invariance (fail-closed)

## Success criteria (measured, honest)

The prototype is successful only if it demonstrates:

1. **100% protected recall** at every budget.
2. **Zero ActionGate decision changes** (envelope + outcome + dispositive rules +
   applied constraints invariant) at every budget.
3. **Meaningful task-quality preservation** — decision-relevant information retained.
4. **Positive net token savings** after compression overhead.

## Budgets

Target compression ratios {10, 20, 30, 40, 50, 60, 70}%. Report per budget: actual
token reduction, decision preservation, protected recall, protected precision,
restored spans, fallback frequency, task accuracy (proxy), latency, cost reduction.

## Fail-closed (preregistered)

If the compressed context changes envelope / outcome / dispositive rules /
constraints / evidence-or-approval requirements (the latter two enforced via the
decision outputs, since a *required* item's removal changes the outcome while a
*redundant* item's removal does not), then restore the necessary spans; if
invariance still fails (e.g. joint effects), fall back to the original context. The
compressor must never knowingly change the decision.

## Baselines

1. No compression. 2. Lossless structural only. 3. Protected-span only (max safe).
4. Full prototype (budgeted). 5. Generic protection-*unaware* extractive selection —
a stand-in for LLMLingua-2-style selection (the actual model is not installed in
this environment) — to measure decision damage from protection-blind compression.

## Downstream-task benchmark — HONEST SCOPE

No runnable open-weights LLM is present (no `transformers`, no checkpoints; only a
canned `MockLLMAdapter`). The task metric is therefore a **deterministic
information-preservation proxy** that upper-bounds real LLM accuracy: a question is
answerable iff the span(s) carrying its ground-truth answer are retained.
Decision-relevant vs incidental questions are reported separately. A real LLM
benchmark (accuracy/latency/cost) is **deferred** and is the gate to an
unconditional GO.

## Recommendation rule (measured evidence only)

- `STOP` if any success criterion fails, or max safe reduction < 25%.
- `LIMITED_GO` if all criteria pass on this naturalistic corpus **with the proxy
  task** (the ceiling achievable without a real LLM + real customer data).
- `GO` reserved for a later run that confirms criterion 3 with a **real LLM on real
  customer data**.

## Adversarial testing

Inject a NON-protected span that carries a decisive gate fact (a deliberate detector
miss) and verify fail-closed restores it (or falls back) with decision invariance
preserved.

## Determinism

All measurements deterministic except wall-clock latency (reported, excluded from
any equality/hash check). Reruns of every rate/fraction are identical (tested).
