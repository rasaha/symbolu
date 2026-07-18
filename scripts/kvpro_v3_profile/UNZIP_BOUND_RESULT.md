# KVPro V3 Part H — unzip memory-vs-compute: MEASURED RESULT

> **VERDICT (measured, NVIDIA A100-SXM4-80GB): `MEMORY-BOUND`, and *scatter*-limited, not
> volume-limited.** The INT4 decode "unzipper" is bottlenecked on fetching the scattered
> packed/scale/xmin/protect streams — **not** on the dequant arithmetic (which is ~7.5× cheaper
> and fully hidden under the fetch). HBM is only **~3% utilised**, so the lever is **coalescing
> the reads (a 6F-style store-as-consumed / densified layout)** — NOT faster hardware (you are not
> bandwidth-limited) and NOT cheaper math (it is already free).

Answered **without `ncu`** (counter perm blocked: `ERR_NVGPUCTRPERM`) and **without clock-scaling**
(both `nvidia-smi -lmc` unsupported *and* no permission on this pod) — the only two counter-free
hardware routes were both dead. The two-half-kernel probe needs neither: it times three
specialisations of the *same* unzip inner loop with CUDA events.

## Provenance
- **GPU:** NVIDIA A100-SXM4-80GB (108 SMs, 85 GB), driver 550.127.05, CUDA 12.4.
- **Probe:** `07_unzip_bound_probe.sh` → `unzip_bound_probe.py`; classified by `08_classify_unzip_bound.py`.
- **Config:** `CONTEXTS="4096 16384 32768" ITERS=100`, H_kv=4, D=128, BS=32, v_group_size=32, n_protect=5.
- **Inputs:** production-faithful packed view (writer contract, `route_a_builder.build_packed_view`) —
  compact bf16 protected sidecar, native `(S,H,·)` layout, per-block K scale, per-token/group V scale.
- **Kernel correctness:** anchored on CPU by `validate_kernel_interp.py` (Triton interpreter, **exact
  0.0 error** vs a numpy reference) — the GPU supplies only timing.
- **Thresholds:** FROZEN in `DECISION_THRESHOLDS.md` Part H *before* the run (OVR 1.5, HIDE 1.25,
  ADD 0.75, SAT_HI 0.60, SAT_LO 0.40).
- **Label discipline:** times are **GPU-MEASURED**; bytes/FLOPs are **MODELED** from the exact layout;
  the roofline is **MODELED-×-MEASURED**. No fabricated numbers.

## Measured times (ms/iter, mean of 100)

| ctx | fetch-only | math-only | full (compact) | full (full-fp16 protect) | per-ctx verdict |
|---:|---:|---:|---:|---:|---|
| 4096  | 0.0561 | 0.0498 | 0.0592 | 0.0544 | `BALANCED-OVERLAPPED` (overhead floor) |
| 16384 | 0.1914 | 0.0463 | 0.1883 | 0.2045 | `MEMORY-BOUND` |
| **32768** | **0.3755** | **0.0498** | **0.3712** | **0.3983** | **`MEMORY-BOUND`** ← decision ctx |

Decision context = the largest (least launch/timer noise). Key signals at ctx=32768:
- **fetch / math = 7.54** — the fetch dominates the dequant arithmetic by 7.5×.
- **full / max(fetch,math) = 0.989** — the full unzip ≈ the fetch alone; the math is **hidden**
  (latency-overlapped), contributing ~nothing to wall time.
- **math is flat across context** (0.050 / 0.046 / 0.050) — it sits at the launch/occupancy floor, so
  the true dequant compute is *even smaller* than 7.5× down. `math-only` is an upper bound (it
  re-fabricates a per-row perturbation the real kernel gets free from its loads), which only
  **strengthens** the memory-bound call.

## Roofline cross-check (MODELED bytes × MEASURED time)

| Quantity | Value |
|---|---|
| Achieved read bandwidth (fetch) | **59.3 GB/s** |
| Peak HBM (A100-SXM4-80GB) | 2039 GB/s |
| **HBM utilisation** | **2.9%** → `UNDER-UTILISED` (≪ SAT_LO 40%) |
| Achieved dequant throughput (math) | 1347 GFLOP/s (of 19 500 peak fp32 = 6.9%) |
| Arithmetic intensity | 3.01 FLOP/byte |
| Roofline ridge (peak_fp32 / peak_HBM) | 9.56 FLOP/byte |
| Region | **memory** (AI < ridge) |

The unzip is memory-bound **and nowhere near the HBM ceiling** — ~97% of bandwidth is unused. That is
the signature of a *scatter/latency*-bound kernel, not a *volume*-bound one.

## The decisive internal evidence: scatter, not volume

The route-A fp16-pool ablation swaps the tiny **scattered** compact-protect gather (10 B/tok/head, a
data-dependent masked gather) for the **contiguous** full-fp16-K load (256 B/tok/head — 2.6× more bytes):

- `full (compact) = 0.3712 ms` → `full (full-fp16) = 0.3983 ms` = **+6.8%** wall time for **+145%** bytes.

Adding a big *contiguous* read is nearly free while the small *scattered* reads dominate. Indicatively,
the incremental (mostly-contiguous) portion moves ~32 MB in ~0.027 ms ≈ **~1190 GB/s**, versus the
scattered base at **~59 GB/s** — roughly **~20× cheaper per byte at identical occupancy**. (This is an
*indicative* in-kernel comparison, not a perfectly clean isolation, but it points the same way as the
2.9% utilisation: the KVPro `(S,H,·)` interleaved layout, read per-head, wastes the bus on short
strided/scattered transactions.)

## Build-vs-buy (what this justifies)

| Lever | Verdict | Why |
|---|---|---|
| Cheaper dequant math / int8-native decode | ❌ **no payoff** | the affine is already free (7.5× under fetch, fully hidden) |
| Buy faster HBM (H100/H200 HBM3e) | ❌ **won't help** | not bandwidth-limited — only 2.9% of A100 HBM is used |
| Compact-protect sidecar (fp16-pool removal) | ⚠️ **minor (~7%)** | the protected stream is only ~6% of the bytes; production (6c.3C) already stores compact |
| **Coalesce the reads — store-as-consumed / densified per-head-contiguous layout (6F read fusion)** | ✅ **the lever** | short scattered reads dominate; contiguous reads are ~20× cheaper/byte; ~97% HBM headroom to recover |

**This is the measured evidence that was gating 6F.** It green-lights *prototyping* a 6F-style
coalesced-read / store-as-consumed kernel as the highest-leverage next step, and red-lights both a
hardware buy (not bandwidth-limited) and any dequant-math optimisation (already free).

## Honest caveats (do not over-read)
1. **The absolute 2.9% / 59 GB/s is probe-specific** and likely pessimistic vs a tuned production
   kernel (small `(BS,D)` tiles, H_kv=4, default `num_warps`). Trust the **direction** — large
   bandwidth headroom + scatter-dominance (both the utilisation *and* the in-kernel contiguous-vs-
   scattered comparison) — not the exact bandwidth number.
2. **Short context (4096) is overhead-bound**, not memory-bound (`BALANCED-OVERLAPPED`): the fetch is
   too small to dominate. The `MEMORY-BOUND` verdict is for **long-context** decode, where KV dominates
   throughput anyway; it strengthens monotonically with context (16k, 32k).
3. **This is the unzip READ only.** The full decode also has host-side gather/staging that this probe
   does not measure. Before committing to 6F, the open risk is whether a coalesced layout is achievable
   within the paged-cache allocation constraints **without pushing cost onto the write path** — 6E (the
   built write-fusion) already showed the write side can regress at batch saturation.
4. Consistent with the standing decode-recovery bound (~0.27–0.30×, never bf16 parity): this refines
   *why* — the recoverable cost is a memory-access-pattern (coalescing) problem, and the dequant
   compute is **not** on the critical path.

## Reproduce
```bash
cd scripts/kvpro_v3_profile
python3 validate_kernel_interp.py                              # CPU correctness anchor (exact vs numpy)
CONTEXTS="4096 16384 32768" ITERS=100 bash 07_unzip_bound_probe.sh
cat runs/unzip_bound_verdict.json
```
Raw artifacts: `runs/unzip_bound.json` (per-ctx times + byte/FLOP model) and
`runs/unzip_bound_verdict.json` (verdict + roofline + ablation). Both live on the run pod (pod push
blocked); the decisive numbers are recorded above.
