# KVPro vs CacheGen — Verdict (DIRECTIONAL, mechanism + codec-fidelity measured)

**Status: DIRECTIONAL VERDICT (2026-06-14), now refined by a MEASURED codec-fidelity test.** Grounded in
(a) CacheGen's *actual* mechanism (shipped config), (b) MEASURED KV-codec fidelity on real Qwen2.5-7B KV
(`scripts/compare_kvpro_vs_cachegen_fidelity.py`), (c) KVPro's MEASURED lossless warm-reuse + footprint,
and (d) three prior MEASURED head-to-heads. **Not yet an end-to-end needle run** (blocked on this pod —
env wall below; needs Option A). Companion: `docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md`.

## MEASURED codec fidelity (real Qwen2.5-7B KV, 28 layers, 2026-06-14)
| method | K bits/elem | K rel-err | **K rel-err@TOP** | V rel-err |
|---|---|---|---|---|
| CacheGen(bins=16) | 3.68 | 0.0557 | 0.0299 | 0.1020 |
| CacheGen(bins=32) | 4.72 | 0.0270 | **0.0145** | 0.0493 |
| naive_int4 | 4.00 | 0.0557 | 0.0299 | 0.1020 |
| **KVPro(int4+protect)** | 4.48 | 0.0521 | **0.0000** | 0.1020 |

**Refined read (this corrects the earlier "CacheGen will collapse like naive/SAW" framing — too strong):**
1. **KVPro uniquely delivers zero error on the high-attention K channels** (`@TOP = 0.0000`) at
   competitive bits (4.48). That is its protected-channel design, confirmed on real KV.
2. **But CacheGen@32 is MORE faithful on average** (K 0.027 vs KVPro 0.052; V 0.049 vs 0.102) — KVPro
   leaves its non-protected 96% at naive-int4 quality, while CacheGen spends bits more evenly.
3. **CacheGen is a stronger codec than naive/SAW:** its critical-channel error (0.0145 @bins32) is HALF
   of naive int4's (0.0299) — so it is NOT obviously in the hard-tail-collapse bucket the way naive int4
   and SAW were.
4. So the question narrows to: **does KVPro's zero-error-on-top-K beat CacheGen's lower-average-error-
   but-small-nonzero-on-top-K?** For retrieval (dominated by high-magnitude K channels) the mechanism
   favors KVPro — but the margin is far SOFTER than vs naive/SAW, and only the end-to-end needle run
   settles whether 0.0145 top-channel error is benign or breaks the tail.

## What CacheGen actually is (verified from lmcache 0.4.7 on the pod)
`lmcache/v1/storage_backend/naive_serde/cachegen_{encoder,decoder,basics}.py`. `CacheGenConfig` =
**per-layer-range quantization to `bins` levels** + **arithmetic coding**. The shipped 7B/8B presets:
- K: `bins=32` (layers 0–10), `bins=16` (10–32); V: `bins=32` (0–2), `bins=16` (2–32).
- `bins=16` ≈ 4 bits, `bins=32` ≈ 5 bits; arithmetic coding then compresses below nominal.
- **No channel protection** — uniform per-layer bins. **Lossy by construction.**

So CacheGen ≈ **dense, unprotected ~4–5-bit KV quant + entropy coding**, with coarse per-layer bin
tuning as its only sensitivity heuristic.

## Side-by-side
| axis | KVPro (int4_protected) | CacheGen |
|---|---|---|
| base | 4-bit + per-channel scales | ~4–5-bit (16–32 bins) + arithmetic coding |
| **high-magnitude K channels** | **protected at bf16 (4%)** | **none — uniform per-layer** |
| reuse fidelity | **lossless restore (MEASURED byte-exact, 8 prefixes, both protect formats)** | lossy (bins quant) |
| density | 1.8× vs bf16 (pays a sidecar tax) | **denser** (entropy-coded, no sidecars) |
| footprint (measured) | ~6 KB/token full-model snapshot (conservative, torch.save-bound) | not measured here |

## Verdict
CacheGen is **structurally the same class** as the three competitors already MEASURED to lose the hard
tail, for the same reason (dense + unprotected):
- **naive int4** — token-agreement vs bf16 collapsed to 0.533; K-bound hard-needle misses.
- **SAW-INT4 (BDR)** — **0% needle/hard-needle on Qwen2.5-7B-Instruct** (`SAW_INT4_QWEN_HEADTOHEAD_RESULTS.md`).
- **KVarN** — hard-needle **0.25 (8K) → 0.06 (32K)**, K-bound (VC brief Page 4).

All three were denser than int4_protected and dropped long-range / hard-tail retrieval exactly where
int4_protected's **protected channels** hold. CacheGen has **no channel-level protection** — the precise
moat — so it is expected to follow the same pattern. Its per-layer bin tuning is a *mild* mitigation,
not channel protection.

**Directional verdict (mechanism + 3 measured analogues + KVPro lossless reuse):**
- **CacheGen wins raw density** (entropy-coded, no sidecar tax).
- **KVPro wins the hard tail at iso-bytes** — its design target — and uniquely offers **lossless warm
  reuse** (proven byte-exact), so its reuse quality = its validated near-bf16 quality, *guaranteed*.
- Maps to the protocol's **QUALITY-EDGE** branch (KVPro holds the tail cheap unprotected quant misses),
  **pending end-to-end confirmation**.

## What is NOT yet measured (the confirming number)
- CacheGen's **measured bytes/token** on our prefixes, swept over `bins`.
- CacheGen's **hard-needle quality at the bins level whose bytes match KVPro** (the iso-bytes crossover).
- KVPro serving TTFT (needs the int4 decode FA fork).
Until these run, the verdict is directional, not a measured DOMINATED/QUALITY-EDGE stamp.

## Environment wall (why the end-to-end run is blocked here) + the A-path
- `pip install lmcache==0.4.7` pulls **vLLM 0.23.0**, whose torch is **2.11.0+cu130** (needs NVIDIA
  driver ≥13.0). This pod's driver is **12.8** → vLLM EngineCore fails at `torch._C._cuda_init()`. The
  CacheGen *server* cannot run here. (It also perturbed the base env — torchaudio cu124 vs torch cu121 —
  fixed by reinstalling `torchaudio==2.5.1+cu121`; **install lmcache only in an isolated venv**.)
- The standalone-serde path (encode/decode KV on CPU) is possible but needs constructing lmcache's
  internal `LMCacheEngineConfig` + `LMCacheMetadata` + `MemoryObj` in CacheGen's exact KV layout —
  deep, untestable internal-API work; **not recommended** as the next step.
- **Option A (recommended for the hard number):** a pod with driver ≥13.0 (or vLLM/torch matched to the
  driver). There the LMCache+CacheGen server + the arms in `ndol/experiments/cachegen_warmtier_eval.py`
  run directly — real bytes + hard-needle + TTFT, no internal-API guessing. Then map to the decision rule.

## Bottom line (refined by the fidelity measurement)
**KVPro has a real, unique, measured advantage: guaranteed zero error on the attention-critical K
channels at competitive bits.** CacheGen does not eliminate that error — but it is a capable codec
(better *average* fidelity, only ~0.0145 critical-channel error at bins=32), **not** the obvious-collapse
case naive int4 / SAW were. So:
- If hard-tail retrieval is dominated by exact preservation of the top-K channels (which the three prior
  collapses suggest), **KVPro is better for the tail** — its 0.0 vs CacheGen's 0.0145.
- But CacheGen's critical-channel error is small and its average fidelity is higher, so a **measured
  end-to-end win is NOT guaranteed** and would be by a smaller margin than vs SAW. It is genuinely open.
- KVPro also uniquely offers **lossless warm reuse** (proven) — orthogonal to raw fidelity, a real
  systems guarantee CacheGen's lossy codec cannot make.

**Honest one-liner:** KVPro concentrates fidelity exactly where attention is most sensitive (zero error
on top-K channels) and guarantees lossless reuse; CacheGen spends bits more evenly and is denser, with
small-but-nonzero error on those critical channels. Whether KVPro's concentration wins end-to-end is the
open question — settle it with the needle run on a newer-driver pod (Option A).
