# K2-M1 Phase B — live-state / INT4 dependency-chain register audit

> Source-level audit of the packed INT4 reconstruction (`int4_packed_load_K_block`, the string in
> `apply_phase2_4_1b_patches.py:209-376`) and the base-kernel state it runs against. Goal: find what
> the M1 change can actually move. **Central finding up front:** the stock bf16 `flash_fwd_splitkv`
> is *already* at 254–255 regs (cuobjdump), and bf16 decode runs healthy at that count — so the
> register **count** is set by the base kernel, not the int4 code. What the int4 code adds is a
> fully-unrolled per-element transform that **spills** (STACK 80–120 B on the heavy variants) and a
> **long per-element dependency chain**. M1 addresses the spill + the chain (latency), not the count.

## The reconstruction, as written (the M1-addressable code)

`int4_packed_load_K_block` = cooperative HBM→smem loads (Phases A–E, `:247-336`) → `__syncthreads()` →
**Phase F transform** (`:344-373`), a triple `#pragma unroll` over each thread's tKsK fragment
(~128 bf16 elements/thread at the target). Per element (`:355-370`):

```
slot = smem.protect_slot[d]                       # dependent smem load #1
if slot in [0,n_protect): x_hat = smem.k_protect[n*kMaxNProtect+slot]   # load #2a
else:  byte  = smem.k_packed[n*kPackedBytesPerToken + d/2]              # load #2b
       nibble= (d&1)? byte>>4 : byte&0xF
       scale = int4_inline_to_float(smem.k_scale[g*kHeadDim+d])         # load #3 + CONVERT
       xmin  = int4_inline_to_float(smem.k_xmin [g*kHeadDim+d])         # load #4 + CONVERT
       x_hat = int4_inline_from_float(nibble*scale + xmin)              # FMA + CONVERT
tKsK(i0,i1,i2) = x_hat                             # smem store
```

Two structural inefficiencies visible in the source:
1. **Redundant per-element scale/xmin load+convert.** `scale`/`xmin` are indexed `[g*kHeadDim+d]`
   with `g=n/kGroupSize` — identical for all **kGroupSize=32** tokens in a group. The loop iterates by
   fragment coord, so it reloads and re-converts them per element instead of once per `(g,d)`.
2. **`int4_inline_to_float` in the hot path.** scale/xmin are stored bf16 in smem and converted to
   float **every element**; the conversion is deterministic and could be done **once**, at load time.

## Major live-value table

`I` = INT4-transform-specific (M1-addressable, in-repo). `B` = inherited base flash kernel
(**[POD]** — exact set/footprint from `flash_fwd_kernel.h`; classification from FA2 architecture).

| value | src | type | lifetime / scope | per-thread? | reducible in M1? |
|---|---|---|---|---|---|
| `acc_o` output accumulator | B | fp32 frag [kBlockM×kHeadDim] | whole main loop | warp | no (base) — dominant consumer; only smaller tiles shrink it |
| `acc_s` / `P` prob frags | B | fp32/bf16 frag | per K-block | warp | no (base) |
| softmax `row_max`,`row_sum` | B | fp32 [kBlockM] | whole main loop | warp | no (base) |
| Q fragment | B | bf16 | per K-block | warp | already in smem (Is_Q_in_regs=false) |
| cute gmem/smem descriptors | B | ptr/int | whole loop | thread | no (base) |
| **Phase F `x_hat`,`x`,`scale`,`xmin`,`nibble`,`byte`,`slot`,`g`,`n`,`d`** | **I** | mixed | **per element × ~128 unrolled** | thread | **YES** — see levers |
| smem scratch base ptrs | I | ptr | whole fn | thread | minor |
| OptionalPackedScratch (k_packed/scale/xmin/protect/slot) | I | **smem** ~5–12 KB | whole fn | block (shared) | not a register; SHARED reported 0 ⇒ dynamic smem |

## Top-3 register consumers (hypothesis; **[POD]** confirm via SASS)

1. **`acc_o` fp32 output accumulator (base).** The reason *stock* bf16 is already 255. Not
   M1-addressable without changing tiling (strategy #2) — out of "narrow M1" scope.
2. **The fully-unrolled Phase F transform temporaries (int4-specific).** `#pragma unroll` over ~128
   elements makes each element's `scale/xmin/x/x_hat/byte/nibble/slot/g` live across the unroll for
   ILP → this is the **added** pressure that pushes past 255 into the STACK spills. **← the M1 target.**
3. **`acc_s`/`P` + softmax state (base).** Inherited; not M1-addressable narrowly.

Only **#2** is both int4-specific and reachable without base-kernel surgery. So M1's register/spill
lever is entirely "shrink Phase F's simultaneously-live footprint," and its latency lever is "shorten
the per-element chain (pre-convert scale/xmin, cut redundant loads) + raise memory-level parallelism."

## Dependency-chain analysis (the latency-bound mechanism)

Per element the chain is: `load slot → branch → load packed → load scale → convert → load xmin →
convert → FMA → convert → store` — ~4 **dependent** smem loads + 3 converts, serialized. Combined
with the roofline (2% HBM BW) and the confirmed 12% occupancy, this is why the kernel stalls: too few
warps to hide the chain, and the chain is longer than it needs to be. **Shortening it is the primary
M1 lever** and matches the reframed objective ("shorten the INT4 reconstruction dependency chain,
reduce live reconstructed state, increase independent load/compute overlap").

## What this proves about the gates

- **≤128 / ≤160 register gate is likely infeasible for a narrow M1** — the base kernel alone is ~255.
  Reaching ≤160 would require the tiling lever (kBlockN 128→64, strategy #2), which also shrinks base
  `acc_o` — a bigger, riskier change with an arithmetic-intensity/combine cost. Register count is a
  **signal**, not the M1 verdict; **latency (≥20% @16K/32K) is the verdict** (per the task correction).
- **Achievable narrow-M1 wins:** (a) eliminate the Phase F spill (STACK → 0) by shrinking per-element
  live state; (b) shorten the dependency chain (pre-convert scale/xmin at load; drop redundant
  reloads) → better ILP/latency at the *same* ~255 regs. Both are **measured**, not assumed.
- **Spill evidence rule:** the nonzero STACK is *not yet* proof of HBM spill traffic. `inspect_k2_m1.sh`
  reports SASS `LDL`/`STL` (local load/store) counts for the exact target symbol before/after — that
  is the spill proof; STACK alone is not.

## Feeds Phase C

The audit points at two bounded levers inside `int4_packed_load.h` (no base-file edit for the core):
**(L1)** pre-convert scale/xmin to float in smem at load time — removes 2 converts from the per-element
chain and shrinks Phase F live state; **(L2)** bound the Phase F `#pragma unroll` — trades ILP for
fewer live temporaries/spill. The larger structural win (reorder the transform to load scale/xmin once
per `(g,d)`) needs the base loop's fragment iteration order → **[POD]**, deferred to after extraction.
