# K2-M1 Phase C — candidate register-reduction / chain-shortening strategy ranking

Scored against the frozen target (`int4_packed_load_K_block` Phase F transform +
`flash_fwd_splitkv_kernel<…,int4kv,packed>`, hdim128/blockM64/blockN128/4warps/sm80). Columns:
**Reg** = register/spill benefit, **Lat** = latency benefit, **Risk** = correctness risk, **Cx** =
implementation complexity, **Port** = portability, **Gather** = interaction with later gather fusion.
`[POD]` = needs the base `flash_fwd_kernel.h` (not in-repo) to implement.

| # | strategy | Reg | Lat | Risk | Cx | in-repo? | verdict |
|---|---|---|---|---|---|---|---|
| 4 | **smem-stage scale/xmin as float (pre-convert at load)** | small | **high** | **low** (bit-identical) | low | **yes** | **M1A core (L1)** |
| 9 | type-narrow / tighten Phase F live ranges | small | med | low | low | yes | **M1A (L2)** |
| 5 | recompute indices vs retain | small | low | low | low | yes | fold into M1A |
| 1 | **late unpack** (unpack inside GEMM K-consumption; never materialize bf16 tile) | med | **high** | med | high | **[POD]** | **M1A.2** (after extraction) |
| 2 | smaller seq tile (kBlockN 128→64) | **high** (only real reg-count lever) | −/med | med | med | [POD] | **fallback** if ≤160-reg is required by a gate |
| 10 | compact protected overlay timing | small | low | low | low | yes | minor, fold in |
| 8 | split-K simplification | small | low | med | med | [POD] | **reject** (combine is 56–62 regs, not the bottleneck) |
| 3 | smaller head/channel tile (chunk D) | med | −/med | high | high | [POD] | reject (breaks hdim128 GEMM) |
| 6 | split load/dequant into a 2nd kernel | high | **−high** | high | high | [POD] | **reject** (extra smem/HBM round-trip + launch per decode step → loses) |
| 7 | GQA G=7 specialization (drop G_PAD=16) | — | — | — | — | — | **N/A** — G_PAD is the *Triton* kernel; the production CUDA kernel uses inherited flash `h_h_k_ratio`, no G_PAD waste to remove |

## Chosen for Milestone 1

**K2-M1A — staged reconstruction + reduced live ranges (no gather fusion).** Refined after reading
the base loop (`extract_target_kernel.sh` section 1): the reconstruction writes the **full bf16 tile
into `sK` smem** and the **cute MMA then reads `sK`** (`flash_fwd_kernel.h:184,203` `tSrK/tSsK`), so
"late unpack into the MMA" would rewrite the core `flash::gemm` K-fragment path — **too invasive for a
narrow M1; deferred to M2.** M1A is therefore entirely inside `int4_packed_load_K_block` (in-repo):

- **M1A.1 — pre-convert scale/xmin to float in smem.** A cooperative pass converts `k_scale`/`k_xmin`
  bf16→**float** **once** at load; Phase F reads the ready float (drops 2 `int4_inline_to_float`/elem).
  **Bit-identical** (same deterministic conversion, same affine math). Shortens the dependency chain.
- **M1A.1b — reduce Phase F peak live-state.** Bound the triple `#pragma unroll` (e.g. `unroll 4` on
  the inner level), narrow index types, hoist the per-`d` `protect_slot` read. Targets the spill
  (STACK→0) at the *same* ~255 regs. Register count stays base-dominated — **latency is the gate**.

**Flag mechanism (decided from section 1):** no new template instantiation is needed for M1A (it is a
runtime-param branch, not a new specialization), so `KVPRO_K2_M1` is plumbed as a **runtime
`params.k2m1` field set host-side from `getenv` in `flash_api.cpp`**, gated by a **build macro**
`KVPRO_K2_M1_BUILD` so "requested-but-not-built" fails loudly (`TORCH_CHECK`). This touches only
`flash_api.cpp` + `flash.h` (field) + `int4_packed_load.h` (loader) + the 2 loader call-sites — far
less than template threading. Caveat: a runtime branch compiles both paths into the kernel, so the M1
**register count** is not a clean isolated number; the clean split (template bool) is an M2 cleanup if
the M1 **latency** wins. That is acceptable because the verdict is latency, not register count.

**K2-M1B — M1A + in-kernel paged gather**, added **only if** it does not raise the target symbol's
register count/spill. The gather lives in the Python launcher (`get_packed_view_batched`), so fusing
it is a separate, larger change; sequence it after M1A clears its kernel-latency gate, not before.

**M2 (out of M1 scope, noted):** true late-unpack-into-MMA + the clean template-bool flag split — the
larger structural win, requires rewriting the `flash::gemm` K-fragment consumption.

## Explicit non-goals for M1 (preserve the known-good path)

Smaller tiles (#2) only if a gate *requires* ≤160 regs and M1A's latency win is insufficient — it is a
base-kernel tiling change with an arithmetic-intensity cost, so it is a **fallback**, not the plan.
No format/quant/threshold change; default path stays OFF; no silent fallback; known-good wheel preserved.

## Honest expectation (projected, not measured)

M1A.1 removes ~2 dependent converts and reduces smem-load pressure per element; the roofline says the
kernel is latency-bound with ~49× bandwidth headroom, so shortening the chain *should* help — but by
how much is **unknown until measured on the pod** (Phase H). No multi-fold claim. If M1A.1 + M1A.2
together do not clear ≥20% kernel-latency at 16K/32K, the verdict is an honest
`K2_M1_NO_GO_KERNEL_LATENCY` and we stop, preserving the production kernel.
