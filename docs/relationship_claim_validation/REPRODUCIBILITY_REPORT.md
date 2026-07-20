# Reproducibility Report (v0.1)

> Scope: self-contained synthetic experiment; deterministic (non-LLM) judges.

---

## 1. Determinism

- Two consecutive full runs (`python -m relationship_claim_validation.runner`)
  produced **byte-identical** JSON output (verified with `diff`).
- No wall-clock, no RNG except the bootstrap, which is seeded (`20260720`) and
  therefore deterministic.
- The test `test_two_runs_match` asserts run-to-run identity as a gate.

## 2. Frozen-hash lock

`runner.hidden_lock()` recomputes content hashes of the frozen components and the
corpus each run (`HIDDEN_LOCK.md`). The persisted
`results/run_v0_1.json` carries the locked hashes:

| Component | Hash (SHA-256) |
|---|---|
| frozen_components | `e4a966f9…dc1d2f7` |
| corpus (public) | `727b27af…21dc16` |
| documents | `63dff7dd…09e4e2` |

## 3. How to reproduce

```
python -m pytest relationship_claim_validation/tests/ -q
python -m relationship_claim_validation.runner            # prints the result JSON
```

Both are Python 3.11+ standard-library only; no external services, no network, no
LLM.

## 4. Prior-lock / drift verification

**N/A.** There is no prior experiment lock, corpus, or pipeline in this repository
to verify zero drift against — this was confirmed by exhaustive search before the
track was built. The only "priors" this commit could affect are other tracks, and
`git status` confirms this commit **adds** files only (nothing else modified) — so
"all prior artifacts remain byte-identical" holds by construction.

## 5. Calibration checks (all pass)

| Calibration precondition | Result |
|---|---|
| V0 disabled = identity pass-through (retain all as SUPPORTED) | pass |
| deterministic checks are pure functions | pass |
| judges are deterministic | pass |
| two full runs byte-identical | pass |
| public projection exposes no gold | pass |
| package imports nothing from other tracks | pass |

(9/9 tests pass: `relationship_claim_validation/tests/test_claim_validation.py`.)
