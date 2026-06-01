# Phase 6M.6 — Hardware: does newer silicon close the 0.22× tax? (Test 2)

> **Status: A100 BASELINE CAPTURED (2026-06-01); H100/H200 + axis attribution
> PENDING.** Test 2 of `PHASE_6M_THROUGHPUT_RECOVERY_TEST_PLAN.md` (§Test 2). Asks
> whether **H100/H200 close the throughput gap for free (no code) — and by which
> axis.** Pure measurement: **same scripts, new hardware; no kernel/quant change.**
> **Read together with Test 1 (6M.5):** H100→H200 changes BOTH native
> low-precision compute AND HBM bandwidth, so a bare H200 gain cannot self-
> attribute — Test 1's bound verdict breaks the confound. **⚠ The axis attribution
> is BLOCKED until Test 1 runs, and Test 1 is itself blocked (`ERR_NVGPUCTRPERM`,
> counters locked) — see `PHASE_6M5_ROOFLINE_FINDINGS.md`. This doc records the
> A100 baseline; the H100/H200 legs + attribution await a profiling-enabled pod.**

## ✅ A100-80GB baseline — REPLICATED on fresh hardware (2026-06-01)

Re-ran `hardware_test_runner.sh` on a **fresh RunPod A100-SXM4-80GB** (independent
of the original Phase 6L pod), with **kernels rebuilt from source** and the
**protect mask regenerated** (`calibrate_phase5b_protect_mask.py`, mml=1024). The
locked Phase 6L density numbers **reproduced to the decimal** — strong evidence
the build path + claim are robust, not a single-pod artifact.

| Metric | bf16 | protected | Ratio |
|---|---:|---:|---:|
| demonstrated_live seqs | 58 | **117** | **2.02× raw** |
| seq/GB (net of sidecar tax) | 1.367 | 2.498 | **1.83× net** ← HEADLINE |
| total HBM (GB) | 42.44 | 46.83 | +4.39 |
| measured sidecar tax (GB) | — | 4.379 | 99.8% of delta |
| agg tok/s | 578.6 | 183.3 | **0.32× agg** |
| per-user tok/s | 9.98 | 1.57 | **0.16× (~6.4× slower/user)** |
| peak KV util | 100% | 100% | both saturated |

Density claim: **DEMONSTRATED** (net 1.83× within the [1.5–2.5] window). Sidecar
tax: **4.38 GB live-measured** (matches the locked value). Both cells saturated at
100% KV-block util (8 / 6 preemptions). Artifact: `bench_out/phase6m6/A100_report.json`.

### ⚠ Throughput here is 0.32× (not 0.22×) — operating-point difference, NOT a change to the headline

This sweep (`--b-list 96,128`, the saturating row landing at the demonstrated
live concurrency) measured **0.32× aggregate / 0.16× per-user**. The **locked
0.22×** headline is from the deeper-saturation point (**B=128, gen=512** in Phase
6L). These are *different operating points*, both firmly "throughput-negative,
density-positive." **The locked 0.22× is NOT superseded** — record this 0.32× as a
corroborating data point at a lighter saturation, not a revision. The story is
unchanged: density win paid for in latency; batch/offline fit.

## Per-GPU ratio table

## How to produce the result (run once per GPU pod)

```bash
source /workspace/venv-vllm/bin/activate
bash CTM_plus/Bench/scripts/hardware_test_runner.sh   # auto-detects the GPU
# -> writes bench_out/phase6m6/<GPU>_report.json (+ <GPU>_kernel_diff.txt)
```

Run on **A100 (baseline), then H100 and/or H200**. Copy each
`<GPU>_report.json` back and attribute the axis (CPU-only) **with Test 1's
verdict**:

```bash
python CTM_plus/Bench/scripts/analyze_phase6m6_hardware.py \
    --report A100=bench_out/phase6m6/A100_report.json \
    --report H100=bench_out/phase6m6/H100_report.json \
    --report H200=bench_out/phase6m6/H200_report.json \
    --bound-verdict <compute-bound|bandwidth-bound-uncoalesced|bandwidth-bound-coalesced> \
    --out bench_out/phase6m6/PHASE_6M6_hardware_report.txt
```

The A100 leg can reuse the Phase 6L numbers if a fresh A100 pod isn't booked —
but a same-config A100 run is the cleanest baseline (controls for vLLM version
drift). Commit artifacts with `git add -f` (`bench_out/` is gitignored).

## Per-GPU ratio table (FILL IN)

| GPU | HBM TB/s | native INT4 | agg ratio (prot/bf16) | per-seq ratio | density ratio | protected agg tps |
|---|---:|:---:|---:|---:|---:|---:|
| A100-80GB | 2.0 | no | **0.317** (this sweep; 0.22 at B=128 gen=512) | **0.157** | **1.827** | **183.3** |
| H100 | 3.35 | yes | _pending (needs pod)_ | _pending_ | _pending_ | _pending_ |
| H200 | 4.8 | yes | _pending (needs pod)_ | _pending_ | _pending_ | _pending_ |

(HBM TB/s + native-INT4 are **annotation**; the verdict is driven by the measured
ratios + Test 1, not the spec sheet. Density ratio should stay ~1.83× across GPUs
— a big swing flags a measurement problem.)

## Bucket-share check (from the 6D profiler)

A100 int4_captured 6D profile (long context, ~7782-tok prompt, self-CUDA total
131.3 s) — **re-confirms the Phase 6M.4 attribution:**

| Bucket | Self-CUDA % | Note |
|---|---:|---|
| GEMMs (`aten::mm` / ampere_bf16_gemm) | ~37% | the model — **shared with bf16, NOT the int4 tax** |
| **paged gather** (`index_elementwise`) | **~25%** (22.6 + 2.5) | the int4-specific KV+sidecar gather — matches/exceeds the locked ~19.5% |
| attention (`flash_fwd` + `varlen_fwd` + `splitkv`) | ~21% | int4 decode/prefill reconstruction |
| `silu`/`act_and_mul`/elementwise | ~10% | shared model ops |
| **host syncs** (`aten::item` ×496,972, `Memcpy DtoH` ×522,256) | **<1.6%** | **re-confirms 6M.4: host syncs amortize to <1% at long context** |

**Takeaway:** the int4 tax is **genuine reconstruction (gather ~25% + attention
~21%)**, not removable host overhead — exactly as 6M.4 found. (CSVs on the pod:
`A100_int4_captured_kernels.csv`, `A100_bf16_stock_kernels.csv`; re-run
`analyze_phase6d_profile.py` on them for the full bf16-diff bucket table.)

## 🚩 CORRECTNESS FLAG — int4 output COLLAPSED in this run (regenerated-mask artifact)

The int4_captured profiling cell produced **collapsed/garbage output**
(`' FactCLUDING10 strugg性价性价性价...'`) vs the bf16 cell's coherent text. **This
is almost certainly the regenerated protect mask**, which was calibrated at
**mml=1024** on this fresh pod (the original session's calibrated mask was not
available). This was a known, pre-flagged risk: a short-context recalibration can
select weaker protect channels.

- **Does NOT affect the density result** (1.83×/2.02×/4.38 GB) — that is a
  memory/concurrency measurement, independent of output text quality, and both
  cells saturated identically.
- **DOES mean no quality claim rests on this pod's run.** The locked quality
  (COLLAPSE=0, +20.4 pt token-agreement) was measured against the original
  session's mask and is unchanged — but it was **NOT** re-validated here.
- **Before any quality re-run:** restore the original calibrated mask, or
  recalibrate at full context (`--max-model-len 8192`, more corpus), then re-check
  with `phase6k12_hard_needle.py` / `bench_phase6j_quality_gpu.py`.

## Axis attribution — BLOCKED pending Test 1

**Cannot be filled.** `analyze_phase6m6_hardware.py` requires Test 1's
`--bound-verdict` (compute- vs bandwidth-bound) to attribute any newer-silicon
gain, and **Test 1 (6M.5 roofline) is blocked** (`ERR_NVGPUCTRPERM` — counters
locked on the available RunPod A100). Until a **profiling-enabled pod** runs Test
1 AND an H100/H200 leg is measured, the compute-vs-bandwidth axis is open.

What we DO know from the A100 baseline alone: throughput is **0.16–0.22× per the
operating point**, density **1.83×** — consistent with Phase 6L. No newer-silicon
data yet, so no axis call. **Next action: profiling-enabled pod → Test 1 → then an
H100 and/or H200 leg → run the analyzer with the verdict.**

### Decision table (plan §Test 2, cross-referenced to Test 1)

| Observation | + Test 1 verdict | Attribution & action |
|---|---|---|
| Ratio improves on **H100** | compute-bound | **Native low-precision compute is the lever.** "Deploy on Hopper" is a zero-NRE throughput answer; 6F optional. |
| Ratio improves on **H100** | bandwidth-bound | H100 raises both axes — the bandwidth bump (2.0→3.35 TB/s) is the likely cause; confirm with H200. |
| Improves **only on H200** (not H100) | any | **HBM bandwidth (HBM3e) is the lever**, not compute → bandwidth-bound; weigh H200 deploy vs the §HBM software layout fix. |
| **No** material improvement | any | **STOP** — throughput is structural to the int4 algorithm; batch/offline density is the position, full stop. |

## Acceptance

This doc finalized with the per-GPU ratio table + the compute-vs-bandwidth
attribution (cross-referenced to Test 1). **No code changed.** A material H100
gain under a compute-bound verdict is the zero-NRE answer; otherwise the gap is
bandwidth-bound (H200 / §HBM layout) or structural (stop).

## Reproduction / artifacts

```
CTM_plus/Bench/bench_out/phase6m6/
  A100_report.json  H100_report.json  H200_report.json
  <GPU>_kernel_diff.txt
  PHASE_6M6_hardware_report.txt
```

CPU-side tooling (runs anywhere; no GPU):
```bash
python CTM_plus/Bench/scripts/analyze_phase6m6_hardware.py --selftest   # 8/8
python CTM_plus/Bench/tests/test_phase6m6_hardware.py                   # 12/12
```
