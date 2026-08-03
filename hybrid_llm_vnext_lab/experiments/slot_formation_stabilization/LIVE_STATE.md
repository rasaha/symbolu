# Slot Formation Stabilization — Live-State Audit

**Date:** 2026-08-03 · **Phase:** Phase-Free Slot Formation Stabilization (three intervention families)

This file records the exact live state audited **before any code change or training**, per the
protocol. Machine-readable values are in `LIVE_STATE.json`, `SOURCE_INVENTORY.json`, and
`FROZEN_BASELINE_MANIFEST.json`.

## 1–5. Repository state
- **Live default branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
- **Default HEAD:** `04f24d3e4ac9bc755f21fc650ec19a73df0b469b`
- **Working tree:** clean at start.
- **Work branch:** `claude/slot-formation-stabilization-dtx0lz` (cut from `04f24d3e`).
  The prompt suggested `chatgpt/slot-formation-stabilization`; this environment mandates the
  harness-designated `claude/` branch. Difference documented.

## 3–4. PR #1300 (the immutable scientific starting point)
- **State:** MERGED (`merged: true`), merged by `rasaha` at `2026-08-03T09:43:05Z`.
- **Merge commit:** `5f0cbe4539a4fad108c0bab90f216e5db7b953a7` — present in default-branch history.
- **Final PR head:** `1ae11f1329600feaf89a293b11f0ac57dc3532ea`; base at PR time `3b521f0f…`.
- **Verdict carried forward (not reclassified):** `PARTIALLY_STABLE` → `NOT_READY_FOR_KDA_VALIDATION`.

## 6. Existing slot-stabilization branch / PR
None. No prior `slot_formation_stabilization` experiment directory exists; the only related branch
is this work branch.

## 7–8. Five-seed inventory & frozen artifacts
All five-seed experiment files and the four frozen artifacts are inventoried in
`SOURCE_INVENTORY.json`; their SHA-256 + git-blob digests are pinned in
`FROZEN_BASELINE_MANIFEST.json`. The frozen `experiments/phase_lc/results/abc.json`
(sha256 `b31989a3…`) is guarded and unchanged.

## 9. Lab verifiers at start
- `scripts/verify_lab.py` → **59 checks, 0 failures**
- `scripts/verify_historical_artifact_protection.py` → **8 checks, 0 failures**

## 10. Platform-freeze status
`platform_freeze.verify` cannot execute in this container: it imports `packages/…` code that
requires `pydantic`, which is not installed here. This is unrelated to the slot lab. This phase
modifies **no** frozen platform surface — all work stays inside `hybrid_llm_vnext_lab/`. The
freeze manifest `platform/PLATFORM_FREEZE_V1.json` (sha256 `700a8a79…`) is recorded and unchanged
pre/post. Status: **PRESERVED_BY_CONSTRUCTION** (verifier dependency gap recorded honestly).

## Environment reality (recorded honestly)
- Python 3.11.15, **torch 2.13.0+cu130**, numpy 2.4.6, CPU, 4 cores, `threads=4`, fp32.
- torch/numpy were **not** pre-installed; installed at session start from the default (internal)
  PyPI mirror. `download.pytorch.org` is blocked (403 via proxy) but the default index served
  **the same torch build (2.13.0+cu130)** the frozen five-seed run recorded — so the neural
  harness runs under the identical torch build that produced the frozen result.
- Calibrated S-arm cost **here**: ~881 ms/step → **~1057 s / seed** for 1200 steps (matches the
  frozen run's 986–1004 s). A window-only arm (A/A+) is ~210 s / seed. Training is **feasible**
  but sequential (4 cores; determinism pins `threads=4`).

## Seed hygiene
- Prior slot experiments used seeds **0–2** and **3–7** only.
- **Stage A diagnostic (development) seeds:** 3, 6, 7 (non-former, marginal-former, non-former).
- **Stage B fresh holdout seeds:** 8, 9, 10, 11, 12 — verified **uncontaminated** (never used for
  this architecture, task, or any intervention).

## Established five-seed baseline (verified from committed artifacts, NOT this prompt)
`artifacts/five_seed_classification_run1.json` (sha256 `25aa4698…`):

| needle@d96 | s3 | s4 | s5 | s6 | s7 |
|---|---|---|---|---|---|
| S | 0.000 | 0.283 | 0.408 | 0.075 | 0.042 |
| A+ | 0.017 | 0.000 | 0.000 | 0.017 | 0.000 |
| forming | no | yes | yes | yes (marginal) | no |

Formation 3/5 → `PARTIALLY_STABLE` → `NOT_READY_FOR_KDA_VALIDATION`. This is the immutable
starting point and is **not** reclassified by this phase.

## Material finding surfaced during the audit (relevant to Family 2)
The frozen `BindingSlots.__init__` **already** calls `nn.init.orthogonal_(keys)` because
`num_slots (32) <= key_dim (64)`, then row-normalizes. **The baseline slot keys are therefore
already orthogonalized and unit-normalized, deterministically per seed.** Intervention Family 2
(orthogonal slot-key init, K1) consequently starts from a baseline that already breaks slot
symmetry at initialization — the initialization audit will quantify how little additional headroom
exists. This is pre-registered as an expected-null-ish arm, not discovered after the fact.
