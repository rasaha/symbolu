# Hidden Lock (v0.1)

Content hashes of the frozen components and the corpus, computed by
`runner.hidden_lock()` and persisted in `relationship_claim_validation/results/run_v0_1.json`.

> **No prior lock exists.** The brief's "verify all prior experiment locks / zero
> drift" is **N/A**: there is no prior lock, corpus, or experiment in this
> repository to compare against. This lock is created for this new track so a
> **future** re-run can prove zero drift against *this* baseline.

---

## 1. Locked hashes (SHA-256)

| Component | Hash |
|---|---|
| frozen_components (deterministic rules, judge rules, legal types, bootstrap params) | `e4a966f9f518899607927666abca5c7b886fcd0c059c686529232f770dc1d2f7` |
| corpus (public projection) | `727b27aff8039472462bebed7dba1902671f28e86539d1fa678167834e21dc16` |
| documents (spans + assertions) | `63dff7dd13a21d6ed16312a0d3fc818770a833000aefaf6dcce32ed01909e4e2` |

## 2. What is frozen before results

- Judge rules (`judges.py`) and deterministic rules (`deterministic.py`).
- The legal relationship-type set.
- The bootstrap parameters (seed `20260720`, 2000 resamples).
- The synthetic corpus (claims + documents).

## 3. Verification

Re-running `python -m relationship_claim_validation.runner` recomputes these
hashes; if any frozen component or the corpus changes, the corresponding hash
changes. Two runs in this session produced **byte-identical** output
(`REPRODUCIBILITY_REPORT.md`).
