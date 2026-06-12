# int4_protected — Design & Deployment Document

**Cognade Labs · quality-preserving 4-bit KV-cache for vLLM**
*Engineering design + deployment package. Companion to the business-facing `INT4_PROTECTED_VC_BRIEF.md`.*

---

## 1. What this is (and the one honest sentence)

int4_protected is a **drop-in vLLM backend** that stores the KV-cache in 4-bit
while **protecting the few K channels that carry the attention signal** at bf16 —
giving **~2× KV density (1.83× net of overhead) at near-bf16 quality**, where fp8
loses quality and naive int4 loses fidelity.

> **The honest sentence, up front:** the win is **density + preserved quality**
> (and, for shared-prefix workloads, an **APC prefill saving**) — **not raw decode
> throughput.** int4_protected is **decode-throughput-negative** (~0.22–0.67× bf16;
> it is kernel-bound). It serves **~2× more concurrent / longer-context users per
> GPU at near-bf16 quality** for **throughput-insensitive, density-bound** and
> **shared-prefix / short-output** workloads. A customer "experiences the savings"
> as **users-per-GPU and TTFT-on-cache-hit**, not tokens/sec per request.

This document is the architecture + the deployment + the demo that lets a partner
run it on a fresh pod and measure those savings on their own hardware.

---

## 2. Problem

At long context (32K+), the **KV-cache exceeds model-weight memory** on most open
models — it is the binding constraint on how many concurrent users a GPU serves.
The industry's 4-bit answers fail on quality:

| Approach | KV density | Quality | Why it fails |
|---|---:|---|---|
| bf16 | 1.0× | perfect | the reference; the memory wall |
| fp8 | ~2× | **poor** (needle 1/15) | 8-bit float can't hold K's per-channel range |
| naive int4 | ~2× | **degraded** (token-agreement 0.533) | uniform 4-bit crushes the high-magnitude K channels |
| **int4_protected** | **~2× (1.83× net)** | **near-bf16** (0.737 agreement; hard-needle 0.964) | protects the channels that matter |

---

## 3. The mechanism (the IP)

KV **K-vectors have highly heterogeneous channel importance**: the attention score
`Q·K` is dominated by a small set of high-magnitude K channels per `(layer, head)`;
the rest is diffuse. Uniform int4 quantizes all channels onto one 4-bit grid under
a single per-block scale, so the few high-dynamic-range channels — the ones the
inner product depends on — are crushed first.

**int4_protected keeps the top `N = round(D × 4%)` (= 5 at D=128) highest-magnitude
K channels per `(layer, h_kv)` at bf16** and quantizes the rest to int4:
- the **protected** channels carry the inner-product signal at full precision;
- the **int4 bulk** carries the cheap remainder.

Properties that make it deployable:
- **Per-`(layer,head)`, static.** Channel importance is a property of the trained
  weights, not the prompt — so a **one-time 30-second calibration** produces a small
  `(layers, H_kv, D) int8` mask (~17–50 KB) and the runtime stays cheap.
- **K-bound defense.** The failure it prevents is long-range retrieval collapse;
  every competitor without protect fails on the hard tail (naive int4, fp8, KVarN
  0.062 @32K). This is the moat, and it lives **only at the aggressive 4-bit point**
  (at int8 K needs no protection → no moat).

---

## 4. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  USER:  llm = Int4ProtectedLLM(model="...")   ← one-line drop-in        │
└───────────────────────────────┬──────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  (A) Int4ProtectedAttentionImpl   (vLLM FlashAttentionImpl subclass)   │
│      installed by a post-init class swap on every Attention layer       │
│   WRITE: bf16 K/V → int4 nibbles + per-block scale/xmin + 4% protect    │
│   READ:  paged gather of nibbles+sidecars → forked FA kernel            │
│   APC:   prefix-prefill over cached int4 KV (eager-only)                │
└───────────────────────────────┬──────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  (B) vllm-flash-attn fork (SHA 720c948 + int4 path)                    │
│      flash_attn_with_int4_kvcache: in-kernel int4 dequant in registers │
│      (NO bf16 KV materialized in HBM) + protect-channel splice + attn   │
└──────────────────────────────────────────────────────────────────────┘
        ▲
        │ (C) calibrate_phase5b_protect_mask.py — 30-sec one-time per model
        │     → (layers, H_kv, D) int8 protect mask artifact
```

**Three components:**
1. **Calibration** (`calibrate_phase5b_protect_mask.py`) — profiles prefill K
   max-abs over a 55-prompt corpus, picks the top-4% channels per `(layer, h_kv)`,
   saves the mask. Model-agnostic for any D=128 GQA/MHA model.
2. **Backend** (`phase5b_backend_install.py`, `phase5b_4c_paged_writer.py`,
   `phase6b2_precapture_hook.py`, `phase6k16_prefix_prefill.py`) — the vLLM impl
   subclass + paged writer + APC hook. ~3000 lines of Python.
3. **Kernel** (forked `vllm-flash-attn`) — the int4 decode read kernel. Dequants in
   registers; splices protected channels; runs the attention inner product.

---

## 5. Data paths

**Write (cache store).** On each KV store, the writer quantizes K/V to int4 nibbles
+ per-block `scale`/`xmin`, extracts the protected channels at bf16, and writes them
to the paged pool + sidecar tensors keyed by `block_id`.

**Read (decode).** `_read_decode_packed_batched` gathers the int4 blocks + 5 sidecars
from the paged pool into contiguous buffers (`get_packed_view_batched`), splices the
partial K-tail from the staging pool, and calls `flash_attn_with_int4_kvcache(...)`
with the **packed** int4 (not bf16) + dequant params. **The kernel reconstructs bf16
in registers — no bf16 KV is written to HBM.** (The remaining "6F" optimization is
to fuse the *gather* into the kernel too; size it with `bench_decode_gather_fusion_headroom.py`.)

**APC (prefix caching).** On a cache hit, the shared prefix's int4 KV is reused: the
`run_prefix_prefill` path attends to the **cached** int4 KV instead of recomputing
the prefix's forward pass — **skipping prefill compute** (compounds with density:
2× blocks ⇒ ~2× cacheable prefix). **Ships eager-only** (see §10).

---

## 6. The savings model (honest)

A deployment realizes value on three axes; one cost is disclosed.

| Axis | What you get | Status |
|---|---|---|
| **Density** (the $ saving) | **2.00× raw pool measured live** (399,792 → 799,584 token-slots, A100-80G, util 0.85, mml 32K); **~1.75× net** of the measured **8.3 GiB** out-of-pool sidecar tax at equal total VRAM. Net is util-dependent (tax ~16% of pool): 1.83× at smaller pools | LIVE-MEASURED (savings demo, June 2026) |
| **Quality** (the differentiator) | near-bf16: needle == bf16 (live: RETRIEVED at ctx=16K); MMLU 0.0 pt; hard-needle 0.964 | MEASURED, 4 models |
| **APC prefill** (shared-prefix) | **Measured** (Llama-3.1-8B, N=16, gen=32): TTFT **−53/−56/−78/−86%** per cache hit at 1K/2K/4K/8K prefixes; batch throughput **1.19–1.85×** at 94% hit rate, 1.28–1.54× at 75%; quality 1.00 == APC-off in every cell; net of the eager tax. Compounds with density | MEASURED (apc_payoff_sweep, June 2026) |
| **Decode throughput** (the cost) | **0.22–0.67× bf16** — kernel-bound; recoverable ceiling ~0.27–0.30×, NOT parity | DISCLOSED |

**Where it wins:** throughput-insensitive density-bound serving (many concurrent
long-context users; batch/offline) **and** shared-prefix / short-output workloads
(agentic, RAG, multi-turn) where APC's prefill saving offsets the decode tax.
**Where it doesn't:** latency-critical, long-generation single-stream chat.

**The customer-facing savings statement:** *"~2× the users (or context) per GPU
(1.75× net of sidecars, measured live) at near-bf16 quality, plus a measured
53–86% TTFT cut per cache hit on shared-prefix traffic — at a disclosed
decode-throughput cost."*

---

## 7. Deployment architecture

```
/workspace/
├── symbolu/                         ← this repo (git clone)
├── venv-vllm/                       ← Python venv (PINNED): vllm 0.7.3, torch 2.5.1+cu121
├── vllm-flash-attn-dev-src.tar.gz   ← the fork source (vendored; NOT in the repo)
├── dev/
│   ├── vllm-flash-attn-dev/         ← untarred fork (built into the vendored slot)
│   └── build-logs/
│       ├── <model>_protect_mask_4pct.pt   ← the calibrated mask (PROTECT_MASK_PATH)
│       └── vllm_flash_attn_vendored_backup ← rollback copy
└── tmp/                             ← TMPDIR for nvcc
```

**The pins are load-bearing.** A kernel built against the wrong torch/vllm builds
fine but fails to import (ABI) or runs garbage. The build script enforces them.

---

## 8. Deploying on a fresh pod

Prereqs on the bare GPU pod (A100-80GB / sm_80 ideal; H100 set arch 9.0):
1. `git clone` the repo to `/workspace/symbolu`.
2. Place the fork tarball at `/workspace/vllm-flash-attn-dev-src.tar.gz`.
3. A GPU attached (`nvidia-smi`), and `HF_TOKEN` if a gated model is needed.

One command does the rest (venv + pins + untar + build + mask + correctness gate):
```bash
bash /workspace/symbolu/CTM_plus/Bench/scripts/bootstrap_fresh_pod.sh
```

To **only (re)build the kernel** (the dev tree may be missing — it auto-untars; the
pins are enforced first):
```bash
source /workspace/venv-vllm/bin/activate
export TORCH_CUDA_ARCH_LIST=8.0        # 9.0 for H100/H200
bash CTM_plus/Bench/scripts/rebuild_all_kernels.sh --clean --verify-source
```
Rollback a bad build: `bash CTM_plus/Bench/scripts/restore_vendored_vllm_flash_attn.sh`.

Calibrate a mask for a **new** model (D=128 GQA/MHA):
```bash
python CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py \
    --output /workspace/dev/build-logs/<model>_protect_mask_4pct.pt \
    --protect-fraction 0.04 --max-model-len 8192
export PROTECT_MASK_PATH=/workspace/dev/build-logs/<model>_protect_mask_4pct.pt
```

---

## 9. Experiencing the savings

After deploy, run the savings demo (density + quality + APC prefill → one report):
```bash
export PROTECT_MASK_PATH=/workspace/dev/build-logs/<model>_protect_mask_4pct.pt
bash deploy/customer_savings_demo.sh --model <model>
```
It runs (each guarded, honest framing):
- **Density** — concurrency / seq-per-GB vs bf16 at the same GPU budget.
- **Quality** — needle retrieval == bf16 (the no-quality-cost proof).
- **APC payoff** — `apc_payoff_sweep.py`: TTFT saved per cache hit + throughput on a
  shared-prefix workload, swept by prefix length, **quality-gated**.

…and prints a consolidated **SAVINGS REPORT** with the honest cost disclosed. See
`deploy/QUICKSTART.md` for the step-by-step and the read-out guide.

---

## 10. Validation gates (trust the pod)

| Gate | Proves | Script |
|---|---|---|
| **S1 byte-gate** | cached APC blocks bit-exact vs fresh prefill (13/13) | `phase6k16_byte_gate.py` |
| **Needle / hard-needle** | retrieval == bf16 (no quality cost) | `phase6k12_hard_needle.py` |
| **COLLAPSE=0** | int4 decode correct, all cells × mml | `phase6k11_needle_failuremode.py` |
| **byte-eq** | int4 vs bf16 byte-equivalence on the FA path | `verify_phase6e_byte_eq.sh` |
| **APC C-GATE** | HITS + WARM + NEEDLE under prefix caching | `phase6k16_prefix_gates.py` |

---

## 11. Honest limits (named, bounded)

| Limit | Detail / mitigation |
|---|---|
| **Decode throughput-negative (0.22–0.67×)** | kernel-bound (gather + dequant); recoverable ceiling ~0.27–0.30×, **not parity**. Size the gather-fusion win first: `bench_decode_gather_fusion_headroom.py`. |
| **+4.4 GB sidecar tax** | structural (scales with KV block pool, **flat with context length**); diet (fp8 sidecars / coarser V) saves ~2.5 GB but not to parity. |
| **graphs + APC gated OFF** | root-caused to the **int4 attention kernel not being CUDA-graph-safe at B>1** (identical inputs → ~1.8× divergent output; our Python state machine measured clean). APC **ships eager-only**; low-ROI to fix since int4 is kernel-bound (graphs buy little). See `PHASE6K16_APC_CONTRACT.md`. *Open: non-APC graphs at B>1 shares the kernel — a revalidation item.* |
| **D=128 head dim only** | Phi (D=96) etc. need a kernel recompile, not a methodology change. |
| **vLLM 0.7.3 V0 fork** | V1 port is 1–2 weeks of maintenance. |
| **Swap preemption** | guarded — factory forces `preemption_mode="recompute"` (sidecars aren't migrated by swap). |
| **TP / 70B** | code expected to generalize; unvalidated. |

---

## 12. Appendix — file map & env vars

**Deploy / build:** `bootstrap_fresh_pod.sh`, `rebuild_all_kernels.sh`,
`restore_vendored_vllm_flash_attn.sh`, `calibrate_phase5b_protect_mask.py`.
**Backend:** `KVPolicy/kv_policy/{int4_protected,phase5b_backend_install,phase5b_4c_paged_writer,phase6b2_precapture_hook,phase6k16_prefix_prefill}.py`.
**Savings demos:** `apc_payoff_sweep.py`, `phase10_crossover_sweep.py`,
`bench_decode_gather_fusion_headroom.py`, `bench_phase6_long_context_gpu.py`.

**Env vars:**
`PROTECT_MASK_PATH` (the mask), `TORCH_CUDA_ARCH_LIST` (8.0 A100 / 9.0 H100),
`FA_TARBALL` / `VLLM_FA_DIR` (kernel build), `REQUIRE_VLLM=0.7.3` / `REQUIRE_TORCH=2.5.1`
(build pins), `PHASE6_MAX_ACTIVE_SLOTS` (pin staging to real concurrency),
`INT4_PROTECTED_APC_ALLOW_GRAPHS=1` (dev override; graphs+APC is broken — do not ship).

**Pins (locked):** torch 2.5.1+cu121 · transformers 4.48.3 · tokenizers 0.21.1 ·
numpy 1.26.4 · triton 3.1.0 · vllm 0.7.3.
