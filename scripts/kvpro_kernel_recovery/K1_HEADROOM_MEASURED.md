# K1 / K2-gate — MEASURED gather-fusion headroom on the recovered kernel

> **Result (A100, recovered kernel, 2026-07-16): the in-kernel paged-gather fusion (K2/6F) is
> `GO` at B=1 — the removable pre-kernel overhead is 52–66% of the int4 read path — BUT this is
> the low-concurrency regime. The aggregate 0.22× loss is a SATURATION phenomenon, where the
> modeled headroom is ~25% → ~0.26–0.29× aggregate (net loss vs bf16). So 6F is a clear win for
> low-concurrency long-context LATENCY, and bounded for high-concurrency THROUGHPUT.** Ran on the
> K0-recovered `flash_attn_with_int4_kvcache`; `bench_decode_gather_fusion_headroom.py` (real CUDA
> events) + `estimate_phase6m_headroom.py` (Amdahl model). Batch-sweep pending to size saturation.

## Measured (B=1, Qwen2.5-7B, gen=64) — real CUDA-event GPU time, read path (`one.*`)

| ctx | GATHER (view_gather) | **FUSEABLE = gather+splice+bf16_backing+kernel_prep** | KERNEL (attention) | verdict |
|---:|--:|--:|--:|---|
| 8 000  | 23.7% | **65.8%** | 34.2% | GO |
| 16 000 | 26.0% | **58.8%** | 41.2% | GO |
| 32 000 | 32.1% | **51.7%** | 48.3% | GO |

FUSEABLE = the Python pre-kernel gather (`get_packed_view_batched`) + splice + bf16_backing +
kernel_prep — exactly what an in-kernel paged gather (consume `block_table` directly) would remove.
The DEQUANT is already in-kernel (confirmed); only the gather/orchestration remains. Verdict thresholds:
≥35% GO · 15–35% MAYBE · <15% NO-GO.

## Modeled (Amdahl, saturation defaults from 6M.4/6M.6)

`estimate_phase6m_headroom.py` (base 0.22× at saturation, gather-share 25.1%, attn-share 21.0%):

| scenario | removed | aggregate | slower/user |
|---|--:|--:|--:|
| gather fully fused | 25.1% | **0.294×** | 3.4× |
| gather 2/3 fused (realistic 6F) | 16.7% | **0.264×** | 3.8× |
| theoretical max (gather+attn) | 46.1% | 0.408× | 2.4× |

Plan ceiling 0.27–0.30× → CONSISTENT. int4 CANNOT reach bf16 parity (irreducible packed+scale+xmin+protect read per token).

## Reconciling the two (the load-bearing nuance)

The measured 52–66% (B=1) and the modeled ~25% (saturation) are **different regimes, not a contradiction**:
- **B=1:** the per-step Python gather/splice/prep is a large fixed cost with only one sequence's kernel
  work to hide it → FUSEABLE looks huge.
- **Saturation (high B):** the batched gather amortizes across B sequences and the attention kernel
  (∝ context × B) dominates → 6M.4 measured gather ~15% at high B.
- The measured trend confirms the direction: as ctx grows 8k→32k, KERNEL climbs 34%→48% and FUSEABLE
  falls 66%→52% (the kernel is taking over). Higher B pushes further that way.

**The 0.22× aggregate loss is a saturation phenomenon**, so the SATURATION headroom governs the
aggregate-throughput decision — not the B=1 number. Do NOT quote 52–66% as an aggregate-throughput
recovery.

## Decision implication (splits by deployment target)

| Target regime | Governing headroom | 6F/K2 verdict |
|---|---|---|
| Low-concurrency long-context (B≈1, latency) | 52–66% (MEASURED) | **clear win** — build it |
| High-concurrency throughput (saturation) | ~25% (MODELED) → 0.26–0.29× aggregate | **bounded, net loss vs bf16** — pivot question stands |

## Next (to make the K1→K2 call on measured, not modeled, saturation)

Sweep batch on the recovered kernel; if FUSEABLE stays >35% at B=32 the aggregate case is real, if it
collapses toward ~25% the model holds:
```bash
export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 PROTECT_MASK_PATH=/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt
for B in 8 32; do python CTM_plus/Bench/scripts/bench_decode_gather_fusion_headroom.py \
    --model Qwen/Qwen2.5-7B-Instruct --context-tokens 16000 --gen 64 --batch $B; done
```

## Status
- **Measured** (B=1): the three rows above — GPU-event timing on the K0-recovered kernel.
- **Modeled** (saturation): the Amdahl table — not a measured TPS.
- **Pending**: the B∈{8,32} saturation sweep (the aggregate-governing number).
- No kernel implemented. No modeled number quoted as measured TPS. Correctness gate
  (`verify_phase6e_byte_eq.sh --cuda`) not yet run this session.
