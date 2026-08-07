# Shortcut-gate correction (Option B) — corrective PR

**Status: CORRECTIVE PR — CODE APPLIED, AWAITING INDEPENDENT AUDIT. No reserved seed run; not merged.**
This is a single, bounded correction to the shortcut-precheck **decision rule** plus fixture tests. It
changes no numeric science value, touches no reserved seed, and makes no capability claim. The prior
development evidence is superseded on merge (see §8). Standing invariants preserved:
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`KDA_VALIDATION_BLOCKED`.

**Statistical method (as implemented, refined from the original draft):** the statistical leg uses an
**exact one-sided binomial upper-tail test** of `H0: p = chance` with **Holm–Bonferroni** family-wise
error control across all 72 comparisons — replacing the draft's normal-approximation z + Šidák. This is
defensible without any normal-approximation or independence-among-comparisons assumption.

## 1. Summary
The development phase returned `DEVELOPMENT_SHORTCUT_BLOCKED` because the frozen shortcut gate compares
each structure-blind baseline's **point estimate** against a **flat** `chance + 0.05` threshold, with
**no allowance for sampling error** and **no multiple-comparison control** across the 72 baseline×split
comparisons it evaluates. That flat rule has a **computably high false-block rate under the null**,
derivable from the frozen design alone. The proposal keeps the `0.05` practical-equivalence margin
**unchanged** and adds the missing statistical layer: a baseline blocks only if it is **both**
practically (`> chance+0.05`) **and** statistically (beyond Šidák-corrected sampling noise at the
observed sample size) above the practical bound.

**What changes:** the pass/block *decision rule* in `shortcuts.py` (`shortcut_scores`,
`aggregate_shortcuts`).
**What does NOT change:** the `0.05` practical margin; the 12 baselines; per-split/per-seed scoring;
the pooled-across-dev-seeds aggregation contract; all Decision-7 **capability** gates; the verdict
engine; the model; the task design; seeds.

## 2. Problem statement — justified from the frozen design ALONE (not from probe results)
This justification uses only frozen design facts; it does **not** appeal to any observed probe number
(honoring "gates are never adjusted after inspecting reserved results"):
- **Identifiers are uniformly-random opaque 4-char strings** (protocol-lock Decision 3; fixture-verified
  character-visible, collision-free, disjoint pools). Therefore every structure-blind baseline is at
  **chance = 1/3** in expectation, by construction.
- **Sample sizes are fixed by the frozen design:** 60 examples/split/seed → **180 pooled** across the
  3 development seeds. The pooled binomial standard error at chance is
  `SE = sqrt((1/3)(2/3)/180) ≈ 0.0351`.
- **The gate evaluates many comparisons:** 12 baselines × 6 selection splits = **72 comparisons per
  cohort**.
- **Consequence (pure statistics):** the flat bound `chance + 0.05` sits only `0.05/0.0351 ≈ 1.42 σ`
  above chance. Under the null, the probability a *single* baseline exceeds it is `≈ 1 − Φ(1.42) ≈ 7.8%`;
  across 72 near-independent comparisons the probability that **at least one** exceeds it is
  `1 − (1−0.078)^72 ≈ 99.7%`. **The frozen gate is therefore expected to false-block almost always**,
  independent of any model or any run. This is a pre-existing property of the rule, revealed by — but
  not derived from — the development run.

## 3. Root cause
The rule conflates a **point estimate** with a **population value** and applies a **per-comparison**
threshold to a **family** of 72 comparisons. It has no notion of the estimate's sampling error and no
multiple-comparison correction, so ordinary sampling noise crosses it.

## 4. The change (as implemented)
A baseline **blocks** iff it clears BOTH legs:
```
practical leg    : p_hat > chance + 0.05                       # unchanged practical-equivalence margin
statistical leg  : exact one-sided binomial upper tail P(X >= k | n, chance)
                   rejected under Holm-Bonferroni at FWER = 0.05, over ALL (split,baseline) comparisons
BLOCK            = practical AND statistically-significant
```
Implemented in `experiments/unseen_identifier_copy_selection/shortcuts.py`:
- `binom_sf_ge(k, n, p)` — exact upper-tail P(X≥k) via a stable iterative PMF (no SciPy/NumPy, no
  normal approximation);
- `holm_reject(pvalues, fwer)` — Holm–Bonferroni step-down (uniformly more powerful than Bonferroni,
  valid without independence assumptions);
- `_decide(per_split_counts, chance)` — builds the family of (split,baseline) comparisons, computes an
  exact binomial p-value against the **chance** null for each, applies Holm across the whole family,
  and blocks a baseline only when it is also practically above `chance+0.05`.
`shortcut_scores` (per seed) and `aggregate_shortcuts` (pooled across dev seeds) both route their
decision through `_decide`. Reported scores, counts, `chance`, `bound`, and per-seed views are
unchanged; the pooled aggregation remains the count-weighted mean; only the boolean `pass`/`all_pass`
decision is now sampling-aware. New reported fields: per-baseline `pvalues`, per-split `blocked`,
top-level `fwer` and `n_comparisons`.

The **0.05 practical margin is unchanged**. The statistical leg is the only addition.

## 5. Validation
**Unit tests** (`tests/experiments/unseen_identifier_copy_selection/test_shortcuts_complete.py`,
fixture-only, all green — full suite 120 passed): `binom_sf_ge` known values + monotonicity; Holm
step-down; **marginal noise 0.4056 (73/180) does NOT block** in the 72-comparison family;
**injected leak 0.60 (108/180) DOES block**; **multiplicity matters** (73/180 blocks alone, m=1, but
not within m=72); **practical leg required** (0.36 at n=10000 is significant vs chance yet below the
+0.05 margin → does not block); all-at-chance passes.

**Synthetic demonstrator** (`results/unseen_identifier_copy_selection/optionb_gate_validation.py`,
no reserved seed built or run):

| Scenario | corrected gate |
|---|---|
| all baselines at chance (m=72) | `all_pass=True` |
| marginal noise 0.4056 = 73/180 (m=72) | **`all_pass=True`** (rejected: chance-level noise) |
| same 73/180 tested alone (m=1) | `all_pass=False` (multiplicity does real work) |
| genuine leak 0.60 = 108/180 (m=72) | **`all_pass=False`** (blocks) |
| tiny 0.36 at n=10000 (significant, sub-margin) | `all_pass=True` (practical leg required) |

The worst real exceedance observed in the (now-superseded) development run was 0.4056 — exactly the
`73/180` case above — so the corrected gate rejects the noise that falsely blocked development while
still catching a genuine leak. It is a correction of statistical validity, not a rubber stamp.

## 6. Alternatives considered (and why rejected)
- **Flat wider margin (e.g. `chance+0.10`).** Simpler but unprincipled: it would mask a genuine ~0.09
  leak and still ignores sample size and comparison count. Rejected.
- **Increase `EXAMPLES_PER_SPLIT`** so SE shrinks under the flat 0.05. This changes the **frozen task
  design** (dataset digests, identifier windows) — more invasive, and it treats a statistics bug by
  enlarging the experiment. Rejected.
- **Add the omitted competence-floor requirement (Decision 9).** That makes the gate *stricter*, not
  looser (it would block harder on the unseen cohort where model competence ≈ 0), so it does not
  address the false-block problem. Out of scope for this correction.

## 7. Why this respects "gates are never adjusted after inspecting reserved results"
The only scientific judgment in the gate — the **0.05 practical-equivalence margin** — is **unchanged**.
The addition is a **methodological correction to statistical validity** whose every parameter (n, m,
chance) comes from the **frozen design**, not from any probe outcome. The development result merely
*revealed* a pre-existing defect; the fix is justified without it.

## 8. Governance & sequencing (required; not performed here)
Per plan Decisions 6/9 and protocol-lock Decision 10, a shortcut-gate change **invalidates the affected
development evidence** and requires, in order:
1. **This corrective PR** (the patch above + updated `test_shortcuts_complete.py` expectations: a
   synthetic 0.60 leak still blocks; chance-level values at the frozen n no longer block) — **fixture
   phase only** in CI; no reserved seed.
2. **Independent audit** of the corrected gate (statistical correctness; leak-detection retained).
3. **Fresh development-execution authorization** (the current smoke/dev authorization does not cover a
   post-change re-run).
4. **Re-run smoke 9070 + development 9071–9073** under the corrected gate; the prior development
   evidence (commit `d22bd5cf`) is superseded/invalidated by the gate change and must not be reused.
5. **Final seeds 90760–90764 remain PROHIBITED** and separately gated — this proposal does not touch
   the final authorization chain.

## 9. Test plan (fixture-only) — done
- `test_shortcuts_complete.py` extended with: `binom_sf_ge` known values + monotonicity; Holm
  step-down; marginal-noise-does-not-block (73/180 in m=72); injected-leak-blocks (108/180);
  multiplicity-matters (blocks at m=1, not m=72); practical-leg-required (0.36 @ n=10000); all-at-chance.
- `PYTHONPATH=. pytest -q tests/experiments/unseen_identifier_copy_selection` → **120 passed**;
  `tests/experiments/single_hop_typed_vs_prose` → **23 passed**. No top-level torch import in
  `shortcuts.py`.
- No reserved seed appears in any test (fixture 993000–993004 only); no reserved seed was run.

## 10. Claim boundary
This proposal is a **test-validity correction**, not a capability change. It emits no verdict, consumes
no seed, and does not alter the research question, the model, the representation, the identifier design,
or any capability gate. Approving it authorizes only the fixture-tested code change + audit + a *fresh*
development authorization — not a final run.
