# K2 kernel diagnosis — why the int4 decode kernel is 12× bf16 (ncu-free)

> **ncu is `ERR_NVGPUCTRPERM`-blocked, and we don't need it.** The 12× is already
> diagnosable from the per-call time we measured. A byte/FLOP roofline on the
> **6.96 ms/call** says the int4 decode-attention kernel runs at **2.0 % of HBM
> bandwidth and 5.0 % of fp32 FLOP** → it saturates *neither* resource →
> **LATENCY/OCCUPANCY-BOUND**, i.e. stalled, not fundamentally limited. The cost is
> **recoverable**: a competent int4 kernel targets ~1.75× bf16 (~1.0 ms), a **~7×
> kernel speedup**, which flips int4 decode from **~12× slower → ~1.8× slower** than bf16.

## The roofline (validated against bf16)

`python scripts/kvpro_kernel_recovery/kernel_roofline.py` — one decode-attention call,
Qwen2.5-7B, ctx≈14.7k, B=32, A100 HBM 2039 GB/s:

| kernel | ms/call | HBM read | achieved BW | achieved FLOP | verdict |
|---|--:|--:|--:|--:|---|
| bf16 `flash_fwd_splitkv` | 0.58 | 966 MB | **1666 GB/s (82 % peak)** | 60 % fp32 | **MEMORY-BOUND (healthy)** |
| **int4 `flash_fwd_splitkv`** | **6.96** | **291 MB** | **42 GB/s (2.0 % peak)** | **5 % fp32 / 0.3 % tc** | **LATENCY/OCCUPANCY-BOUND** |

**The bf16 row validates the model** — a plain paged bf16 read *must* be memory-bound near
peak, and it is (82 %). Against the same model int4 reads **3.3× LESS data** (compressed) yet
costs **12× MORE time**, achieving 2 % of the bandwidth that byte volume should reach. That
is the signature of a kernel that is stalling (dependent unpack→dequant→FMA chains, too few
warps to hide HBM latency, register-pressure-limited occupancy) — **not** an inherent int4 tax
(an efficient int4 kernel would be memory-bound below bf16's time, since it moves less data).

- bandwidth-optimal int4 ceiling: **0.14 ms** (49× headroom) — the theoretical floor.
- realistic int4 target (dequant ALU included, ~1.75× bf16): **~1.0 ms** — a **~7× kernel speedup**.

## Confirming the mechanism without ncu (both permission-free)

1. **Static occupancy — `bash scripts/kvpro_kernel_recovery/cuobjdump_occupancy.sh` (pod).**
   `cuobjdump -res-usage` reads registers/shared-mem per kernel straight from the installed
   `_vllm_fa2_C.*.so` — no HW counters, no GPU run, no perms. On A100, ≥64 regs/thread already
   caps occupancy; a flash+dequant+splice kernel commonly runs 160–255 regs → **12–25 %
   theoretical occupancy**, which alone explains a latency-bound 2 %-bandwidth kernel. If the
   reg count is high, the K2 rewrite target is **register pressure**, not the gather.
2. **Context-scaling (reuse `bench_decode_gather_fusion_headroom.py`).** Time the int4 kernel at
   ctx ∈ {8k,16k,32k}. A large fixed intercept + shallow slope ⇒ launch/combine-latency-bound;
   a steep slope far below the bandwidth line ⇒ per-element dequant-latency-bound. Either way
   confirms latency-bound and points at the fix.

## What this does to the K2 decision

`K2_AGGREGATE_LOCK_MEASURED.md` decomposed the decode step into ~58 % attention-kernel +
~38 % fuseable gather. This diagnosis re-weights the two levers:

| lever | measured effect | ceiling |
|---|---|---|
| 6F gather-fusion (removes the 38 %) | ~1.4× decode | leaves the 12× kernel intact → int4 stays ~7.7× slower |
| **int4 attention-kernel rewrite (occupancy)** | — (not yet built) | **~7× kernel → int4 decode ~1.8× slower; gather fuses in for free** |

**The kernel rewrite dominates the gather fusion**, and an in-kernel paged gather is naturally
part of an occupancy-first rewrite (one kernel that reads packed KV via `block_table`,
dequants with a vectorized nibble load, and attends — the gather never materializes). So:

- **K2 = occupancy-first rewrite of `fwd_kvcache_int4`, with the paged gather fused in.**
- **First step is the cuobjdump occupancy read** (minutes, permission-free): if occupancy is
  register-limited as expected, that is the concrete rewrite target and the ~7× is credible.
- If, against expectation, occupancy is already high and the stall is elsewhere, re-open the
  question before committing kernel-eng weeks.

## Caveats

- Single operating point (ctx≈14.7k, B=32); the roofline is regime-independent in *shape* (a
  2 %-bandwidth kernel is latency-bound anywhere) but the exact ms will move with ctx/B.
- The ~1.75× bf16 target is an engineering estimate (published int4/fp8 decode kernels land
  ~1.3–2× their bf16 baseline), not a measured result — labelled as a target, not a TPS.
- The byte model assumes the documented layout (int4 packed K+V, per-group scale/xmin,
  5-channel compact protect); the bf16 82 %-peak validation is the evidence it is right.

## Reproduce
```bash
python scripts/kvpro_kernel_recovery/kernel_roofline.py            # the table above
python scripts/kvpro_kernel_recovery/kernel_roofline.py --selftest # CPU, 11 checks
bash   scripts/kvpro_kernel_recovery/cuobjdump_occupancy.sh        # pod: static occupancy
```
