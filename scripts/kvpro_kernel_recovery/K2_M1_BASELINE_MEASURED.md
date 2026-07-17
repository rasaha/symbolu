# K2-M1 measured baseline — the exact target kernel's static resources + SASS spill

> Confirmed on the recovered K0 `.so` (A100 pod, 2026-07-17) via
> `extract_target_kernel.sh` (`cuobjdump -res-usage` + `-sass`). This is the frozen baseline the
> M1 static gate (Phase F) and latency gate (Phase H) measure against. c++filt was available →
> the target `int4kv_packed` symbol (`…Lb1ELb1E…`, `Is_int4kv=Is_int4kv_packed=true`) was isolated
> from the ~stock/causal variants.

## Static resources

| kernel | REG | STACK | SHARED | theo. occ |
|---|--:|--:|--:|--:|
| **TARGET `int4kv_packed`** (`traits<128,64,128,4,false,false,bf16>`) | **255** | **480–760** | **≈22 656 B** | **8/64 = 12 %** |
| stock bf16 `hdim128` splitkv (same traits, `int4=false`) | 252–255 | 0–200 | 0 (dynamic) | 12 % |

The 22 656 B static SHARED on the target = the `OptionalPackedScratch` staging buffer
(k_packed + k_scale + k_xmin + k_protect + protect_slot); stock uses dynamic smem (reported 0).

## SASS spill + smem-traffic (the load-bearing measurement)

| kernel | LDL (local load) | STL (local store) | LDS (shared load) | STS |
|---|--:|--:|--:|--:|
| **TARGET `int4kv_packed`** | **223 – 1218** | **118 – 427** | **2343 – 3538** | 720 – 1117 |
| stock bf16 `hdim128` (low-STACK rows) | **0** | **0** | 150 – 470 | 50 – 160 |

**Two confirmed facts:**
1. **The int4 kernel truly spills.** `LDL/STL` in the hundreds–thousands = real register spill to
   local (HBM-backed) memory — *not* call-frame. The stock kernels' `LDL/STL=0` prove their nonzero
   STACK was call-frame, so we only claim a spill where SASS shows one. The int4 path is it.
2. **The int4 transform is smem-load-heavy.** `LDS=2343–3538` vs stock `150–470` (~7–20×) — the
   per-element `protect_slot`/`packed`/`scale`/`xmin` reads in the Phase F transform
   (`int4_packed_load_K_block`), confirming the Phase B audit's dependency-chain analysis.

## What this means for M1A (and the gate)

- Occupancy is **12 %**, set by the base kernel's 255 regs (stock bf16 is 255 too) — M1 **cannot**
  raise occupancy by trimming the transform (base-dominated). So the `≤128/≤160` register gate is
  **not achievable narrowly**, confirmed by measurement. **Latency is the gate.**
- The **int4-specific, M1-addressable** costs are the **spill (LDL/STL 223–1218)** and the
  **excess shared loads (LDS 2343–3538)**. M1A targets these; `inspect_k2_m1.sh` re-reads LDL/STL/LDS
  for the M1 symbol and the win is "spill/LDS down vs this baseline," then latency confirms it.
- **Pre-convert scale/xmin alone (M1A.1) is unlikely to clear ≥20 %** — it removes ~2 converts/elem
  (ALU), not the spill or the smem-load count. The measured spill says the effective lever is
  **reducing Phase F's simultaneously-live state** (bound the `#pragma unroll`) to cut LDL/STL, which
  is a **compile-time** change → it must be a separately-compiled M1 kernel (`Is_m1` template split),
  not a runtime branch (a runtime branch keeps *both* transforms live → would raise the spill, the
  opposite of the goal, and contaminate the register/spill measurement).

## Decision recorded

`KVPRO_K2_M1` is plumbed as a **template split** (`Is_int4kv_m1` → a separate compiled kernel that
calls an M1 loader), selected at the `flash_api.cpp` dispatch by `getenv("KVPRO_K2_M1")`, gated by
build macro `KVPRO_K2_M1_BUILD` (fail-loud `TORCH_CHECK` if requested-but-not-built). This keeps the
M1 kernel's regs/spill **clean and measurable** vs this baseline. Baseline for the gate:
**LDL 223–1218 / STL 118–427 / LDS 2343–3538 at REG 255 / 12 % occ.**
