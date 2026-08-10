# FEASIBILITY_AUDIT — ActionGate Context Span-Ablation

**What this is.** A narrow, cheap falsification experiment that measures whether
ActionGate-aware context compression has enough theoretical and empirical room to
justify building a compressor — *before* any compressor, SCC, USE, or learned
retention model is written. It reuses the **real deterministic ActionGate
evaluation path** and ablates context spans to see which ones actually change the
canonical envelope, the decision, or the assurance requirements.

**What this is NOT.** Not a compressor, not a product, not a validation of one.
The corpus is authored-synthetic, so by construction (origin lock) this run emits
**no scientific/product verdict** — only a pipeline-verified, indicative-only
signal.

---

## Headline result (this run)

- **Mechanical verdict: `SYNTHETIC_NO_SCIENTIFIC_VERDICT`** — correct and expected.
  Synthetic data can verify the pipeline; it can never decide the product.
- **Pipeline path verified:** the labeler drives the real frozen gate end-to-end
  and detects every effect class (envelope / decision / assurance / structure /
  redundancy / interaction / extractor-sensitivity).
- **Indicative-only (NON-AUTHORITATIVE):** `EXTRACTOR_NOT_RELIABLE` — extractor
  instability 18.8% (> the 10% preregistered bound), driven by the Tier-3
  held-out paraphrase split (45.5%). This is a *demonstration that the metric
  bites*, not a claim about real data.

| metric (token-weighted, all tiers) | value |
|---|---|
| true decision-critical fraction | 39.2% |
| true critical-union fraction | 54.6% |
| conservative protected fraction | 55.6% |
| detector recall / precision (P0) | 78.3% / 76.9% |
| oracle compression ceiling | 45.4% |
| deployable compression ceiling | 44.4% |
| interaction miss rate | 13.5% |
| extractor-instability rate | 18.8% |
| cache-adjusted net savings | 35.3% |

(Full, regenerable table in `results/RESULTS_RECORD.md`.)

**Read these numbers as artifacts of hand-authored fixtures, not findings.** They
exist to prove the instrument works and that the thresholds discriminate. The
fixtures were deliberately built dense (to exercise every effect class), which is
exactly why the indicative critical fraction is ~55% — not a measurement of real
context.

---

## What the experiment establishes (validly, on synthetic data)

1. **The instrument works.** `F` (context→envelope) and `D` (envelope→decision)
   are the real ActionGate functions via a thin adapter; a fixed clock and fixed
   valid UUIDv4 `action_id` make every ablation a clean content diff. Verified
   flips include `ALLOW_WITH_CONSTRAINTS→DENY`, `ALLOW→SIMULATE_AND_RETRY`,
   `ALLOW→ESCALATE_TO_HUMAN`, and `DENY→ALLOW`.
2. **Effect classes are separable and not collapsed.** A span that changes an
   amount (envelope) is labelled differently from one that flips the outcome
   (decision) or one that changes a required approval/credential-scope while the
   outcome holds (assurance). Multi-label is preserved; the critical union counts
   each span once (tested — no double counting).
3. **Single-unit ablation is provably insufficient by itself.** Duplicated facts
   (redundancy-set) and jointly-sufficient spans (linked-pair) are individually
   inert under single ablation and only surface under group/redundancy/pair
   ablation. The interaction-miss rate quantifies this.
4. **Extractor error is separated from semantics.** Where the narrow realistic
   extractor and the structured oracle disagree on criticality, the ablation is
   labelled `EXTRACTOR_SENSITIVE` and excluded from ground-truth critical sets, so
   NLP instability is never mistaken for action-relevance. Tier-3 paraphrase makes
   this measurable.
5. **The precision/ceiling tension is real and observable.** The recall-favoring
   rule detector over-marks (precision as low as ~44–65% on table/JSON/rollback
   fixtures), so the *deployable* ceiling sits below the *oracle* ceiling — the
   central risk any real study must quantify.
6. **Prompt caching can erase the opportunity.** With 80% cacheable context and
   15% overhead, the same removable fraction yields **negative** net savings
   (demo 8). The economic gate is not a formality.

---

## What it does NOT establish (and cannot, here)

- **Nothing about real context.** The true action-relevant fraction of *real*
  enterprise agent context is unknown; the ~55% here is a property of the
  fixtures. The entire product case rides on that unknown number being **small**,
  and this run does not measure it.
- **No compressor performance.** No compressor exists in this package.
- **No verdict.** The origin lock is the point: a positive result cannot be forced
  from synthetic data.

---

## The one number that decides the product

> On a real, provenance-documented corpus: what fraction of context is
> decision/assurance-critical (the oracle ceiling), and does a recall-1.0 detector
> leave a deployable ceiling above ~25% after prompt caching and overhead?

If that fraction is large (dense context), the verdict branch is
`CONTEXT_INTRINSICALLY_DENSE` and the product should **not** be built (demo 7). If
the fraction is small but the detector over-protects, it is
`DETECTOR_PRECISION_BOTTLENECK` (detection must improve first). If both are healthy
and economics clear, it is `ABLATION_OPPORTUNITY_SUPPORTED` (demo 9). This harness
computes that branch deterministically — it just needs real data plugged into the
same, unchanged thresholds.

---

## How to run

```bash
cd experiments/actiongate_context_ablation
python -m pytest tests/ -q          # 19 tests: gate path, effects, metrics, lock, determinism
python -m demos.run_demos           # the 10 required demonstrations
python -c "from actiongate_context_ablation import runner; \
           print(runner.render_results_md(runner.run_study()))"
```

## To make it a real study

Swap the authored fixtures for a `NATURALISTIC_REPO`/`FIELD_REAL` corpus with
documented provenance and a truly untouched held-out split; re-run with the
**same** frozen thresholds (PREREGISTRATION.md). Only then does the mechanical
verdict carry weight. Do not build a compressor before that verdict says the
opportunity is real.
