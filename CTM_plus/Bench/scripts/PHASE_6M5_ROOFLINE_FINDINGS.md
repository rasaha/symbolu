# Phase 6M.5 — Roofline: compute-bound vs bandwidth-bound (Test 1, THE GATE)

> **Status: BLOCKED on hardware — `ERR_NVGPUCTRPERM` (counters locked).** This is
> Test 1 of `PHASE_6M_THROUGHPUT_RECOVERY_TEST_PLAN.md` (§Test 1), the gate that
> decides whether 6F (kernel work), H100/H200 (Test 2), or an HBM-level change is
> the right lever. The CPU-side tooling is committed and self-tested; the **GPU
> measurement requires an ncu-unlocked pod**. This doc is finalized once the `ncu`
> SpeedOfLight split is captured. **No code/kernel/quant change is authorized.**

## ⛔ ATTEMPT LOG — Test 1 BLOCKED on RunPod A100 (2026-06-01)

Ran `roofline_ncu_runner.sh` on a fresh **RunPod A100-SXM4-80GB** (driver
570.195.03, CUDA 12.8, vLLM 0.7.3, torch 2.5.1+cu121). The §9 ncu unlock probe
**failed**:

```
==ERROR== ERR_NVGPUCTRPERM - The user does not have permission to access NVIDIA
GPU Performance Counters on the target device 0.
```

The runner aborted before booking profiling time (as designed). **ncu cannot
collect SpeedOfLight on this pod** — GPU performance counters are gated at the
host/driver level (`NVreg_RestrictProfilingToAdminUsers`), which the container
cannot change. This is the *same* lock the prior pod hit; it is a RunPod
instance-type permission, not a fixable in-container issue.

**Environment WAS verified GREEN on this A100** (so the block is purely the ncu
permission, not the build):
- Kernel rebuild succeeded (`rebuild_all_kernels.sh`, A100 `sm_80`, after a
  torch-2.5.1 restore — see note below).
- **Byte-equivalence: PASS (15/15, 1 skip)** via `verify_phase6e_byte_eq.sh --cuda`.
- torch 2.5.1+cu121, `cuda=True`; vllm 0.7.3; `vllm.vllm_flash_attn` +
  `int4_protected_C` import OK.

> Build gotcha recorded: the kernel `setup.py`/`pyproject` declare a `torch`
> dependency, so `pip install -e .` (even with `--no-build-isolation`) silently
> **downgraded torch 2.5.1 → 2.4.0** mid-build, breaking vLLM 0.7.3. Fix:
> restore with `pip install --no-deps --force-reinstall torch==2.5.1
> --index-url .../cu121`, and build the kernels with **`--no-deps`**.
> `rebuild_all_kernels.sh` now passes `--no-deps` + a torch-version guard.

### What this unblocks vs blocks
- **BLOCKED:** the SM%-vs-DRAM% roofline split (needs ncu counters). Therefore
  **Test 3 (6F) entry gate stays UNVERIFIED** — do not greenlight the multi-week
  kernel work until the roofline runs on a profiling-enabled pod.
- **NOT blocked (no ncu needed):** the capacity/throughput baseline
  (`hardware_test_runner.sh` → `A100_report.json`) and the `torch.profiler` 6D
  bucket attribution. Run those here to get the reproducible A100 baseline.

### To resolve
Obtain a pod with GPU performance counters enabled
(`NVreg_RestrictProfilingToAdminUsers=0`, or a privileged/Secure instance where
the §9 probe prints the metrics table). RunPod Community-cloud pods typically
keep counters locked; ask support for a profiling-enabled instance. Then re-run
`roofline_ncu_runner.sh` and paste the verdict here.

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
