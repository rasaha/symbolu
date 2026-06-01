# Phase 6M.5 — Roofline: compute-bound vs bandwidth-bound (Test 1, THE GATE)

> **Status: SCAFFOLD — AWAITING GPU RUN.** This is Test 1 of
> `PHASE_6M_THROUGHPUT_RECOVERY_TEST_PLAN.md` (§Test 1), the gate that decides
> whether 6F (kernel work), H100/H200 (Test 2), or an HBM-level change is the
> right lever. The CPU-side tooling is committed and self-tested; the **GPU
> measurement runs on an ncu-unlocked pod** (the user drives it). This doc is
> finalized once the `ncu` SpeedOfLight split is pasted back. **No code/kernel/
> quant change is authorized by this test.**

## Goal (one fact)

Classify the int4 decode-attention kernel as **compute-bound**,
**bandwidth-bound (coalesced)**, **bandwidth-bound (uncoalesced)**, or
**latency/occupancy-bound** — the single fact that gates every downstream lever.

## How to produce the result (the user runs this on the pod)

```bash
source /workspace/venv-vllm/bin/activate
# Sanity: python -c "import vllm,torch;print(torch.cuda.is_available())"
bash CTM_plus/Bench/scripts/roofline_ncu_runner.sh
```

The runner (a) runs the **§9 ncu unlock probe first** and aborts with a clear
message if counters are locked (`ERR_NVGPUCTRPERM` → get a privileged pod), then
(b) profiles `int4_captured` and `bf16_stock` at the saturation operating point
(`--max-model-len 8192 --batch-size 48 --max-tokens 96 --prompt-frac 0.95`,
matching 6M.4) with `ncu` sections SpeedOfLight + MemoryWorkloadAnalysis +
ComputeWorkloadAnalysis + Occupancy + LaunchStats, NVTX-scoped to
`phase6d_step/`, kernel-filtered to the attention kernels, then (c) runs
`analyze_phase6m5_roofline.py` to print the verdict.

**Paste back:** the printed `VERDICT` block + `bench_out/phase6m5_roofline/
PHASE_6M5_roofline_report.txt`. Commit the CSV artifacts with `git add -f`
(`bench_out/` is gitignored) so the conclusion is reproducible.

### ncu unlock probe (HARD PREREQ — §9 of the plan)

```bash
ncu --metrics sm__throughput.avg.pct_of_peak_sustained_elapsed \
    python -c "import torch; x=torch.randn(4096,4096,device='cuda'); \
torch.cuda.synchronize(); (x@x).sum().item(); torch.cuda.synchronize()" 2>&1 | tail -5
# metrics table  -> ncu works; Test 1 is runnable (the runner proceeds)
# ERR_NVGPUCTRPERM -> counters locked; get a privileged pod FIRST
```

The prior pod returned `ERR_NVGPUCTRPERM`. **If the probe fails, Test 1 cannot
run — do not book GPU time until a pod where the probe succeeds is available.**

## Result table (FILL IN from `ncu`)

| SpeedOfLight metric (int4 attention kernel) | int4 | bf16 (ref) |
|---|---:|---:|
| Compute (SM) Throughput [%] | _pending_ | _pending_ |
| DRAM Throughput [%] | _pending_ | _pending_ |
| Memory Throughput [%] | _pending_ | _pending_ |
| Achieved Occupancy [%] | _pending_ | _pending_ |
| Global-load Sectors/Request (coalescing) | _pending_ | _pending_ |

## Verdict (FILL IN)

**`<compute-bound | bandwidth-bound-uncoalesced | bandwidth-bound-coalesced |
latency/occupancy-bound>`** — _reason from the analyzer._

### Decision table (what this verdict hands the rest — from plan §Test 1)

| If verdict is… | Then the lever is… | Gates… |
|---|---|---|
| **compute-bound** (SM% ≫ DRAM%) | in-kernel dequant tightening (6F) + H100 **native INT4** (Test 2). **HBM bandwidth will NOT help.** | Test 3 entry GREEN (compute arm); Test 2 H100 leg is the zero-NRE answer. |
| **bandwidth-bound, uncoalesced** (DRAM leads, sectors/req low) | **software layout/coalescing fix in 6F's read path** (interleave nibbles + scale + xmin + protected into one contiguous, coalesced transaction). The actionable "HBM-level" answer (§HBM). | Test 3 entry GREEN (layout arm). |
| **bandwidth-bound, coalesced** (DRAM ≈ 100%, good sectors/req) | raw HBM bandwidth → **H200 HBM3e (Test 2)**. 6F kernel work has a low ceiling. | Test 3 entry **low-ceiling**; prefer Test 2 H200 leg. |
| **latency/occupancy-bound** (neither engine near peak) | re-check operating point — 6M.4 says host sync <1% at saturation, so this warrants a re-run at the exact saturation B/context before gating. | re-measure, do not gate. |

## Sanity prior (plan §HBM)

int4 reads **~half the KV bytes** of bf16 (4-bit packing) yet runs **slower** — so
a *raw-bandwidth-saturated* verdict (DRAM ≈ 100% with good coalescing) is **a
priori unlikely**: if it were raw-bandwidth-bound it would be *faster*. The
expected outcomes are **compute-bound** (dequant arithmetic on the SMs) or
**bandwidth-bound-uncoalesced** (the scattered paged gather + 3 separate sidecar
reads waste effective bandwidth). The measurement decides which.

## Acceptance

A recorded verdict (this doc, finalized) with the SoL split + bound
classification. **No code changed.** Funding Test 3 (6F) is a separate decision
made *after* Tests 1–2, gated on this verdict ∈ {compute-bound,
bandwidth-bound-uncoalesced} AND the ~0.27–0.30× ceiling clearing the product bar.

## Reproduction / artifacts

```
CTM_plus/Bench/bench_out/phase6m5_roofline/
  int4_captured_ncu.csv   int4_captured_ncu.ncu-rep
  bf16_stock_ncu.csv      bf16_stock_ncu.ncu-rep
  PHASE_6M5_roofline_report.txt
```

CPU-side tooling (runs anywhere; no GPU):
```bash
python CTM_plus/Bench/scripts/analyze_phase6m5_roofline.py --selftest   # 7/7
python CTM_plus/Bench/tests/test_phase6m5_roofline.py                   # 10/10
```
