# Phase 6M.6 — Hardware: does newer silicon close the 0.22× tax? (Test 2)

> **Status: SCAFFOLD — AWAITING GPU RUNS.** Test 2 of
> `PHASE_6M_THROUGHPUT_RECOVERY_TEST_PLAN.md` (§Test 2). Asks whether
> **H100/H200 close the throughput gap for free (no code) — and by which axis.**
> Pure measurement: **same scripts, new hardware; no kernel/quant change.**
> **Read together with Test 1 (6M.5):** H100→H200 changes BOTH native
> low-precision compute AND HBM bandwidth, so a bare H200 gain cannot self-
> attribute — Test 1's bound verdict breaks the confound.

## Goal

Per-GPU `protected/bf16` aggregate-tps ratio (the **0.22× on A100**) + the
**compute-vs-bandwidth axis attribution**, cross-referenced to Test 1.

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
| A100-80GB | 2.0 | no | _pending (≈0.22 from 6L)_ | _≈0.11_ | _≈1.83_ | _≈117_ |
| H100 | 3.35 | yes | _pending_ | _pending_ | _pending_ | _pending_ |
| H200 | 4.8 | yes | _pending_ | _pending_ | _pending_ | _pending_ |

(HBM TB/s + native-INT4 are **annotation**; the verdict is driven by the measured
ratios + Test 1, not the spec sheet. Density ratio should stay ~1.83× across GPUs
— a big swing flags a measurement problem.)

## Bucket-share check (FILL IN from the 6D profiler)

Does the **~29% attention + ~19.5% gather** share shrink on newer silicon?
Reference `<GPU>_kernel_diff.txt`. _pending._

## Axis attribution (FILL IN — from the analyzer)

**`<COMPUTE | BANDWIDTH | STRUCTURAL>` axis** — _headline from
`analyze_phase6m6_hardware.py` (it consumes the Test-1 verdict)._

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
