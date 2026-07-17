# K2-M1 Phase C — candidate register-reduction / chain-shortening strategy ranking

Scored against the frozen target (`int4_packed_load_K_block` Phase F transform +
`flash_fwd_splitkv_kernel<…,int4kv,packed>`, hdim128/blockM64/blockN128/4warps/sm80). Columns:
**Reg** = register/spill benefit, **Lat** = latency benefit, **Risk** = correctness risk, **Cx** =
implementation complexity, **Port** = portability, **Gather** = interaction with later gather fusion.
`[POD]` = needs the base `flash_fwd_kernel.h` (not in-repo) to implement.

| # | strategy | Reg | Lat | Risk | Cx | in-repo? | verdict |
|---|---|---|---|---|---|---|---|
| 4 | **smem-stage scale/xmin as float (pre-convert at load)** | small | med | **low** (value-identical) | low | yes | deferred (M1A.2 if unroll helps) |
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

**K2-M1A — bounded Phase F unroll, same-wheel control + sweep (no gather fusion).** Finalized after
the measured baseline (`K2_M1_BASELINE_MEASURED.md`: the int4-packed kernel truly spills, `LDL
223–1218`) and a design review. The reconstruction writes the **full bf16 tile into `sK` smem** and the
**cute MMA reads `sK`** (`flash_fwd_kernel.h:184,203`), so "late unpack into the MMA" would rewrite the
core `flash::gemm` path — **too invasive; deferred to M2.** M1A is the one lever that directly cuts the
measured spill: **bound the Phase F outer `#pragma unroll`** so fewer per-element temporaries are
simultaneously live.

- **Implemented as a template split, not a runtime branch.** Register allocation is per-compiled-kernel;
  a runtime `if (use_m1)` keeps *both* loop bodies live → the full-unroll pressure dominates → **zero
  spill reduction**. So `int kM1Unroll` is threaded `run_flash_splitkv_fwd → DEFINE macro →
  compute_attn_splitkv → compute_attn_1rowblock_splitkv`, and each factor is its own compiled kernel.
- **Unroll sweep {1, 2, 4} + a same-wheel control (kM1Unroll=0).** One wheel carries the freshly-compiled
  control *and* the M1 factors, so the comparison isolates the single compile-time difference (no
  cross-wheel compiler/link nondeterminism). Too little unroll = loop overhead; too much = spills
  return; the optimum is usually between — hence a small sweep, not one guessed factor.
- **Numerics: value-identical, verified not promised.** Each `tKsK` element is computed independently
  (no cross-element accumulation), so the unroll factor cannot change any value — expected bit-identical,
  but `bench_k2_m1_op.py` confirms it by exact output-token match before any perf claim.

**Flag/selection:** `flash_api.cpp` reads `getenv("KVPRO_K2_M1")` → `params.k2m1_unroll` (validated
∈ {0,1,2,4}) and dispatches the matching compiled kernel; `flash.h` defines `KVPRO_K2_M1_BUILD` (all
TUs) so a mis-built wheel fails loud (`TORCH_CHECK`). Production path byte-identical + default.

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
