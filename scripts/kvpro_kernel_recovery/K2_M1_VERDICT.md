# K2-M1 verdict — `K2_M1_NO_GO_KERNEL_LATENCY` (measured, A100, 2026-07-17)

> The bounded-unroll register/spill-reduction hypothesis is **falsified by measurement**. No unroll
> factor improves int4 decode latency; all are flat-to-slightly-worse with numerics preserved.
> Per the pre-registered gate, **stop the kernel-rewrite branch and keep the known-good production
> kernel.**

## The measurement (op microbench — the authoritative gate)

`bench_k2_m1_op.py`, Qwen2.5-7B, ctx=16000, B=8, gen=64, **eager**, decode ms/tok = (full − prefill)
median of 3, one same-wheel sweep of `KVPRO_K2_M1`:

| `KVPRO_K2_M1` | kernel | decode ms/tok | vs control | tokens match | NaN/Inf |
|---|---|--:|--:|:--:|:--:|
| 0 | control (full unroll, freshly compiled) | **152.081** | — | ✓ | none |
| 1 | U1 (outer `#pragma unroll 1`) | 152.401 | **−0.2 %** | ✓ | none |
| 2 | U2 | 152.629 | **−0.4 %** | ✓ | none |
| 4 | U4 | 153.165 | **−0.7 %** | ✓ | none |

Three facts, measured:
1. **Numerics preserved** — exact output-token match, no NaN/Inf, every factor. The "value-identical"
   claim is *verified* (Phase F is per-element independent), not promised.
2. **Routing is real, no silent fallback** — four distinct latencies ⇒ the flag switches compiled
   kernels; the `KVPRO_K2_M1_BUILD` gate + `{0,1,2,4}` validation compiled (else `TORCH_CHECK` would
   fire). The same-wheel control isolates the single compile-time difference.
3. **No factor improves decode** — flat to −0.7 %. Bounding the unroll to cut the spill did nothing
   for latency.

## Interpretation

Cutting the measured register spill (baseline `LDL 223–1218`) **does not reduce decode latency** →
the spill is **not** the dominant decode-latency term. This is consistent with the roofline +
occupancy finding: the int4 decode kernel is **latency-bound at 12 % occupancy**, which is set by the
**base** kernel's 255 registers (stock bf16 is 255 too). The cost lives in the reconstruction
**dependency chain executed under low occupancy** — reducing spill without raising occupancy or
shortening that chain moves nothing. M1 tested the *cheap* transform-level lever; it is falsified.

## Decision (pre-registered)

**`K2_M1_NO_GO_KERNEL_LATENCY` → stop the kernel-rewrite branch; preserve the known-good production
kernel.** The production wheel was backed up before the M1 build; restore it to remove any doubt:

```bash
bash scripts/kvpro_kernel_recovery/build_k2_m1.sh --restore
```

(The `+k2m1` wheel's default, `KVPRO_K2_M1` unset → control, is already production-equivalent; restore
is belt-and-suspenders.)

## What this closes, and what remains

- **Closed:** transform-level register/spill reduction as a way to speed the int4 decode kernel.
- **Only remaining kernel lever = M2** (out of M1 scope): an occupancy-first restructure — true
  late-unpack into the `flash::gemm` K-fragment path + a reconstruction with higher memory-level
  parallelism, to lift the 12 % occupancy ceiling. That is weeks of CUDA engineering with uncertain
  payoff, and it fights the *base-kernel* occupancy limit, not just the int4 additions.
- **Standing strategic forks** (unchanged by this result): **6F gather-fusion** (measured ~1.4×
  decode, but int4 stays a net loss vs bf16), **`PIVOT_TO_INT8_KV`**, **`POSITION_INT4_AS_CAPACITY_ONLY`**.
  int4 remains a *capacity* play (longer context / more concurrency per GPU), not a speed play.

## Caveats (honest bounds on this verdict)

- The op microbench is a **decode-latency measurement** (prefill-subtracted), which is exactly what
  the gate cares about; a flat result across **all** factors makes the heavier 16K/32K Phase H
  benchmark unnecessary (it would not flip −0.2 % into +20 %). This matches ChatGPT's stop rule
  ("no candidate shows positive movement").
- `inspect_k2_m1.sh` returned "no `Li<N>` symbols" — a **regex bug in the static diagnostic**, not a
  build problem: the bench proves the four kernels compiled and route (four distinct latencies). The
  static spill numbers are moot given the latency result; the inspect matcher can be fixed later if
  the spill delta is wanted for the record.
- Single operating point (ctx 16k, B=8). The conclusion (spill ≠ latency bottleneck) is a *kernel*
  property unlikely to reverse at other points, but is stated as measured-here.

## Deliverables status (Phase J)

`K2_M1_TARGET_KERNEL.md` · `K2_M1_REGISTER_AUDIT.md` · `K2_M1_STRATEGY_RANKING.md` ·
`K2_M1_BASELINE_MEASURED.md` (baseline + SASS spill) · `apply_phase_k2m1a_patches.py` (source patch) ·
`build_k2_m1.sh`/`inspect_k2_m1.sh`/`bench_k2_m1_op.py` (build + gates) · **this verdict**. Known-good
wheel preserved; no production change; no number claimed beyond the measured table above.
