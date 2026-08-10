# Live-state audit — BindingSlots Confirmatory Replication

Audit performed before any change or training. Machine-readable form: [`LIVE_STATE.json`](./LIVE_STATE.json).

## Repository state

| Item | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default branch tip / starting commit | `ba665e42af8c60fd9aa9e7381020edc9a3d618bb` |
| Working branch | `claude/bindingslots-confirmatory-replication-d117c1` (env mandates `claude/` prefix; suggested `chatgpt/`) |
| Working tree at audit | clean |
| Existing confirmatory branch/PR | none |

## Merged prerequisites

- **PR #1300** — MERGED, merge commit `5f0cbe45`, merged 2026-08-03T09:43:05Z. Verdict
  `PARTIALLY_STABLE` → `NOT_READY_FOR_KDA_VALIDATION`; S formed 3/5 on holdout seeds 3–7.
- **PR #1319** — MERGED, merge commit `ba665e42` (= default tip), merged 2026-08-03T19:39:36Z.
  Verdict `PROVISIONALLY_STABILIZED` → `NOT_READY_FOR_KDA_VALIDATION`; **CR1 forms 4/5** fresh
  seeds 8–12 (B0 3/5, A+ 0/5), every forming seed causally slot-dependent, **seed 9 post-scaffold
  retention failure**.

`ba665e42` (PR #1319 merge) is verified an ancestor of, and equal to, the live default-branch tip.

## Frozen artifacts (verified)

- `experiments/phase_lc/results/abc.json` sha256 `b31989a3…` — matches the pinned value.
- All 15 frozen source/config hashes (models, evaluate, tasks_adapter, legacy slots, tasks,
  five_seed gates, stabilization gates/matrix/selection/interventions/stabilize/diagnostics,
  classifier, selected candidate) recomputed and **match** the values recorded in the merged
  `SELECTED_CANDIDATE.json`. See [`FROZEN_CR1_CONFIG.json`](./FROZEN_CR1_CONFIG.json).
- Architecture signature `6e8672bd…`; slot arm 2 000 104 params; A+ control 2 000 392 params.

## Verifiers at audit

| Verifier | Result |
|---|---|
| PR #1319 pre-registration integrity | 26 checks, 0 failures |
| lab verifier | 81 checks, 0 failures |
| historical-artifact protection | 8 checks, 0 failures |
| stdlib tests | 74 run, 0 failed |
| stabilization config tests | 19 passed |
| **confirmatory pre-registration integrity (new)** | 27 checks, 0 failures |

## Environment

Python 3.11.15, torch **2.2.2+cu121**, CPU, fp32, threads=4. The merged Stage B run used a
different torch build. The frozen protocol pins the optimizer/lr/betas/schedule, **not** the torch
build; and the confirmatory seeds (13–17) are new, so exact numerical reproduction of seeds 8–12 is
neither required nor expected. The torch-build delta is recorded as a documented environment factor,
not a protocol change (see `IMPLEMENTATION_DECISIONS.md`).
