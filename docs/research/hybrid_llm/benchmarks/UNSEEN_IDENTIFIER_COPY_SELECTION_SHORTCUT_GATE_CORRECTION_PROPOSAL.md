# PROPOSAL (Option B) — sampling-aware shortcut gate correction

**Status: DRAFT PROPOSAL FOR REVIEW. Nothing here is applied, merged, executed, or re-run.** This
document proposes a single, bounded correction to the shortcut-precheck **decision rule** and states
the governance chain that must follow before any re-run. It changes no numeric science value and makes
no capability claim. Standing invariants preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` ·
`E1_TEMPORAL_TRANSFER_PARTIAL` · `KDA_VALIDATION_BLOCKED`.

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

## 4. Proposed change (exact)
Add a sampling-aware, multiple-comparison-corrected decision. A baseline **blocks** iff it is
practically **and** statistically above the practical bound `p0 = chance + 0.05`:

```
p0        = chance + 0.05                         # unchanged practical-equivalence margin
se0       = sqrt(p0*(1-p0)/n)                      # binomial SE under the boundary null, at observed n
z         = (score - p0) / se0                     # one-sided
m         = number of (split,baseline) comparisons in the cohort
alpha_per = 1 - (1 - 0.05)**(1/m)                  # Šidák correction, family-wise error rate 0.05
z_crit    = Phi^{-1}(1 - alpha_per)
BLOCK     = (score > p0) AND (z > z_crit)
```

### Exact patch to `experiments/unseen_identifier_copy_selection/shortcuts.py`
```python
# --- new imports / constants ---
from statistics import NormalDist

SHORTCUT_BOUND = 0.05     # practical-equivalence margin (UNCHANGED)
SHORTCUT_FWER  = 0.05     # family-wise error rate for the multiple-comparison correction (NEW)

def _sidak_zcrit(m: int, fwer: float = SHORTCUT_FWER) -> float:
    """One-sided z critical value after a Šidák correction over m comparisons."""
    alpha_per = 1.0 - (1.0 - fwer) ** (1.0 / max(1, m))
    return NormalDist().inv_cdf(1.0 - alpha_per)

def _baseline_blocks(score: float, n: int, chance: float, m: int) -> bool:
    """Block a baseline ONLY if it is BOTH practically (> chance+0.05) AND statistically (beyond
    Šidák-corrected sampling noise at the observed n) above the practical bound. On uniformly-random
    opaque identifiers this rejects chance-level noise while still catching a genuine leak."""
    p0 = chance + SHORTCUT_BOUND
    if score <= p0 or n <= 0:
        return False
    se0 = (p0 * (1.0 - p0) / n) ** 0.5
    if se0 == 0.0:
        return score > p0
    return (score - p0) / se0 > _sidak_zcrit(m)
```
Then replace the two flat comparisons:
- in `shortcut_scores`, per split (n = len(sel), m = 12 × #selection-splits):
  `split_pass = not any(_baseline_blocks(v, len(sel), chance, m) for v in baselines.values())`
- in `aggregate_shortcuts`, per split (n = pooled applicable count, m = total comparisons):
  `passes[name] = not _baseline_blocks(score, applicable, chance, m)`

The reported per-split/per-seed scores, counts, `chance`, and `bound` fields are **unchanged**; only
the boolean `pass`/`all_pass` decision becomes sampling-aware. (`competence_floor = chance+0.05` stays
as a reported field.)

## 5. Validation (reproducible: `results/unseen_identifier_copy_selection/optionb_gate_validation.py`)
Computed on already-generated data; parameters (FWER 0.05, Šidák, one-sided normal) fixed a priori:

| Cohort | frozen gate | proposed gate | proposed blocks (real data) | control: inject a 0.60 leak |
|---|---|---|---|---|
| seen | `all_pass=False` | **`all_pass=True`** (m=72, z_crit=3.19) | NONE | **blocks** (z=5.98) |
| unseen | `all_pass=False` | **`all_pass=True`** (m=72, z_crit=3.19) | NONE | **blocks** (z=5.98) |

→ The proposed rule **rejects the chance-level noise** that falsely blocked development (worst real
exceedance 0.4056 → z≈0.6 ≪ 3.19) while **still catching a genuine leak** (a baseline reliably above
`chance+0.05` yields z≈6 and blocks). It does not "rubber-stamp" — it is strictly a correction of the
test's statistical validity.

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

## 9. Test plan (fixture-only)
- Update `tests/experiments/unseen_identifier_copy_selection/test_shortcuts_complete.py`: assert
  `_baseline_blocks` blocks a clear leak (e.g. 0.60 at n=180) and does **not** block chance-level
  values (e.g. 0.40 at n=60/180); assert `z_crit` monotonic in `m`.
- `PYTHONPATH=. pytest -q tests/experiments/unseen_identifier_copy_selection` must stay green.
- No reserved seed appears in any test (fixture 993000–993004 only).

## 10. Claim boundary
This proposal is a **test-validity correction**, not a capability change. It emits no verdict, consumes
no seed, and does not alter the research question, the model, the representation, the identifier design,
or any capability gate. Approving it authorizes only the fixture-tested code change + audit + a *fresh*
development authorization — not a final run.
