# MILESTONE_PREREGISTRATION — Extraction + Protected-Span Quality

**Frozen before measurement.** This milestone improves ONLY the two bottlenecks the
naturalistic study identified. It does not build a compressor, SCC, USE, or any new
theoretical formula, does not modify ActionGate, and reuses the existing corpus
unchanged. The gate-derived labels are reused as-is (no manual relabeling).

## Hypotheses

- **H1 (extractor).** A multi-stage extractor (deterministic structured → semantic
  frames → independent fuzzy validator with fail-closed) reduces held-out extractor
  instability from ≈41% to **< 10%**, and to < 10% in every domain, without
  regressing DEV/VALIDATION.
- **H2 (detector).** A detector trained on the deterministic ActionGate ablation
  labels (DEV+VALIDATION only) substantially increases held-out protected-span
  **precision** over the keyword baseline while **maintaining recall** (safety).

## Frozen targets (engineering goals)

| target | threshold |
|---|---|
| held-out extractor instability | < 10% |
| per-domain extractor instability | < 10% (all domains) |
| held-out protected recall (fail-closed hybrid) | = 100% (never drop a decision-relevant fact) |
| held-out protected precision gain over baseline | ≥ +20pp ("substantial") |

## Anti-leakage protocol

- The protected-span detector is trained on **DEV + VALIDATION units only**;
  HELDOUT_TEST is never used for training or threshold tuning.
- Stage-3 validator thresholds (`CONFIRM=0.50`, `RECOVER=0.60`) are calibrated on
  DEV/VALIDATION phrasing (true-concept fuzzy sims ≈ 0.9 vs cross-concept bleed
  ≈ 0.35–0.45) and frozen here. Held-out phrasings were not inspected to set them.
- The semantic lexicon uses **general** domain synonyms (approve/sign-off/authorize/
  greenlight …), not held-out-specific strings — the goal is paraphrase
  generalization, not memorization.
- The corpus is not modified. ActionGate is not modified.

## Adversarial testing

- The HELDOUT_TEST split is itself the paraphrase adversary (recognized phrasing in
  DEV/VALIDATION, unseen paraphrases in held-out).
- An explicit perturbation test (distractor-sentence injection + partition-preserving
  noise) checks that instability stays < 10% and hybrid recall stays 100% under
  added noise (see `tests/test_extractor_v2.py`).

## Determinism

- Structured/semantic/validator stages are pure functions. The detector is a
  from-scratch multinomial logistic regression with zero initialization and fixed
  epochs/lr/L2 — no randomness. Reruns are bit-identical (tested).

## Honest-reporting commitments

- Report before/after for both bottlenecks, per domain and held-out.
- Flag that near-perfect precision reflects the corpus's clean structural separation
  and will not survive intact on messier real data.
- If targets are not met, report the negative result and recommend stopping.
