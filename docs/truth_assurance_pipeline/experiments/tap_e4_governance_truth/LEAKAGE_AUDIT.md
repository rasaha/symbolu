# TAP-E4 — Leakage & Integrity Audit

## 1. Primary experimental limitation (state plainly)

The eval split is **content-hash locked and preregistered, but was inspected during
iterative engineering**. It is a **locked development evaluation, not an untouched or
interpreter-blind holdout.** Some implementation decisions followed observation of how
baselines behaved on the corpus as a whole. The verdict `PASS_WITH_LIMITED_CLAIM` therefore
attests to **mechanism/construction validity on this study's synthetic corpus**, not to
blind generalization. This is the same honesty posture as TAP-E1.1/E2/E3.

## 2. Leakage controls in place

- **Locked eval inputs.** `eval_inputs_hash = c28e23f3…` over the public view of the 15 eval
  cases (`n_eval = 15`); recorded in `experiments/experiment_lock.json`.
- **Dev-only selection.** The baseline is chosen as the simplest (A..F) passing all gates on
  **DEV**; `select_config` never reads eval metrics. The lock records both the dev gate-pass
  table and the eval gate results.
- **Frozen mechanism hash.** `frozen_components_hash = 9e44afd7…` folds every resolver
  module, the metrics, the gate list, and the baseline definitions; any change to the
  mechanism changes the hash.
- **Preregistration.** `experiments/preregistration.json` fixes the baselines, the 14 gates,
  the 10 critical-failure classes, the selection rule, and the verdict rule **before** the
  locked-set scoring.
- **Gold-free loader.** `loader.py` exposes only situation + candidate names; the
  `expected_authority`/disqualifier gold is never in the public view.
- **Independent gold authorship.** No upstream (E1/E2/E3) gold is reused as governance gold;
  the corpus and its ground truth are new for this layer.

## 3. Determinism

Verified byte-identical result hash and `frozen_components_hash` across
`PYTHONHASHSEED ∈ {0, 1, 7, 42, 123}`. No `set`/`dict` iteration order affects any decision;
every sort has a stable name tiebreak, and tie *detection* deliberately ignores that
tiebreak so genuine ties surface as conflicts.

## 4. Upstream integrity (frozen layers untouched)

TAP-E1, TAP-E1.1, TAP-E2, and TAP-E3 are consumed **through their frozen public interfaces
only** and are **byte-identical** — the sole working-tree change for this phase is the new
`tap_e4_governance_truth/` package and this `docs/.../tap_e4_governance_truth/` directory.
Full repository regression after the change: **124 tests pass** (all upstream suites green).

## 5. Threats to validity (residual)

- **Synthetic corpus, this study only.** 30 cases; no real policy documents. Results do not
  transfer to production governance without new, blind, real-world evaluation.
- **Documented model ≠ law.** The authority hierarchy and precedence rules are a versioned
  design decision, not legal ground truth.
- **Perfect upstream inputs.** Confidence-1.0 relationship inputs isolate the governance
  layer but understate real-world difficulty; upstream extraction error is out of scope here.
- **Development-inspected eval.** As in §1, the locked set informed engineering; a future
  blind holdout is required to claim generalization.

## 6. Future validation (to lift the "limited" qualifier)

1. A **blind** governance holdout authored by a separate party, scored once.
2. Real (redacted) policy/regulation/contract corpora with independent legal review of the
   gold.
3. End-to-end runs on **noisy** upstream records (real E2/E3 output) to measure error
   propagation.
4. Adversarial expansion: nested exceptions, multi-jurisdiction overlap, partial
   supersession, conflicting emergency overrides.
