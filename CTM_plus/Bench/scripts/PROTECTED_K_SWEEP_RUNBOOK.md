# §20.4.1 follow-on — outlier-protected K sweep runbook

Status: **harness + driver landed CPU-side, unit tests green.** Waiting for
one GPU pod execution. Prerequisite: the **K-INT8 sanity run must be done
first** (see `DIAGNOSTIC_SPRINT_LONG_CONTEXT_RUNBOOK.md`).

## Why this experiment

§20.4.1 isolated the long-context INT4 failure to the **K channel**. The
mechanism analysis (`PHASE4_GPU_FINDINGS.md` §20.4) attributes most of the
K-INT4 error to a handful of **outlier channels** — post-RoPE, a few (h,d)
channels carry disproportionate magnitude, and one INT4 scale per channel
still crushes the normal channels to cover the outlier's range.

K-INT8 (the sanity run) tests whether *bit depth alone* recovers quality —
but it caps at ~2.3× compression. **Outlier-protected K** tests a better
deal: keep V at INT4, keep *most* K channels at INT4, and protect only the
top-magnitude K channels at FP16. Protecting ~1% of channels adds only
~0.1 bit/elem, so if quality recovers this keeps compression near the full
~3.2× — the only path measured so far that would *meaningfully* beat FP8's
2×.

## Run order

1. **First:** the K-INT8 sanity run (`--k-bits 8 --v-bits 4`). Do not run
   this sweep until that result is in — see the decision rule below.
2. **Then:** this sweep.

## Prerequisites

Identical to the K-INT8 run — pod, packages (`transformers≥5`, `torch
2.5.1+cu124`, `pip install -e CTM_plus/Bench`, `pip uninstall -y
torchvision`), and HF cache / disk setup (`HF_HOME` on `/workspace` or
`/dev/shm`, not the 20 GB container disk). The checked-out branch must
include the `--k-protect-fraction` flag — verify with
`python -m ctm_bench.scripts.track_e_long_context --help | grep k-protect`.

## One command (~25 min on an A100)

```bash
cd /workspace/symbolu/CTM_plus/Bench
SAMPLES=8 bash scripts/protected_k_sweep.sh
```

Five cells on the fixed 16k needle setup (n=24/cell): `k_protect_fraction ∈
{0.000, 0.005, 0.010, 0.020, 0.040}`. `0.000` is full INT4 K — the §20.4.1
RED anchor. V is INT4 throughout. Output: `bench_out/protected_k/protect_*.json`,
plus a printed summary table.

## What is logged

Per the §20.4.v2 schema — per needle trial: `correct` (needle success),
`first_stutter_position`, `repeated_token_rate`, `decode_entropy_*`,
`cache_*_bytes`, `decode_tokens_per_s`. Per cell, aggregated:
`int4_needle_accuracy`, `int4_first_stutter_earliest`,
`int4_repeated_token_rate_mean`, `int4_entropy_collapse_rate`.

**Memory caveat:** the per-row `cache_compression_ratio` reflects the
kvstore's INT4 quantization only — it does *not* account for the FP16
outlier patch (protection happens in the cache wrapper, post-store). The
protected-K memory is near full-INT4: protecting fraction *f* of channels
costs ≈ `f × (16 − 5)` extra bits/elem on K, so e.g. *f*=0.01 → +~0.1
bit/elem → still ~3.1–3.2× overall. Memory is not the open question here;
needle recovery is.

## Decision rule (set with the experiment, per the §20.4.1 plan)

Read against the K-INT8 sanity result:

* **K-INT8 recovers AND outlier-protected K-INT4 recovers most of it** → the
  architecture direction is **adaptive / protected K + INT4 V**. Pick the
  smallest `k_protect_fraction` whose needle accuracy is within noise of
  baseline — that is the ship config, at ~3× compression.
* **K-INT8 recovers but no protected-INT4 cell does** → bit depth, not
  outlier channels, is the lever; fall back to the K-INT5/6 ladder
  (`diagnostic_sprint_long_context.sh`) and accept the ~2.3× ceiling.
* **K-INT8 does not recover** → do not run this sweep yet. The problem is
  deeper than K precision; investigate **pre-RoPE K quantization** and
  **scale calibration** (`calibrate_int4_scales.py`) before any kernel work.

Decode-side repetition penalties / sampling are explicitly **out of scope** —
they can hide stutter but do not restore retrieval.

## Notes / honest limitations

* Outlier selection here is **dynamic** (recomputed per block from the
  current K's per-channel max-abs) — the optimistic upper bound. A shipped
  protected-K cache would calibrate a **static** channel set offline; if the
  dynamic version doesn't recover quality, the static one won't either, so
  this is the right first test.
* This sweep measures **quality vs protected-fraction**. It does not by
  itself produce a shippable kernel — route-A integration and a fused
  unpack-attend kernel remain separate, later tracks.
