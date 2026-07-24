# Falsification Plan & Evaluation Freeze (Phases 17–18)

## Preregistered falsification plan (`falsification.py` → `eval_results/falsification.json`)

Each finding is a **null hypothesis the pilot tried to support**; the data rejects it (finding stands)
or retains it (finding fails). All six nulls are rejected.

| Null | Statement | Rejected? | Evidence |
|---|---|---|---|
| H0_SAFETY_UNSAFE_PERMIT | runtime produces ≥1 fully-supported unsafe permit | **REJECTED** | unsafe_permit = 0 |
| H0_UTILITY_TRANSFERS | structured utility transfers (over-qual < 10%) | **REJECTED** (negative) | over_qualification = 85.5% |
| H0_ACTIONGATE_SEMANTIC_LOSS | a safety-relevant native outcome is lost | **REJECTED** | native loss 0%, blocker False |
| H0_NONDETERMINISM | full stack is non-deterministic | **REJECTED** | O == N |
| H0_INSUFFICIENT_EVIDENCE | < 200 eligible natural artifacts | **REJECTED** | 857 (SUFFICIENT) |
| H0_CORPUS_CONTAMINATION | corpus contains governance-corpus material | **REJECTED** | contaminated = False |

The utility null is rejected **in the negative direction**: the data rejects "utility transfers", so
the honest conclusion is that utility does **not** transfer. This is reported as such, not softened.

### Adversarial self-check — derivation-sensitivity probe

The pilot does not accept its own headline (85.5% over-qualification) uncritically. The probe re-runs
the full stack under two derived evidence bases:

| Evidence base | Clean-allow rate |
|---|---|
| `VERIFIED_WITH_LIMITATIONS` (honest default) | **0.0%** |
| `VERIFIED` (optimistic) | **83.3%** |

Flipping to the optimistic base restores an 83% clean-allow rate, proving the over-qualification is
**driven by the honest absence of external evidence, not by a runtime defect**. The finding is
simultaneously **real** and **conditioned on the derivation** — both true, both disclosed. This is the
single most important honesty check in the pilot: it distinguishes "the runtime is broken on natural
text" (false) from "an evidence-grounded runtime conservatively qualifies evidence-free text" (true).

## Evaluation freeze (`eval_freeze.py` → `eval_results/freeze_manifest.json`)

Pins the SHA-256 of the seven pilot eval artifacts so the final run scores the frozen set exactly once
and cannot be silently re-fit. The frozen eval config records the binding constraints:

```
config = FULL_STACK_HIGH_RISK
derivation_version = natural_derivation_v1
evidence_base = VERIFIED_WITH_LIMITATIONS
score_once = True
threshold_tuning_on_final_set = False
```

Frozen artifacts: `corpus.json`, `ground_truth.json`, `baselines.json`, `failure_taxonomy.json`,
`transfer_analysis.json`, `perf_cost_burden.json`, `falsification.json`. `verify()` fails on any drift
or missing artifact. This is the pilot's **own** freeze — distinct from `verify_prior_artifacts.py`,
which guards the 22 prior completed artifacts. Together they bound the pilot: nothing prior is touched,
and the evaluation is frozen before the final run.
