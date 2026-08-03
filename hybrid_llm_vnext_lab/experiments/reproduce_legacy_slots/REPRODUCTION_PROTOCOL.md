# Reproduce Legacy Bounded-Slot Result — Protocol

**Status in this environment:** `RESOURCE_BLOCKED` — PyTorch and NumPy are not installed, so the
neural training run cannot execute here. The exact parameters, runnable command, and comparison
logic are provided so the run is a single command in a torch-enabled environment. Parameters are
extracted from live artifacts (see `config.json`), never reconstructed from memory.

## Objective

Reproduce the **saved** phase_lc A/B/C positive bounded-slot result before changing the
algorithm — reproduction **before** improvement. The target is the saved artifact
`experiments/phase_lc/results/abc.json` (1200 steps, batch 16, 3 seeds), **not** the report's
prose-only "1800-step → needle 1.00" figure, which is `NOT_FOUND` as any artifact and is
explicitly excluded from the gate.

## Arms

| Arm | Definition |
|---|---|
| **A** | local/sliding-window only (`ABCMixer` window, no phase, no slots) |
| **B** | A + real Phase (window + Phase) — included only to reproduce the historical reference; **Phase is not a candidate** and is not incubated |
| **C** | B + bounded slots (window + Phase + slots) |
| **C-slots-off** | identical C checkpoint, `slots.ablate='zero'` |
| **C-random-address** | identical C checkpoint, `slots.ablate='rand_keys'` |
| **C-phase-off** | identical C checkpoint, `ablate_phase=True` |

Note on Phase: the reproduction runs against the *original* phase_lc source tree (which contains
Phase), invoked read-only. **No Phase code is copied into this lab**; arm B exists solely to
reproduce the historical numbers and confirm the slot result is Phase-independent (C-phase-off ≈
C-baseline). The incubated slot core (`src/binding_slots/`) is Phase-free.

## Exact parameters

See `config.json`. Model d=128, h=4, layers=4, window=64, num_slots=32, ff auto-tuned to
2,000,000 params, vocab 1291, corpus 55,547 tokens (two corpus.json files), train N=160 / eval
N=256, batch 16, AdamW lr=2e-3 wd=0.01, warmup 60, **1200 steps**, grad-clip 1.0, no dropout,
CPU fp32, seeds [0,1,2], loss = 20% LM + 80% tasks (needle .20 / binding .20 / supersession .15
/ source .15 / multihop .10).

## Primary metric and acceptance

- **Primary:** needle accuracy at distance 96 (beyond the window of 64), n=120, exact-match.
- **Saved per-seed targets:** C-baseline **0.467 / 0.000 / 0.000**; C-slots-off **0.017 / 0.000
  / 0.042**; C-rand-keys **0.050 / 0.000 / 0.008**; C-phase-off **0.475 / 0.000 / 0.000**.

## Reproduction classification (assign after running)

`EXACT_REPRODUCTION` (identical fixture + checkpoint + seed, outputs within tolerance) ·
`STATISTICAL_REPRODUCTION` (retrain → equivalent means/variance/ablation behavior) ·
`PARTIAL_REPRODUCTION` · `NOT_REPRODUCED` · `RESOURCE_BLOCKED`.

**A single successful seed is NOT a robust reproduction.** The saved result itself forms in 1/3
seeds; reproduction must reproduce that *pattern* (seed-0 circuit forms; slots-off/rand-keys
collapse it; phase-off does not), not just one lucky seed.

## Run (torch-enabled environment)

```
# environment manifest (minimum):
#   python >=3.9, torch (CPU wheel sufficient), the repo checked out at commit 8b4ec6e7
pip install torch
python hybrid_llm_vnext_lab/experiments/reproduce_legacy_slots/run.py --seeds 0 1 2 --steps 1200
python hybrid_llm_vnext_lab/experiments/reproduce_legacy_slots/compare.py \
    --against experiments/phase_lc/results/abc.json \
    --got hybrid_llm_vnext_lab/artifacts/legacy_slot_reproduction.json
```

`run.py` invokes the **original** `experiments/phase_lc/harness_abc.py` with the pinned config
(so the reproduction is faithful and the original code is exercised, not a re-transcription),
writes `artifacts/legacy_slot_reproduction.json`, and `compare.py` diffs per-seed needle@d96 and
the ablation deltas against the saved baseline, emitting the reproduction classification.
